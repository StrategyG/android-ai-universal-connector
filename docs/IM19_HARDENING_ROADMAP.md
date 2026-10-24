# IM19 Universal MCP — security hardening roadmap

## Scope of this change

This change introduces a **provider-neutral authorization decision module**.
It does not enable external APIs or production login.

- A verified subject and provider account must match the requested operation.
- Required provider scopes are checked independently from MCP resource authentication.
- Mutation operations require an exact payload-bound, unexpired approval.
- Missing scopes return a structured SCOPE_REQUIRED result.
- A denied or missing approval never triggers an external operation.

## Integration requirements (not yet implemented)

1. Validate MCP client tokens against the intended MCP resource audience.
2. Implement OAuth Authorization Code + PKCE for each external provider.
3. Bind provider account IDs to the authenticated MCP subject in persistent storage.
4. Store refresh tokens encrypted with managed encryption keys; never return them to tools.
5. Use authorization decisions at the execution boundary, not merely during planning.
6. Issue one-time approval IDs server-side; bind to canonical payload hash and expire them.
7. Atomically consume approval IDs to prevent replay; use idempotency keys for mutations.
8. Build real read-only YouTube and Drive connectors with documented API scopes.
9. Add persistent audit storage, retention policy, and redaction tests.
10. Deploy remote MCP over HTTPS and verify ChatGPT OAuth end-to-end.

## Verification

Run `python -m unittest discover -s tests -v` after installing dependencies.
These are unit tests, not evidence of successful Google or ChatGPT login.
Do not advertise this prototype as production-ready.

## Threat boundaries

ChatGPT-to-MCP OAuth is distinct from MCP-to-Google OAuth.
A Google identity token is not an authorization token for arbitrary Google APIs.
The `Principal` object must be constructed only from verified server-side
session state; never accept it directly from model-generated tool arguments.
