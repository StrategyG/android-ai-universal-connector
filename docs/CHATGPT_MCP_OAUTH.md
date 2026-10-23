# ChatGPT custom MCP OAuth readiness

## Purpose

This repository is being prepared to connect as a custom remote MCP server in
ChatGPT. The gateway is a **resource server**, not a complete OAuth
authorization server. It exposes RFC 9728 protected-resource metadata and an
OAuth challenge so a compatible client can discover the configured issuer.

## Required deployment shape

- Public HTTPS MCP resource endpoint: `https://YOUR_HOST/mcp`.
- Protected-resource metadata: `https://YOUR_HOST/.well-known/oauth-protected-resource/mcp`.
- Trusted OAuth/OIDC authorization server at `AIC_MCP_ISSUER_URL`.
- Authorization-server discovery metadata at the issuer's supported
  `/.well-known/oauth-authorization-server` or
  `/.well-known/openid-configuration` URL.
- Authorization-code grant with PKCE S256; token endpoint authentication
  compatible with ChatGPT's supported CIMD or DCR registration path.
- Authorization responses include the exact issuer (`iss`) when the server
  advertises RFC 9207 issuer identification.
- Authorization and token requests preserve the `resource` parameter and the
  resulting access token is audience-bound to the exact configured MCP resource.
- Refresh tokens are issued and renewable if persistent connections are needed.

## Environment

Configure these only in the deployment's secret/environment manager:

- `AIC_MCP_ISSUER_URL`: exact issuer string advertised by the authorization
  server (including or excluding a trailing slash exactly as its metadata does).
- `AIC_MCP_RESOURCE_URL`: canonical public MCP resource URL, including `/mcp`.
- `AIC_OAUTH_INTROSPECTION_URL`: trusted provider introspection endpoint.
- `AIC_OAUTH_CLIENT_ID` and `AIC_OAUTH_CLIENT_SECRET`: confidential client
  credentials permitted to introspect tokens.
- `AIC_MCP_REQUIRED_SCOPES`: least-privilege scopes required by the tools.

Never commit or paste secrets into chat or logs. Do not set the issuer to a
Google/Meta/Shopee login URL merely because the account exists; it must be an
OAuth authorization server configured to issue tokens for this MCP resource.
Provider OAuth used *inside* the connector to access Google/Meta/Shopee accounts
is a separate authorization relationship from ChatGPT's OAuth login to this MCP
server.

## What this implementation does and does not do

Implemented in this stage:
- RFC 9728 protected-resource metadata endpoints.
- A 401 `WWW-Authenticate` challenge that points to resource metadata.
- Unit tests for exact resource identity, issuer, scopes, endpoint exposure,
  and the discovery challenge.

Still required before ChatGPT can complete login:
- Configure a real OAuth/OIDC authorization server that meets the MCP OAuth
  requirements above.
- Configure exact production redirect URI(s) from the ChatGPT app setup.
- Deploy behind public HTTPS, then verify metadata discovery and authorization
  code + PKCE end-to-end from ChatGPT web.
- Confirm introspection responses include `active`, exact `iss`, expected
  `aud`, `exp`, `client_id`, `sub`, and granted `scope`.
- Add persistent storage and production deployment controls before treating
  this as production-ready.

This stage does not implement an OAuth authorization server, does not connect
Google/Meta/Shopee accounts, does not issue tokens, and does not claim a ChatGPT
login has succeeded. The documented client is ChatGPT web; custom MCP server
connections are not supported from ChatGPT mobile.
