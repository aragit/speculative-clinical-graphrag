import math
import time
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class RoutingDecision(BaseModel):
    action: Literal["correct_differential", "synthesize", "escalate"]
    confidence: float
    reason: str


class NeuralPolicyNetwork:
    """
    Neural routing policy for workflow decisions.
    Currently heuristic-based; will be replaced with trained model in R4.
    """

    def __init__(self, enable_learning: bool = True):
        self.enable_learning = enable_learning
        self.history: List[Dict] = []
        self._trained_weights: Optional[Dict] = None
        self._trained_bias: Optional[Dict] = None

    def predict(self, state: Dict) -> RoutingDecision:
        features = self._extract_features(state)

        # Type 2 safety invariant: symbolic unsafe + high risk → escalate
        if not features.get("symbolic_safe", True) and self._risk_score(features) > 0.6:
            return RoutingDecision(
                action="escalate",
                confidence=0.9,
                reason="Type 2 invariant: symbolic verifier failed + high risk profile",
            )

        # Type 2 safety invariant: max iterations → escalate
        if features.get("iteration_count", 1) >= features.get("max_iterations", 3):
            return RoutingDecision(
                action="escalate",
                confidence=1.0,
                reason="Type 2 invariant: max iterations reached",
            )

        # Use trained weights if available
        if self._trained_weights and self._trained_bias:
            actions = {"synthesize", "correct_differential", "escalate"}
            scores = {}
            for action in actions:
                if action not in self._trained_weights:
                    continue
                score = self._trained_bias.get(action, 0.0)
                for k, v in features.items():
                    score += self._trained_weights[action].get(k, 0.0) * v
                scores[action] = score

            if scores:
                max_score = max(scores.values())
                exp_scores = {a: math.exp(s - max_score) for a, s in scores.items()}
                sum_exp = sum(exp_scores.values())
                best_action = max(scores, key=scores.get)
                confidence = exp_scores[best_action] / sum_exp

                return RoutingDecision(
                    action=best_action,
                    confidence=confidence,
                    reason=f"Trained model prediction (score: {scores[best_action]:.3f})",
                )

        # Fallback: heuristic routing
        complexity_score = self._complexity_score(features)
        risk_score = self._risk_score(features)
        uncertainty_score = self._uncertainty_score(features)

        if complexity_score < 0.3 and risk_score < 0.3 and features.get("is_safe", False):
            return RoutingDecision(
                action="synthesize",
                confidence=0.8 - uncertainty_score,
                reason="Low complexity, low risk, safe path",
            )

        if uncertainty_score > 0.5 and features.get("iteration_count", 1) < features.get("max_iterations", 3):
            return RoutingDecision(
                action="correct_differential",
                confidence=0.7,
                reason="High uncertainty, attempt correction",
            )

        return RoutingDecision(
            action="escalate",
            confidence=0.6,
            reason="Ambiguous case: complexity/risk/uncertainty in middle zone",
        )

    def load_trained_weights(self, weights: Dict, bias: Dict):
        """Load weights from RLHFTrainer. Updates heuristic scoring."""
        self._trained_weights = weights
        self._trained_bias = bias
        logger.info("Loaded trained weights into neural policy")

    def _extract_features(self, state: Dict) -> Dict:
        symptoms = state.get("extracted_symptoms", [])
        path = state.get("proposed_path", [])
        ctx = state.get("patient_context", {})
        violations = state.get("violations", [])
        safety = state.get("safety_result", {})

        return {
            "symptom_count": len(symptoms),
            "path_length": len(path),
            "violation_count": len(violations),
            "iteration_count": state.get("iteration_count", 1),
            "max_iterations": state.get("max_iterations", 3),
            "is_safe": safety.get("is_safe", False),
            "symbolic_safe": safety.get("symbolic_valid", True),
            "age": ctx.get("age", 50),
            "med_count": len(ctx.get("medications", [])),
            "condition_count": len(ctx.get("conditions", [])),
            "has_allergies": len(ctx.get("allergies", [])) > 0,
            "ontology_coverage": len(state.get("ontology_mappings", {})) / max(len(symptoms), 1),
        }

    def _complexity_score(self, features: Dict) -> float:
        score = 0.0
        score += min(features["symptom_count"] / 5.0, 0.3)
        score += min(features["med_count"] / 4.0, 0.2)
        score += min(features["condition_count"] / 3.0, 0.2)
        score += 0.3 if features["has_allergies"] else 0.0
        return min(score, 1.0)

    def _risk_score(self, features: Dict) -> float:
        score = 0.0
        if features["age"] > 75:
            score += 0.3
        elif features["age"] < 12:
            score += 0.4
        score += min(features["violation_count"] / 2.0, 0.4)
        score += 0.3 if not features["symbolic_safe"] else 0.0
        return min(score, 1.0)

    def _uncertainty_score(self, features: Dict) -> float:
        if features["path_length"] == 0:
            return 1.0
        return 1.0 - features["ontology_coverage"]

    def record_outcome(self, state_features: Dict, predicted: str, actual: str, reward: float):
        if not self.enable_learning:
            return
        self.history.append({
            "features": state_features,
            "predicted": predicted,
            "actual": actual,
            "reward": reward,
            "timestamp": time.time(),
        })
        logger.info(f"Policy outcome recorded: predicted={predicted}, actual={actual}, reward={reward}")

    def get_accuracy(self) -> float:
        if not self.history:
            return 0.0
        correct = sum(1 for h in self.history if h["predicted"] == h["actual"])
        return correct / len(self.history)
