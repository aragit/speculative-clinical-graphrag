from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, Literal, List
from datetime import datetime, timezone
import uuid


class ReActTracePayload(BaseModel):
    agent_name: str
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[Any] = None


class NodeStartEndPayload(BaseModel):
    node_label: str
    detail: str = ""


class StateMutationPayload(BaseModel):
    changed_keys: List[str]
    state_snapshot: Dict[str, Any]


class GovernanceCheckPayload(BaseModel):
    policy_name: str
    passed: bool
    violations: List[Dict[str, Any]] = []
    details: Dict[str, Any] = {}


class FinalSynthesisPayload(BaseModel):
    output_type: Literal["synthesis", "escalation"]
    summary: str
    full_output: Dict[str, Any]


class MASEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_type: Literal[
        "NODE_START",
        "REACT_TRACE",
        "STATE_MUTATION",
        "GOVERNANCE_CHECK",
        "NODE_END",
        "FINAL_SYNTHESIS",
    ]
    node_id: str
    payload: Dict[str, Any]
