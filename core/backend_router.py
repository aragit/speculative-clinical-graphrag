import time
from typing import Dict, Optional
from dataclasses import dataclass, field
from core.llm_backend import LLMBackend, MockLLMBackend
import logging

logger = logging.getLogger(__name__)


@dataclass
class BackendMetrics:
    calls: int = 0
    total_latency_ms: float = 0.0
    escalations: int = 0
    validations: int = 0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.calls if self.calls > 0 else 0.0

    @property
    def escalation_rate(self) -> float:
        return self.escalations / self.calls if self.calls > 0 else 0.0


class BackendRouter:
    def __init__(self, backends: Dict[str, LLMBackend], default: str = "mock"):
        self.backends = backends
        self.default = default
        self.semantic = None
        self.metrics: Dict[str, BackendMetrics] = {k: BackendMetrics() for k in backends}

    def get_backend(self, key: Optional[str] = None) -> LLMBackend:
        if not key:
            return self.backends.get(self.default, MockLLMBackend())
        if key not in self.backends:
            logger.warning(f"Backend '{key}' not found, falling back to '{self.default}'")
            return self.backends.get(self.default, MockLLMBackend())
        return self.backends[key]

    def register(self, key: str, backend: LLMBackend):
        self.backends[key] = backend
        if key not in self.metrics:
            self.metrics[key] = BackendMetrics()

    def record_call(self, backend_key: str, latency_ms: float, status: str):
        if backend_key not in self.metrics:
            self.metrics[backend_key] = BackendMetrics()
        self.metrics[backend_key].calls += 1
        self.metrics[backend_key].total_latency_ms += latency_ms
        if status == "escalated":
            self.metrics[backend_key].escalations += 1
        elif status == "valid":
            self.metrics[backend_key].validations += 1

    def get_metrics(self) -> Dict:
        return {
            k: {
                "calls": m.calls,
                "avg_latency_ms": round(m.avg_latency_ms, 2),
                "escalation_rate": round(m.escalation_rate, 3),
                "validations": m.validations,
            }
            for k, m in self.metrics.items()
        }
