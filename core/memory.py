from typing import Any, Dict, List

class MultiTieredMemory:
    """Stub: Working (Redis), Episodic (Vector), Semantic (Neo4j)."""
    def __init__(self, redis_client=None, vector_store=None, graph_store=None):
        self.redis = redis_client
        self.vector = vector_store
        self.graph = graph_store

    async def working_get(self, session_id: str, key: str) -> Any:
        return None

    async def working_set(self, session_id: str, key: str, value: Any, ttl: int = 86400):
        pass

    async def episodic_search(self, query: str, top_k: int = 5) -> List[Dict]:
        return []

    async def episodic_store(self, session_id: str, memory: Dict):
        pass

    async def semantic_query(self, cypher: str) -> List[Dict]:
        return []
