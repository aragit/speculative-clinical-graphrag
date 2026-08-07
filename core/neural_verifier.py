from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from pydantic import BaseModel


class NeuralVerificationResult(BaseModel):
    is_safe: bool = True
    confidence: float = 0.5
    violations: List[Dict] = []
    reasoning: str = ""


class NeuralVerifier(ABC):
    @abstractmethod
    async def validate(self, proposed_path: List[Dict], patient_context: Optional[Dict] = None) -> NeuralVerificationResult:
        """Neural policy network evaluates proposed path safety."""
        pass

    @abstractmethod
    async def critique(self, proposed_path: List[Dict], prior_reasoning: str, patient_context: Optional[Dict] = None) -> NeuralVerificationResult:
        """Critique mode: provide improvement suggestions without blocking."""
        pass


class MockNeuralVerifier(NeuralVerifier):
    """Stub implementation. Returns neutral confidence, no violations."""

    async def validate(self, proposed_path: List[Dict], patient_context: Optional[Dict] = None) -> NeuralVerificationResult:
        return NeuralVerificationResult(
            is_safe=True,
            confidence=0.5,
            violations=[],
            reasoning="MockNeuralVerifier: neutral (stub)",
        )

    async def critique(self, proposed_path: List[Dict], prior_reasoning: str, patient_context: Optional[Dict] = None) -> NeuralVerificationResult:
        return NeuralVerificationResult(
            is_safe=True,
            confidence=0.5,
            violations=[],
            reasoning="MockNeuralVerifier: critique mode stub",
        )
