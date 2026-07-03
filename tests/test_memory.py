import pytest
from core.memory import MultiTieredMemory


@pytest.mark.asyncio
async def test_working_get_returns_none_without_redis():
    mem = MultiTieredMemory()
    val = await mem.working_get("session-1", "key-1")
    assert val is None


@pytest.mark.asyncio
async def test_working_set_no_error_without_redis():
    mem = MultiTieredMemory()
    await mem.working_set("session-1", "key-1", {"data": "test"})
    assert True


@pytest.mark.asyncio
async def test_episodic_search_returns_empty_without_vector_store():
    mem = MultiTieredMemory()
    results = await mem.episodic_search("test query")
    assert results == []


@pytest.mark.asyncio
async def test_episodic_store_noop_without_vector_store():
    mem = MultiTieredMemory()
    await mem.episodic_store("session-1", {"text": "test memory"})
    assert True


@pytest.mark.asyncio
async def test_semantic_query_returns_empty_without_graph_store():
    mem = MultiTieredMemory()
    results = await mem.semantic_query("MATCH (n) RETURN n LIMIT 1")
    assert results == []
