"""Provider-neutral authorization decisions for IM19 connector tools.

This module never receives raw tokens. A trusted OAuth layer supplies the
verified subject, scopes and connected provider account.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class Decision(StrEnum):
    ALLOW = "ALLOW"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    SCOPE_REQUIRED = "SCOPE_REQUIRED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    DENY = "DENY"


@dataclass(frozen=True)
class Principal:
    subject: str
    provider: str
    account_id: str
    scopes: frozenset[str]

    def __post_init__(self) -> None:
        if not self.subject or not self.provider or not self.account_id:
            raise ValueError("principal_identity_required")


@dataclass(frozen=True)
class ToolPolicy:
    action: str
    provider: str
    required_scopes: frozenset[str]
    mutates: bool = False

    def __post_init__(self) -> None:
        if not self.action or not self.provider:
            raise ValueError("policy_identity_required")


@dataclass(frozen=True)
class Approval:
    subject: str
    provider: str
    account_id: str
    action: str
    payload_digest: str
    expires_at: float


@dataclass(frozen=True)
class AuthorizationResult:
    decision: Decision
    missing_scopes: tuple[str, ...] = ()


def authorize(
    policy: ToolPolicy,
    principal: Principal | None,
    *,
    expected_subject: str,
    expected_account_id: str,
    payload_digest: str = "",
    approval: Approval | None = None,
    now: float,
) -> AuthorizationResult:
    """Fail closed: identity -> provider -> scopes -> exact, expiring approval.

    The caller MUST validate the OAuth access token, resource audience and
    account ownership before constructing Principal. Never trust model args
    for principal, expected_subject or approval.
    """
    if not expected_subject or not expected_account_id:
        return AuthorizationResult(Decision.DENY)
    if principal is None:
        return AuthorizationResult(Decision.AUTH_REQUIRED)
    if (
        principal.subject != expected_subject
        or principal.account_id != expected_account_id
        or principal.provider != policy.provider
    ):
        return AuthorizationResult(Decision.DENY)
    missing = tuple(sorted(policy.required_scopes - principal.scopes))
    if missing:
        return AuthorizationResult(Decision.SCOPE_REQUIRED, missing)
    if policy.mutates:
        if not payload_digest:
            return AuthorizationResult(Decision.DENY)
        if approval is None:
            return AuthorizationResult(Decision.APPROVAL_REQUIRED)
        if (
            approval.subject != principal.subject
            or approval.provider != principal.provider
            or approval.account_id != principal.account_id
            or approval.action != policy.action
            or approval.payload_digest != payload_digest
            or approval.expires_at <= now
        ):
            return AuthorizationResult(Decision.DENY)
    return AuthorizationResult(Decision.ALLOW)
