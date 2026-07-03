from typing import Dict, List
import logging
logger = logging.getLogger(__name__)

class HybridRetriever:
    """Stub: LlamaIndex + Qdrant vector + Neo4j graph hybrid RAG."""
    def __init__(self, qdrant_host: str = "http://localhost:6333", neo4j_verifier=None, embed_model: str = "local"):
        self.qdrant_host = qdrant_host
        self.neo4j = neo4j_verifier

    async def retrieve(self, query: str, proposed_path: List[Dict]) -> Dict:
        logger.info("HybridRetriever.retrieve stub called")
        return {
            "vector_results": [],
            "graph_results": [],
            "merged_context": "",
        }
