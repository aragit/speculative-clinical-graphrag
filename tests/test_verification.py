import pytest
from core.verification_layer import Neo4jVerifier, SymbolicVerifier, OPAClient

@pytest.fixture(scope="module")
def neo4j():
    v = Neo4jVerifier()
    try:
        v.seed_mock_ontology()
        with v.driver.session() as s:
            s.run("RETURN 1")
    except Exception as e:
        pytest.fail(
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

@pytest.mark.asyncio
async def test_opa_policy_block():
    opa = OPAClient(opa_url="http://localhost:8181/v1/data/clinical")
    payload = {"proposed_path": [{"head": "Aspirin", "relation": "INDICATES", "tail": "Warfarin"}]}
    result = await opa.evaluate(payload)
    assert result["allow"] is False, "OPA must be running to enforce policies. Start with: docker compose up -d opa"
