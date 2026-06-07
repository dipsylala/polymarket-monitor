import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import main


class PrivateIssueRoutingTests(unittest.TestCase):
    @patch.object(main.requests, "post")
    def test_creates_issue_in_configured_repository(self, post):
        response = Mock()
        response.ok = True
        response.json.return_value = {
            "html_url": "https://github.com/owner/private/issues/1"
        }
        post.return_value = response

        env = {
            "ALERT_REPOSITORY": "owner/private",
            "ALERT_REPO_TOKEN": "secret-token",
        }
        with patch.dict(os.environ, env, clear=True):
            main._create_github_issue("Alert title", "Alert body")

        post.assert_called_once()
        call = post.call_args
        self.assertEqual(
            "https://api.github.com/repos/owner/private/issues",
            call.args[0],
        )
        self.assertEqual(
            "Bearer secret-token",
            call.kwargs["headers"]["Authorization"],
        )
        self.assertEqual(
            {"title": "Alert title", "body": "Alert body"},
            call.kwargs["json"],
        )

    @patch.object(main.requests, "post")
    def test_does_not_fall_back_to_public_repository_token(self, post):
        env = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": "owner/public",
            "GITHUB_TOKEN": "public-token",
        }
        with patch.dict(os.environ, env, clear=True):
            main._create_github_issue("Alert title", "Alert body")

        post.assert_not_called()

    def test_actions_run_fails_before_scan_without_private_token(self):
        env = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": "owner/public",
            "ALERT_REPOSITORY": "owner/private",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(RuntimeError, "ALERT_REPO_TOKEN"):
                main._validate_alert_routing()

    def test_actions_routing_configuration_is_valid(self):
        env = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": "owner/public",
            "ALERT_REPOSITORY": "owner/private",
            "ALERT_REPO_TOKEN": "secret-token",
        }
        with patch.dict(os.environ, env, clear=True):
            main._validate_alert_routing()

    def test_public_actions_summary_redacts_alert_details(self):
        with tempfile.NamedTemporaryFile(delete=False) as summary_file:
            summary_path = summary_file.name

        env = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": "owner/public",
            "GITHUB_STEP_SUMMARY": summary_path,
            "ALERT_REPOSITORY": "owner/private",
        }
        try:
            with patch.dict(os.environ, env, clear=True):
                main._write_step_summary(
                    alerts_data=[({"title": "Sensitive market"}, Mock())],
                    clusters_data=[],
                    watchlist_hits_data=[],
                )

            with open(summary_path, encoding="utf-8") as summary_file:
                summary = summary_file.read()
        finally:
            os.unlink(summary_path)

        self.assertIn("1 alert(s)", summary)
        self.assertIn("private alert repository", summary)
        self.assertNotIn("Sensitive market", summary)


if __name__ == "__main__":
    unittest.main()
