from typing import Dict
import logging
logger = logging.getLogger(__name__)

class CQRSStateManager:
    """Stub: Commands to append-only store, Queries from read replicas."""
    def __init__(self, redis_url: str = "redis://localhost:6379", db_path: str = "./events.db"):
        self.redis_url = redis_url
        self.db_path = db_path

    async def commit_event(self, trace_id: str, event: Dict) -> None:
        logger.info(f"Event committed: {trace_id} {event.get('node')}")

    async def get_state(self, trace_id: str) -> Dict:
        return {"trace_id": trace_id, "events": []}
