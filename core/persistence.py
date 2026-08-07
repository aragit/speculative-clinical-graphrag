import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class TraceStore(ABC):
    @abstractmethod
    async def save(self, trace_id: str, trace: Dict) -> None:
        pass

    @abstractmethod
    async def get(self, trace_id: str) -> Optional[Dict]:
        pass

    @abstractmethod
    async def update(self, trace_id: str, updates: Dict) -> bool:
        pass

    @abstractmethod
    async def list_recent(self, limit: int = 100) -> List[Dict]:
        pass


class InMemoryTraceStore(TraceStore):
    def __init__(self, ttl_seconds: int = 604800):
        self._store: Dict[str, Dict] = {}
        self._ttl = ttl_seconds

    async def save(self, trace_id: str, trace: Dict) -> None:
        trace["_stored_at"] = datetime.utcnow().isoformat()
        self._store[trace_id] = trace

    async def get(self, trace_id: str) -> Optional[Dict]:
        trace = self._store.get(trace_id)
        if trace is None:
            return None
        stored = datetime.fromisoformat(trace["_stored_at"])
        if datetime.utcnow() - stored > timedelta(seconds=self._ttl):
            del self._store[trace_id]
            return None
        return trace

    async def update(self, trace_id: str, updates: Dict) -> bool:
        trace = await self.get(trace_id)
        if trace is None:
            return False
        trace.update(updates)
        return True

    async def list_recent(self, limit: int = 100) -> List[Dict]:
        now = datetime.utcnow()
        valid = []
        for tid, trace in list(self._store.items()):
            stored = datetime.fromisoformat(trace["_stored_at"])
            if now - stored > timedelta(seconds=self._ttl):
                del self._store[tid]
            else:
                valid.append(trace)
        return sorted(valid, key=lambda x: x["_stored_at"], reverse=True)[:limit]


class RedisTraceStore(TraceStore):
    def __init__(self, redis_url: str = None, ttl_seconds: int = 604800):
        self.ttl = ttl_seconds
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self._redis = None

    def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as redis
            self._redis = redis.from_url(self.redis_url)
        return self._redis

    async def save(self, trace_id: str, trace: Dict) -> None:
        r = self._get_redis()
        key = f"trace:{trace_id}"
        trace["_stored_at"] = datetime.utcnow().isoformat()
        await r.setex(key, self.ttl, json.dumps(trace))

    async def get(self, trace_id: str) -> Optional[Dict]:
        r = self._get_redis()
        key = f"trace:{trace_id}"
        data = await r.get(key)
        if data is None:
            return None
        return json.loads(data)

    async def update(self, trace_id: str, updates: Dict) -> bool:
        trace = await self.get(trace_id)
        if trace is None:
            return False
        trace.update(updates)
        await self.save(trace_id, trace)
        return True

    async def list_recent(self, limit: int = 100) -> List[Dict]:
        logger.warning("RedisTraceStore.list_recent() not efficiently implemented; returning empty")
        return []


def get_trace_store() -> TraceStore:
    if os.getenv("REDIS_URL") or os.getenv("USE_REDIS", "").lower() == "true":
        return RedisTraceStore()
    return InMemoryTraceStore()
