"""Tests for gateway configuration and OAuth introspection verification."""
from __future__ import annotations

import os
import time
import unittest
from unittest.mock import patch

from aic_connector.gateway import (
    GatewayConfig,
    IntrospectionTokenVerifier,
    UserScopedStores,
)


def valid_config() -> GatewayConfig:
    return GatewayConfig(
        issuer_url="https://identity.example.test/",
        resource_url="https://mcp.example.test/mcp",
        introspection_url="https://identity.example.test/introspect",
        client_id="aic-resource-server",
        client_secret="test-only-secret",
        required_scopes=("aic:read",),
        allowed_origins=(),
    )


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return _FakeResponse(self.payload)


class GatewayConfigTests(unittest.TestCase):
    def test_missing_environment_is_rejected(self) -> None:
        names = (
            "AIC_MCP_ISSUER_URL",
            "AIC_MCP_RESOURCE_URL",
            "AIC_OAUTH_INTROSPECTION_URL",
            "AIC_OAUTH_CLIENT_ID",
            "AIC_OAUTH_CLIENT_SECRET",
        )
        with patch.dict(os.environ, {name: "" for name in names}, clear=False):
            with self.assertRaisesRegex(ValueError, "Missing required gateway"):
                GatewayConfig.from_env()

    def test_public_http_resource_is_rejected(self) -> None:
        from aic_connector.gateway import _validated_url

        with self.assertRaisesRegex(ValueError, "must use HTTPS"):
            _validated_url("resource", "http://mcp.example.test/mcp")


class IntrospectionVerifierTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_active_token_is_accepted(self) -> None:
        config = valid_config()
        payload = {
            "active": True,
            "iss": config.issuer_url,
            "aud": config.resource_url,
            "exp": time.time() + 60,
            "client_id": "ai-client",
            "sub": "user-123",
            "scope": "aic:read",
        }
        fake = _FakeClient(payload)
        with patch("aic_connector.gateway.httpx2.AsyncClient", return_value=fake):
            result = await IntrospectionTokenVerifier(config).verify_token("opaque-test-token")
        self.assertIsNotNone(result)
        self.assertEqual(result.client_id, "ai-client")
        self.assertEqual(result.scopes, ["aic:read"])
        self.assertEqual(result.resource, config.resource_url)
        self.assertEqual(result.subject, "user-123")

    async def test_inactive_token_is_rejected(self) -> None:
        config = valid_config()
        fake = _FakeClient({"active": False})
        with patch("aic_connector.gateway.httpx2.AsyncClient", return_value=fake):
            result = await IntrospectionTokenVerifier(config).verify_token("opaque-test-token")
        self.assertIsNone(result)

    async def test_wrong_audience_expiry_or_subject_is_rejected(self) -> None:
        config = valid_config()
        base = {
            "active": True,
            "iss": config.issuer_url,
            "aud": config.resource_url,
            "exp": time.time() + 60,
            "client_id": "ai-client",
            "sub": "user-123",
            "scope": "aic:read",
        }
        bad_payloads = []
        for changes in (
            {"aud": "https://other.example.test/mcp"},
            {"exp": time.time() - 60},
            {"sub": ""},
        ):
            bad_payloads.append({**base, **changes})
        for payload in bad_payloads:
            fake = _FakeClient(payload)
            with patch("aic_connector.gateway.httpx2.AsyncClient", return_value=fake):
                result = await IntrospectionTokenVerifier(config).verify_token("opaque-test-token")
            self.assertIsNone(result)

    def test_user_stores_are_isolated_by_subject(self) -> None:
        stores = UserScopedStores(max_users=2)
        first = stores.for_subject("user-one")
        second = stores.for_subject("user-two")
        self.assertIsNot(first, second)
        self.assertIs(first, stores.for_subject("user-one"))
        with self.assertRaisesRegex(PermissionError, "capacity"):
            stores.for_subject("user-three")


if __name__ == "__main__":
    unittest.main()
