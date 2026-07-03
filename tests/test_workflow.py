import pytest
from core.llm_backend import MockLLMBackend
from core.verification_layer import Neo4jVerifier, SymbolicVerifier
from core.workflow import SpeculativeGraphRAG

@pytest.fixture
def rag():
    llm = MockLLMBackend()
    verifier = Neo4jVerifier()
    symbolic = SymbolicVerifier()
    try:
        verifier.seed_mock_ontology()
        with verifier.driver.session() as s:
            s.run("RETURN 1")
    except Exception:
        pass
    yield SpeculativeGraphRAG(llm=llm, verifier=verifier, symbolic_verifier=symbolic, max_iterations=3)
    try:
        verifier.close()
    except Exception:
        pass


@pytest.mark.asyncio
async def test_valid_path_1_iteration(rag):
    result = await rag.run("Patient has dyspnea and orthopnea")
    assert result["status"] == "valid"
    assert result["iteration_count"] == 1
    assert len(result["validation_result"]["valid_edges"]) > 0
    assert any(e["node"] == "ingest" for e in result["audit_log"])
    assert len(result.get("extracted_symptoms", [])) == 2
    assert any("dyspnea" in str(k).lower() for k in result.get("ontology_mappings", {}))


@pytest.mark.asyncio
async def test_invalid_path_escalation(rag):
    result = await rag.run("Patient has unknown rare symptom XYZ123")
    assert result["status"] == "escalated"
    assert result["iteration_count"] == 3


@pytest.mark.asyncio
async def test_escalate_on_nonsensical_input(rag):
    result = await rag.run("Completely nonsensical medical text")
    assert result["status"] == "escalated"
    assert "human review" in result["final_output"].lower()


@pytest.mark.asyncio
async def test_reasoning_trace_in_response(rag):
    result = await rag.run("Patient has chest pain")
    assert "reasoning_trace" in result
    assert result.get("reasoning_trace") != ""
