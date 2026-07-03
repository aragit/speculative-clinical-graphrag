import pytest
from core.supervisor import SupervisorAgent
from core.llm_backend import MockLLMBackend
from core.verification_layer import SymbolicVerifier


@pytest.mark.asyncio
async def test_delegate_returns_structure():
    llm = MockLLMBackend()
    symbolic = SymbolicVerifier()
    supervisor = SupervisorAgent(llm_backend=llm, symbolic_verifier=symbolic)
    result = await supervisor.delegate("extract_symptoms", {"patient_note": "Patient has dyspnea"})
    assert "task" in result
    assert "worker" in result
    assert "worker_results" in result
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_delegate_unknown_task_uses_default_worker():
    llm = MockLLMBackend()
    supervisor = SupervisorAgent(llm_backend=llm)
    result = await supervisor.delegate("unknown_task_xyz", {"patient_note": "test"})
    assert result["status"] in ("completed", "no_worker_found")


@pytest.mark.asyncio
async def test_delegate_verify_safety_with_symbolic():
    llm = MockLLMBackend()
    symbolic = SymbolicVerifier()
    supervisor = SupervisorAgent(llm_backend=llm, symbolic_verifier=symbolic)
    context = {
        "proposed_path": [{"head": "Warfarin", "relation": "CONTRAINDICATES", "tail": "Aspirin"}],
        "patient_context": {},
    }
    result = await supervisor.delegate("verify_safety", context)
    assert result["status"] == "completed"
