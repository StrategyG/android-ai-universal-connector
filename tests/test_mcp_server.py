"""Protocol-level smoke tests for the MCP server using the official SDK client."""
from __future__ import annotations

import asyncio
import sys
import unittest

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from aic_connector.server import mcp


EXPECTED_TOOLS = {
    "connector.list",
    "connector.status",
    "connector.permissions",
    "task.create",
    "task.status",
    "task.cancel",
    "approval.request",
    "audit.query",
}


class MCPDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_tools_are_discoverable_and_callable_in_process(self) -> None:
        async with Client(mcp) as client:
            response = await client.list_tools()
            names = {tool.name for tool in response.tools}
            self.assertTrue(EXPECTED_TOOLS.issubset(names))

            result = await client.call_tool("connector.list", {})
            self.assertFalse(result.is_error)
            self.assertIsNotNone(result.structured_content)
            self.assertIn("connectors", result.structured_content)

    async def test_stdio_transport_starts_and_discovers_tools(self) -> None:
        async def probe() -> None:
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "aic_connector.server"],
            )
            async with Client(params) as client:
                response = await client.list_tools()
                names = {tool.name for tool in response.tools}
                self.assertTrue(EXPECTED_TOOLS.issubset(names))

        await asyncio.wait_for(probe(), timeout=15)


if __name__ == "__main__":
    unittest.main()
