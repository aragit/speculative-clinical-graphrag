import pytest
import json
from core.mcp_protocol import ToolRegistry, MCPProtocolServer, PermissionLevel, MCPControlPlane
from core.mcp_tools import register_all_clinical_tools


@pytest.fixture
def mcp_setup():
    registry = ToolRegistry()
    register_all_clinical_tools(registry)
    server = MCPProtocolServer(registry)
    return registry, server


@pytest.mark.asyncio
async def test_mcp_initialize(mcp_setup):
    _, server = mcp_setup
    request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    response = await server.handle_request(request)
    assert response["result"]["protocolVersion"] == "2024-11-05"
    assert "tools" in response["result"]["capabilities"]


@pytest.mark.asyncio
async def test_mcp_tools_list_by_permission(mcp_setup):
    _, server = mcp_setup
    # Clinician should see read tools but NOT admin-only tools
    request = {
        "jsonrpc": "2.0", "id": 1, "method": "tools/list",
        "params": {"permission": "clinician"},
    }
    response = await server.handle_request(request)
    tool_names = [t["name"] for t in response["result"]["tools"]]
    assert "query_ehr" in tool_names
    assert "order_lab" not in tool_names

    # Admin should see all
    request["params"]["permission"] = "admin"
    response = await server.handle_request(request)
    tool_names = [t["name"] for t in response["result"]["tools"]]
    assert "order_lab" in tool_names

    # Readonly should not see admin tools (or clinician tools)
    request["params"]["permission"] = "readonly"
    response = await server.handle_request(request)
    tool_names = [t["name"] for t in response["result"]["tools"]]
    assert "order_lab" not in tool_names


@pytest.mark.asyncio
async def test_mcp_tool_execution_permission_denied(mcp_setup):
    _, server = mcp_setup
    request = {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {
            "name": "order_lab",
            "arguments": {"patient_id": "123", "test_code": "CBC"},
            "caller_role": "clinician",  # Should fail — admin only
        },
    }
    response = await server._handle_tools_call(request["params"], request["id"])
    assert "error" in response
    assert "Permission denied" in response["error"]["message"]


@pytest.mark.asyncio
async def test_mcp_tool_execution_success(mcp_setup):
    _, server = mcp_setup
    request = {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {
            "name": "check_drug_interaction",
            "arguments": {"drug_a": "Warfarin", "drug_b": "Aspirin"},
            "caller_role": "clinician",
        },
    }
    response = await server._handle_tools_call(request["params"], request["id"])
    assert "result" in response
    assert not response["result"]["isError"]
    data = json.loads(response["result"]["content"][0]["text"])
    assert data["interaction_found"]


@pytest.mark.asyncio
async def test_mcp_control_plane_agent_request(mcp_setup):
    registry, server = mcp_setup
    cp = MCPControlPlane(registry, server)
    result = await cp.agent_request_tool(
        agent_name="test_agent",
        tool_name="retrieve_literature",
        arguments={"query": "diabetes management", "max_results": 2},
    )
    assert result.success
    assert result.permission_checked


@pytest.mark.asyncio
async def test_mcp_ping(mcp_setup):
    _, server = mcp_setup
    request = {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}
    response = await server.handle_request(request)
    assert response["result"] == {}


@pytest.mark.asyncio
async def test_mcp_tools_list_by_capability(mcp_setup):
    registry, _ = mcp_setup
    read_tools = registry.list_by_capability("read")
    tool_names = [t.name for t in read_tools]
    assert "query_ehr" in tool_names
    assert "check_drug_interaction" in tool_names
    assert "order_lab" not in tool_names


@pytest.mark.asyncio
async def test_mcp_tool_not_found(mcp_setup):
    _, server = mcp_setup
    request = {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {
            "name": "nonexistent_tool",
            "arguments": {},
            "caller_role": "system",
        },
    }
    response = await server._handle_tools_call(request["params"], request["id"])
    assert "error" in response
    assert "not found" in response["error"]["message"].lower()


@pytest.mark.asyncio
async def test_mcp_tool_execution_admin_only_via_opa(mcp_setup):
    registry, _ = mcp_setup
    schema = registry.get("order_lab")
    assert schema is not None
    assert schema.required_permission == PermissionLevel.ADMIN
    schema_clinician = registry.get("query_ehr")
    assert schema_clinician.required_permission == PermissionLevel.CLINICIAN
