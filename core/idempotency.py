import hashlib
import uuid
import json
from typing import Dict

class IdempotencyManager:
    """Cryptographic idempotency keys for every agent tool call."""
    def generate_key(self, trace_id: str, tool_name: str, payload: Dict) -> str:
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # DNS namespace
        return str(uuid.uuid5(namespace, f"{trace_id}:{tool_name}:{canonical}"))

    async def check_and_store(self, key: str, ttl_seconds: int = 3600) -> bool:
        # Stub: in production, check Redis/DB
        return True
