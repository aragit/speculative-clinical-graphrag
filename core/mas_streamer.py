import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional

from schemas.mas_events import MASEvent

logger = logging.getLogger(__name__)


def _make_event(event_type: str, node_id: str, payload: Dict[str, Any]) -> MASEvent:
    return MASEvent(event_type=event_type, node_id=node_id, payload=payload)


NODE_LABELS = {
    "supervisor": "Supervisor Agent",
    "clinical_extractor": "Clinical Extraction Agent",
    "ontology_traverser": "Ontology Traversal Agent",
    "opa_verifier": "Policy Governance Agent",
    "synthesizer": "Synthesis Agent",
}


class MASStreamer:
    """Wraps a SpeculativeGraphRAG workflow to emit structured SSE events
    as each logical agent node executes.

    Maps the 5 MAS agents to the underlying 9-node SpeculativeGraphRAG pipeline:
      clinical_extractor  → _ingest + _retrieve_context + _extract_symptoms + _map_to_ontology
      ontology_traverser  → _assess_differential
      opa_verifier        → _verify_safety
      synthesizer         → _synthesize | _escalate
    """

    def __init__(self, workflow):
        self.workflow = workflow

    async def stream(
        self,
        patient_note: str,
        patient_context: Optional[Dict] = None,
    ) -> AsyncGenerator[MASEvent, None]:
        state = {
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
            "backend_key": "",
            "violations": [],
            "prior_reasoning": "",
        }

        # ── Supervisor entry ──
        yield _make_event("NODE_START", "supervisor", {
            "node_label": NODE_LABELS["supervisor"],
            "detail": f"Received patient note ({len(patient_note)} chars). Routing to specialized agents.",
        })
        yield _make_event("REACT_TRACE", "supervisor", {
            "agent_name": "Supervisor Agent",
            "thought": (
                f"Input received ({len(patient_note)} chars). "
                "Routing to Clinical Extraction Agent for entity extraction."
            ),
            "action": "delegate",
            "action_input": {"target": "clinical_extractor"},
        })

        # ── Clinical Extraction Agent ──
        yield _make_event("NODE_START", "clinical_extractor", {
            "node_label": NODE_LABELS["clinical_extractor"],
            "detail": "Extracting clinical entities from patient note...",
        })
        yield _make_event("REACT_TRACE", "clinical_extractor", {
            "agent_name": "Clinical Extraction Agent",
            "thought": (
                "Parsing patient note for demographics, medications, and symptoms. "
                "Running ingest + retrieve_context + extract_symptoms + map_to_ontology."
            ),
            "action": "ingest_and_extract",
            "action_input": {"patient_note_preview": patient_note[:200]},
        })

        # Step 1: ingest
        try:
            result = await self.workflow._ingest(state)
            state.update(result)
        except Exception as e:
            logger.warning(f"_ingest failed: {e}")

        # Step 2: retrieve_context
        try:
            result = await self.workflow._retrieve_context(state)
            state.update(result)
        except Exception as e:
            logger.warning(f"_retrieve_context failed: {e}")

        # Step 3: extract_symptoms
        try:
            result = await self.workflow._extract_symptoms(state)
            state.update(result)
        except Exception as e:
            logger.warning(f"_extract_symptoms failed: {e}")

        # Step 4: map_to_ontology
        try:
            result = await self.workflow._map_to_ontology(state)
            state.update(result)
        except Exception as e:
            logger.warning(f"_map_to_ontology failed: {e}")

        symptoms = [s.get("term", s) if isinstance(s, dict) else s
                     for s in state.get("extracted_symptoms", [])]
        mappings = state.get("ontology_mappings", {})

        yield _make_event("REACT_TRACE", "clinical_extractor", {
            "agent_name": "Clinical Extraction Agent",
            "thought": "Entity extraction complete.",
            "observation": f"Extracted {len(symptoms)} symptoms: {symptoms}. Mapped to {len(mappings)} ontology groups.",
        })
        yield _make_event("STATE_MUTATION", "clinical_extractor", {
            "changed_keys": ["patient_context", "retrieval_context", "extracted_symptoms", "ontology_mappings"],
            "state_snapshot": {
                "patient_context": state.get("patient_context", {}),
                "extracted_symptoms": symptoms,
                "ontology_mapping_count": len(mappings),
            },
        })
        yield _make_event("NODE_END", "clinical_extractor", {
            "node_label": NODE_LABELS["clinical_extractor"],
            "detail": f"Extracted {len(symptoms)} symptoms, {len(mappings)} ontology mappings.",
        })

        # ── Ontology Traversal Agent ──
        yield _make_event("NODE_START", "ontology_traverser", {
            "node_label": NODE_LABELS["ontology_traverser"],
            "detail": "Assessing differential diagnosis pathways...",
        })
        yield _make_event("REACT_TRACE", "ontology_traverser", {
            "agent_name": "Ontology Traversal Agent",
            "thought": (
                f"Running LLM differential assessment over {len(symptoms)} symptoms "
                f"and {sum(len(v) for v in mappings.values())} ontology edges."
            ),
            "action": "assess_differential",
            "action_input": {"symptoms": symptoms},
        })

        try:
            result = await self.workflow._assess_differential(state)
            state.update(result)
        except Exception as e:
            logger.warning(f"_assess_differential failed: {e}")
            state["proposed_path"] = []
            state["reasoning_trace"] = str(e)

        triplets = state.get("proposed_path", [])
        yield _make_event("REACT_TRACE", "ontology_traverser", {
            "agent_name": "Ontology Traversal Agent",
            "thought": "Differential assessment complete.",
            "observation": f"Proposed {len(triplets)} diagnostic triplets for verification.",
        })
        yield _make_event("STATE_MUTATION", "ontology_traverser", {
            "changed_keys": ["proposed_path", "reasoning_trace"],
            "state_snapshot": {
                "proposed_path_count": len(triplets),
                "reasoning_preview": str(state.get("reasoning_trace", ""))[:300],
            },
        })
        yield _make_event("NODE_END", "ontology_traverser", {
            "node_label": NODE_LABELS["ontology_traverser"],
            "detail": f"Proposed {len(triplets)} diagnostic triplets.",
        })

        # ── Policy Governance Agent (may loop for corrections) ──
        max_iter = self.workflow.max_iterations
        for iteration in range(1, max_iter + 1):
            state["iteration_count"] = iteration

            yield _make_event("NODE_START", "opa_verifier", {
                "node_label": NODE_LABELS["opa_verifier"],
                "detail": f"Safety verification pass {iteration}/{max_iter}...",
            })
            yield _make_event("REACT_TRACE", "opa_verifier", {
                "agent_name": "Policy Governance Agent",
                "thought": (
                    f"Pass {iteration}: Running 3-layer safety gate — "
                    "Neo4j taxonomy + Symbolic drug rules + OPA Rego policy."
                ),
                "action": "multi_layer_verify",
                "action_input": {"path_length": len(triplets)},
            })

            try:
                result = await self.workflow._verify_safety(state)
                state.update(result)
            except Exception as e:
                logger.warning(f"_verify_safety failed: {e}")
                state["safety_result"] = {"is_safe": False, "violations": [{"reason": str(e)}]}
                state["validation_result"] = {"is_valid": False, "violations": []}

            safety = state.get("safety_result", {})
            is_safe = safety.get("is_safe", False)
            violations = safety.get("violations", [])

            yield _make_event("GOVERNANCE_CHECK", "opa_verifier", {
                "policy_name": "multi_layer_clinical_safety",
                "passed": is_safe,
                "violations": [{"reason": v.get("reason", str(v))} for v in violations],
                "details": {
                    "iteration": iteration,
                    "neo4j_valid": safety.get("neo4j_valid", False),
                    "symbolic_valid": safety.get("symbolic_valid", False),
                    "opa_allowed": safety.get("opa_allowed", True),
                },
            })
            yield _make_event("REACT_TRACE", "opa_verifier", {
                "agent_name": "Policy Governance Agent",
                "thought": f"Pass {iteration} result: {'SAFE' if is_safe else 'BLOCKED'} ({len(violations)} violations).",
                "observation": f"{'No violations.' if not violations else violations[0].get('reason', str(violations[0]))}",
            })
            yield _make_event("STATE_MUTATION", "opa_verifier", {
                "changed_keys": ["safety_result", "validation_result", "violations", "status"],
                "state_snapshot": {
                    "is_safe": is_safe,
                    "violation_count": len(violations),
                    "iteration": iteration,
                },
            })
            yield _make_event("NODE_END", "opa_verifier", {
                "node_label": NODE_LABELS["opa_verifier"],
                "detail": f"Pass {iteration}: {'SAFE' if is_safe else 'BLOCKED'}.",
            })

            if is_safe:
                break

            if iteration < max_iter:
                # Correct and loop
                yield _make_event("NODE_START", "ontology_traverser", {
                    "node_label": NODE_LABELS["ontology_traverser"],
                    "detail": f"Correcting differential (attempt {iteration + 1})...",
                })
                yield _make_event("REACT_TRACE", "ontology_traverser", {
                    "agent_name": "Ontology Traversal Agent",
                    "thought": f"Incorrecting with {len(violations)} violation(s) as feedback.",
                    "action": "regenerate_with_feedback",
                    "action_input": {"violations": [v.get("reason", "") for v in violations[:3]]},
                })
                try:
                    result = await self.workflow._correct_differential(state)
                    state.update(result)
                except Exception as e:
                    logger.warning(f"_correct_differential failed: {e}")
                triplets = state.get("proposed_path", [])
                yield _make_event("REACT_TRACE", "ontology_traverser", {
                    "agent_name": "Ontology Traversal Agent",
                    "observation": f"Corrected to {len(triplets)} triplets (attempt {iteration + 1}).",
                })
                yield _make_event("NODE_END", "ontology_traverser", {
                    "node_label": NODE_LABELS["ontology_traverser"],
                    "detail": f"Correction applied ({iteration + 1}/{max_iter}).",
                })

        # ── Synthesis Agent ──
        yield _make_event("NODE_START", "synthesizer", {
            "node_label": NODE_LABELS["synthesizer"],
            "detail": "Synthesizing final clinical output..." if is_safe
                      else "Escalating to human review...",
        })

        if is_safe:
            yield _make_event("REACT_TRACE", "synthesizer", {
                "agent_name": "Synthesis Agent",
                "thought": "All safety gates passed. Generating bounded clinical summary.",
                "action": "synthesize_clinical_summary",
            })
            try:
                result = await self.workflow._synthesize(state)
                state.update(result)
            except Exception as e:
                logger.warning(f"_synthesize failed: {e}")
                state["final_output"] = json.dumps({"error": str(e)})
                state["status"] = "error"

            yield _make_event("FINAL_SYNTHESIS", "synthesizer", {
                "output_type": "synthesis",
                "summary": state.get("final_output", ""),
                "full_output": {"final_output": state.get("final_output", "")},
            })
        else:
            yield _make_event("REACT_TRACE", "synthesizer", {
                "agent_name": "Synthesis Agent",
                "thought": f"Escalating after {max_iter} attempt(s) with {len(violations)} violation(s).",
                "action": "escalate_to_hitl",
            })
            try:
                result = self.workflow._escalate(state)
                state.update(result)
            except Exception as e:
                logger.warning(f"_escalate failed: {e}")
                state["final_output"] = f"Escalation error: {e}"
                state["status"] = "error"

            yield _make_event("FINAL_SYNTHESIS", "synthesizer", {
                "output_type": "escalation",
                "summary": state.get("final_output", ""),
                "full_output": {"final_output": state.get("final_output", "")},
            })

        yield _make_event("STATE_MUTATION", "synthesizer", {
            "changed_keys": ["final_output", "status"],
            "state_snapshot": {
                "status": state.get("status", "unknown"),
                "iteration_count": state.get("iteration_count", 0),
                "final_output_preview": str(state.get("final_output", ""))[:200],
            },
        })
        yield _make_event("NODE_END", "synthesizer", {
            "node_label": NODE_LABELS["synthesizer"],
            "detail": f"Complete. Status: {state.get('status', 'unknown')}.",
        })

        # ── Supervisor exit ──
        yield _make_event("NODE_END", "supervisor", {
            "node_label": NODE_LABELS["supervisor"],
            "detail": "Multi-agent workflow execution complete.",
        })
