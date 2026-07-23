from typing import TypedDict, Any, Dict, List, Optional, Literal
import logging
import json
from langgraph.graph import StateGraph, END

from agents.reasoner.graph_reasoner import GraphReasonerAgent

logger = logging.getLogger(__name__)


class ClinicalState(TypedDict):
    trace_id: str
    query: str
    patient_note: str
    patient_context: Dict[str, Any]
    retrieved_context: Dict[str, Any]
    speculative_paths: List[Dict[str, Any]]
    proposed_path: List[Dict]
    symbolic_validation_passed: bool
    validation_errors: List[str]
    validation_result: Dict[str, Any]
    surface_output: Optional[str]
    escalation_reason: Optional[str]
    reasoning_trace: str
    status: str
    audit_log: List[Dict[str, Any]]


class ClinicalOrchestrator:
    """
    LangGraph-based Neuro-Symbolic State Machine Orchestrator.
    Manages state transitions from initial retrieval through speculative reasoning,
    symbolic safety checks, and optional HITL escalation.
    """

    def __init__(self, reasoner: GraphReasonerAgent, symbolic_verifier: Any, llm_backend: Any):
        self.reasoner = reasoner
        self.verifier = symbolic_verifier
        self.llm = llm_backend
        self.app = self._build_workflow()

    def _log(self, state: ClinicalState, node: str, detail: str = ""):
        import time
        entry = {
            "timestamp": time.time(),
            "node": node,
            "detail": detail,
        }
        state.setdefault("audit_log", []).append(entry)
        logger.info(f"[{state.get('trace_id')}] [{node}] {detail}")

    async def _retrieval_node(self, state: ClinicalState) -> Dict[str, Any]:
        self._log(state, "retrieve", "Fetching graph context from knowledge graph...")
        query = state.get("query", state.get("patient_note", ""))

        from core.verification_layer import lookup_edges, lookup_all_by_symptoms
        from core.retrieval import HybridRetriever

        # Symbolic lookup on in-memory EDGES
        graph_results = lookup_edges(query)

        # Also do batch symptom lookup if query contains known symptoms
        note_lower = query.lower()
        known_symptoms = [
            "dyspnea", "orthopnea", "chest pain", "fatigue", "edema",
            "palpitations", "cough", "wheeze", "fever", "headache",
            "nausea", "confusion", "syncope", "jaundice", "hematuria",
        ]
        found_symptoms = [s for s in known_symptoms if s in note_lower]
        if found_symptoms:
            symptom_mappings = lookup_all_by_symptoms(found_symptoms)
            for symptom, edges in symptom_mappings.items():
                graph_results.extend(edges)

        # Deduplicate
        seen = set()
        unique_results = []
        for e in graph_results:
            key = (e.get("head"), e.get("relation"), e.get("tail"))
            if key not in seen:
                seen.add(key)
                unique_results.append(e)

        self._log(state, "retrieve", f"Found {len(unique_results)} graph edges")
        return {
            "retrieved_context": {
                "graph_edges": unique_results,
                "symptoms_found": found_symptoms,
            }
        }

    async def _reasoning_node(self, state: ClinicalState) -> Dict[str, Any]:
        self._log(state, "speculative_reasoning", "Executing Speculative Graph Reasoner...")
        return await self.reasoner.__acall__(state)

    async def _symbolic_verification_node(self, state: ClinicalState) -> Dict[str, Any]:
        self._log(state, "symbolic_verification", "Running Symbolic Constraint Checks...")
        paths = state.get("speculative_paths", [])

        # Convert speculative paths to triplet format for verifier
        triplets = []
        for p in paths:
            nodes = p.get("nodes", [])
            relations = p.get("relations", [])
            if len(nodes) >= 2 and relations:
                triplets.append({
                    "head": nodes[0],
                    "relation": relations[0],
                    "tail": nodes[-1],
                    "confidence": p.get("confidence_score", 0.5),
                })

        if not triplets:
            # Fallback: check if any proposed_path exists
            triplets = state.get("proposed_path", [])

        # Run symbolic validation
        result = self.verifier.validate(triplets, state.get("patient_context"))
        is_valid = result.get("is_valid", False)
        errors = [v.get("reason", str(v)) for v in result.get("violations", [])]

        self._log(state, "symbolic_verification", f"valid={is_valid} errors={len(errors)}")

        return {
            "symbolic_validation_passed": is_valid,
            "validation_errors": errors,
            "validation_result": result,
            "proposed_path": triplets,
            "status": "validated" if is_valid else "validation_failed",
        }

    async def _synthesis_node(self, state: ClinicalState) -> Dict[str, Any]:
        self._log(state, "synthesize", "Synthesizing verified response...")

        paths = state.get("speculative_paths", [])
        validation = state.get("validation_result", {})
        query = state.get("query", state.get("patient_note", ""))

        # Build synthesis prompt
        validated_edges = validation.get("valid_edges", [])
        path_descriptions = []
        for p in paths:
            nodes = p.get("nodes", [])
            relations = p.get("relations", [])
            rationale = p.get("rationale", "")
            path_descriptions.append(f"  - {' -> '.join(nodes)} ({', '.join(relations)}): {rationale}")

        prompt = f"""You are a clinical decision support system. Synthesize the following verified clinical pathways into a clear, actionable response for a clinician.

Patient Query: {query}

Verified Paths:
{chr(10).join(path_descriptions) if path_descriptions else '  No verified paths available.'}

Validated Edges: {json.dumps(validated_edges, indent=2) if validated_edges else 'None'}

Provide a concise clinical summary."""

        try:
            if hasattr(self.llm, '_chat'):
                response = await self.llm._chat(prompt, max_tokens=2048)
            elif hasattr(self.llm, 'generate'):
                response = self.llm.generate(prompt)
            else:
                result = await self.llm.generate_path(query)
                response = json.dumps(result, indent=2)
        except Exception as e:
            logger.warning(f"LLM synthesis failed: {e}")
            response = json.dumps({
                "validated_paths": paths,
                "validation": validation,
                "note": "LLM synthesis unavailable, returning raw validated paths.",
            }, indent=2)

        return {
            "surface_output": response,
            "reasoning_trace": response,
            "status": "completed",
        }

    async def _escalation_node(self, state: ClinicalState) -> Dict[str, Any]:
        self._log(state, "escalate", "Escalating to HITL due to symbolic failure.")
        errors = state.get("validation_errors", [])
        paths = state.get("speculative_paths", [])

        escalation_detail = {
            "reason": f"Symbolic rule violation: {'; '.join(errors)}" if errors else "Validation failed",
            "speculative_paths": paths,
            "validation_errors": errors,
            "query": state.get("query", state.get("patient_note", "")),
        }

        return {
            "escalation_reason": json.dumps(escalation_detail, indent=2),
            "surface_output": f"Escalated to human review. {len(errors)} validation error(s) detected.",
            "status": "escalated_to_hitl",
        }

    def _route_after_validation(self, state: ClinicalState) -> str:
        """Conditional router based on symbolic validation outcome."""
        if state.get("symbolic_validation_passed", False):
            return "synthesize"
        return "escalate"

    def _build_workflow(self):
        builder = StateGraph(ClinicalState)

        # Define nodes
        builder.add_node("retrieve", self._retrieval_node)
        builder.add_node("speculative_reasoning", self._reasoning_node)
        builder.add_node("symbolic_verification", self._symbolic_verification_node)
        builder.add_node("synthesize", self._synthesis_node)
        builder.add_node("escalate", self._escalation_node)

        # Build edges
        builder.set_entry_point("retrieve")
        builder.add_edge("retrieve", "speculative_reasoning")
        builder.add_edge("speculative_reasoning", "symbolic_verification")

        # Conditional route
        builder.add_conditional_edges(
            "symbolic_verification",
            self._route_after_validation,
            {
                "synthesize": "synthesize",
                "escalate": "escalate",
            },
        )

        builder.add_edge("synthesize", END)
        builder.add_edge("escalate", END)

        return builder.compile()

    async def run(self, trace_id: str, query: str, patient_context: Optional[Dict] = None) -> Dict[str, Any]:
        initial_state: ClinicalState = {
            "trace_id": trace_id,
            "query": query,
            "patient_note": query,
            "patient_context": patient_context or {},
            "retrieved_context": {},
            "speculative_paths": [],
            "proposed_path": [],
            "symbolic_validation_passed": False,
            "validation_errors": [],
            "validation_result": {},
            "surface_output": None,
            "escalation_reason": None,
            "reasoning_trace": "",
            "status": "initialized",
            "audit_log": [],
        }
        return await self.app.ainvoke(initial_state, config={"recursion_limit": 20})

    def run_sync(self, trace_id: str, query: str, patient_context: Optional[Dict] = None) -> Dict[str, Any]:
        """Synchronous wrapper for non-async contexts."""
        import asyncio
        return asyncio.run(self.run(trace_id, query, patient_context))
