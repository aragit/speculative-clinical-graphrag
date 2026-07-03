from typing import Dict, List, Callable, Optional
from collections import deque, defaultdict
import logging

logger = logging.getLogger(__name__)


class DAGCompiler:
    def compile_plan(self, llm_plan: Dict) -> Dict:
        steps = llm_plan.get("steps", [])
        nodes = [{"id": s["id"], "action": s["action"], "params": s.get("parameters", {})} for s in steps]
        edges = []
        for s in steps:
            for dep in s.get("depends_on", []):
                edges.append({"from": dep, "to": s["id"]})
        topo = self._topological_sort(nodes, edges)
        return {"nodes": nodes, "edges": edges, "is_dag": len(topo) == len(nodes), "topological_order": topo}

    def validate_dag(self, dag: Dict) -> bool:
        return dag.get("is_dag", False)

    def _topological_sort(self, nodes: List[Dict], edges: List[Dict]) -> List[str]:
        in_degree = {n["id"]: 0 for n in nodes}
        adj = defaultdict(list)
        for e in edges:
            adj[e["from"]].append(e["to"])
            in_degree[e["to"]] = in_degree.get(e["to"], 0) + 1
        q = deque([nid for nid, deg in in_degree.items() if deg == 0])
        topo = []
        while q:
            node = q.popleft()
            topo.append(node)
            for nei in adj[node]:
                in_degree[nei] -= 1
                if in_degree[nei] == 0:
                    q.append(nei)
        return topo

    def execute_dag(self, dag: Dict, context: Dict, node_executor: Optional[Callable] = None) -> Dict:
        order = dag.get("topological_order", dag.get("nodes", []))
        nodes_map = {n["id"]: n for n in dag.get("nodes", [])}
        results = {}

        for node_id in order:
            node = nodes_map.get(node_id)
            if not node:
                continue
            action = node["action"]
            params = node["params"]

            if node_executor:
                result = node_executor(action, params, context)
            else:
                result = {"action": action, "params": params, "status": "executed"}

            results[node_id] = result
            context[f"dag_result_{node_id}"] = result

        return {
            "results": results,
            "status": "completed",
            "execution_order": order,
        }
