"""MCP stdio server and shared P0 tool registration."""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from mcp.server import MCPServer

from aic_connector.core import StateStore

_MAX_PAYLOAD_CHARS = 16_384
StoreProvider = Callable[[], StateStore]


def register_tools(server: MCPServer, store: StateStore | StoreProvider) -> None:
    """Register P0 tools using either a fixed store or a request-scoped store provider."""

    def current_store() -> StateStore:
        return store() if callable(store) else store

    @server.tool(name="connector.list")
    def connector_list() -> dict[str, Any]:
        """List registered connectors and their verified configuration status."""
        return {"connectors": current_store().list_connectors()}

    @server.tool(name="connector.status")
    def connector_status(connector_id: str = "") -> dict[str, Any]:
        """Read the status of one connector, or all connectors when the ID is empty."""
        return current_store().connector_status(connector_id.strip() or None)

    @server.tool(name="connector.permissions")
    def connector_permissions(connector_id: str = "") -> dict[str, Any]:
        """List required scopes and current setup status without exposing credentials."""
        return current_store().connector_permissions(connector_id.strip() or None)

    @server.tool(name="task.create")
    def task_create(action: str, target: str, payload_json: str = "{}") -> dict[str, Any]:
        """Create a plan only; this tool never executes a platform action."""
        if len(payload_json) > _MAX_PAYLOAD_CHARS:
            return {"created": False, "decision": "DENY", "reason": "payload_too_large"}
        try:
            payload = json.loads(payload_json)
        except (TypeError, json.JSONDecodeError, RecursionError):
            return {"created": False, "decision": "DENY", "reason": "payload_json_invalid"}
        if not isinstance(payload, dict):
            return {"created": False, "decision": "DENY", "reason": "payload_must_be_object"}
        try:
            return current_store().create_task(action, target, payload)
        except (TypeError, ValueError) as exc:
            return {"created": False, "decision": "DENY", "reason": str(exc)}

    @server.tool(name="task.status")
    def task_status(task_id: str) -> dict[str, Any]:
        """Read task state; P0 tasks are plans and are not executed externally."""
        return current_store().get_task(task_id)

    @server.tool(name="task.cancel")
    def task_cancel(task_id: str) -> dict[str, Any]:
        """Cancel a draft task and any associated pending approval request."""
        return current_store().cancel_task(task_id)

    @server.tool(name="approval.request")
    def approval_request(task_id: str) -> dict[str, Any]:
        """Queue a human-review request for a sensitive task; does not approve or execute it."""
        return current_store().request_approval(task_id)

    @server.tool(name="audit.query")
    def audit_query(limit: int = 50, event_type: str = "") -> dict[str, Any]:
        """Query recent sanitized audit events. Limits are restricted to 1-100 records."""
        try:
            return current_store().query_audit(limit, event_type.strip() or None)
        except ValueError as exc:
            return {"events": [], "count": 0, "error": str(exc)}


mcp = MCPServer("Android AI Universal Connector")
_store = StateStore()
register_tools(mcp, _store)


def main() -> None:
    """Run the local MCP stdio server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
