from typing import Dict, Callable
import logging
logger = logging.getLogger(__name__)

class MCPRegistry:
    """Stub: Model Context Protocol tool registry."""
    def __init__(self):
        self._tools: Dict[str, Dict] = {}

    def register_tool(self, name: str, handler: Callable, schema: Dict):
        self._tools[name] = {"handler": handler, "schema": schema}

    async def execute(self, tool_name: str, payload: Dict, idempotency_key: str) -> Dict:
        if tool_name not in self._tools:
            raise ValueError(f"Tool {tool_name} not registered")
        logger.info(f"MCP execute {tool_name} key={idempotency_key}")
        return await self._tools[tool_name]["handler"](payload)
