"""MCP stdio server for the P0 foundation."""
from __future__ import annotations

import json
from typing import Any

from mcp.server import MCPServer

from aic_connector.core import StateStore

mcp = MCPServer("Android AI Universal Connector")
_store = StateStore()
_MAX_PAYLOAD_CHARS = 16_384


@mcp.tool(name="connector.list")
def connector_list() -> dict[str, Any]:
    """List registered connectors and their verified configuration status."""
    return {"connectors": _store.list_connectors()}


@mcp.tool(name="connector.status")
def connector_status(connector_id: str = "") -> dict[str, Any]:
    """Read the status of one connector, or all connectors when the ID is empty."""
    return _store.connector_status(connector_id.strip() or None)


@mcp.tool(name="connector.permissions")
def connector_permissions(connector_id: str = "") -> dict[str, Any]:
    """List required scopes and current setup status without exposing credentials."""
    return _store.connector_permissions(connector_id.strip() or None)


@mcp.tool(name="task.create")
def task_create(action: str, target: str, payload_json: str = "{}") -> dict[str, Any]:
    """Create a plan only; this tool never executes a platform action."""
    if len(payload_json) > _MAX_PAYLOAD_CHARS:
        return {"created": False, "decision": "DENY", "reason": "payload_too_large"}
    try:
        payload = json.loads(payload_json)
    except (TypeError, json.JSONDecodeError):
        return {"created": False, "decision": "DENY", "reason": "payload_json_invalid"}
    if not isinstance(payload, dict):
        return {"created": False, "decision": "DENY", "reason": "payload_must_be_object"}
    try:
        return _store.create_task(action, target, payload)
    except (TypeError, ValueError) as exc:
        return {"created": False, "decision": "DENY", "reason": str(exc)}


@mcp.tool(name="task.status")
def task_status(task_id: str) -> dict[str, Any]:
    """Read task state; P0 tasks are plans and are not executed externally."""
    return _store.get_task(task_id)


@mcp.tool(name="task.cancel")
def task_cancel(task_id: str) -> dict[str, Any]:
    """Cancel a draft task and any associated pending approval request."""
    return _store.cancel_task(task_id)


@mcp.tool(name="approval.request")
def approval_request(task_id: str) -> dict[str, Any]:
    """Queue a human-review request for a sensitive task; does not approve or execute it."""
    return _store.request_approval(task_id)


@mcp.tool(name="audit.query")
def audit_query(limit: int = 50, event_type: str = "") -> dict[str, Any]:
    """Query recent sanitized audit events. Limits are restricted to 1-100 records."""
    try:
        return _store.query_audit(limit, event_type.strip() or None)
    except ValueError as exc:
        return {"events": [], "count": 0, "error": str(exc)}


def main() -> None:
    """Run the local MCP stdio server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
