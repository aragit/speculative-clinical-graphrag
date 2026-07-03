from typing import Dict, List
import json
import time
import logging
import os

logger = logging.getLogger(__name__)


class CQRSStateManager:
    def __init__(self, redis_url: str = None, db_path: str = "./events.db"):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.db_path = db_path
        self._redis = None

    def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as redis
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def commit_event(self, trace_id: str, event: Dict) -> None:
        event["timestamp"] = event.get("timestamp", time.time())
        event["trace_id"] = trace_id
        try:
            r = self._get_redis()
            stream_key = f"events:{trace_id}"
            await r.xadd(stream_key, {
                k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                for k, v in event.items()
            })
            await r.expire(stream_key, 86400)
            logger.info(f"Event committed: {trace_id} {event.get('node', event.get('type', 'unknown'))}")
        except Exception as e:
            logger.warning(f"Redis unavailable ({e}), logging event to file")
            with open(self.db_path, "a") as f:
                f.write(json.dumps({"trace_id": trace_id, **event}) + "\n")

    async def get_state(self, trace_id: str) -> Dict:
        try:
            r = self._get_redis()
            entries = await r.xrange(f"events:{trace_id}")
            events = []
            for _, fields in entries:
                ev = {
                    k: json.loads(v) if v.startswith("{") or v.startswith("[") else v
                    for k, v in fields.items()
                }
                events.append(ev)
            return {"trace_id": trace_id, "events": events}
        except Exception as e:
            logger.warning(f"Redis unavailable ({e}), reading from file")
            events = []
            if os.path.exists(self.db_path):
                with open(self.db_path, "r") as f:
                    for line in f:
                        ev = json.loads(line)
                        if ev.get("trace_id") == trace_id:
                            events.append(ev)
            return {"trace_id": trace_id, "events": events}
