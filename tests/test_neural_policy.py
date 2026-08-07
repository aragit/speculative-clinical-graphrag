import pytest
from core.neural_policy import NeuralPolicyNetwork, RoutingDecision


@pytest.fixture
def policy():
    return NeuralPolicyNetwork(enable_learning=False)


def _make_state(**overrides) -> dict:
    return {
        "extracted_symptoms": [{"term": "fever", "confidence": 0.9}],
        "proposed_path": [{"head": "Fever", "relation": "INDICATES", "tail": "Infection", "confidence": 0.8}],
        "patient_context": {"age": 45, "medications": [], "conditions": [], "allergies": []},
        "violations": [],
        "safety_result": {"is_safe": True, "symbolic_valid": True},
        "iteration_count": 1,
        "max_iterations": 3,
        "ontology_mappings": {"fever": [{"head": "Fever", "tail": "Infection"}]},
        **overrides,
    }


def test_neural_policy_simple_case_synthesizes(policy):
    state = _make_state()
    decision = policy.predict(state)
    assert decision.action == "synthesize"


def test_neural_policy_complex_case_corrects(policy):
    state = _make_state(
        extracted_symptoms=[{"term": s} for s in ["fever", "cough", "dyspnea", "fatigue", "chest pain"]],
        proposed_path=[],
        patient_context={"age": 50, "medications": ["warfarin", "aspirin", "metformin", "insulin"], "conditions": ["DM", "HTN"], "allergies": ["penicillin"]},
        safety_result={"is_safe": True, "symbolic_valid": True},
        ontology_mappings={},
    )
    decision = policy.predict(state)
    assert decision.action == "correct_differential"


def test_neural_policy_max_iterations_escalate(policy):
    state = _make_state(iteration_count=3, max_iterations=3)
    decision = policy.predict(state)
    assert decision.action == "escalate"
    assert "max iterations" in decision.reason


def test_neural_policy_invariant_escalates():
    policy = NeuralPolicyNetwork(enable_learning=False)
    state = _make_state(
        safety_result={"is_safe": False, "symbolic_valid": False},
        patient_context={"age": 80, "medications": ["warfarin"], "conditions": [], "allergies": []},
        violations=[{"type": "drug_interaction", "triplet": {"head": "Warfarin", "tail": "Aspirin"}}],
    )
    decision = policy.predict(state)
    assert decision.action == "escalate"
    assert "Type 2 invariant" in decision.reason


def test_neural_policy_invariant_overrides_neural_heuristic():
    """Even if neural heuristic says synthesize, Type 2 invariant forces escalate."""
    policy = NeuralPolicyNetwork(enable_learning=False)
    state = _make_state(
        safety_result={"is_safe": True, "symbolic_valid": False},
        patient_context={"age": 80, "medications": [], "conditions": [], "allergies": []},
    )
    decision = policy.predict(state)
    assert decision.action == "escalate"


def test_neural_policy_record_outcome():
    policy = NeuralPolicyNetwork(enable_learning=True)
    features = {"symptom_count": 3, "risk_score": 0.5}
    policy.record_outcome(features, "synthesize", "escalate", -0.5)
    assert len(policy.history) == 1
    assert policy.history[0]["reward"] == -0.5
    assert policy.get_accuracy() == 0.0


def test_neural_policy_record_outcome_disabled():
    policy = NeuralPolicyNetwork(enable_learning=False)
    policy.record_outcome({}, "synthesize", "escalate", 1.0)
    assert len(policy.history) == 0
    assert policy.get_accuracy() == 0.0


def test_neural_policy_routing_high_risk_age():
    policy = NeuralPolicyNetwork(enable_learning=False)
    state = _make_state(
        patient_context={"age": 85, "medications": [], "conditions": [], "allergies": []},
        safety_result={"is_safe": True, "symbolic_valid": True},
    )
    decision = policy.predict(state)
    # High age risk + not perfectly safe scenario -> may escalate or correct depending on scores
    assert decision.action in ("escalate", "correct_differential")
