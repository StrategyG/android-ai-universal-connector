import unittest

from aic_connector.core import ALLOW, DENY, REQUIRE_APPROVAL, StateStore, classify_action, payload_digest


class PolicyTests(unittest.TestCase):
    def test_read_only_action_is_allowlisted(self):
        self.assertEqual(classify_action("gmail.search"), (ALLOW, "known_read_only_action"))

    def test_sensitive_action_requires_approval(self):
        self.assertEqual(
            classify_action("gmail.message.send"),
            (REQUIRE_APPROVAL, "sensitive_action_requires_human_approval"),
        )

    def test_unknown_action_is_denied_by_default(self):
        decision, reason = classify_action("shell.execute")
        self.assertEqual(decision, DENY)
        self.assertEqual(reason, "action_not_allowlisted")

    def test_payload_digest_is_stable_for_key_order(self):
        self.assertEqual(payload_digest({"b": 2, "a": 1}), payload_digest({"a": 1, "b": 2}))

    def test_payload_digest_rejects_non_json_numbers(self):
        with self.assertRaises(ValueError):
            payload_digest({"not_a_number": float("nan")})


class TaskStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = StateStore()

    def test_task_creation_stores_digest_not_raw_payload(self):
        result = self.store.create_task("gmail.draft.create", "recipient@example.com", {"body": "private content"})
        self.assertTrue(result["created"])
        self.assertFalse(result["execution_performed"])
        task = result["task"]
        self.assertEqual(task["status"], "DRAFT")
        self.assertNotIn("private content", str(task))
        self.assertEqual(len(task["payload_sha256"]), 64)

    def test_sensitive_task_requires_approval_and_no_execution(self):
        created = self.store.create_task("gmail.message.send", "recipient@example.com", {"body": "hello"})
        self.assertEqual(created["task"]["status"], "AWAITING_APPROVAL")
        approval = self.store.request_approval(created["task"]["id"])
        self.assertTrue(approval["requested"])
        self.assertFalse(approval["execution_performed"])
        self.assertEqual(approval["approval"]["payload_sha256"], created["task"]["payload_sha256"])

    def test_unknown_action_is_denied_without_creating_task(self):
        result = self.store.create_task("arbitrary.shell.command", "local", {})
        self.assertFalse(result["created"])
        self.assertEqual(result["decision"], DENY)

    def test_approval_request_is_idempotent_while_pending(self):
        created = self.store.create_task("facebook.post.publish", "page-123", {"caption": "draft"})
        task_id = created["task"]["id"]
        first = self.store.request_approval(task_id)
        second = self.store.request_approval(task_id)
        self.assertEqual(first["approval"]["id"], second["approval"]["id"])
        self.assertTrue(second["idempotent_reuse"])

    def test_cancel_cancels_pending_approval(self):
        created = self.store.create_task("tiktok.post.publish", "account-1", {"caption": "draft"})
        task_id = created["task"]["id"]
        approval = self.store.request_approval(task_id)
        cancelled = self.store.cancel_task(task_id)
        self.assertTrue(cancelled["cancelled"])
        self.assertEqual(cancelled["task"]["status"], "CANCELLED")
        self.assertEqual(self.store.query_audit()["count"] >= 2, True)
        self.assertEqual(self.store._approvals[approval["approval"]["id"]].status, "CANCELLED")

    def test_unknown_connector_status_does_not_claim_connection(self):
        status = self.store.connector_status("not-a-connector")
        self.assertFalse(status["found"])

    def test_audit_does_not_include_payload_content(self):
        self.store.create_task("gmail.draft.create", "recipient@example.com", {"body": "secret-body"})
        audit = self.store.query_audit()
        self.assertNotIn("secret-body", str(audit))


if __name__ == "__main__":
    unittest.main()
