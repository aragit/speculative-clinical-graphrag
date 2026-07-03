import uuid
import json
import time
from typing import Dict, Optional
import os


class IdempotencyManager:
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self._redis = None

    def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as redis
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    def generate_key(self, trace_id: str, tool_name: str, payload: Dict) -> str:
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
        return str(uuid.uuid5(namespace, f"{trace_id}:{tool_name}:{canonical}"))

    async def check_and_store(self, key: str, ttl_seconds: int = 3600) -> bool:
        try:
            r = self._get_redis()
            result = await r.setnx(key, json.dumps({"stored_at": time.time()}))
            if result:
                await r.expire(key, ttl_seconds)
                return True
            return False
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Redis unreachable ({e}), allowing by default")
            return True

    async def get_result(self, key: str) -> Optional[Dict]:
        try:
            r = self._get_redis()
            val = await r.get(key)
            return json.loads(val) if val else None
        except Exception:
            return None
