# Multi-app connector adapter contract

## Goal

Use one MCP-facing connector with provider-specific adapters. The shared gateway
standardizes discovery, policy, and audit; it does **not** make external login
sessions portable across services.

## Request path

`AI client → MCP server → policy/approval gate → adapter registry → provider adapter → official API`

Each adapter is responsible for one provider's API and connection state. A
Facebook adapter must not reuse a Dropbox token; a Google adapter must not infer
authorization from a browser's existing Google session.

## Authorization lifecycle

1. The user selects a provider and starts its official authorization flow.
2. The provider validates the registered application, redirect URI, requested
   scopes, and user consent.
3. The backend validates the callback/state/PKCE as applicable and exchanges
   the authorization code server-side.
4. Tokens are stored encrypted in a dedicated token vault, keyed by provider
   and authenticated user/tenant. Never return tokens to the model or logs.
5. Each action checks the authenticated subject, provider connection, minimum
   scope, token expiry, and policy before calling the provider API.
6. Disconnect revokes provider access where supported and deletes the stored
   credential. Expired/revoked credentials fail closed and require reconnection.

The adapter registry added in P1 is metadata and deterministic action routing
only. It is not an OAuth client, token vault, scheduler, or external API executor.

## Consent and side effects

- Draft generation is local and should not require provider write scopes.
- Read, write, publish, delete, and send actions must have distinct capabilities.
- Sensitive external actions require an approval record bound to the exact action,
  target, and payload digest; editing the payload invalidates prior approval.
- Any autonomous schedule must run in a persistent scheduler/backend, not in an
  MCP tool call or an open chat session. Store idempotency keys and audit each
  attempt to prevent duplicate posts after retries.
- Use provider APIs and app review requirements. Do not automate private web
  sessions or collect users' passwords.

## Security acceptance gates before a real adapter is enabled

- Provider-specific OAuth configuration and redirect URI reviewed.
- State/CSRF and PKCE protections tested where applicable.
- Scopes minimized and explained to the user.
- Token storage encryption and per-user/tenant isolation tested.
- Revocation, expiry, refresh, and failure paths tested.
- Action allowlist, target ownership, rate limits, and audit redaction tested.
- Integration tests use a provider sandbox or test account.
- Live publishing remains disabled until the user explicitly enables it.

## Current implementation status

`aic_connector.adapters` provides a typed manifest contract, duplicate-ID
rejection, and explicit action routing. No real provider adapters are registered
by this module yet. All platform integrations remain unconfigured until their
OAuth/API implementation and provider-specific tests exist.
