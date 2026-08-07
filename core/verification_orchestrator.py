from typing import List, Dict, Optional
from pydantic import BaseModel, Field
import logging

from core.neural_verifier import NeuralVerifier, MockNeuralVerifier, NeuralVerificationResult
from core.confidence_fusion import ConfidenceFusion, VerifierConfidence

logger = logging.getLogger(__name__)


class VerificationResult(BaseModel):
    is_safe: bool = False
    is_valid: bool = False
    violations: List[Dict] = Field(default_factory=list)
    valid_edges: List[Dict] = Field(default_factory=list)
    total_checked: int = 0
    confidence_decay: float = 1.0
    neo4j_valid: bool = False
    symbolic_valid: bool = False
    opa_allowed: bool = False
    validation_mode: str = "symbolic_only"
    neural_confidence: Optional[float] = None
    neural_active: bool = False
    fused_confidence: float = 0.0
    decision: str = "escalate"
    verifier_breakdown: List[Dict] = Field(default_factory=list)


class VerificationOrchestrator:
    def __init__(
        self,
        neo4j_verifier=None,
        symbolic_verifier=None,
        opa_client=None,
        neural_verifier: Optional[NeuralVerifier] = None,
        enable_neural: bool = False,
        confidence_fusion: Optional[ConfidenceFusion] = None,
    ):
        from core.verification_layer import Neo4jVerifier, SymbolicVerifier, OPAClient
        self.neo4j = neo4j_verifier or Neo4jVerifier()
        self.symbolic = symbolic_verifier or SymbolicVerifier()
        self.opa = opa_client or OPAClient()
        self.neural = neural_verifier or MockNeuralVerifier()
        self.enable_neural = enable_neural
        self.fusion = confidence_fusion or ConfidenceFusion()

    async def verify(self, proposed_path: List[Dict], patient_context: Optional[Dict] = None) -> VerificationResult:
        ctx = patient_context or {}

        neo_result = await self.neo4j.validate_async(proposed_path)
        neo_mode = neo_result.get("mode", "degraded")

        sym_result = self.symbolic.validate(proposed_path, ctx)

        opa_result = await self.opa.evaluate({"proposed_path": proposed_path})
        opa_allow = opa_result.get("allow", True)

        merged_violations = list(neo_result.get("violations", [])) + list(sym_result.get("violations", []))

        if not opa_allow:
            merged_violations.append({
                "reason": "OPA policy blocked the proposed path",
                "triplet": {},
            })

        seen = set()
        merged_edges = []
        for e in neo_result.get("valid_edges", []) + sym_result.get("valid_edges", []):
            key = (e.get("head"), e.get("relation"), e.get("tail"))
            if key not in seen:
                seen.add(key)
                merged_edges.append(e)

        decay = min(
            neo_result.get("confidence_decay", 1.0),
            sym_result.get("confidence_decay", 1.0),
        )

        if neo_mode == "full" and sym_result["is_valid"] and opa_allow:
            mode = "full"
        elif neo_mode == "degraded" and sym_result["is_valid"] and opa_allow:
            mode = "degraded"
        else:
            mode = "symbolic_only"

        neural_result = NeuralVerificationResult()
        if self.enable_neural:
            neural_result = await self.neural.validate(proposed_path, patient_context)

        confidences = [
            VerifierConfidence(
                name="neo4j",
                confidence=1.0 - (len(neo_result.get("violations", [])) * 0.15),
                weight=self.fusion.weights.get("neo4j", 0.30),
                is_valid=neo_result["is_valid"],
            ),
            VerifierConfidence(
                name="symbolic",
                confidence=1.0 - (len(sym_result.get("violations", [])) * 0.20),
                weight=self.fusion.weights.get("symbolic", 0.35),
                is_valid=sym_result["is_valid"],
            ),
            VerifierConfidence(
                name="opa",
                confidence=1.0 if opa_allow else 0.0,
                weight=self.fusion.weights.get("opa", 0.20),
                is_valid=opa_allow,
            ),
        ]

        if self.enable_neural:
            confidences.append(VerifierConfidence(
                name="neural",
                confidence=neural_result.confidence,
                weight=self.fusion.weights.get("neural", 0.15),
                is_valid=neural_result.is_safe,
            ))

        fusion_result = self.fusion.fuse(confidences)

        is_safe = fusion_result["is_safe"]

        return VerificationResult(
            is_safe=is_safe and len(merged_edges) > 0,
            is_valid=fusion_result["is_safe"],
            violations=merged_violations,
            valid_edges=merged_edges,
            total_checked=len(proposed_path),
            confidence_decay=decay,
            neo4j_valid=neo_result["is_valid"],
            symbolic_valid=sym_result["is_valid"],
            opa_allowed=opa_allow,
            validation_mode=mode,
            neural_confidence=neural_result.confidence if self.enable_neural else None,
            neural_active=self.enable_neural,
            fused_confidence=fusion_result["fused_confidence"],
            decision=fusion_result["decision"],
            verifier_breakdown=fusion_result["verifier_breakdown"],
        )
