from typing import Any, Dict, List, Optional
import json
import logging
import os

logger = logging.getLogger(__name__)


class MultiTieredMemory:
    def __init__(self, redis_client=None, vector_store=None, graph_store=None):
        self._vector_store = vector_store
        self._graph_store = graph_store
        self._redis = None
        self.working_memory: Dict[str, Dict] = {}

    def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as redis
            self._redis = redis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379"),
                decode_responses=True,
            )
        return self._redis

    async def working_get(self, session_id: str, key: str) -> Any:
        try:
            r = self._get_redis()
            val = await r.get(f"wm:{session_id}:{key}")
            return json.loads(val) if val else None
        except Exception:
            return None

    async def working_set(self, session_id: str, key: str, value: Any, ttl: int = 86400):
        try:
            r = self._get_redis()
            await r.set(f"wm:{session_id}:{key}", json.dumps(value, default=str), ex=ttl)
        except Exception as e:
            logger.warning(f"Redis working_set failed: {e}")

    async def episodic_search(self, query: str, top_k: int = 5) -> List[Dict]:
        if self._vector_store is None:
            return []
        try:
            from sentence_transformers import SentenceTransformer
            enc = SentenceTransformer("all-MiniLM-L6-v2")
            query_vec = enc.encode(query).tolist()
            results = self._vector_store.search(
                collection_name="episodic_memory",
                query_vector=query_vec,
                limit=top_k,
            )
            return [{"id": r.id, "score": r.score, "payload": r.payload} for r in results]
        except Exception as e:
            logger.warning(f"Episodic search failed: {e}")
            return []

    async def episodic_store(self, session_id: str, memory: Dict):
        if self._vector_store is None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            import uuid
            enc = SentenceTransformer("all-MiniLM-L6-v2")
            text = memory.get("text", json.dumps(memory))
            vec = enc.encode(text).tolist()
            from qdrant_client.models import PointStruct
            point = PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{session_id}:{text[:64]}")),
                vector=vec,
                payload={"session_id": session_id, "text": text, **memory},
            )
            self._vector_store.upsert(collection_name="episodic_memory", points=[point])
        except Exception as e:
            logger.warning(f"Episodic store failed: {e}")

    async def semantic_query(self, cypher: str) -> List[Dict]:
        if self._graph_store is None:
            return []
        try:
            with self._graph_store.session() as session:
                result = session.run(cypher)
                return [dict(r) for r in result]
        except Exception as e:
            logger.warning(f"Semantic query failed: {e}")
            return []

    def get_working_memory(self, session_id: str = "default") -> Dict:
        return self.working_memory.get(session_id, {})

    def get_episodic_memory(self, session_id: str = "default") -> Any:
        return self._vector_store

    def get_semantic_memory(self) -> Any:
        return self._graph_store
