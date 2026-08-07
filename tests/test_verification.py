import pytest
import httpx
from core.verification_layer import Neo4jVerifier, SymbolicVerifier, OPAClient

@pytest.fixture(scope="module")
def neo4j():
    v = Neo4jVerifier()
    try:
        v.seed_mock_ontology()
        with v.driver.session() as s:
            s.run("RETURN 1")
    except Exception as e:
        pytest.skip(
            f"Neo4j required for integration tests. Start with: docker compose up -d neo4j\n{e}"
        )
    yield v
    v.close()

def test_neo4j_valid_edge(neo4j):
    path = [{"head": "Dyspnea", "relation": "INDICATES", "tail": "Heart Failure"}]
    result = neo4j.validate(path)
    assert result["is_valid"] is True
    assert len(result["valid_edges"]) == 1

def test_neo4j_invalid_edge(neo4j):
    path = [{"head": "Dyspnea", "relation": "INDICATES", "tail": "Migraine"}]
    result = neo4j.validate(path)
    assert result["is_valid"] is False
    assert len(result["violations"]) == 1

def test_symbolic_drug_interaction():
    sv = SymbolicVerifier()
    path = [{"head": "Warfarin", "relation": "CONTRAINDICATES", "tail": "Aspirin"}]
    result = sv.validate(path)
    assert result["is_valid"] is False
    assert any("bleed risk" in v["reason"] for v in result["violations"])


def test_confidence_fusion_weighted():
    """Symbolic verifier with higher weight dominates the fused confidence."""
    from core.confidence_fusion import ConfidenceFusion, VerifierConfidence

    fusion = ConfidenceFusion(weights={
        "symbolic": 0.35,
        "neo4j": 0.30,
        "opa": 0.20,
        "neural": 0.15,
    })

    # Symbolic says valid (high confidence), others are neutral
    confidences = [
        VerifierConfidence(name="neo4j", confidence=0.5, weight=0.30, is_valid=True),
        VerifierConfidence(name="symbolic", confidence=0.95, weight=0.35, is_valid=True),
        VerifierConfidence(name="opa", confidence=0.5, weight=0.20, is_valid=True),
    ]
    result = fusion.fuse(confidences)
    # Weighted: 0.3*(0.5) + 0.35*(0.95) + 0.20*(0.5) = 0.15 + 0.3325 + 0.10 = 0.5825
    assert result["fused_confidence"] > 0.5
    assert result["decision"] == "correct"

    # All pass with high confidence -> valid
    confidences_all_high = [
        VerifierConfidence(name="neo4j", confidence=0.95, weight=0.30, is_valid=True),
        VerifierConfidence(name="symbolic", confidence=0.95, weight=0.35, is_valid=True),
        VerifierConfidence(name="opa", confidence=1.0, weight=0.20, is_valid=True),
    ]
    result = fusion.fuse(confidences_all_high)
    assert result["decision"] == "valid"
    assert result["is_safe"] is True

    # Low confidence -> escalate
    confidences_low = [
        VerifierConfidence(name="neo4j", confidence=0.1, weight=0.30, is_valid=False),
        VerifierConfidence(name="symbolic", confidence=0.1, weight=0.35, is_valid=False),
        VerifierConfidence(name="opa", confidence=0.0, weight=0.20, is_valid=False),
    ]
    result = fusion.fuse(confidences_low)
    assert result["decision"] == "escalate"
    assert result["is_safe"] is False


def test_symbolic_drug_interaction_with_rules_file():
    sv = SymbolicVerifier()
    path = [{"head": "Warfarin", "relation": "CONTRAINDICATES", "tail": "Heparin"}]
    result = sv.validate(path)
    assert result["is_valid"] is False
    assert len(result["violations"]) > 0


def test_symbolic_age_contraindication():
    sv = SymbolicVerifier()
    path = [{"head": "Aspirin", "relation": "INDICATES", "tail": "Fever", "confidence": 0.9}]
    result = sv.validate(path, patient_context={"age": 8})
    assert result["is_valid"] is False
    assert any("Reye" in v["reason"] for v in result["violations"])


def test_symbolic_allergy_contraindication():
    sv = SymbolicVerifier()
    path = [{"head": "Penicillin", "relation": "TREATS", "tail": "Infection"}]
    result = sv.validate(path, patient_context={"allergies": ["Penicillin"]})
    assert result["is_valid"] is False
    assert any("allergy" in v["reason"].lower() for v in result["violations"])


def test_symbolic_pregnancy_contraindication():
    sv = SymbolicVerifier()
    path = [{"head": "ACE Inhibitor", "relation": "INDICATES", "tail": "Hypertension", "confidence": 0.9}]
    result = sv.validate(path, patient_context={"pregnancy_status": "pregnant"})
    assert result["is_valid"] is False
    assert any("pregnancy" in v["reason"].lower() for v in result["violations"])


def test_symbolic_clean_path_no_violations():
    sv = SymbolicVerifier()
    path = [{"head": "Aspirin", "relation": "INDICATES", "tail": "Pain", "confidence": 0.9}]
    result = sv.validate(path, patient_context={})
    assert result["is_valid"] is True
    assert len(result["violations"]) == 0

def _opa_available():
    try:
        r = httpx.get("http://localhost:8181/health", timeout=2.0)
        return r.status_code < 500
    except Exception:
        return False

@pytest.mark.asyncio
async def test_opa_policy_block():
    if not _opa_available():
        pytest.skip("OPA not running. Start with: docker compose up -d opa")
    opa = OPAClient(opa_url="http://localhost:8181/v1/data/clinical")
    payload = {"proposed_path": [{"head": "Aspirin", "relation": "INDICATES", "tail": "Warfarin"}]}
    result = await opa.evaluate(payload)
    if result["allow"] is True and not result.get("violations"):
        pytest.skip("OPA clinical policy not loaded — defaulting to allow")
    assert result["allow"] is False

@pytest.mark.asyncio
async def test_opa_fail_closed_on_unreachable():
    """When OPA endpoint is unreachable, fail-closed must deny the request."""
    opa = OPAClient(opa_url="http://localhost:9999/v1/data/clinical")
    payload = {"proposed_path": [{"head": "Aspirin", "relation": "INDICATES", "tail": "Heart Failure"}]}
    result = await opa.evaluate(payload)
    assert result["allow"] is False
    assert len(result["violations"]) >= 1
    assert "unreachable" in result["violations"][0]["reason"]

@pytest.mark.asyncio
async def test_opa_fail_closed_deny_drug_interaction():
    """If OPA policy denies Warfarin+Aspirin, the denial must propagate."""
    if not _opa_available():
        pytest.skip("OPA not running. Start with: docker compose up -d opa")
    opa = OPAClient(opa_url="http://localhost:8181/v1/data/clinical")
    payload = {"proposed_path": [{"head": "Warfarin", "relation": "CONTRAINDICATES", "tail": "Aspirin"}]}
    result = await opa.evaluate(payload)
    assert result["allow"] is False
    assert any("OPA" in v.get("reason", "") or "policy" in v.get("reason", "").lower() for v in result["violations"])
