from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal
from datetime import datetime


class SpeculateRequest(BaseModel):
    patient_note: str = Field(..., min_length=1, max_length=10000)
    patient_context: Optional[Dict] = Field(default=None, description="Age, gender, allergies, current meds")
    preferred_backend: Optional[Literal["mock", "ollama", "deepseek_r1", "medgemma_4b_it"]] = Field(default=None)
    
class SpeculateResponse(BaseModel):
    proposed_path: List[Dict]
    validation: Dict
    iterations: int
    final_output: str
    status: Literal["valid", "corrected", "escalated", "error"]
    reasoning_trace: Optional[str] = Field(default=None, description="Clinician-reviewable reasoning")
    retrieval_sources: Optional[List[Dict]] = Field(default=None, description="Hybrid RAG source attribution")
    audit_log: Optional[List[Dict]] = Field(default=None)
    validation_mode: Literal["full", "degraded", "symbolic_only"] = Field(
        default="symbolic_only",
        description="Validation layer status: full (Neo4j+Symbolic+OPA), degraded (in-memory+Symbolic+OPA), symbolic_only (no graph)"
    )
    reasoning_history: Optional[List[Dict]] = Field(
        default=None,
        description="Full chain of reasoning across all correction iterations",
    )
    ab_variant: Optional[str] = Field(
        default=None,
        description="A/B test variant identifier from X-AB-Variant header",
    )
    ab_metadata: Optional[Dict] = Field(
        default=None,
        description="A/B test metadata including variant, seed, and selection reason",
    )

class ReasoningTraceRequest(BaseModel):
    trace_id: str

class ReasoningTraceResponse(BaseModel):
    trace_id: str
    reasoning_trace: str
    surface_output: str
    validation_history: List[Dict]
    escalation_reason: Optional[str] = None
    ab_variant: Optional[str] = None
    ab_metadata: Optional[Dict] = None

class HealthResponse(BaseModel):
    status: str
    llm_mode: str
    neo4j_connected: bool
    qdrant_connected: bool
    opa_connected: bool
    redis_connected: bool = False
    version: str = "0.6.0"


class OverrideRequest(BaseModel):
    trace_id: str = Field(..., description="ID of the escalated trace to override")
    override_action: Literal["approve", "reject", "modify"] = Field(
        ..., description="Clinician decision: approve, reject, or modify the path"
    )
    modified_path: Optional[List[Dict]] = Field(
        default=None,
        description="Replacement diagnostic triplets when override_action is 'modify'",
    )
    clinician_notes: str = Field(
        ..., min_length=1, max_length=5000,
        description="Free-text clinician justification for the override",
    )


class OverrideResponse(BaseModel):
    trace_id: str
    status: Literal["clinician_approved", "clinician_rejected", "clinician_modified"]
    override_action: str
    clinician_notes: str
    surface_output: Optional[str] = None
    modified_path: Optional[List[Dict]] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
