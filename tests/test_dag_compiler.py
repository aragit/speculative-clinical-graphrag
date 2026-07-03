from core.dag_compiler import DAGCompiler


def test_compile_plan_returns_structure():
    compiler = DAGCompiler()
    plan = {"steps": [
        {"id": "a", "action": "extract", "parameters": {}, "depends_on": []},
        {"id": "b", "action": "map", "parameters": {}, "depends_on": ["a"]},
        {"id": "c", "action": "assess", "parameters": {}, "depends_on": ["b"]},
    ]}
    dag = compiler.compile_plan(plan)
    assert "nodes" in dag
    assert "edges" in dag
    assert "topological_order" in dag
    assert dag["topological_order"] == ["a", "b", "c"]


def test_compile_plan_empty():
    compiler = DAGCompiler()
    dag = compiler.compile_plan({"steps": []})
    assert dag["is_dag"] is True
    assert dag["topological_order"] == []


def test_validate_dag_valid():
    compiler = DAGCompiler()
    plan = {"steps": [
        {"id": "a", "action": "x", "parameters": {}, "depends_on": []},
        {"id": "b", "action": "y", "parameters": {}, "depends_on": ["a"]},
    ]}
    dag = compiler.compile_plan(plan)
    assert compiler.validate_dag(dag) is True


def test_execute_dag_without_executor():
    compiler = DAGCompiler()
    plan = {"steps": [
        {"id": "a", "action": "extract", "parameters": {"query": "test"}, "depends_on": []},
    ]}
    dag = compiler.compile_plan(plan)
    result = compiler.execute_dag(dag, {})
    assert result["status"] == "completed"
    assert "a" in result["results"]


def test_execute_dag_with_executor():
    compiler = DAGCompiler()
    plan = {"steps": [
        {"id": "s1", "action": "echo", "parameters": {"msg": "hello"}, "depends_on": []},
    ]}
    dag = compiler.compile_plan(plan)

    def executor(action, params, ctx):
        return {"action": action, "output": params.get("msg", ""), "status": "done"}

    result = compiler.execute_dag(dag, {}, node_executor=executor)
    assert result["results"]["s1"]["output"] == "hello"
