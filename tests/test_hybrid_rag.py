import pytest
from core.retrieval import HybridRetriever


@pytest.mark.asyncio
async def test_vector_retrieval_returns_structure():
    retriever = HybridRetriever()
    result = await retriever._vector_search("dyspnea", top_k=3)
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_graph_traversal_returns_edges():
    retriever = HybridRetriever()
    result = await retriever._graph_search("dyspnea")
    assert isinstance(result, list)
    if result:
        assert "head" in result[0]
        assert "tail" in result[0]
