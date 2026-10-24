import unittest
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from aic_connector.google_oauth import GOOGLE_SCOPES, GoogleOAuthFlow


class GoogleOAuthFlowTests(unittest.TestCase):
    def setUp(self):
        self.flow = GoogleOAuthFlow("client-id", "https://example.org/oauth/google/callback")

    def test_pkce_and_minimal_scopes(self):
        url, state = self.flow.begin("user-1", ("youtube_read",))
        parsed = urlsplit(url)
        params = parse_qs(parsed.query)
        self.assertEqual(parsed.hostname, "accounts.google.com")
        self.assertEqual(params["code_challenge_method"], ["S256"])
        self.assertEqual(params["scope"], [GOOGLE_SCOPES["youtube_read"]])
        self.assertEqual(params["state"], [state])
        txn = self.flow.consume(subject="user-1", state=state)
        self.assertGreater(len(txn.code_verifier), 43)

    def test_replay_denied(self):
        _, state = self.flow.begin("user-1", ("drive_metadata",))
        self.flow.consume(subject="user-1", state=state)
        with self.assertRaises(PermissionError):
            self.flow.consume(subject="user-1", state=state)

    def test_cross_user_denied_and_consumed(self):
        _, state = self.flow.begin("user-1", ("drive_metadata",))
        with self.assertRaises(PermissionError):
            self.flow.consume(subject="user-2", state=state)
        with self.assertRaises(PermissionError):
            self.flow.consume(subject="user-1", state=state)

    def test_expiry_denied(self):
        with patch("aic_connector.google_oauth.time.time", return_value=100.0):
            _, state = self.flow.begin("user-1", ("youtube_read",))
        with patch("aic_connector.google_oauth.time.time", return_value=1000.0):
            with self.assertRaises(PermissionError):
                self.flow.consume(subject="user-1", state=state)

    def test_unknown_scope_denied(self):
        with self.assertRaises(ValueError):
            self.flow.begin("user-1", ("gmail_all",))

    def test_http_redirect_denied(self):
        with self.assertRaises(ValueError):
            GoogleOAuthFlow("client", "http://example.org/callback")

    def test_loopback_redirect_allowed(self):
        GoogleOAuthFlow("client", "http://127.0.0.1:8765/callback")


if __name__ == "__main__":
    unittest.main()
