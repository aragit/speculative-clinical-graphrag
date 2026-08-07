from dataclasses import dataclass, field
from typing import Dict, List, Callable, Optional, Any
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


@dataclass
class Agent:
    name: str
    func: Callable
    capabilities: List[str]
    version: str = "1.0.0"
    description: str = ""
    enabled: bool = True
    last_executed: Optional[datetime] = None
    execution_count: int = 0
    avg_latency_ms: float = 0.0
    error_count: int = 0

    def record_execution(self, latency_ms: float, error: bool = False):
        self.last_executed = datetime.now(timezone.utc)
        self.execution_count += 1
        if error:
            self.error_count += 1
        alpha = 0.3
        self.avg_latency_ms = (alpha * latency_ms) + ((1 - alpha) * self.avg_latency_ms)

    @property
    def health(self) -> str:
        if not self.enabled:
            return "disabled"
        if self.error_count > 10 and self.error_count / max(self.execution_count, 1) > 0.5:
            return "unhealthy"
        return "healthy"


class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, Agent] = {}

    def register(self, agent: Agent):
        self._agents[agent.name] = agent
        logger.info(f"Agent registered: {agent.name} (capabilities: {agent.capabilities})")

    def unregister(self, name: str):
        if name in self._agents:
            del self._agents[name]
            logger.info(f"Agent unregistered: {name}")

    def get(self, name: str) -> Optional[Agent]:
        return self._agents.get(name)

    def list_by_capability(self, capability: str) -> List[Agent]:
        return [a for a in self._agents.values() if capability in a.capabilities and a.enabled]

    def list_all(self) -> List[Agent]:
        return list(self._agents.values())

    def get_health_report(self) -> Dict[str, str]:
        return {name: agent.health for name, agent in self._agents.items()}

    async def execute(self, name: str, state: Any) -> Any:
        agent = self.get(name)
        if agent is None:
            raise ValueError(f"Agent {name} not found")
        if not agent.enabled:
            raise RuntimeError(f"Agent {name} is disabled")

        import time
        import inspect
        start = time.time()
        error = False
        try:
            if inspect.iscoroutinefunction(agent.func):
                result = await agent.func(state)
            else:
                result = agent.func(state)
            return result
        except Exception:
            error = True
            raise
        finally:
            latency_ms = (time.time() - start) * 1000
            agent.record_execution(latency_ms, error=error)
