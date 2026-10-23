"""Safe preflight wizard for configuring provider adapters.

This command checks whether required configuration names are present in the
environment. It never prints secret values and does not claim an account is
connected; a real OAuth callback/token vault and provider API health check are
separate implementation steps.
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ProviderSetup:
    provider_id: str
    display_name: str
    developer_url: str
    env_requirements: tuple[str, ...]
    setup_steps: tuple[str, ...]
    notes: str


PROVIDERS: tuple[ProviderSetup, ...] = (
    ProviderSetup(
        provider_id="google",
        display_name="Google identity / shared OAuth client",
        developer_url="https://console.cloud.google.com/",
        env_requirements=("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI"),
        setup_steps=(
            "Choose or create a Google OAuth application in a trusted project.",
            "Configure the consent screen and exact redirect URI.",
            "Request only the scopes needed by the selected Google services.",
            "Store client credentials in Codespaces Secrets or a deployment secret manager.",
        ),
        notes="A Google login alone does not grant Drive or YouTube API access.",
    ),
    ProviderSetup(
        provider_id="google_drive",
        display_name="Google Drive",
        developer_url="https://console.cloud.google.com/apis/library/drive.googleapis.com",
        env_requirements=("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI"),
        setup_steps=(
            "Enable Google Drive API for the OAuth project.",
            "Use the official Google OAuth flow and least-privilege Drive scopes.",
            "Authorize the intended account and test a read-only operation first.",
        ),
        notes="Can share the Google OAuth client with other Google APIs, but requires its own scopes and API enablement.",
    ),
    ProviderSetup(
        provider_id="youtube",
        display_name="YouTube Data API",
        developer_url="https://console.cloud.google.com/apis/library/youtube.googleapis.com",
        env_requirements=("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI"),
        setup_steps=(
            "Enable YouTube Data API v3 for the OAuth project.",
            "Request only scopes required for the selected channel operations.",
            "Authorize the intended channel and verify read access before enabling writes.",
        ),
        notes="Google Drive authorization does not automatically authorize YouTube actions.",
    ),
    ProviderSetup(
        provider_id="facebook",
        display_name="Facebook Pages",
        developer_url="https://developers.facebook.com/apps/",
        env_requirements=("META_APP_ID", "META_APP_SECRET", "META_REDIRECT_URI"),
        setup_steps=(
            "Create/configure a Meta app and add the required product/API.",
            "Configure the exact OAuth redirect URI and required permissions.",
            "Complete any Meta review or business verification required for the intended operations.",
            "Authorize a Page you control and test read access first.",
        ),
        notes="App credentials alone do not mean a Facebook account or Page is connected.",
    ),
    ProviderSetup(
        provider_id="instagram",
        display_name="Instagram Professional",
        developer_url="https://developers.facebook.com/apps/",
        env_requirements=("META_APP_ID", "META_APP_SECRET", "META_REDIRECT_URI"),
        setup_steps=(
            "Confirm the account is eligible for the chosen official Instagram API path.",
            "Configure the required Meta products, permissions, and redirect URI.",
            "Authorize the account and verify permitted read operations before publishing.",
        ),
        notes="Supported account types, scopes, and publishing features depend on the selected Meta API path.",
    ),
    ProviderSetup(
        provider_id="shopee",
        display_name="Shopee Open Platform",
        developer_url="https://open.shopee.com/",
        env_requirements=("SHOPEE_PARTNER_ID", "SHOPEE_PARTNER_KEY", "SHOPEE_REDIRECT_URI"),
        setup_steps=(
            "Register/configure an eligible Shopee Open Platform application.",
            "Set the exact redirect URI and store partner credentials in a secret manager.",
            "Complete the official shop authorization flow and verify a read-only API call.",
        ),
        notes="Partner access and API capabilities depend on Shopee's approval and the app's permissions.",
    ),
)

_PROVIDER_BY_ID = {provider.provider_id: provider for provider in PROVIDERS}


def inspect_provider(provider: ProviderSetup, environ: Mapping[str, str] | None = None) -> dict[str, object]:
    """Return safe configuration metadata without returning environment values."""
    env = os.environ if environ is None else environ
    present = [key for key in provider.env_requirements if bool(env.get(key, "").strip())]
    missing = [key for key in provider.env_requirements if key not in present]
    if missing:
        status = "NOT_CONFIGURED"
    else:
        status = "CONFIGURED_NOT_CONNECTED"
    return {
        "id": provider.provider_id,
        "name": provider.display_name,
        "status": status,
        "required_environment_variables": list(provider.env_requirements),
        "present_variables": present,
        "missing_variables": missing,
        "developer_url": provider.developer_url,
        "setup_steps": list(provider.setup_steps),
        "notes": provider.notes,
        "connection_verified": False,
        "next_step": (
            "Configure the missing variables in a secret manager, then implement/run the provider OAuth flow and API health check."
            if missing
            else "Run the provider OAuth flow and a real API health check; environment configuration alone is not a connection."
        ),
    }


def build_report(
    provider_ids: Sequence[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Build a setup report for all or selected providers."""
    ids = list(provider_ids) if provider_ids else [provider.provider_id for provider in PROVIDERS]
    unknown = sorted(set(ids) - set(_PROVIDER_BY_ID))
    if unknown:
        raise ValueError("unknown_provider:" + ",".join(unknown))
    entries = [inspect_provider(_PROVIDER_BY_ID[provider_id], environ) for provider_id in ids]
    return {
        "mode": "configuration_preflight",
        "connection_verified": False,
        "warning": "This wizard checks configuration presence only. It does not perform OAuth, connect accounts, or call provider APIs.",
        "providers": entries,
        "summary": {
            "total": len(entries),
            "not_configured": sum(item["status"] == "NOT_CONFIGURED" for item in entries),
            "configured_not_connected": sum(item["status"] == "CONFIGURED_NOT_CONNECTED" for item in entries),
            "connected": 0,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aic-setup",
        description="Safely inspect setup requirements for the Universal MCP providers.",
    )
    parser.add_argument("--provider", action="append", choices=sorted(_PROVIDER_BY_ID), help="Provider ID; repeat to select several.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable report. Secret values are never printed.")
    args = parser.parse_args(argv)
    report = build_report(args.provider)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    print("Universal MCP — provider setup preflight")
    print(report["warning"])
    for item in report["providers"]:
        print(f"\n[{item['status']}] {item['name']} ({item['id']})")
        print(f"  Setup portal: {item['developer_url']}")
        if item["missing_variables"]:
            print("  Missing configuration names: " + ", ".join(item["missing_variables"]))
        else:
            print("  Required configuration names are present; account connection is NOT verified.")
        for step_no, step in enumerate(item["setup_steps"], start=1):
            print(f"  {step_no}. {step}")
        print(f"  Note: {item['notes']}")
    summary = report["summary"]
    print(
        f"\nSummary: {summary['total']} selected; "
        f"{summary['not_configured']} not configured; "
        f"{summary['configured_not_connected']} configured but not connected."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
