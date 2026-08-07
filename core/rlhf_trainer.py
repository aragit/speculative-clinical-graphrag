import json
import logging
import math
import os
from typing import Dict, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TrainingExample(BaseModel):
    features: Dict[str, float]
    predicted_action: str
    actual_outcome: str
    reward: float
    timestamp: float


class RLHFTrainer:
    """
    Trains the neural policy from recorded outcomes.
    Uses interpretable logistic regression (not deep learning) for clinical safety.
    """

    def __init__(self, policy_network, model_dir: str = "models/policy"):
        self.policy = policy_network
        self.model_dir = model_dir
        os.makedirs(model_dir, exist_ok=True)
        self.weights: Dict[str, Dict[str, float]] = {}
        self.bias: Dict[str, float] = {}
        self.learning_rate = 0.01
        self.regularization = 0.001

    def export_dataset(self, filepath: str = "data/policy_training.jsonl") -> int:
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        count = 0
        with open(filepath, "w") as f:
            for record in self.policy.history:
                example = TrainingExample(
                    features=record["features"],
                    predicted_action=record["predicted"],
                    actual_outcome=record["actual"],
                    reward=record["reward"],
                    timestamp=record["timestamp"],
                )
                f.write(json.dumps(example.model_dump()) + "\n")
                count += 1
        logger.info(f"Exported {count} training examples to {filepath}")
        return count

    def load_dataset(self, filepath: str = "data/policy_training.jsonl") -> List[TrainingExample]:
        examples = []
        if not os.path.exists(filepath):
            return examples
        with open(filepath) as f:
            for line in f:
                try:
                    examples.append(TrainingExample(**json.loads(line)))
                except Exception:
                    continue
        return examples

    def train(self, epochs: int = 100) -> Dict:
        if not self.policy.history:
            return {"status": "no_data", "message": "No recorded outcomes to train on"}

        actions = {"synthesize", "correct_differential", "escalate"}
        feature_keys = set()
        for record in self.policy.history:
            feature_keys.update(record["features"].keys())

        for action in actions:
            if action not in self.weights:
                self.weights[action] = {k: 0.0 for k in feature_keys}
                self.bias[action] = 0.0

        accuracy = 0.0
        for epoch in range(epochs):
            total_loss = 0.0
            correct = 0

            for record in self.policy.history:
                features = record["features"]
                actual = record["actual"]
                reward = record["reward"]

                scores = {}
                for action in actions:
                    score = self.bias[action]
                    for k, v in features.items():
                        score += self.weights[action].get(k, 0.0) * v
                    scores[action] = score

                max_score = max(scores.values())
                exp_scores = {a: math.exp(s - max_score) for a, s in scores.items()}
                sum_exp = sum(exp_scores.values())
                probs = {a: exp_scores[a] / sum_exp for a in actions}

                loss = -math.log(max(probs[actual], 1e-10))
                for action in actions:
                    for k in feature_keys:
                        w = self.weights[action].get(k, 0.0)
                        loss += self.regularization * (w ** 2)
                total_loss += loss

                if probs[actual] == max(probs.values()):
                    correct += 1

                for action in actions:
                    target = 1.0 if action == actual else 0.0
                    error = probs[action] - target
                    scale = error * self.learning_rate * (1.0 if reward > 0 else 0.5)

                    for k, v in features.items():
                        self.weights[action][k] -= scale * v + self.regularization * self.weights[action].get(k, 0.0)
                    self.bias[action] -= scale

            accuracy = correct / len(self.policy.history)
            if epoch % 20 == 0:
                logger.info(f"Epoch {epoch}: loss={total_loss:.4f}, accuracy={accuracy:.3f}")

        self._save_model()

        return {
            "status": "trained",
            "epochs": epochs,
            "final_accuracy": accuracy,
            "dataset_size": len(self.policy.history),
            "weights_file": os.path.join(self.model_dir, "policy_weights.json"),
        }

    def _save_model(self):
        model = {
            "weights": self.weights,
            "bias": self.bias,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "version": "0.6.0",
        }
        filepath = os.path.join(self.model_dir, "policy_weights.json")
        with open(filepath, "w") as f:
            json.dump(model, f, indent=2)
        logger.info(f"Policy model saved to {filepath}")

    def load_model(self) -> bool:
        filepath = os.path.join(self.model_dir, "policy_weights.json")
        if not os.path.exists(filepath):
            return False
        with open(filepath) as f:
            model = json.load(f)
        self.weights = model.get("weights", {})
        self.bias = model.get("bias", {})
        logger.info(f"Policy model loaded from {filepath}")
        return True

    def evaluate_vs_static(self, test_cases: List[Dict]) -> Dict:
        neural_correct = 0
        static_correct = 0

        for case in test_cases:
            features = case["features"]
            expected = case["expected_action"]

            if self.weights:
                scores = {}
                for action, weights in self.weights.items():
                    score = self.bias.get(action, 0.0)
                    for k, v in features.items():
                        score += weights.get(k, 0.0) * v
                    scores[action] = score

                if scores:
                    neural_pred = max(scores, key=scores.get)
                else:
                    neural_pred = "escalate"
            else:
                neural_pred = "escalate"

            static_pred = self._static_predict(features)

            if neural_pred == expected:
                neural_correct += 1
            if static_pred == expected:
                static_correct += 1

        total = len(test_cases)
        return {
            "neural_accuracy": neural_correct / total if total > 0 else 0.0,
            "static_accuracy": static_correct / total if total > 0 else 0.0,
            "improvement": (neural_correct - static_correct) / total if total > 0 else 0.0,
            "total_cases": total,
        }

    def _static_predict(self, features: Dict) -> str:
        is_safe = features.get("is_safe", False)
        iteration = features.get("iteration_count", 1)
        max_iter = features.get("max_iterations", 3)

        if is_safe:
            return "synthesize"
        if iteration < max_iter:
            return "correct_differential"
        return "escalate"
