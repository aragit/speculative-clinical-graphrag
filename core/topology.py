from typing import Dict, List, Callable, Optional
from dataclasses import dataclass, field


@dataclass
class NodeSpec:
    name: str
    func: Callable
    edges: List[str] = field(default_factory=list)
    conditional_router: Optional[Callable] = None
    conditional_targets: Optional[Dict[str, str]] = None
    entry_point: bool = False


class WorkflowTopology:
    def __init__(self):
        self.nodes: Dict[str, NodeSpec] = {}
        self.entry_point: Optional[str] = None

    def register(
        self,
        name: str,
        edges: List[str] = None,
        conditional_router: Callable = None,
        conditional_targets: Dict[str, str] = None,
        entry_point: bool = False,
    ):
        def decorator(func: Callable) -> Callable:
            spec = NodeSpec(
                name=name,
                func=func,
                edges=edges or [],
                conditional_router=conditional_router,
                conditional_targets=conditional_targets,
                entry_point=entry_point,
            )
            self.nodes[name] = spec
            if entry_point:
                self.entry_point = name
            return func
        return decorator

    def build(self, state_graph_class):
        from langgraph.graph import StateGraph, END

        workflow = state_graph_class()

        for spec in self.nodes.values():
            workflow.add_node(spec.name, spec.func)

        if self.entry_point:
            workflow.set_entry_point(self.entry_point)

        for spec in self.nodes.values():
            for target in spec.edges:
                workflow.add_edge(spec.name, END if target == "END" else target)

            if spec.conditional_router and spec.conditional_targets:
                workflow.add_conditional_edges(
                    spec.name,
                    spec.conditional_router,
                    spec.conditional_targets,
                )

        return workflow.compile()

    def get_node(self, name: str) -> Optional[NodeSpec]:
        return self.nodes.get(name)

    def unregister(self, name: str):
        if name in self.nodes:
            del self.nodes[name]
            if self.entry_point == name:
                self.entry_point = None
