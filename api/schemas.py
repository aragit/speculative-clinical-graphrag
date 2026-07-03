from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal

class SpeculateRequest(BaseModel):
    patient_note: str = Field(..., min_length=1, max_length=10000)
    patient_context: Optional[Dict] = Field(default=None, description="Age, gender, allergies, current meds")
    preferred_backend: Optional[Literal["mock", "ollama", "deepseek_r1"]] = Field(default=None)

class SpeculateResponse(BaseModel):
    proposed_path: List[Dict]
    validation: Dict
    iterations: int
    final_output: str
    status: Literal["valid", "corrected", "escalated"]
    reasoning_trace: Optional[str] = Field(default=None, description="Clinician-reviewable reasoning")
    retrieval_sources: Optional[List[Dict]] = Field(default=None, description="Hybrid RAG source attribution")
    audit_log: Optional[List[Dict]] = Field(default=None)

class ReasoningTraceRequest(BaseModel):
    trace_id: str

class ReasoningTraceResponse(BaseModel):
    trace_id: str
    reasoning_trace: str
    surface_output: str
    validation_history: List[Dict]
    escalation_reason: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    llm_mode: str
    neo4j_connected: bool
    qdrant_connected: bool
    opa_connected: bool
    version: str = "0.2.0"
