# Universal MCP provider setup wizard

## What this stage provides

The `aic-setup` command is a safe **configuration preflight**, not an OAuth client.
It guides setup for Google identity/shared OAuth, Google Drive, YouTube, Facebook
Pages, Instagram Professional, and Shopee Open Platform. It checks only whether
required environment-variable names are populated and reports missing names.
It never prints environment values, stores tokens, opens login pages, calls
provider APIs, or marks a provider connected.

## Run in Codespaces

From the repository root:

```bash
python -m pip install -e .
aic-setup
```

Inspect one provider:

```bash
aic-setup --provider google_drive
aic-setup --provider youtube --provider instagram
```

Machine-readable output:

```bash
aic-setup --json
```

The JSON report deliberately sets `connection_verified: false` and the
connected count to zero. `CONFIGURED_NOT_CONNECTED` means only that expected
configuration names are present; it does not prove OAuth consent, token validity,
scope grants, or API reachability.

## Configuration variable names

| Provider | Required variable names (values must be stored as secrets where sensitive) |
|---|---|
| Google identity / shared OAuth client | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` |
| Google Drive | Same Google OAuth client variables; Drive API must be enabled and Drive scopes consented |
| YouTube | Same Google OAuth client variables; YouTube Data API must be enabled and channel scopes consented |
| Facebook Pages | `META_APP_ID`, `META_APP_SECRET`, `META_REDIRECT_URI` |
| Instagram Professional | Same Meta app variables; account eligibility, API path, and permissions must be checked |
| Shopee | `SHOPEE_PARTNER_ID`, `SHOPEE_PARTNER_KEY`, `SHOPEE_REDIRECT_URI` |

Configure these names through GitHub Codespaces Secrets or a trusted deployment
secret manager. Never commit real values, paste secrets into chat, or print them
in logs. A provider's exact credentials, scopes, redirect URI, app review, and
API capabilities must follow its official documentation.

## What still needs implementation

This is the first setup-wizard layer only. It does **not** yet implement:
- interactive "Connect account" OAuth authorization and callback handling;
- state/CSRF and PKCE validation as required by the provider flow;
- encrypted token storage, token refresh, disconnect, or revocation;
- real provider adapters and read-only API health checks;
- automatic activation/registration of verified adapters in the MCP server;
- package build/deployment after configuration changes.

Do not label an account `CONNECTED` until a provider OAuth flow has completed
and a real API health check succeeds. Do not package credentials into the MCP
distribution. The intended end state is one modular MCP server with provider
adapters activated per verified connection, not a separate MCP package for each
platform.
