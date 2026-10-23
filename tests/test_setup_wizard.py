import json
import unittest
from io import StringIO
from unittest.mock import patch

from aic_connector.setup_wizard import build_report, main


class SetupWizardTests(unittest.TestCase):
    def test_all_six_platforms_are_included_by_default(self):
        report = build_report(environ={})
        self.assertEqual(
            [item["id"] for item in report["providers"]],
            ["google", "google_drive", "youtube", "facebook", "instagram", "shopee"],
        )
        self.assertEqual(report["summary"]["total"], 6)
        self.assertEqual(report["summary"]["connected"], 0)

    def test_environment_presence_is_not_misreported_as_connection(self):
        env = {
            "GOOGLE_CLIENT_ID": "example-id",
            "GOOGLE_CLIENT_SECRET": "super-secret-value",
            "GOOGLE_REDIRECT_URI": "https://example.test/callback",
        }
        report = build_report(["google_drive"], environ=env)
        provider = report["providers"][0]
        self.assertEqual(provider["status"], "CONFIGURED_NOT_CONNECTED")
        self.assertFalse(provider["connection_verified"])
        self.assertEqual(provider["missing_variables"], [])

    def test_report_never_contains_environment_values(self):
        secret = "DO_NOT_LEAK_THIS_SECRET"
        report = build_report(["google"], environ={
            "GOOGLE_CLIENT_ID": "client-id",
            "GOOGLE_CLIENT_SECRET": secret,
            "GOOGLE_REDIRECT_URI": "https://example.test/callback",
        })
        serialized = json.dumps(report)
        self.assertNotIn(secret, serialized)
        self.assertNotIn("client-id", serialized)

    def test_missing_environment_is_reported_by_name_only(self):
        report = build_report(["shopee"], environ={})
        provider = report["providers"][0]
        self.assertEqual(provider["status"], "NOT_CONFIGURED")
        self.assertIn("SHOPEE_PARTNER_KEY", provider["missing_variables"])

    def test_unknown_provider_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown_provider"):
            build_report(["made_up_provider"], environ={})

    def test_cli_json_is_explicit_about_preflight_only(self):
        output = StringIO()
        with patch("sys.stdout", output):
            result = main(["--provider", "google", "--json"])
        self.assertEqual(result, 0)
        parsed = json.loads(output.getvalue())
        self.assertFalse(parsed["connection_verified"])
        self.assertIn("does not perform OAuth", parsed["warning"])


if __name__ == "__main__":
    unittest.main()
