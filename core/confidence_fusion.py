from typing import List, Dict, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class VerifierConfidence(BaseModel):
    name: str
    confidence: float
    weight: float
    is_valid: bool


class ConfidenceFusion:
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        safe_threshold: float = 0.7,
        unsafe_threshold: float = 0.3,
    ):
        self.weights = weights or {
            "symbolic": 0.35,
            "neo4j": 0.30,
            "opa": 0.20,
            "neural": 0.15,
        }
        self.safe_threshold = safe_threshold
        self.unsafe_threshold = unsafe_threshold

    def fuse(self, confidences: List[VerifierConfidence]) -> Dict:
        if not confidences:
            return {"is_safe": False, "fused_confidence": 0.0, "decision": "escalate"}

        total_weight = sum(v.weight for v in confidences)
        if total_weight == 0:
            return {"is_safe": False, "fused_confidence": 0.0, "decision": "escalate"}

        normalized = []
        for v in confidences:
            normalized.append(VerifierConfidence(
                name=v.name,
                confidence=v.confidence,
                weight=v.weight / total_weight,
                is_valid=v.is_valid,
            ))

        fused = sum(v.confidence * v.weight for v in normalized)

        if fused >= self.safe_threshold and all(v.is_valid for v in confidences):
            decision = "valid"
            is_safe = True
        elif fused <= self.unsafe_threshold:
            decision = "escalate"
            is_safe = False
        elif any(not v.is_valid for v in confidences):
            decision = "correct"
            is_safe = False
        else:
            decision = "correct"
            is_safe = False

        return {
            "is_safe": is_safe,
            "fused_confidence": round(fused, 4),
            "decision": decision,
            "verifier_breakdown": [
                {"name": v.name, "confidence": v.confidence, "weight": v.weight, "is_valid": v.is_valid}
                for v in confidences
            ],
        }

    def update_weight(self, verifier_name: str, new_weight: float):
        self.weights[verifier_name] = new_weight
        logger.info(f"Updated confidence weight for {verifier_name}: {new_weight}")
