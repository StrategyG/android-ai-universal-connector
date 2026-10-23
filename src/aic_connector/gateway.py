"""Authenticated Streamable HTTP gateway prototype.

This module fails closed unless an OAuth 2.1 resource-server configuration is
provided. It is not production-ready until deployed behind HTTPS and tested with
the actual identity provider and target MCP clients.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx2
from mcp.server import MCPServer
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import JSONResponse

from aic_connector.core import StateStore
from aic_connector.server import register_tools

logger = logging.getLogger(__name__)


def _validated_url(name: str, value: str, *, allow_loopback_http: bool = True) -> str:
    value = value.strip()
    parsed = urlsplit(value)
    if parsed.scheme != "https":
        if not (
            allow_loopback_http
            and parsed.scheme == "http"
            and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        ):
            raise ValueError(f"{name} must use HTTPS (HTTP is allowed only for loopback testing)")
    if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError(f"{name} must be an absolute URL without userinfo or fragment")
    return value


@dataclass(frozen=True)
class GatewayConfig:
    issuer_url: str
    resource_url: str
    introspection_url: str
    client_id: str
    client_secret: str
    required_scopes: tuple[str, ...]
    allowed_origins: tuple[str, ...]
    bind_host: str = "127.0.0.1"
    port: int = 8000

    @classmethod
    def from_env(cls) -> "GatewayConfig":
        required = {
            "AIC_MCP_ISSUER_URL": os.getenv("AIC_MCP_ISSUER_URL", ""),
            "AIC_MCP_RESOURCE_URL": os.getenv("AIC_MCP_RESOURCE_URL", ""),
            "AIC_OAUTH_INTROSPECTION_URL": os.getenv("AIC_OAUTH_INTROSPECTION_URL", ""),
            "AIC_OAUTH_CLIENT_ID": os.getenv("AIC_OAUTH_CLIENT_ID", ""),
            "AIC_OAUTH_CLIENT_SECRET": os.getenv("AIC_OAUTH_CLIENT_SECRET", ""),
        }
        missing = [key for key, value in required.items() if not value.strip()]
        if missing:
            raise ValueError("Missing required gateway environment variables: " + ", ".join(missing))

        issuer_url = _validated_url("AIC_MCP_ISSUER_URL", required["AIC_MCP_ISSUER_URL"])
        resource_url = _validated_url("AIC_MCP_RESOURCE_URL", required["AIC_MCP_RESOURCE_URL"])
        introspection_url = _validated_url(
            "AIC_OAUTH_INTROSPECTION_URL", required["AIC_OAUTH_INTROSPECTION_URL"]
        )
        resource = urlsplit(resource_url)
        if resource.query:
            raise ValueError("AIC_MCP_RESOURCE_URL must not include a query string")
        scopes = tuple(
            scope for scope in os.getenv("AIC_MCP_REQUIRED_SCOPES", "aic:read").split() if scope
        )
        if not scopes:
            raise ValueError("AIC_MCP_REQUIRED_SCOPES must contain at least one scope")
        origins = tuple(
            origin.strip()
            for origin in os.getenv("AIC_MCP_ALLOWED_ORIGINS", "").split(",")
            if origin.strip()
        )
        for origin in origins:
            parsed_origin = urlsplit(origin)
            if parsed_origin.scheme not in {"https", "http"} or not parsed_origin.netloc:
                raise ValueError("AIC_MCP_ALLOWED_ORIGINS must contain absolute origins")
            if parsed_origin.path or parsed_origin.query or parsed_origin.fragment:
                raise ValueError("AIC_MCP_ALLOWED_ORIGINS entries must be origins, not URLs with paths")
            if parsed_origin.scheme != "https" and parsed_origin.hostname not in {
                "127.0.0.1", "localhost", "::1"
            }:
                raise ValueError("Non-loopback allowed origins must use HTTPS")

        try:
            port = int(os.getenv("AIC_MCP_PORT", "8000"))
        except ValueError as exc:
            raise ValueError("AIC_MCP_PORT must be an integer") from exc
        if not 1 <= port <= 65535:
            raise ValueError("AIC_MCP_PORT must be between 1 and 65535")

        return cls(
            issuer_url=issuer_url,
            resource_url=resource_url,
            introspection_url=introspection_url,
            client_id=required["AIC_OAUTH_CLIENT_ID"].strip(),
            client_secret=required["AIC_OAUTH_CLIENT_SECRET"],
            required_scopes=scopes,
            allowed_origins=origins,
            bind_host=os.getenv("AIC_MCP_BIND_HOST", "127.0.0.1").strip(),
            port=port,
        )

    def transport_security(self) -> TransportSecuritySettings:
        parsed = urlsplit(self.resource_url)
        host = parsed.hostname
        if not host:
            raise ValueError("AIC_MCP_RESOURCE_URL has no hostname")
        allowed_hosts = [host]
        if parsed.port:
            allowed_hosts.append(f"{host}:{parsed.port}")
        return TransportSecuritySettings(
            allowed_hosts=allowed_hosts,
            allowed_origins=list(self.allowed_origins),
        )


class IntrospectionTokenVerifier(TokenVerifier):
    """Verify opaque OAuth bearer tokens through a trusted RFC 7662 endpoint.

    The introspection response must include active=true, the configured issuer,
    an audience containing the exact MCP resource URL, an unexpired exp, client_id,
    and scope. Missing or invalid claims fail closed.
    """

    def __init__(self, config: GatewayConfig) -> None:
        self._config = config

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            async with httpx2.AsyncClient(timeout=5.0, follow_redirects=False) as client:
                response = await client.post(
                    self._config.introspection_url,
                    data={"token": token},
                    auth=(self._config.client_id, self._config.client_secret),
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            # Never log token, client secret, or the provider's response body.
            logger.warning("OAuth token introspection failed (%s)", type(exc).__name__)
            return None

        if not isinstance(payload, dict) or payload.get("active") is not True:
            return None
        if payload.get("iss") != self._config.issuer_url:
            return None
        audience = payload.get("aud")
        if not (
            audience == self._config.resource_url
            or isinstance(audience, list) and self._config.resource_url in audience
        ):
            return None
        expiry = payload.get("exp")
        if not isinstance(expiry, (int, float)) or isinstance(expiry, bool) or expiry <= time.time():
            return None

        client_id = payload.get("client_id")
        if not isinstance(client_id, str) or not client_id.strip():
            return None
        raw_scopes = payload.get("scope", "")
        scopes = raw_scopes.split() if isinstance(raw_scopes, str) else []
        subject = payload.get("sub")
        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=scopes,
            resource=self._config.resource_url,
            subject=subject if isinstance(subject, str) else None,
        )


def create_gateway(config: GatewayConfig | None = None) -> MCPServer:
    """Create an authenticated MCP server; configuration is required."""
    cfg = config or GatewayConfig.from_env()
    server = MCPServer(
        "Android AI Universal Connector",
        token_verifier=IntrospectionTokenVerifier(cfg),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(cfg.issuer_url),
            resource_server_url=AnyHttpUrl(cfg.resource_url),
            required_scopes=list(cfg.required_scopes),
            validate_token_resource=True,
        ),
    )
    register_tools(server, StateStore())

    @server.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "aic-connector-gateway"})

    return server


def main() -> None:
    """Run authenticated Streamable HTTP; keep behind a trusted HTTPS proxy."""
    config = GatewayConfig.from_env()
    server = create_gateway(config)
    server.run(
        transport="streamable-http",
        host=config.bind_host,
        port=config.port,
        transport_security=config.transport_security(),
        max_request_body_size=1_048_576,
    )


if __name__ == "__main__":
    main()
