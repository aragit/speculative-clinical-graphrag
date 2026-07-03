import pytest
from core.telemetry import TelemetryManager


def test_get_tracer_returns_fallback():
    mgr = TelemetryManager(jaeger_host="nonexistent:6831")
    tracer = mgr.get_tracer("test")
    assert tracer is not None


@pytest.mark.asyncio
async def test_llm_as_judge_stub_without_backend():
    mgr = TelemetryManager()
    result = await mgr.llm_as_judge({"final_output": "test"}, llm_backend=None)
    assert result["status"] == "stub"
    assert "factual_accuracy" in result
    assert "tone" in result
    assert "logic" in result
