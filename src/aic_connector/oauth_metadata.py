"""OAuth protected-resource metadata and challenge helpers for remote MCP clients.

The authorization server itself remains an external, standards-compliant OAuth
2.1/OIDC provider. This module advertises resource metadata; it does not issue
tokens or pretend that a provider login has been configured.
"""
from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from starlette.requests import Request
from starlette.responses import JSONResponse


def protected_resource_metadata(config) -> dict[str, object]:
    """Return RFC 9728 metadata for the configured MCP resource."""
    resource = config.resource_url
    parsed = urlsplit(resource)
    # RFC 9728 appends a resource path to the well-known path when the resource
    # identifier itself contains a path (e.g. /mcp).
    well_known_path = "/.well-known/oauth-protected-resource"
    resource_path = parsed.path.rstrip("/")
    metadata_path = well_known_path + resource_path
    metadata_url = urlunsplit((parsed.scheme, parsed.netloc, metadata_path, "", ""))
    return {
        "resource": resource,
        "authorization_servers": [config.issuer_url],
        "scopes_supported": list(config.required_scopes),
    }


def register_oauth_metadata_routes(server, config) -> None:
    """Register the path-specific RFC 9728 endpoint and a compatibility alias."""
    payload = protected_resource_metadata(config)

    @server.custom_route("/.well-known/oauth-protected-resource", methods=["GET"])
    async def protected_resource_root(_: Request) -> JSONResponse:
        return JSONResponse(payload, headers={"Cache-Control": "public, max-age=300"})

    @server.custom_route("/.well-known/oauth-protected-resource/mcp", methods=["GET"])
    async def protected_resource_mcp(_: Request) -> JSONResponse:
        return JSONResponse(payload, headers={"Cache-Control": "public, max-age=300"})


class OAuthChallengeMiddleware:
    """Attach an RFC 9728 discovery challenge to unauthenticated MCP requests."""

    def __init__(self, app, config) -> None:
        self.app = app
        parsed = urlsplit(config.resource_url)
        resource_path = parsed.path.rstrip("/")
        self.metadata_url = urlunsplit(
            (parsed.scheme, parsed.netloc,
             "/.well-known/oauth-protected-resource" + resource_path, "", "")
        )
        self.scopes = " ".join(config.required_scopes)

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_challenge(message):
            if message["type"] == "http.response.start" and message.get("status") == 401:
                headers = list(message.get("headers", []))
                if not any(k.lower() == b"www-authenticate" for k, _ in headers):
                    challenge = (
                        f'Bearer resource_metadata="{self.metadata_url}", '
                        f'scope="{self.scopes}"'
                    ).encode("ascii")
                    headers.append((b"www-authenticate", challenge))
                    message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_challenge)
