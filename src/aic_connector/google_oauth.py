"""Google OAuth authorization-code PKCE flow primitives.

OAuth transaction storage here is ephemeral and single-process. Production
deployment requires a shared, encrypted/TTL transaction store. No credentials
or tokens are accepted from model-supplied MCP tool arguments.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from threading import RLock
from urllib.parse import urlencode, urlsplit

GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = {
    "youtube_read": "https://www.googleapis.com/auth/youtube.readonly",
    "drive_metadata": "https://www.googleapis.com/auth/drive.metadata.readonly",
    "drive_file": "https://www.googleapis.com/auth/drive.file",
}


@dataclass(frozen=True)
class OAuthTransaction:
    subject: str
    state: str
    code_verifier: str
    scopes: tuple[str, ...]
    redirect_uri: str
    expires_at: float


class GoogleOAuthFlow:
    def __init__(self, client_id: str, redirect_uri: str, *, ttl_seconds: int = 600):
        parsed = urlsplit(redirect_uri)
        loopback = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
        if not client_id or not (parsed.scheme == "https" or loopback):
            raise ValueError("google_oauth_configuration_invalid")
        if parsed.fragment or parsed.username or parsed.password or not parsed.netloc:
            raise ValueError("google_oauth_redirect_invalid")
        if not 30 <= ttl_seconds <= 900:
            raise ValueError("google_oauth_ttl_invalid")
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.ttl_seconds = ttl_seconds
        self._pending: dict[str, OAuthTransaction] = {}
        self._lock = RLock()

    def begin(self, subject: str, scope_keys: tuple[str, ...]) -> tuple[str, str]:
        """Return authorization URL and opaque state; keep verifier server-side."""
        if not subject or not scope_keys or any(key not in GOOGLE_SCOPES for key in scope_keys):
            raise ValueError("google_oauth_request_invalid")
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        state = secrets.token_urlsafe(32)
        scopes = tuple(sorted({GOOGLE_SCOPES[key] for key in scope_keys}))
        txn = OAuthTransaction(subject, state, verifier, scopes, self.redirect_uri, time.time() + self.ttl_seconds)
        with self._lock:
            self._pending = {key: value for key, value in self._pending.items() if value.expires_at > time.time()}
            self._pending[state] = txn
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "access_type": "offline",
            "include_granted_scopes": "true",
        }
        return GOOGLE_AUTHORIZATION_ENDPOINT + "?" + urlencode(params), state

    def consume(self, *, subject: str, state: str) -> OAuthTransaction:
        """Atomically consume a state; replay, expiration and wrong user fail closed."""
        with self._lock:
            txn = self._pending.pop(state, None)
        if txn is None or txn.expires_at <= time.time() or txn.subject != subject:
            raise PermissionError("oauth_state_invalid_or_expired")
        return txn
