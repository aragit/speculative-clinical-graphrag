from typing import TypedDict, List, Dict, Literal
from langgraph.graph import StateGraph, END
from core.llm_backend import LLMBackend
from core.verification_layer import Neo4jVerifier


class GraphState(TypedDict):
    patient_note: str
    proposed_path: List[Dict]
    validation_result: Dict
    iteration_count: int
    final_output: str
    status: Literal["valid", "corrected", "escalated"]


class SpeculativeGraphRAG:
    def __init__(self, llm: LLMBackend, verifier: Neo4jVerifier, max_iterations: int = 3):
        self.llm = llm
        self.verifier = verifier
        self.max_iterations = max_iterations
        self.workflow = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(GraphState)

        workflow.add_node("speculate", self._speculate)
        workflow.add_node("verify", self._verify)
        workflow.add_node("correct", self._correct)
        workflow.add_node("finalize", self._finalize)
        workflow.add_node("escalate", self._escalate)

        workflow.set_entry_point("speculate")
        workflow.add_edge("speculate", "verify")
        workflow.add_conditional_edges(
            "verify",
            self._route,
            {
                "valid": "finalize",
                "correct": "correct",
                "escalate": "escalate",
            },
        )
        workflow.add_edge("correct", "verify")
        workflow.add_edge("finalize", END)
        workflow.add_edge("escalate", END)

        return workflow.compile()

    def _speculate(self, state: GraphState):
        path = self.llm.generate_path(state["patient_note"])
        return {
            "proposed_path": path,
            "iteration_count": state.get("iteration_count", 0) + 1,
        }

    def _verify(self, state: GraphState):
        result = self.verifier.validate(state["proposed_path"])
        return {"validation_result": result}

    def _route(self, state: GraphState) -> Literal["valid", "correct", "escalate"]:
        if state["validation_result"]["is_valid"]:
            return "valid"
        if state["iteration_count"] >= self.max_iterations:
            return "escalate"
        return "correct"

    def _correct(self, state: GraphState):
        corrected = self.llm.regenerate_with_feedback(
            state["patient_note"],
            state["validation_result"]["violations"],
        )
        return {
            "proposed_path": corrected,
            "iteration_count": state["iteration_count"] + 1,
        }

    def _finalize(self, state: GraphState):
        return {
            "final_output": f"Validated path: {state['proposed_path']}",
            "status": "valid",
        }

    def _escalate(self, state: GraphState):
        return {
            "final_output": f"Escalated to human review after {state['iteration_count']} attempts.",
            "status": "escalated",
        }

    def run(self, patient_note: str):
        initial_state: GraphState = {
            "patient_note": patient_note,
            "proposed_path": [],
            "validation_result": {},
            "iteration_count": 0,
            "final_output": "",
            "status": "valid",
        }
        return self.workflow.invoke(
            initial_state, 
            config={"recursion_limit": 10}
        )
