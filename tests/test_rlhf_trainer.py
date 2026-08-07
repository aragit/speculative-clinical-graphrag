import json
import os
import pytest
import tempfile
import shutil
from unittest.mock import MagicMock
from core.rlhf_trainer import RLHFTrainer, TrainingExample
from core.neural_policy import NeuralPolicyNetwork


@pytest.fixture
def policy():
    return NeuralPolicyNetwork(enable_learning=True)


@pytest.fixture
def trainer(policy):
    tmpdir = tempfile.mkdtemp(prefix="rlhf_models_")
    return RLHFTrainer(policy, model_dir=tmpdir), tmpdir


def _seed_history(policy, count=3):
    for i in range(count):
        policy.history.append({
            "features": {
                "symptom_count": 3,
                "path_length": 2,
                "violation_count": 0,
                "iteration_count": 1,
                "max_iterations": 3,
                "is_safe": True,
                "symbolic_safe": True,
                "age": 45,
                "med_count": 1,
                "condition_count": 0,
                "has_allergies": False,
                "ontology_coverage": 0.8,
            },
            "predicted": "synthesize",
            "actual": "escalate",
            "reward": -0.5,
            "timestamp": 1000 + i,
        })


@pytest.mark.asyncio
async def test_rlhf_trainer_export(trainer, policy):
    tr, tmpdir = trainer
    _seed_history(policy, 3)

    filepath = os.path.join(tmpdir, "test_export.jsonl")
    count = tr.export_dataset(filepath)

    assert count == 3
    assert os.path.exists(filepath)

    with open(filepath) as f:
        lines = f.readlines()
    assert len(lines) == 3

    for line in lines:
        example = json.loads(line)
        assert "features" in example
        assert "predicted_action" in example
        assert "actual_outcome" in example
        assert "reward" in example


def test_rlhf_trainer_load_dataset(trainer, policy):
    tr, tmpdir = trainer
    _seed_history(policy, 5)

    filepath = os.path.join(tmpdir, "test_dataset.jsonl")
    tr.export_dataset(filepath)

    loaded = tr.load_dataset(filepath)
    assert len(loaded) == 5
    assert all(isinstance(ex, TrainingExample) for ex in loaded)


@pytest.mark.asyncio
async def test_rlhf_training_improves_accuracy(trainer, policy):
    """Create synthetic dataset where static routing is wrong, assert trained model beats static."""
    tr, tmpdir = trainer

    # Static routing predicts "escalate" for these cases (is_safe=False, iteration=1, max=3)
    # But actual outcome is always "correct_differential" — static is wrong
    for i in range(20):
        policy.history.append({
            "features": {
                "symptom_count": 1 + (i % 3),
                "path_length": 1,
                "violation_count": i % 2,
                "iteration_count": 1,
                "max_iterations": 3,
                "is_safe": False,  # Static will try correct_differential
                "symbolic_safe": True,
                "age": 30 + (i % 20),
                "med_count": 0,
                "condition_count": 0,
                "has_allergies": False,
                "ontology_coverage": 0.9,
            },
            "predicted": "correct_differential",
            "actual": "synthesize",  # Override wants synthesize, not correct
            "reward": 0.5,
            "timestamp": 1000 + i,
        })

    result = tr.train(epochs=50)
    assert result["status"] == "trained"
    assert os.path.exists(os.path.join(tmpdir, "policy_weights.json"))

    # Evaluate
    test_cases = [{"features": r["features"], "expected_action": r["actual"]} for r in policy.history]
    eval_result = tr.evaluate_vs_static(test_cases)

    assert eval_result["total_cases"] == 20
    assert eval_result["neural_accuracy"] > eval_result["static_accuracy"]


def test_neural_policy_load_trained_weights(policy, trainer):
    tr, tmpdir = trainer
    _seed_history(policy, 5)
    tr.train(epochs=10)
    tr.load_model()

    policy.load_trained_weights(tr.weights, tr.bias)
    assert policy._trained_weights is not None
    assert policy._trained_bias is not None


def test_rlhf_trainer_no_data(policy, trainer):
    tr, tmpdir = trainer
    result = tr.train()
    assert result["status"] == "no_data"
