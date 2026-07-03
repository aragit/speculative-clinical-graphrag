from typing import TypedDict, List, Dict, Literal, Optional
from langgraph.graph import StateGraph, END
from core.llm_backend import LLMBackend, MockLLMBackend, SemanticRouter
from core.verification_layer import Neo4jVerifier, SymbolicVerifier, OPAClient, lookup_all_by_symptoms
from core.reasoning_extractor import surface_reasoning_for_clinician
from core.retrieval import HybridRetriever
import logging
import time
import json
import asyncio
import re

logger = logging.getLogger(__name__)


class GraphState(TypedDict):
    patient_note: str
    patient_context: Dict
    retrieval_context: str
    extracted_symptoms: List[Dict]
    ontology_mappings: Dict[str, List[Dict]]
    proposed_path: List[Dict]
    safety_result: Dict
    validation_result: Dict
    reasoning_trace: str
    final_output: str
    status: Literal["valid", "corrected", "escalated", "error"]
    audit_log: List[Dict]
    iteration_count: int
    backend_key: str
    violations: List[Dict]
    prior_reasoning: str


class SpeculativeGraphRAG:
    def __init__(
        self,
        llm: Optional[LLMBackend] = None,
        verifier: Optional[Neo4jVerifier] = None,
        symbolic_verifier: Optional[SymbolicVerifier] = None,
        opa_client: Optional[OPAClient] = None,
        retriever: Optional[HybridRetriever] = None,
        max_iterations: int = 3,
    ):
        self.llm = llm or MockLLMBackend()
        self.verifier = verifier or Neo4jVerifier()
        self.symbolic = symbolic_verifier or SymbolicVerifier()
        self.opa = opa_client or OPAClient()
        self.retriever = retriever or HybridRetriever()
        self.router = SemanticRouter()
        self.max_iterations = max_iterations
        self.workflow = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(GraphState)
        workflow.add_node("ingest", self._ingest)
        workflow.add_node("retrieve_context", self._retrieve_context)
        workflow.add_node("extract_symptoms", self._extract_symptoms)
        workflow.add_node("map_to_ontology", self._map_to_ontology)
        workflow.add_node("assess_differential", self._assess_differential)
        workflow.add_node("verify_safety", self._verify_safety)
        workflow.add_node("correct_differential", self._correct_differential)
        workflow.add_node("synthesize", self._synthesize)
        workflow.add_node("escalate", self._escalate)
        workflow.set_entry_point("ingest")
        workflow.add_edge("ingest", "retrieve_context")
        workflow.add_edge("retrieve_context", "extract_symptoms")
        workflow.add_edge("extract_symptoms", "map_to_ontology")
        workflow.add_edge("map_to_ontology", "assess_differential")
        workflow.add_edge("assess_differential", "verify_safety")
        workflow.add_conditional_edges(
            "verify_safety",
            self._route,
            {
                "correct_differential": "correct_differential",
                "synthesize": "synthesize",
                "escalate": "escalate",
            },
        )
        workflow.add_conditional_edges(
            "correct_differential",
            self._route_after_correction,
            {"assess_differential": "assess_differential", "escalate": "escalate"},
        )
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
        ctx = dict(state.get("patient_context") or {})
        age_match = re.search(r'(\d+)\s*-?\s*year\s*-?\s*old', note, re.IGNORECASE)
        if age_match:
            ctx["age"] = int(age_match.group(1))
        gender_match = re.search(r'\b(male|female|man|woman)\b', note, re.IGNORECASE)
        if gender_match:
            g = gender_match.group(1).lower()
            ctx["gender"] = "male" if g in ("male", "man") else "female"
        meds_match = re.findall(
            r'\b(Warfarin|Aspirin|Metformin|Insulin|Furosemide|Lisinopril|Atorvastatin)\b',
            note, re.IGNORECASE,
        )
        if meds_match:
            ctx["medications"] = list(set(m.title() for m in meds_match))
        self._log(state, "ingest", f"ctx={ctx}")
        return {"patient_context": ctx, "iteration_count": 1}

    def _retrieve_context(self, state: GraphState):
        note = state["patient_note"]
        result = asyncio.get_event_loop().run_until_complete(
            self.retriever.retrieve(note)
        )
        ctx = result.get("merged_context", "")
        self._log(state, "retrieve_context", f"vector={len(result['vector_results'])} graph={len(result['graph_results'])}")
        return {"retrieval_context": ctx}

    def _extract_symptoms(self, state: GraphState):
        note = state["patient_note"]
        ctx = dict(state.get("patient_context") or {})
        if state.get("retrieval_context"):
            ctx["retrieval_context"] = state["retrieval_context"]
        result = asyncio.get_event_loop().run_until_complete(
            self.llm.extract_symptoms(note, ctx)
        )
        symptoms = result.get("symptoms", [])
        self._log(state, "extract_symptoms", f"found {len(symptoms)} symptoms: {symptoms}")
        return {"extracted_symptoms": symptoms}

    def _map_to_ontology(self, state: GraphState):
        symptoms = [s["term"] for s in state.get("extracted_symptoms", [])]
        if not symptoms:
            return {"ontology_mappings": {}}
        mappings = lookup_all_by_symptoms(symptoms)
        total_edges = sum(len(v) for v in mappings.values())
        self._log(state, "map_to_ontology", f"mapped {len(mappings)} symptoms to {total_edges} ontology edges")
        return {"ontology_mappings": mappings}

    def _assess_differential(self, state: GraphState):
        symptoms = [s["term"] for s in state.get("extracted_symptoms", [])]
        mappings_flat = []
        for symptom_edges in state.get("ontology_mappings", {}).values():
            mappings_flat.extend(symptom_edges)
        result = asyncio.get_event_loop().run_until_complete(
            self.llm.assess_differential(symptoms, mappings_flat, state.get("patient_context"))
        )
        triplets = result.get("triplets", [])
        reasoning = result.get("reasoning", "")
        self._log(state, "assess_differential", f"proposed {len(triplets)} differential edges")
        return {"proposed_path": triplets, "reasoning_trace": reasoning, "prior_reasoning": reasoning}

    def _correct_differential(self, state: GraphState):
        violations = state.get("safety_result", {}).get("violations", [])
        prior = state.get("reasoning_trace", "")
        result = asyncio.get_event_loop().run_until_complete(
            self.llm.regenerate_with_feedback(
                state["patient_note"], violations, prior, state.get("patient_context")
            )
        )
        triplets = result.get("triplets", [])
        reasoning = result.get("reasoning", "")
        iteration = state.get("iteration_count", 1) + 1
        self._log(state, "correct_differential", f"corrected: {len(triplets)} edges (attempt {iteration})")
        return {
            "proposed_path": triplets,
            "reasoning_trace": reasoning,
            "iteration_count": iteration,
            "violations": violations,
        }

    def _verify_safety(self, state: GraphState):
        path = state.get("proposed_path", [])
        ctx = state.get("patient_context", {})

        neo_result = self.verifier.validate(path)
        sym_result = self.symbolic.validate(path, ctx)
        opa_result = asyncio.get_event_loop().run_until_complete(self.opa.evaluate({"proposed_path": path}))

        opa_allow = opa_result.get("allow", True)
        merged_valid = neo_result["is_valid"] and sym_result["is_valid"] and opa_allow
        merged_violations = neo_result["violations"] + sym_result["violations"]
        if not opa_allow:
            merged_violations.append({"reason": "OPA policy blocked the proposed path", "triplet": {}})

        merged_edges = list(
            {json.dumps(e, sort_keys=True): e for e in (
                neo_result["valid_edges"] + sym_result["valid_edges"]
            )}.values()
        )
        decay = min(
            neo_result.get("confidence_decay", 1.0),
            sym_result.get("confidence_decay", 1.0),
        )
        safety_result = {
            "is_safe": merged_valid,
            "violations": merged_violations,
            "opa_allowed": opa_allow,
            "neo4j_valid": neo_result["is_valid"],
            "symbolic_valid": sym_result["is_valid"],
        }
        validation_result = {
            "is_valid": merged_valid,
            "valid_edges": merged_edges,
            "violations": merged_violations,
            "total_checked": len(path),
            "confidence_decay": decay,
        }
        self._log(state, "verify_safety", f"safe={merged_valid} violations={len(merged_violations)}")
        return {"safety_result": safety_result, "validation_result": validation_result, "violations": merged_violations}

    def _route(self, state: GraphState) -> Literal["correct_differential", "synthesize", "escalate"]:
        is_safe = state.get("safety_result", {}).get("is_safe", False)
        iteration = state.get("iteration_count", 1)
        if is_safe:
            return "synthesize"
        if iteration < self.max_iterations:
            return "correct_differential"
        return "escalate"

    def _route_after_correction(self, state: GraphState) -> Literal["assess_differential", "escalate"]:
        iteration = state.get("iteration_count", 1)
        if iteration >= self.max_iterations:
            return "escalate"
        return "assess_differential"

    def _synthesize(self, state: GraphState):
        path = state.get("proposed_path", [])
        reasoning = surface_reasoning_for_clinician(state.get("reasoning_trace", ""), 1500)
        sources = []
        for e in state.get("validation_result", {}).get("valid_edges", []):
            sources.append({
                "head": e.get("head"),
                "relation": e.get("relation"),
                "tail": e.get("tail"),
                "validated_by": "neo4j+symbolic+opa",
            })
        output = {
            "validated_path": path,
            "reasoning_summary": reasoning,
            "source_attribution": sources,
            "patient_context": state.get("patient_context"),
            "ontology_mappings": {
                sym: len(edges)
                for sym, edges in state.get("ontology_mappings", {}).items()
            },
            "retrieval_context": state.get("retrieval_context", ""),
        }
        self._log(state, "synthesize", f"sources={len(sources)}")
        return {
            "final_output": json.dumps(output, indent=2),
            "status": "valid",
        }

    def _escalate(self, state: GraphState):
        if state.get("status") == "escalated":
            return state
        violations = state.get("violations", state.get("safety_result", {}).get("violations", []))
        reason = f"Escalated after {state['iteration_count']} attempt(s). Violations: {len(violations)}"
        self._log(state, "escalate", reason)
        return {
            "status": "escalated",
            "final_output": f"Escalated to human review. {reason} Violations: {json.dumps(violations, indent=2)}",
        }

    def run(self, patient_note: str, patient_context: Optional[Dict] = None, backend_key: Optional[str] = None) -> GraphState:
        if backend_key and self.router:
            routed = asyncio.get_event_loop().run_until_complete(
                self.router.route(patient_note)
            )
            backend_key = routed
        initial_state: GraphState = {
            "patient_note": patient_note,
            "patient_context": patient_context or {},
            "retrieval_context": "",
            "extracted_symptoms": [],
            "ontology_mappings": {},
            "proposed_path": [],
            "safety_result": {},
            "validation_result": {},
            "reasoning_trace": "",
            "final_output": "",
            "status": "valid",
            "audit_log": [],
            "iteration_count": 0,
            "backend_key": backend_key or "",
            "violations": [],
            "prior_reasoning": "",
        }
        return self.workflow.invoke(initial_state, config={"recursion_limit": 20})
