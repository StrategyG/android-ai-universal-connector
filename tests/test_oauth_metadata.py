"""Tests for MCP OAuth protected-resource discovery and challenges."""
from __future__ import annotations

import unittest

from starlette.testclient import TestClient

from aic_connector.gateway import GatewayConfig, create_gateway_app
from aic_connector.oauth_metadata import protected_resource_metadata


def valid_config() -> GatewayConfig:
    return GatewayConfig(
        issuer_url="https://identity.example.test/",
        resource_url="https://mcp.example.test/mcp",
        introspection_url="https://identity.example.test/introspect",
        client_id="aic-resource-server",
        client_secret="test-only-secret",
        required_scopes=("aic:read", "aic:tools"),
        allowed_origins=(),
    )


class ProtectedResourceMetadataTests(unittest.TestCase):
    def test_metadata_uses_exact_resource_and_issuer(self) -> None:
        payload = protected_resource_metadata(valid_config())
        self.assertEqual(payload["resource"], "https://mcp.example.test/mcp")
        self.assertEqual(payload["authorization_servers"], ["https://identity.example.test/"])
        self.assertEqual(payload["scopes_supported"], ["aic:read", "aic:tools"])

    def test_metadata_endpoint_is_public_and_cacheable(self) -> None:
        with TestClient(create_gateway_app(valid_config()), base_url="https://mcp.example.test") as client:
            response = client.get("/.well-known/oauth-protected-resource/mcp")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["resource"], "https://mcp.example.test/mcp")
        # The MCP/HTTP stack may apply its own cache policy; assert cacheability
        # rather than pinning a specific max-age value.
        self.assertIn("max-age=", response.headers["cache-control"])

    def test_root_metadata_compatibility_alias(self) -> None:
        with TestClient(create_gateway_app(valid_config()), base_url="https://mcp.example.test") as client:
            response = client.get("/.well-known/oauth-protected-resource")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["authorization_servers"], ["https://identity.example.test/"])

    def test_unauthenticated_mcp_request_has_discovery_challenge(self) -> None:
        with TestClient(create_gateway_app(valid_config()), base_url="https://mcp.example.test") as client:
            response = client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            )
        self.assertEqual(response.status_code, 401)
        challenge = response.headers.get("www-authenticate", "")
        # The gateway's token middleware may already set WWW-Authenticate;
        # the discovery middleware must preserve that challenge while ensuring
        # the protected-resource metadata URL is advertised.
        self.assertIn("resource_metadata=", challenge)
        self.assertIn("https://mcp.example.test/.well-known/oauth-protected-resource/mcp", challenge)


if __name__ == "__main__":
    unittest.main()
