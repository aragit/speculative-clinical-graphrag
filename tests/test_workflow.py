import pytest
from core.llm_backend import MockLLMBackend
from core.verification_layer import Neo4jVerifier
from core.workflow import SpeculativeGraphRAG


@pytest.fixture
def rag():
    llm = MockLLMBackend()
    verifier = Neo4jVerifier()
    verifier.seed_mock_taxonomy()
    yield SpeculativeGraphRAG(llm=llm, verifier=verifier, max_iterations=3)
    verifier.close()


def test_valid_path(rag):
    result = rag.run("Patient has dyspnea and orthopnea")
    assert result["status"] == "valid"
    assert result["iteration_count"] == 1
    assert len(result["validation_result"]["valid_edges"]) > 0


def test_invalid_then_corrected(rag):
    result = rag.run("Patient has unknown rare symptom XYZ123")
    assert result["status"] in ["valid", "escalated"]
    assert result["iteration_count"] <= 3


def test_escalation_after_max_iterations(rag):
    result = rag.run("Completely nonsensical medical text")
    assert result["status"] == "escalated"
    assert "human review" in result["final_output"].lower()
