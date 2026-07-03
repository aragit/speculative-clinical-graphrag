from typing import TypedDict, List, Dict, Literal, Optional
from langgraph.graph import StateGraph, END
from core.llm_backend import LLMBackend, MockLLMBackend, SemanticRouter
from core.verification_layer import Neo4jVerifier, SymbolicVerifier
from core.reasoning_extractor import surface_reasoning_for_clinician
import logging
import time
import json
import asyncio
import re

logger = logging.getLogger(__name__)


class GraphState(TypedDict):
    patient_note: str
    patient_context: Optional[Dict]
    proposed_path: List[Dict]
    reasoning_trace: str
    validation_result: Dict
    retrieval_context: Optional[Dict]
    iteration_count: int
    max_iterations: int
    final_output: str
    status: Literal["valid", "corrected", "escalated", "error"]
    audit_log: List[Dict]
    dag_plan: Optional[Dict]
    backend_key: str


class SpeculativeGraphRAG:
    def __init__(
        self,
        llm: Optional[LLMBackend] = None,
        verifier: Optional[Neo4jVerifier] = None,
        symbolic_verifier: Optional[SymbolicVerifier] = None,
        max_iterations: int = 3,
    ):
        self.llm = llm or MockLLMBackend()
        self.verifier = verifier or Neo4jVerifier()
        self.symbolic = symbolic_verifier or SymbolicVerifier()
        self.router = SemanticRouter()
        self.max_iterations = max_iterations
        self.workflow = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(GraphState)
        workflow.add_node("ingest", self._ingest)
        workflow.add_node("speculate", self._speculate)
        workflow.add_node("retrieve", self._retrieve)
        workflow.add_node("verify", self._verify)
        workflow.add_node("correct", self._correct)
        workflow.add_node("validate", self._validate)
        workflow.add_node("escalate", self._escalate)
        workflow.add_node("synthesize", self._synthesize)
        workflow.set_entry_point("ingest")
        workflow.add_edge("ingest", "speculate")
        workflow.add_edge("speculate", "retrieve")
        workflow.add_edge("retrieve", "verify")
        workflow.add_conditional_edges(
            "verify",
            self._route,
            {"validate": "validate", "correct": "correct", "escalate": "escalate"},
        )
        workflow.add_edge("correct", "verify")
        workflow.add_edge("validate", "synthesize")
        workflow.add_edge("synthesize", END)
        workflow.add_edge("escalate", END)
        return workflow.compile()

    def _log(self, state: GraphState, node: str, detail: str = ""):
        entry = {
            "timestamp": time.time(),
            "node": node,
            "iteration": state.get("iteration_count", 0),
            "detail": detail,
        }
        state["audit_log"].append(entry)
        logger.info(f"[{node}] iter={entry['iteration']} {detail}")

    def _ingest(self, state: GraphState):
        note = state["patient_note"]
        ctx = state.get("patient_context") or {}
        if not ctx:
            age_match = re.search(r'(\\d+)\\s*-?\\s*year\\s*-?\\s*old', note, re.IGNORECASE)
            if age_match:
                ctx["age"] = int(age_match.group(1))
            gender_match = re.search(r'\\b(male|female|man|woman)\\b', note, re.IGNORECASE)
            if gender_match:
                g = gender_match.group(1).lower()
                ctx["gender"] = "male" if g in ("male", "man") else "female"
        state["patient_context"] = ctx
        self._log(state, "ingest", f"ctx={ctx}")
        return {"patient_context": ctx}

    def _speculate(self, state: GraphState):
        note = state["patient_note"]
        result = asyncio.run(
            self.llm.generate_path(note, state.get("patient_context"))
        )
        self._log(state, "speculate", f"triplets={len(result['triplets'])}")
        return {
            "proposed_path": result["triplets"],
            "reasoning_trace": result.get("reasoning", ""),
            "iteration_count": state.get("iteration_count", 0) + 1,
        }

    def _retrieve(self, state: GraphState):
        self._log(state, "retrieve", "hybrid RAG stub")
        return {"retrieval_context": {"vector_results": [], "graph_results": [], "merged_context": ""}}

    def _verify(self, state: GraphState):
        path = state["proposed_path"]
        neo_result = self.verifier.validate(path)
        sym_result = self.symbolic.validate(path, state.get("patient_context"))
        merged_valid = neo_result["is_valid"] and sym_result["is_valid"]
        merged_violations = neo_result["violations"] + sym_result["violations"]
        merged_edges = list({json.dumps(e, sort_keys=True): e for e in (neo_result["valid_edges"] + sym_result["valid_edges"])}.values())
        decay = min(neo_result.get("confidence_decay", 1.0), sym_result.get("confidence_decay", 1.0))
        result = {
            "is_valid": merged_valid,
            "valid_edges": merged_edges,
            "violations": merged_violations,
            "total_checked": neo_result["total_checked"],
            "confidence_decay": decay,
            "neo4j_result": neo_result,
            "symbolic_result": sym_result,
        }
        self._log(state, "verify", f"valid={merged_valid} v={len(merged_violations)}")
        return {"validation_result": result}

    def _route(self, state: GraphState) -> Literal["validate", "correct", "escalate"]:
        if state["validation_result"]["is_valid"]:
            return "validate"
        if state["iteration_count"] >= state["max_iterations"]:
            return "escalate"
        return "correct"

    def _correct(self, state: GraphState):
        note = state["patient_note"]
        violations = state["validation_result"]["violations"]
        prior = state["reasoning_trace"]
        ctx = state.get("patient_context", {})
        ctx["iteration"] = state.get("iteration_count", 1)
        result = asyncio.run(
            self.llm.regenerate_with_feedback(note, violations, prior, ctx)
        )
        self._log(state, "correct", f"new_triplets={len(result['triplets'])}")
        return {
            "proposed_path": result["triplets"],
            "reasoning_trace": result.get("reasoning", prior),
            "iteration_count": state.get("iteration_count", 0) + 1,
        }

    def _validate(self, state: GraphState):
        self._log(state, "validate", "path accepted")
        return {"status": "valid"}

    def _escalate(self, state: GraphState):
        reason = f"Escalated after {state['iteration_count']} attempts. Violations: {len(state['validation_result']['violations'])}"
        self._log(state, "escalate", reason)
        return {
            "status": "escalated",
            "final_output": f"Escalated to human review. {reason}",
        }

    def _synthesize(self, state: GraphState):
        path = state["proposed_path"]
        reasoning = surface_reasoning_for_clinician(state["reasoning_trace"], 1500)
        sources = []
        for e in state["validation_result"].get("valid_edges", []):
            sources.append({
                "head": e.get("head"),
                "relation": e.get("relation"),
                "tail": e.get("tail"),
                "validated_by": "neo4j+symbolic",
            })
        output = {
            "validated_path": path,
            "reasoning_summary": reasoning,
            "source_attribution": sources,
            "patient_context": state.get("patient_context"),
        }
        self._log(state, "synthesize", f"sources={len(sources)}")
        return {
            "final_output": json.dumps(output, indent=2),
            "status": "valid",
        }

    def run(self, patient_note: str, patient_context: Optional[Dict] = None, backend_key: Optional[str] = None) -> GraphState:
        initial_state: GraphState = {
            "patient_note": patient_note,
            "patient_context": patient_context,
            "proposed_path": [],
            "reasoning_trace": "",
            "validation_result": {},
            "retrieval_context": None,
            "iteration_count": 0,
            "max_iterations": self.max_iterations,
            "final_output": "",
            "status": "valid",
            "audit_log": [],
            "dag_plan": None,
            "backend_key": backend_key or "",
        }
        return self.workflow.invoke(initial_state, config={"recursion_limit": 10})
