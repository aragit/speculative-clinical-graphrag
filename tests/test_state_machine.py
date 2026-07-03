import pytest
from core.state_machine import CQRSStateManager


@pytest.mark.asyncio
async def test_commit_and_get_state_fallback():
    mgr = CQRSStateManager(redis_url="redis://nonexistent:6379")
    await mgr.commit_event("test-trace", {"node": "extract", "type": "step"})
    state = await mgr.get_state("test-trace")
    assert state["trace_id"] == "test-trace"
    assert "events" in state


@pytest.mark.asyncio
async def test_get_state_empty():
    mgr = CQRSStateManager(redis_url="redis://nonexistent:6379")
    state = await mgr.get_state("nonexistent-trace")
    assert state["trace_id"] == "nonexistent-trace"
    assert state["events"] == []
