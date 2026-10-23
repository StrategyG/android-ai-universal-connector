"""P0 domain logic for the Android AI Universal Connector.

This module intentionally contains no platform API calls. Tasks are plans only;
no external action is executed by this foundation.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import secrets
from threading import RLock
from typing import Any

ALLOW = "ALLOW"
REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
DENY = "DENY"

NOT_CONFIGURED = "NOT_CONFIGURED"
CONFIGURED_UNVERIFIED = "CONFIGURED_UNVERIFIED"
VERIFIED = "VERIFIED"
BLOCKED = "BLOCKED"

READ_ONLY_ACTIONS = {
    "connector.status",
    "connector.permissions",
    "audit.query",
    "gmail.search",
    "gmail.message.get",
    "youtube.video.search",
    "youtube.video.get",
    "instagram.account.status",
    "facebook.pages.list",
    "facebook.insights.get",
    "tiktok.account.status",
    "shopee.shop.status",
    "shopee.product.list",
    "shopee.product.get",
    "android.device.status",
}
PREPARATION_ACTIONS = {
    "gmail.draft.create",
    "youtube.upload.prepare",
    "instagram.media.prepare",
    "facebook.post.prepare",
    "tiktok.post.prepare",
    "android.share.prepare",
}
SENSITIVE_ACTIONS = {
    "gmail.message.send",
    "youtube.upload.execute",
    "instagram.media.publish",
    "facebook.post.publish",
    "tiktok.post.publish",
    "shopee.product.update",
    "android.accessibility.execute",
    "android.task.schedule",
    "android.app.open",
}
SUPPORTED_ACTIONS = READ_ONLY_ACTIONS | PREPARATION_ACTIONS | SENSITIVE_ACTIONS

CONNECTOR_SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "gmail",
        "name": "Gmail",
        "status": NOT_CONFIGURED,
        "required_scopes": [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.compose",
            "https://www.googleapis.com/auth/gmail.send",
        ],
    },
    {
        "id": "youtube",
        "name": "YouTube",
        "status": NOT_CONFIGURED,
        "required_scopes": [
            "https://www.googleapis.com/auth/youtube.readonly",
            "https://www.googleapis.com/auth/youtube.upload",
        ],
    },
    {
        "id": "instagram",
        "name": "Instagram",
        "status": NOT_CONFIGURED,
        "required_scopes": ["instagram_business_basic", "instagram_business_content_publish"],
    },
    {
        "id": "facebook",
        "name": "Facebook Pages",
        "status": NOT_CONFIGURED,
        "required_scopes": ["pages_show_list", "pages_manage_posts", "read_insights"],
    },
    {
        "id": "tiktok",
        "name": "TikTok",
        "status": NOT_CONFIGURED,
        "required_scopes": ["user.info.basic", "video.publish"],
    },
    {
        "id": "shopee",
        "name": "Shopee",
        "status": NOT_CONFIGURED,
        "required_scopes": ["shop/product read-write scopes defined by the approved Open Platform app"],
    },
    {
        "id": "android",
        "name": "Android device bridge",
        "status": NOT_CONFIGURED,
        "required_scopes": ["Android runtime permissions granted explicitly by the device owner"],
    },
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime | None = None) -> str:
    return (value or utc_now()).isoformat().replace("+00:00", "Z")


def classify_action(action: str) -> tuple[str, str]:
    """Classify a known action. Unknown actions are denied by default."""
    if not isinstance(action, str) or not action.strip():
        return DENY, "action_missing"
    normalized = action.strip().lower()
    if normalized in SENSITIVE_ACTIONS:
        return REQUIRE_APPROVAL, "sensitive_action_requires_human_approval"
    if normalized in READ_ONLY_ACTIONS:
        return ALLOW, "known_read_only_action"
    if normalized in PREPARATION_ACTIONS:
        return ALLOW, "preparation_only_no_external_side_effect"
    return DENY, "action_not_allowlisted"


def payload_digest(payload: dict[str, Any]) -> str:
    """Hash a canonical JSON payload without retaining its raw contents."""
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class Task:
    id: str
    action: str
    target: str
    payload_sha256: str
    decision: str
    status: str
    reason: str
    created_at: str
    approval_id: str | None = None


@dataclass
class Approval:
    id: str
    task_id: str
    action: str
    target: str
    payload_sha256: str
    status: str
    requested_at: str
    expires_at: str


class StateStore:
    """Thread-safe, in-memory P0 state store; restart clears state by design."""

    def __init__(self, audit_capacity: int = 1000) -> None:
        if audit_capacity < 1:
            raise ValueError("audit_capacity must be at least 1")
        self._lock = RLock()
        self._tasks: dict[str, Task] = {}
        self._approvals: dict[str, Approval] = {}
        self._events: deque[dict[str, Any]] = deque(maxlen=audit_capacity)

    def _event(self, event_type: str, **fields: Any) -> None:
        self._events.append(
            {
                "id": secrets.token_urlsafe(8),
                "timestamp": iso_utc(),
                "event_type": event_type,
                **fields,
            }
        )

    def list_connectors(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in CONNECTOR_SPECS]

    def connector_status(self, connector_id: str | None = None) -> dict[str, Any]:
        connectors = self.list_connectors()
        if not connector_id:
            return {"connectors": connectors}
        found = next((item for item in connectors if item["id"] == connector_id), None)
        if found is None:
            return {"found": False, "connector_id": connector_id}
        return {"found": True, "connector": found}

    def connector_permissions(self, connector_id: str | None = None) -> dict[str, Any]:
        connectors = self.list_connectors()
        selected = [item for item in connectors if not connector_id or item["id"] == connector_id]
        if connector_id and not selected:
            return {"found": False, "connector_id": connector_id}
        return {
            "connectors": [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "status": item["status"],
                    "required_scopes": list(item["required_scopes"]),
                }
                for item in selected
            ]
        }

    def create_task(self, action: str, target: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")
        if not isinstance(target, str) or not target.strip():
            raise ValueError("target is required")
        digest = payload_digest(payload)
        decision, reason = classify_action(action)
        with self._lock:
            if decision == DENY:
                self._event("task.create.denied", action=action, decision=decision, reason=reason)
                return {"created": False, "decision": decision, "reason": reason}
            task_id = "task_" + secrets.token_urlsafe(9)
            task = Task(
                id=task_id,
                action=action.strip().lower(),
                target=target.strip(),
                payload_sha256=digest,
                decision=decision,
                status="AWAITING_APPROVAL" if decision == REQUIRE_APPROVAL else "DRAFT",
                reason=reason,
                created_at=iso_utc(),
            )
            self._tasks[task_id] = task
            self._event(
                "task.created",
                task_id=task_id,
                action=task.action,
                decision=decision,
                status=task.status,
            )
            return {"created": True, "task": asdict(task), "execution_performed": False}

    def get_task(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return {"found": False, "task_id": task_id}
            return {"found": True, "task": asdict(task), "execution_performed": False}

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return {"cancelled": False, "reason": "task_not_found"}
            if task.status in {"CANCELLED", "COMPLETED", "FAILED"}:
                return {"cancelled": False, "reason": "task_not_cancellable", "status": task.status}
            task.status = "CANCELLED"
            for approval in self._approvals.values():
                if approval.task_id == task_id and approval.status == "PENDING":
                    approval.status = "CANCELLED"
            self._event("task.cancelled", task_id=task_id, action=task.action)
            return {"cancelled": True, "task": asdict(task)}

    def request_approval(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return {"requested": False, "reason": "task_not_found"}
            if task.status == "CANCELLED":
                return {"requested": False, "reason": "task_cancelled"}
            if task.decision != REQUIRE_APPROVAL:
                return {"requested": False, "reason": "task_does_not_require_approval"}
            if task.approval_id:
                current = self._approvals.get(task.approval_id)
                if current and current.status == "PENDING":
                    return {"requested": True, "approval": asdict(current), "idempotent_reuse": True}
            now = utc_now()
            approval = Approval(
                id="approval_" + secrets.token_urlsafe(9),
                task_id=task.id,
                action=task.action,
                target=task.target,
                payload_sha256=task.payload_sha256,
                status="PENDING",
                requested_at=iso_utc(now),
                expires_at=iso_utc(now + timedelta(minutes=15)),
            )
            self._approvals[approval.id] = approval
            task.approval_id = approval.id
            task.status = "AWAITING_APPROVAL"
            self._event("approval.requested", task_id=task.id, approval_id=approval.id, action=task.action)
            return {"requested": True, "approval": asdict(approval), "execution_performed": False}

    def query_audit(self, limit: int = 50, event_type: str | None = None) -> dict[str, Any]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        with self._lock:
            events = list(self._events)
        if event_type:
            events = [event for event in events if event["event_type"] == event_type]
        return {"events": events[-limit:], "count": min(len(events), limit), "retention_capacity": self._events.maxlen}
