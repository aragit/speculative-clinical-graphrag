import pytest
from core.retrieval import HybridRetriever


@pytest.mark.asyncio
async def test_retrieve_returns_structure():
    retriever = HybridRetriever()
    result = await retriever.retrieve("dyspnea", proposed_path=[])
    assert "vector_results" in result
    assert "graph_results" in result
    assert "merged_context" in result


@pytest.mark.asyncio
async def test_retrieve_graph_results_uses_in_memory_edges():
    retriever = HybridRetriever()
    result = await retriever.retrieve("dyspnea")
    assert len(result["graph_results"]) > 0
    first = result["graph_results"][0]
    assert "head" in first
    assert "relation" in first
    assert "tail" in first


def test_fusion_score():
    score = HybridRetriever._fusion_score(1.0, 0.5, alpha=0.7)
    assert round(score, 2) == 0.85


def test_fusion_score_default_alpha():
    score = HybridRetriever._fusion_score(0.8, 0.2)
    assert round(score, 2) == 0.62
