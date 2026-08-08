import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any, Callable
from pydantic import BaseModel, Field
from enum import Enum

logger = logging.getLogger(__name__)


class PermissionLevel(str, Enum):
    CLINICIAN = "clinician"
    ADMIN = "admin"
    SYSTEM = "system"
    READONLY = "readonly"


class ToolSchema(BaseModel):
    name: str
    description: str
    input_schema: Dict
    required_permission: PermissionLevel = PermissionLevel.CLINICIAN
    timeout_seconds: float = 10.0
    capabilities: List[str] = Field(default_factory=list)


class ToolResult(BaseModel):
    tool: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    permission_checked: bool = False
    opa_allowed: bool = False


class ToolRegistry:
    """Registry for MCP tools with metadata and capability tags."""

    def __init__(self):
        self._tools: Dict[str, ToolSchema] = {}
        self._handlers: Dict[str, Callable] = {}

    def register(self, schema: ToolSchema, handler: Callable):
        self._tools[schema.name] = schema
        self._handlers[schema.name] = handler
        logger.info(f"MCP tool registered: {schema.name} (perm: {schema.required_permission.value})")

    def unregister(self, name: str):
        if name in self._tools:
            del self._tools[name]
            del self._handlers[name]

    def get(self, name: str) -> Optional[ToolSchema]:
        return self._tools.get(name)

    def get_handler(self, name: str) -> Optional[Callable]:
        return self._handlers.get(name)

    def list_tools(self, permission: Optional[PermissionLevel] = None) -> List[ToolSchema]:
        tools = list(self._tools.values())
        if permission:
            perm_order = {
                PermissionLevel.READONLY: 0,
                PermissionLevel.CLINICIAN: 1,
                PermissionLevel.ADMIN: 2,
                PermissionLevel.SYSTEM: 3,
            }
            caller_level = perm_order.get(permission, 0)
            tools = [
                t for t in tools
                if perm_order.get(t.required_permission, 0) <= caller_level
            ]
        return tools

    def list_by_capability(self, capability: str) -> List[ToolSchema]:
        return [t for t in self._tools.values() if capability in t.capabilities]


class MCPProtocolServer:
    """
    JSON-RPC 2.0 MCP server for tool discovery and execution.
    Spec: https://modelcontextprotocol.io/specification
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        opa_client=None,
        circuit_breaker_factory=None,
    ):
        self.registry = tool_registry
        self.opa = opa_client
        self.cb_factory = circuit_breaker_factory or (lambda name: None)
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def handle_request(self, request: Dict) -> Dict:
        """Handle a single JSON-RPC 2.0 request."""
        method = request.get("method")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "tools/list":
            return self._handle_tools_list(params, req_id)
        elif method == "tools/call":
            return await self._handle_tools_call(params, req_id)
        elif method == "initialize":
            return self._handle_initialize(params, req_id)
        elif method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}
        else:
            return self._error(req_id, -32601, f"Method not found: {method}")

    def _handle_initialize(self, params: Dict, req_id: Any) -> Dict:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": True},
                    "logging": {},
                },
                "serverInfo": {
                    "name": "speculative-clinical-graphrag-mcp",
                    "version": "0.6.1",
                },
            },
        }

    def _handle_tools_list(self, params: Dict, req_id: Any) -> Dict:
        permission_str = params.get("permission", "readonly")
        try:
            perm = PermissionLevel(permission_str)
        except ValueError:
            perm = PermissionLevel.READONLY

        tools = self.registry.list_tools(permission=perm)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "inputSchema": t.input_schema,
                    }
                    for t in tools
                ],
            },
        }

    async def _handle_tools_call(self, params: Dict, req_id: Any) -> Dict:
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        caller_role = params.get("caller_role", "readonly")

        schema = self.registry.get(tool_name)
        if schema is None:
            return self._error(req_id, -32602, f"Tool not found: {tool_name}")

        # Permission check
        try:
            required_perm = schema.required_permission
            perm_order = {
                PermissionLevel.READONLY: 0,
                PermissionLevel.CLINICIAN: 1,
                PermissionLevel.ADMIN: 2,
                PermissionLevel.SYSTEM: 3,
            }
            if perm_order.get(PermissionLevel(caller_role), 0) < perm_order.get(required_perm, 0):
                return self._error(req_id, -32001, f"Permission denied: {tool_name} requires {required_perm.value}")
        except ValueError:
            return self._error(req_id, -32001, "Invalid caller_role")

        # OPA policy check
        opa_allowed = True
        if self.opa:
            opa_payload = dict(arguments)
            opa_payload["caller_role"] = caller_role
            try:
                opa_result = await self.opa.evaluate_tool_execution(tool_name, opa_payload)
                opa_allowed = opa_result.get("allow", True)
            except Exception as e:
                logger.warning(f"OPA tool eval failed: {e}")
                opa_allowed = False  # fail-closed

        if not opa_allowed:
            return self._error(req_id, -32002, "OPA policy denied tool execution")

        # Execute with circuit breaker
        handler = self.registry.get_handler(tool_name)
        if handler is None:
            return self._error(req_id, -32603, f"Handler not found for: {tool_name}")

        cb = self.cb_factory(tool_name)
        start = time.time()
        try:
            if cb:
                result_data = await cb.call(handler, arguments)
            else:
                if asyncio.iscoroutinefunction(handler):
                    result_data = await handler(arguments)
                else:
                    result_data = handler(arguments)

            elapsed_ms = (time.time() - start) * 1000
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result_data, indent=2),
                        }
                    ],
                    "isError": False,
                    "execution_time_ms": round(elapsed_ms, 2),
                },
            }
        except Exception as e:
            elapsed_ms = (time.time() - start) * 1000
            logger.exception(f"Tool execution failed: {tool_name}")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error: {str(e)}",
                        }
                    ],
                    "isError": True,
                    "execution_time_ms": round(elapsed_ms, 2),
                },
            }

    def _error(self, req_id: Any, code: int, message: str) -> Dict:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        }


class MCPControlPlane:
    """
    High-level control plane integrating MCP with existing agent registry.
    Agents discover and request tools through this plane.
    """

    def __init__(self, tool_registry: ToolRegistry, mcp_server: MCPProtocolServer, agent_registry=None):
        self.registry = tool_registry
        self.server = mcp_server
        self.agent_registry = agent_registry

    async def agent_request_tool(self, agent_name: str, tool_name: str, arguments: Dict) -> ToolResult:
        """Agent requests tool execution via control plane."""
        # Check agent health
        if self.agent_registry:
            agent = self.agent_registry.get(agent_name)
            if agent is None:
                return ToolResult(tool=tool_name, success=False, error=f"Agent {agent_name} not found")
            if agent.health != "healthy":
                return ToolResult(tool=tool_name, success=False, error=f"Agent {agent_name} is {agent.health}")

        # Route through MCP server
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
                "caller_role": "system",  # Agents run as system role
            },
        }
        response = await self.server._handle_tools_call(request["params"], request["id"])

        if "error" in response:
            return ToolResult(
                tool=tool_name,
                success=False,
                error=response["error"]["message"],
                permission_checked=True,
            )

        result = response["result"]
        return ToolResult(
            tool=tool_name,
            success=not result.get("isError", False),
            data=result["content"][0]["text"] if result.get("content") else None,
            execution_time_ms=result.get("execution_time_ms", 0),
            permission_checked=True,
            opa_allowed=True,
        )
