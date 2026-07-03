import pytest
from core.idempotency import IdempotencyManager


def test_generate_key_is_deterministic():
    mgr = IdempotencyManager()
    key1 = mgr.generate_key("trace-1", "tool-a", {"x": 1, "y": 2})
    key2 = mgr.generate_key("trace-1", "tool-a", {"y": 2, "x": 1})
    assert isinstance(key1, str)
    assert key1 == key2


def test_generate_key_changes_with_payload():
    mgr = IdempotencyManager()
    key1 = mgr.generate_key("trace-1", "tool-a", {"x": 1})
    key2 = mgr.generate_key("trace-1", "tool-a", {"x": 2})
    assert key1 != key2


@pytest.mark.asyncio
async def test_check_and_store_returns_true_without_redis():
    mgr = IdempotencyManager(redis_url="redis://nonexistent:6379")
    result = await mgr.check_and_store("test-key-123")
    assert result is True
