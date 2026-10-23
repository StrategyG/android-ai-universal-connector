"""Provider-neutral adapter contracts for the universal connector.

This module defines discovery and routing metadata only. It does not implement
OAuth, store tokens, or execute external platform actions. Concrete adapters
must perform provider-specific authorization and API calls in separate modules.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

_CONNECTOR_ID = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
_ACTION = re.compile(r"^[a-z][a-z0-9_-]{1,63}\.[a-z][a-z0-9_.-]{0,127}$")
_AUTH_MODES = frozenset({"oauth2", "device_permissions", "none"})


@dataclass(frozen=True)
class ConnectorManifest:
    """Non-secret description of one provider adapter and its capabilities."""

    connector_id: str
    display_name: str
    auth_mode: str
    required_scopes: tuple[str, ...]
    supported_actions: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.connector_id, str) or not _CONNECTOR_ID.fullmatch(self.connector_id):
            raise ValueError("connector_id_invalid")
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise ValueError("display_name_required")
        if self.auth_mode not in _AUTH_MODES:
            raise ValueError("auth_mode_unsupported")
        if any(not isinstance(scope, str) or not scope.strip() for scope in self.required_scopes):
            raise ValueError("scope_invalid")
        if len(set(self.required_scopes)) != len(self.required_scopes):
            raise ValueError("duplicate_scope")
        if len(set(self.supported_actions)) != len(self.supported_actions):
            raise ValueError("duplicate_action")
        for action in self.supported_actions:
            if not isinstance(action, str) or not _ACTION.fullmatch(action):
                raise ValueError("action_invalid")
            if action.split(".", 1)[0] != self.connector_id:
                raise ValueError("action_connector_prefix_mismatch")


@runtime_checkable
class ConnectorAdapter(Protocol):
    """Contract implemented by a provider adapter.

    Implementations must fail closed when authorization is absent or expired.
    They must not accept credentials from model-generated tool arguments.
    """

    @property
    def manifest(self) -> ConnectorManifest:
        """Return non-secret adapter metadata."""

    def status(self, *, subject: str | None = None) -> dict[str, Any]:
        """Return sanitized connection status; never return tokens or secrets."""


class AdapterRegistry:
    """Explicit allowlist of adapters, with deterministic action routing."""

    def __init__(self) -> None:
        self._adapters: dict[str, ConnectorAdapter] = {}

    def register(self, adapter: ConnectorAdapter) -> None:
        manifest = adapter.manifest
        if not isinstance(manifest, ConnectorManifest):
            raise TypeError("adapter_manifest_required")
        if manifest.connector_id in self._adapters:
            raise ValueError("connector_id_already_registered")
        self._adapters[manifest.connector_id] = adapter

    def get(self, connector_id: str) -> ConnectorAdapter | None:
        return self._adapters.get(connector_id)

    def list_manifests(self) -> list[dict[str, Any]]:
        """Return safe, JSON-compatible metadata; no credentials are included."""
        return [
            {
                "id": adapter.manifest.connector_id,
                "name": adapter.manifest.display_name,
                "auth_mode": adapter.manifest.auth_mode,
                "required_scopes": list(adapter.manifest.required_scopes),
                "supported_actions": list(adapter.manifest.supported_actions),
            }
            for adapter in self._adapters.values()
        ]

    def resolve_action(self, action: str) -> ConnectorAdapter | None:
        """Resolve only explicitly registered actions; unknown actions fail closed."""
        if not isinstance(action, str) or "." not in action:
            return None
        connector_id = action.split(".", 1)[0]
        adapter = self._adapters.get(connector_id)
        if adapter is None or action not in adapter.manifest.supported_actions:
            return None
        return adapter

    def __len__(self) -> int:
        return len(self._adapters)
