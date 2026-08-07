from typing import List, Dict, Literal, Optional
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field
from core.llm_backend import LLMBackend, MockLLMBackend, SemanticRouter
from core.backend_router import BackendRouter
from core.verification_layer import lookup_all_by_symptoms
from core.verification_orchestrator import VerificationOrchestrator, VerificationResult
from core.topology import WorkflowTopology
from core.fhir_parser import FHIRParser
from core.neural_policy import NeuralPolicyNetwork
from core.agents import AgentRegistry, Agent
from core.dag_modifier import DAGModifier
from core.reasoning_extractor import surface_reasoning_for_clinician
from core.retrieval import HybridRetriever
import logging
import time
import json
import re
import os

logger = logging.getLogger(__name__)


class GraphState(BaseModel):
    patient_note: str = ""
    patient_context: Dict = Field(default_factory=dict)
    retrieval_context: str = ""
    extracted_symptoms: List[Dict] = Field(default_factory=list)
    ontology_mappings: Dict[str, List[Dict]] = Field(default_factory=dict)
    proposed_path: List[Dict] = Field(default_factory=list)
    safety_result: Dict = Field(default_factory=dict)
    validation_result: Dict = Field(default_factory=dict)
    reasoning_trace: str = ""
    reasoning_history: List[Dict] = Field(default_factory=list)
    final_output: str = ""
    status: Literal["valid", "corrected", "escalated", "error"] = "valid"
    audit_log: List[Dict] = Field(default_factory=list)
    iteration_count: int = 0
    backend_key: str = ""
    violations: List[Dict] = Field(default_factory=list)
    prior_reasoning: str = ""
    prior_reasoning_path: List[Dict] = Field(default_factory=list)
    validation_mode: Literal["full", "degraded", "symbolic_only"] = "symbolic_only"
    active_llm_type: str = ""

    def evolve(self, **updates) -> "GraphState":
        return self.model_copy(update=updates)

    def to_dict(self) -> Dict:
        return self.model_dump()

    @classmethod
    def from_dict(cls, d: Dict) -> "GraphState":
        return cls(**d)


class SpeculativeGraphRAG:
    def __init__(
        self,
        llm: Optional[LLMBackend] = None,
        router: Optional["BackendRouter"] = None,
        verifier: Optional["object"] = None,
        symbolic_verifier: Optional["object"] = None,
        opa_client: Optional["object"] = None,
        verification_orchestrator: Optional[VerificationOrchestrator] = None,
        retriever: Optional[HybridRetriever] = None,
        neural_verifier: Optional["object"] = None,
        enable_neural: bool = False,
        max_iterations: int = 3,
    ):
        if router is not None:
            self.router_backend = router
        elif llm is not None:
            self.router_backend = BackendRouter({llm.backend_type: llm}, default=llm.backend_type)
        else:
            self.router_backend = BackendRouter({"mock": MockLLMBackend()}, default="mock")

        if verification_orchestrator is not None:
            self.verification = verification_orchestrator
        else:
            self.verification = VerificationOrchestrator(
                neo4j_verifier=verifier,
                symbolic_verifier=symbolic_verifier,
                opa_client=opa_client,
                neural_verifier=neural_verifier,
                enable_neural=enable_neural,
            )

        self.retriever = retriever or HybridRetriever()
        self.router = SemanticRouter()
        self.max_iterations = max_iterations
        self.topology = WorkflowTopology()
        self._register_nodes()
        self.workflow = self._build_graph()
        self.dag_modifier = DAGModifier(self.topology)
        self.enable_dynamic_dag = os.getenv("ENABLE_DYNAMIC_DAG", "false").lower() == "true"
        self.agent_registry = AgentRegistry()
        self._register_agents()
        self.neural_policy = NeuralPolicyNetwork(
            enable_learning=os.getenv("ENABLE_NEURAL_POLICY_LEARNING", "true").lower() == "true"
        )
        self.enable_neural_policy = os.getenv("ENABLE_NEURAL_POLICY", "false").lower() == "true"
        self._pending_decision: Optional[Dict] = None

    def _register_agents(self):
        """Register all workflow nodes as agents with capabilities."""
        agents = [
            Agent(
                name="fhir_parse",
                func=self._fhir_parse,
                capabilities=["parsing", "fhir", "structured_input"],
                description="Parses FHIR R4 resources into patient context",
            ),
            Agent(
                name="ingest",
                func=self._ingest,
                capabilities=["parsing", "regex", "fallback"],
                description="Extracts age/gender/meds from free text via regex",
            ),
            Agent(
                name="retrieve_context",
                func=self._retrieve_context,
                capabilities=["retrieval", "rag", "vector", "graph"],
                description="Hybrid vector+graph retrieval",
            ),
            Agent(
                name="extract_symptoms",
                func=self._extract_symptoms,
                capabilities=["extraction", "symptom", "nlp", "llm"],
                description="LLM-based symptom extraction",
            ),
            Agent(
                name="map_to_ontology",
                func=self._map_to_ontology,
                capabilities=["mapping", "ontology", "graph"],
                description="Maps symptoms to ontology edges",
            ),
            Agent(
                name="assess_differential",
                func=self._assess_differential,
                capabilities=["reasoning", "differential", "llm"],
                description="LLM-based differential diagnosis assessment",
            ),
            Agent(
                name="verify_safety",
                func=self._verify_safety,
                capabilities=["verification", "safety", "multi_layer"],
                description="Multi-layer safety verification",
            ),
            Agent(
                name="correct_differential",
                func=self._correct_differential,
                capabilities=["correction", "feedback", "llm"],
                description="LLM correction with violation feedback",
            ),
            Agent(
                name="synthesize",
                func=self._synthesize,
                capabilities=["synthesis", "output", "formatting"],
                description="Final output synthesis",
            ),
            Agent(
                name="escalate",
                func=self._escalate,
                capabilities=["escalation", "human_in_loop", "safety"],
                description="Human escalation for unsafe paths",
            ),
        ]
        for agent in agents:
            self.agent_registry.register(agent)

    def _register_nodes(self):
        @self.topology.register("fhir_parse", edges=["ingest"], entry_point=True)
        async def fhir_parse(state: GraphState):
            return await self._fhir_parse(state)

        @self.topology.register("ingest", edges=["retrieve_context"], entry_point=False)
        async def ingest(state: GraphState):
            return await self._ingest(state)

        @self.topology.register("retrieve_context", edges=["extract_symptoms"])
        async def retrieve_context(state: GraphState):
            return await self._retrieve_context(state)

        @self.topology.register("extract_symptoms", edges=["map_to_ontology"])
        async def extract_symptoms(state: GraphState):
            return await self._extract_symptoms(state)

        @self.topology.register("map_to_ontology", edges=["assess_differential"])
        async def map_to_ontology(state: GraphState):
            return await self._map_to_ontology(state)

        @self.topology.register("assess_differential", edges=["verify_safety"])
        async def assess_differential(state: GraphState):
            return await self._assess_differential(state)

        @self.topology.register(
            "verify_safety",
            conditional_router=self._route,
            conditional_targets={
                "correct_differential": "correct_differential",
                "synthesize": "synthesize",
                "escalate": "escalate",
            },
        )
        async def verify_safety(state: GraphState):
            return await self._verify_safety(state)

        @self.topology.register(
            "correct_differential",
            conditional_router=self._route_after_correction,
            conditional_targets={
                "assess_differential": "assess_differential",
                "escalate": "escalate",
            },
        )
        async def correct_differential(state: GraphState):
            return await self._correct_differential(state)

        @self.topology.register("synthesize", edges=["END"])
        async def synthesize(state: GraphState):
            return await self._synthesize(state)

        @self.topology.register("escalate", edges=["END"])
        async def escalate(state: GraphState):
            return self._escalate(state)

        @self.topology.register("dag_modifier", edges=["synthesize"])
        async def dag_modifier(state: GraphState):
            return await self._dag_modify(state)

    def _build_graph(self):
        return self.topology.build(lambda: StateGraph(GraphState))

    @staticmethod
    def _s(state, key, default=None):
        """Access state field whether it's a GraphState or dict."""
        if isinstance(state, dict):
            return state.get(key, default)
        return getattr(state, key, default)

    def _paths_equal(self, path_a: List[Dict], path_b: List[Dict]) -> bool:
        """Check if two paths are semantically identical."""
        if len(path_a) != len(path_b):
            return False
        def normalize(path):
            return sorted(
                [(t.get("head"), t.get("relation"), t.get("tail")) for t in path],
                key=lambda x: (x[0] or "", x[1] or "", x[2] or "")
            )
        return normalize(path_a) == normalize(path_b)

    def _path_is_subset(self, new_path: List[Dict], old_path: List[Dict]) -> bool:
        """Check if new_path offers no new edges compared to old_path."""
        old_edges = {(t.get("head"), t.get("relation"), t.get("tail")) for t in old_path}
        new_edges = {(t.get("head"), t.get("relation"), t.get("tail")) for t in new_path}
        return new_edges.issubset(old_edges)

    async def _fhir_parse(self, state: GraphState):
        ctx = self._s(state, "patient_context", {})
        fhir_data = FHIRParser.extract_from_context(ctx)
        if fhir_data:
            self._log(state, "fhir_parse", f"parsed {len(fhir_data)} FHIR fields")
            merged = dict(ctx)
            merged.update(fhir_data)
            return {**self._log(state, "fhir_parse", f"parsed {len(fhir_data)} FHIR fields"), "patient_context": merged}
        self._log(state, "fhir_parse", "no FHIR data found, falling back to regex")
        return {**self._log(state, "fhir_parse", "no FHIR data found, falling back to regex")}

    def _log(self, state: GraphState, node: str, detail: str = ""):
        entry = {
            "timestamp": time.time(),
            "node": node,
            "iteration": self._s(state, "iteration_count", 0),
            "detail": detail,
        }
        logger.info(f"[{node}] iter={entry['iteration']} {detail}")
        audit = self._s(state, "audit_log", [])
        return {"audit_log": list(audit) + [entry]}

    async def _ingest(self, state: GraphState):
        note = self._s(state, "patient_note", "")
        ctx = dict(self._s(state, "patient_context") or {})

        # Only use regex fallback if FHIR didn't already populate these
        if "age" not in ctx:
            age_match = re.search(r'(\d+)\s*-?\s*year\s*-?\s*old', note, re.IGNORECASE)
            if age_match:
                ctx["age"] = int(age_match.group(1))

        if "gender" not in ctx:
            gender_match = re.search(r'\b(male|female|man|woman)\b', note, re.IGNORECASE)
            if gender_match:
                g = gender_match.group(1).lower()
                ctx["gender"] = "male" if g in ("male", "man") else "female"

        if "medications" not in ctx:
            meds_match = re.findall(
                r'\b(Warfarin|Aspirin|Metformin|Insulin|Furosemide|Lisinopril|Atorvastatin)\b',
                note, re.IGNORECASE,
            )
            if meds_match:
                ctx["medications"] = list(set(m.title() for m in meds_match))

        log_update = self._log(state, "ingest", f"ctx={ctx}")
        return {**log_update, "patient_context": ctx, "iteration_count": 1}

    async def _retrieve_context(self, state: GraphState):
        note = self._s(state, "patient_note", "")
        result = await self.retriever.retrieve(note)
        ctx = result.get("merged_context", "")
        log_update = self._log(state, "retrieve_context", f"vector={len(result['vector_results'])} graph={len(result['graph_results'])}")
        return {**log_update, "retrieval_context": ctx}

    async def _extract_symptoms(self, state: GraphState):
        note = self._s(state, "patient_note", "")
        ctx = dict(self._s(state, "patient_context") or {})
        if self._s(state, "retrieval_context"):
            ctx["retrieval_context"] = self._s(state, "retrieval_context")
        backend = self.router_backend.get_backend(self._s(state, "backend_key"))
        result = await backend.extract_symptoms(note, ctx)
        symptoms = result.get("symptoms", [])
        log_update = self._log(state, "extract_symptoms", f"found {len(symptoms)} symptoms: {symptoms}")
        return {**log_update, "extracted_symptoms": symptoms}

    async def _map_to_ontology(self, state: GraphState):
        symptoms = [s["term"] for s in self._s(state, "extracted_symptoms", [])]
        if not symptoms:
            return {"ontology_mappings": {}}
        mappings = lookup_all_by_symptoms(symptoms)
        total_edges = sum(len(v) for v in mappings.values())
        log_update = self._log(state, "map_to_ontology", f"mapped {len(mappings)} symptoms to {total_edges} ontology edges")
        return {**log_update, "ontology_mappings": mappings}

    async def _assess_differential(self, state: GraphState):
        symptoms = [s["term"] for s in self._s(state, "extracted_symptoms", [])]
        mappings_flat = []
        for symptom_edges in self._s(state, "ontology_mappings", {}).values():
            mappings_flat.extend(symptom_edges)

        result = await self.router_backend.get_backend(self._s(state, "backend_key")).assess_differential(symptoms, mappings_flat, self._s(state, "patient_context"))
        triplets = result.get("triplets", [])
        reasoning = result.get("reasoning", "")

        iteration = self._s(state, "iteration_count", 1)
        history_entry = {
            "iteration": iteration,
            "timestamp": time.time(),
            "node": "assess_differential",
            "reasoning": reasoning,
            "proposed_path_count": len(triplets),
        }
        new_history = list(self._s(state, "reasoning_history", []))
        new_history.append(history_entry)

        log_update = self._log(state, "assess_differential", f"proposed {len(triplets)} differential edges")
        return {**log_update, "proposed_path": triplets, "reasoning_trace": reasoning, "prior_reasoning": reasoning, "reasoning_history": new_history}

    async def _correct_differential(self, state: GraphState):
        violations = (self._s(state, "safety_result") or {}).get("violations", [])
        prior = self._s(state, "reasoning_trace", "")
        prior_path = self._s(state, "proposed_path", [])

        backend = self.router_backend.get_backend(self._s(state, "backend_key"))
        result = await backend.regenerate_with_feedback(
            self._s(state, "patient_note"), violations, prior, self._s(state, "patient_context")
        )
        triplets = result.get("triplets", [])

        # CONVERGENCE CHECK: if corrected path is identical to the rejected one
        # Check against raw LLM output before defense-in-depth filtering
        if prior_path and triplets and self._paths_equal(triplets, prior_path):
            return {
                "status": "escalated",
                "final_output": "Escalated to human review: correction produced identical pathway to previously rejected version.",
                "reasoning_trace": "Convergence failure: LLM could not produce a distinct alternative.",
                "reasoning_history": list(self._s(state, "reasoning_history", [])) + [{
                    "iteration": self._s(state, "iteration_count", 1) + 1,
                    "timestamp": time.time(),
                    "node": "correct_differential",
                    "reasoning": "Convergence failure: identical path returned",
                    "convergence_failed": True,
                }],
            }

        if prior_path and triplets and self._path_is_subset(triplets, prior_path):
            return {
                "status": "escalated",
                "final_output": "Escalated to human review: correction produced no new diagnostic edges.",
                "reasoning_trace": "Convergence failure: LLM produced subset of previously rejected path.",
                "reasoning_history": list(self._s(state, "reasoning_history", [])) + [{
                    "iteration": self._s(state, "iteration_count", 1) + 1,
                    "timestamp": time.time(),
                    "node": "correct_differential",
                    "reasoning": "Convergence failure: subset path returned",
                    "convergence_failed": True,
                }],
            }

        # Defense-in-depth: explicitly filter any remaining violating triplets
        if violations and triplets:
            violating_heads_tails = set()
            for v in violations:
                t = v.get("triplet", {})
                if t.get("head") and t.get("tail"):
                    violating_heads_tails.add((t["head"], t["tail"]))
                    violating_heads_tails.add((t["tail"], t["head"]))
            triplets = [
                t for t in triplets
                if (t.get("head"), t.get("tail")) not in violating_heads_tails
            ]

        reasoning = result.get("reasoning", "")
        iteration = self._s(state, "iteration_count", 0) + 1

        history_entry = {
            "iteration": iteration,
            "timestamp": time.time(),
            "node": "correct_differential",
            "reasoning": reasoning,
            "proposed_path_count": len(triplets),
            "violations_addressed": len(violations),
        }
        new_history = list(self._s(state, "reasoning_history", []))
        new_history.append(history_entry)

        log_update = self._log(state, "correct_differential", f"corrected: {len(triplets)} edges (attempt {iteration})")
        old_path = self._s(state, "proposed_path", [])
        return {**log_update, "proposed_path": triplets, "reasoning_trace": reasoning, "iteration_count": iteration, "violations": violations, "reasoning_history": new_history, "prior_reasoning_path": old_path}

    async def _verify_safety(self, state: GraphState):
        vresult: VerificationResult = await self.verification.verify(
            self._s(state, "proposed_path", []),
            self._s(state, "patient_context"),
        )

        safety_result = {
            "is_safe": vresult.is_safe,
            "violations": vresult.violations,
            "opa_allowed": vresult.opa_allowed,
            "neo4j_valid": vresult.neo4j_valid,
            "symbolic_valid": vresult.symbolic_valid,
        }

        validation_result = {
            "is_valid": vresult.is_valid,
            "valid_edges": vresult.valid_edges,
            "violations": vresult.violations,
            "total_checked": vresult.total_checked,
            "confidence_decay": vresult.confidence_decay,
            "validation_mode": vresult.validation_mode,
            "fused_confidence": vresult.fused_confidence,
            "decision": vresult.decision,
            "verifier_breakdown": vresult.verifier_breakdown,
        }

        log_update = self._log(state, "verify_safety", f"safe={vresult.is_safe} violations={len(vresult.violations)} mode={vresult.validation_mode} decision={vresult.decision} fused={vresult.fused_confidence}")
        return {**log_update, "safety_result": safety_result, "validation_result": validation_result, "violations": vresult.violations, "validation_mode": vresult.validation_mode, "neural_confidence": vresult.neural_confidence, "neural_active": vresult.neural_active, "decision": vresult.decision, "fused_confidence": vresult.fused_confidence}

    def _route(self, state: GraphState) -> Literal["correct_differential", "synthesize", "escalate"]:
        if not self.enable_neural_policy:
            decision = (self._s(state, "validation_result") or {}).get("decision", "correct")
            iteration = self._s(state, "iteration_count", 1)
            if decision == "valid":
                return "synthesize"
            if decision == "escalate":
                return "escalate"
            if iteration < self.max_iterations:
                return "correct_differential"
            return "escalate"

        state_dict = state.to_dict() if hasattr(state, "to_dict") else dict(state)
        decision = self.neural_policy.predict(state_dict)

        self._pending_decision = {
            "features": self.neural_policy._extract_features(state_dict),
            "predicted": decision.action,
        }

        return decision.action

    def _route_after_correction(self, state: GraphState) -> Literal["assess_differential", "escalate"]:
        if self._s(state, "status") == "escalated":
            return "escalate"
        iteration = self._s(state, "iteration_count", 1)
        if iteration >= self.max_iterations:
            return "escalate"
        return "assess_differential"

    async def _dag_modify(self, state: GraphState):
        if not self.enable_dynamic_dag:
            return {}
        self._log(state, "dag_modifier", "dynamic DAG disabled at runtime, passing through")
        return {**self._log(state, "dag_modifier", "dynamic DAG disabled, passing through")}

    async def _synthesize(self, state: GraphState):
        path = self._s(state, "proposed_path", [])
        reasoning = surface_reasoning_for_clinician(self._s(state, "reasoning_trace", ""), 1500)
        sources = []
        for e in (self._s(state, "validation_result") or {}).get("valid_edges", []):
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
            "patient_context": self._s(state, "patient_context"),
            "ontology_mappings": {
                sym: len(edges)
                for sym, edges in self._s(state, "ontology_mappings", {}).items()
            },
            "retrieval_context": self._s(state, "retrieval_context", ""),
        }
        log_update = self._log(state, "synthesize", f"sources={len(sources)}")
        result = {**log_update, "final_output": json.dumps(output, indent=2), "status": "valid"}

        if self.enable_neural_policy and self._pending_decision:
            self.neural_policy.record_outcome(
                self._pending_decision["features"],
                self._pending_decision["predicted"],
                "synthesize",
                reward=1.0 if self._s(state, "validation_mode") == "full" else 0.5,
            )
            self._pending_decision = None

        return result

    def _escalate(self, state: GraphState):
        if self._s(state, "status") == "escalated":
            return {}
        violations = self._s(state, "violations", []) or (self._s(state, "safety_result") or {}).get("violations", [])
        ic = self._s(state, "iteration_count", 0)
        reason = f"Escalated after {ic} attempt(s). Violations: {len(violations)}"
        log_update = self._log(state, "escalate", reason)
        result = {**log_update, "status": "escalated", "final_output": f"Escalated to human review. {reason} Violations: {json.dumps(violations, indent=2)}"}

        if self.enable_neural_policy and self._pending_decision:
            self.neural_policy.record_outcome(
                self._pending_decision["features"],
                self._pending_decision["predicted"],
                "escalate",
                reward=0.2 if self._s(state, "iteration_count") >= self.max_iterations else -0.5,
            )
            self._pending_decision = None

        return result

    async def run(self, patient_note: str, patient_context: Optional[Dict] = None, backend_key: Optional[str] = None) -> GraphState:
        if not backend_key and self.router:
            routed = await self.router.route_with_context(patient_note, patient_context or {})
            backend_key = routed
        selected_llm = self.router_backend.get_backend(backend_key)
        resolved_key = selected_llm.backend_type
        initial_state = GraphState(
            patient_note=patient_note,
            patient_context=patient_context or {},
            backend_key=resolved_key,
            active_llm_type=resolved_key,
        )
        log_update = self._log(initial_state, "run", f"backend_key={resolved_key}")
        initial_state = initial_state.evolve(**log_update)
        start_time = time.time()
        result = await self.workflow.ainvoke(initial_state, config={"recursion_limit": 20})
        elapsed_ms = (time.time() - start_time) * 1000

        if isinstance(result, dict):
            status = result.get("status", "unknown")
            bk = result.get("backend_key", self.router_backend.default)
        else:
            status = result.status
            bk = result.backend_key

        self.router_backend.record_call(bk, elapsed_ms, status)

        if isinstance(result, dict):
            return GraphState.from_dict(result)
        return result
