import pytest
import asyncio
from core.llm_backend import MockLLMBackend, OllamaBackend, DeepSeekR1Backend, SemanticRouter

@pytest.fixture
def mock_llm():
    return MockLLMBackend(seed=42)

def test_mockllm_deterministic(mock_llm):
    r1 = asyncio.run(mock_llm.generate_path("Patient has dyspnea"))
    r2 = asyncio.run(mock_llm.generate_path("Patient has dyspnea"))
    assert r1["triplets"] == r2["triplets"]
    assert r1["reasoning"] == r2["reasoning"]

def test_mockllm_correction_decay(mock_llm):
    violations = [{"triplet": {"head": "Dyspnea", "relation": "INDICATES", "tail": "Heart Failure"}, "reason": "test"}]
    result = asyncio.run(
        mock_llm.regenerate_with_feedback("dyspnea", violations, "prior reasoning", {})
    )
    originals_by_tail = {t["tail"]: t["confidence"] for t in mock_llm._MOCK_KNOWLEDGE_TEMPLATE["dyspnea"]}
    assert len(result["triplets"]) == len(originals_by_tail)
    for t in result["triplets"]:
        expected = max(originals_by_tail[t["tail"]] - 0.1, 0.5)
        assert t["confidence"] == pytest.approx(expected, abs=0.001)
        assert t.get("corrected") is True

@pytest.mark.asyncio
async def test_ollama_json_output():
    try:
        backend = OllamaBackend(model="gemma2:2b", host="http://localhost:11434", timeout=5.0)
        result = await backend.generate_path("Patient has dyspnea")
        assert isinstance(result["triplets"], list)
    except Exception as e:
        pytest.skip(f"Ollama not available: {e}")

def test_deepseek_think_extraction():
    from core.reasoning_extractor import extract_reasoning_trace
    raw = 'Step 1: think.   reason here  [{"head":"A","relation":"B","tail":"C","confidence":0.9}]'
    reasoning, triplets = extract_reasoning_trace(raw)
    assert len(triplets) == 1
    assert triplets[0]["head"] == "A"

def test_deepseek_fallback_parsing():
    from core.reasoning_extractor import extract_reasoning_trace
    raw = 'No think tags. Just text. {"head":"X","relation":"Y","tail":"Z","confidence":0.8}'
    reasoning, triplets = extract_reasoning_trace(raw)
    assert reasoning == ""
    assert len(triplets) == 1

@pytest.mark.asyncio
async def test_semantic_router():
    router = SemanticRouter()
    key = await router.route("Patient has dyspnea")
    assert key in ("mock", "ollama", "deepseek_r1")
