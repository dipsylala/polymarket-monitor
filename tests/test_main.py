import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import detector
import main


class AlertAndWatchlistViewTests(unittest.TestCase):
    def test_alert_view_derives_fields(self):
        trade = {
            "proxyWallet": "0x1234567890abcdef1234567890abcdef12345678",
            "title": "Will X happen?",
            "slug": "will-x-happen",
            "price": "0.1",
            "size": "10000",
            "transactionHash": "0xabc123",
        }
        result = detector.ScoreResult(score=7, reasons=["low_odds($0.10/share)"])

        v = main._alert_view(trade, result)

        self.assertEqual(7, v.score)
        self.assertEqual("0x1234...5678", v.short_addr)
        self.assertEqual(1000.0, v.usdc_spent)
        self.assertEqual(9000.0, v.potential_profit)
        self.assertEqual(
            "https://polymarket.com/event/will-x-happen", v.market_url
        )

    def test_watchlist_hit_view_prefers_explicit_watchlist_address(self):
        # Regression: the step-summary renderer used to read only
        # trade["proxyWallet"], ignoring the enriched watchlist address —
        # this covers the case where they'd disagree (or proxyWallet is absent).
        trade = {
            "_watchlist_address": "0xAAAA000000000000000000000000000000AAAA",
            "_watchlist_label": "known insider",
            "title": "Watched market",
        }

        v = main._watchlist_hit_view(trade)

        self.assertEqual("0xAAAA...AAAA", v.short_addr)

    def test_format_alert_includes_key_fields(self):
        trade = {
            "proxyWallet": "0x1234567890abcdef1234567890abcdef12345678",
            "title": "Will X happen?",
            "price": "0.1",
            "size": "10000",
            "transactionHash": "0xabc123",
        }
        result = detector.ScoreResult(score=7, reasons=["low_odds($0.10/share)"])

        text = main._format_alert(trade, result)

        self.assertIn("Score=7", text)
        self.assertIn("0x1234...5678", text)
        self.assertIn("Will X happen?", text)

    def test_format_watchlist_hit_includes_key_fields(self):
        trade = {
            "_watchlist_address": "0xAAAA000000000000000000000000000000AAAA",
            "_watchlist_label": "known insider",
            "title": "Watched market",
            "price": "0.5",
            "size": "100",
            "transactionHash": "0xdef456",
        }

        text = main._format_watchlist_hit(trade)

        self.assertIn("0xAAAA...AAAA", text)
        self.assertIn("known insider", text)
        self.assertIn("Watched market", text)


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

    def test_summary_watchlist_row_uses_watchlist_address(self):
        # Regression: this row used to render an empty wallet link whenever
        # the raw trade lacked a top-level "proxyWallet" key.
        with tempfile.NamedTemporaryFile(delete=False) as summary_file:
            summary_path = summary_file.name

        env = {"GITHUB_STEP_SUMMARY": summary_path}
        try:
            with patch.dict(os.environ, env, clear=True):
                main._write_step_summary(
                    alerts_data=[],
                    clusters_data=[],
                    watchlist_hits_data=[
                        {
                            "_watchlist_address": "0xAAAA000000000000000000000000000000AAAA",
                            "_watchlist_label": "known insider",
                            "title": "Watched market",
                        }
                    ],
                )

            with open(summary_path, encoding="utf-8") as summary_file:
                summary = summary_file.read()
        finally:
            os.unlink(summary_path)

        self.assertIn("0xAAAA...AAAA", summary)


if __name__ == "__main__":
    unittest.main()
