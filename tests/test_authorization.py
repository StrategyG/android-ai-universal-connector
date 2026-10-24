"""Security regression tests for connector authorization."""
import unittest

from aic_connector.authorization import (
    Approval, Decision, Principal, ToolPolicy, authorize,
)


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.principal = Principal("user-1", "google", "channel-1", frozenset({"youtube.readonly"}))
        self.read = ToolPolicy("youtube.analytics", "google", frozenset({"youtube.readonly"}))
        self.write = ToolPolicy("youtube.publish", "google", frozenset({"youtube.upload"}), True)

    def check(self, policy=None, principal=None, **kwargs):
        return authorize(
            policy or self.read,
            self.principal if principal is None else principal,
            expected_subject="user-1",
            expected_account_id="channel-1",
            now=100.0,
            **kwargs,
        )

    def test_read_allowed(self):
        self.assertEqual(self.check().decision, Decision.ALLOW)

    def test_missing_scope(self):
        result = self.check(self.write)
        self.assertEqual(result.decision, Decision.SCOPE_REQUIRED)
        self.assertEqual(result.missing_scopes, ("youtube.upload",))

    def test_cross_user_denied(self):
        other = Principal("user-2", "google", "channel-1", self.principal.scopes)
        self.assertEqual(self.check(principal=other).decision, Decision.DENY)

    def test_cross_account_denied(self):
        other = Principal("user-1", "google", "channel-2", self.principal.scopes)
        self.assertEqual(self.check(principal=other).decision, Decision.DENY)

    def test_cross_provider_denied(self):
        other = Principal("user-1", "meta", "channel-1", self.principal.scopes)
        self.assertEqual(self.check(principal=other).decision, Decision.DENY)

    def test_mutation_requires_approval(self):
        principal = Principal("user-1", "google", "channel-1", frozenset({"youtube.upload"}))
        result = self.check(self.write, principal=principal, payload_digest="sha256:abc")
        self.assertEqual(result.decision, Decision.APPROVAL_REQUIRED)

    def test_valid_approval(self):
        principal = Principal("user-1", "google", "channel-1", frozenset({"youtube.upload"}))
        approval = Approval("user-1", "google", "channel-1", "youtube.publish", "sha256:abc", 101.0)
        result = self.check(self.write, principal=principal, payload_digest="sha256:abc", approval=approval)
        self.assertEqual(result.decision, Decision.ALLOW)

    def test_expired_approval_denied(self):
        principal = Principal("user-1", "google", "channel-1", frozenset({"youtube.upload"}))
        approval = Approval("user-1", "google", "channel-1", "youtube.publish", "sha256:abc", 100.0)
        result = self.check(self.write, principal=principal, payload_digest="sha256:abc", approval=approval)
        self.assertEqual(result.decision, Decision.DENY)

    def test_modified_payload_denied(self):
        principal = Principal("user-1", "google", "channel-1", frozenset({"youtube.upload"}))
        approval = Approval("user-1", "google", "channel-1", "youtube.publish", "sha256:abc", 101.0)
        result = self.check(self.write, principal=principal, payload_digest="sha256:other", approval=approval)
        self.assertEqual(result.decision, Decision.DENY)

    def test_missing_payload_digest_denied(self):
        principal = Principal("user-1", "google", "channel-1", frozenset({"youtube.upload"}))
        self.assertEqual(self.check(self.write, principal=principal).decision, Decision.DENY)

    def test_no_identity_denied(self):
        self.assertEqual(
            authorize(self.read, self.principal, expected_subject="", expected_account_id="channel-1", now=100).decision,
            Decision.DENY,
        )


if __name__ == "__main__":
    unittest.main()
