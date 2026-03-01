"""
tests/test_detector.py — Unit tests for the scoring model.

Scenarios covered
-----------------
TRUE POSITIVES (should fire alerts):
  - Iran strike incident  (Feb 2026): new wallet, funded <48h, low odds, large bet
  - Venezuela/Maduro incident (Jan 2026): new wallet, funded <48h, low odds, large bet
  - ZachXBT/Axiom incident (Feb 2026): same wallet signals, low-odds bet on investigation market

TRUE NEGATIVES (should NOT fire alerts):
  - High-odds bet ($0.98/share) from a new funded wallet → suppressed (no trade-quality signal)
  - Established wallet (>30d) with many trades betting low odds → score below threshold
  - New wallet, large bet, but at high odds → large_bet passes quality gate (not suppressed)

KEYWORD FILTER TESTS:
  - All four incident market titles must be caught by keyword matching
  - Sports / entertainment markets must be excluded
"""

import time
import unittest

import config
from detector import score_wallet


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> int:
    return int(time.time())


def _days_ago(days: float) -> int:
    return _now() - int(days * 86400)


def _hours_ago(hours: float) -> int:
    return _now() - int(hours * 3600)


# ── True positive tests ───────────────────────────────────────────────────────

class TestIranStrikeProfile(unittest.TestCase):
    """
    Feb 2026 US-Iran strike incident.
    conditionId: (to be confirmed via API — not publicly reported)
    One wallet: ~560,000 YES shares @ $0.108, ~$60,800 USDC spent.
    Another wallet: ~150,000 YES shares @ $0.20.
    Test uses the larger wallet; 27 days old, funded ~24h before trades.
    Expected: score=12, is_alert=True.
    """

    def setUp(self):
        self.result = score_wallet(
            address="0xABCD1234abcd1234abcd1234abcd1234abcd1234",
            trade_price=0.108,
            trade_size=560_680,       # ~$60,800 USDC
            first_tx_ts=_days_ago(27),
            last_funded_ts=_hours_ago(24),
            prior_trade_count=0,
            distinct_markets=1,
        )

    def test_is_alert(self):
        self.assertTrue(self.result.is_alert)

    def test_score(self):
        self.assertEqual(self.result.score, 12)

    def test_new_wallet_signal(self):
        self.assertTrue(any(r.startswith("new_wallet") for r in self.result.reasons))

    def test_funded_signal(self):
        self.assertTrue(any(r.startswith("funded_") for r in self.result.reasons))

    def test_low_history_signal(self):
        self.assertTrue(any(r.startswith("low_history") for r in self.result.reasons))

    def test_single_market_signal(self):
        self.assertIn("single_market", self.result.reasons)

    def test_low_odds_signal(self):
        self.assertTrue(any(r.startswith("low_odds") for r in self.result.reasons))

    def test_large_bet_signal(self):
        self.assertTrue(any(r.startswith("large_bet") for r in self.result.reasons))


class TestMaduroProfile(unittest.TestCase):
    """
    Jan 2026 Venezuela/Maduro removal incident.
    conditionId: 0x85e324091c717c527c4bfa633109ba83c9b9d49b7d003182fe39756d7c1197b6
    Market title: "Maduro out by January 31, 2026?"
    Brand-new wallet (no on-chain history), funded hours before trade.
    ~$50,000 wagered at ~7 cents per share (714,285 shares).
    Expected: score=12 (max), is_alert=True.
    """
    CONDITION_ID = "0x85e324091c717c527c4bfa633109ba83c9b9d49b7d003182fe39756d7c1197b6"

    def setUp(self):
        self.result = score_wallet(
            address="0xBEEF5678beef5678beef5678beef5678beef5678",
            trade_price=0.07,
            trade_size=714_285,       # ~$50,000 / $0.07
            first_tx_ts=None,         # brand-new — no on-chain history
            last_funded_ts=_hours_ago(6),
            prior_trade_count=0,
            distinct_markets=1,
        )

    def test_is_alert(self):
        self.assertTrue(self.result.is_alert)

    def test_max_score(self):
        self.assertEqual(self.result.score, 12)

    def test_no_history_signal(self):
        self.assertIn("new_wallet(no_history)", self.result.reasons)

    def test_low_odds_signal(self):
        self.assertTrue(any(r.startswith("low_odds") for r in self.result.reasons))

    def test_large_bet_signal(self):
        self.assertTrue(any(r.startswith("large_bet") for r in self.result.reasons))


class TestZachXBTAxiomProfile(unittest.TestCase):
    """
    Feb 2026 ZachXBT/Axiom investigation incident.
    Market: "Which crypto company will ZachXBT expose for insider trading?"
    Wallet: 0xe31b852756937aef6a047b8de0d36196804b3fb7 (reported by Lookonchain)
    ~$50,700 wagered at ~15.1 cents per share (~335,000 shares).
    Trades occurred in a ~3-hour window before public announcement.
    Expected: score=12, is_alert=True.
    """
    WALLET = "0xe31b852756937aef6a047b8de0d36196804b3fb7"

    def setUp(self):
        self.result = score_wallet(
            address=self.WALLET,
            trade_price=0.151,
            trade_size=335_762,       # ~$50,700 / $0.151
            first_tx_ts=None,         # brand-new
            last_funded_ts=_hours_ago(3),
            prior_trade_count=0,
            distinct_markets=1,
        )

    def test_is_alert(self):
        self.assertTrue(self.result.is_alert)

    def test_max_score(self):
        self.assertEqual(self.result.score, 12)

    def test_all_signals_present(self):
        reasons = self.result.reasons
        self.assertIn("new_wallet(no_history)", reasons)
        self.assertTrue(any(r.startswith("funded_") for r in reasons))
        self.assertTrue(any(r.startswith("low_history") for r in reasons))
        self.assertIn("single_market", reasons)
        self.assertTrue(any(r.startswith("low_odds") for r in reasons))
        self.assertTrue(any(r.startswith("large_bet") for r in reasons))


# ── True negative tests ───────────────────────────────────────────────────────

class TestHighOddsBetSuppressed(unittest.TestCase):
    """
    Wallet seen in live run: new wallet, funded <48h, BUT betting at $0.98/share.
    This is a near-certainty bet with no directional insider edge.
    Wallet: 0x110edef01810239c23307ad3d4373e48bc9e8b11 (observed in production)
    Market: "Will US or Israel strike Iran on March 2, 2026?"
    Expected: suppressed (score=0, is_alert=False).
    """

    def setUp(self):
        self.result = score_wallet(
            address="0x110edef01810239c23307ad3d4373e48bc9e8b11",
            trade_price=0.98,
            trade_size=2_000,         # $1,960 spent — above MIN_BET_USDC
            first_tx_ts=_days_ago(2),
            last_funded_ts=_hours_ago(7),
            prior_trade_count=0,
            distinct_markets=1,
        )

    def test_not_alert(self):
        self.assertFalse(self.result.is_alert)

    def test_score_is_zero(self):
        self.assertEqual(self.result.score, 0)

    def test_suppression_reason(self):
        self.assertIn("suppressed_no_trade_quality", self.result.reasons)


class TestEstablishedWalletLowOdds(unittest.TestCase):
    """
    Experienced trader: wallet 120 days old, funded 2 weeks ago, 50 prior trades
    across 15 markets. Makes a low-odds large bet — missing all wallet signals.
    Expected: is_alert=False (score below threshold).
    """

    def setUp(self):
        self.result = score_wallet(
            address="0xDEAD0000dead0000dead0000dead0000dead0000",
            trade_price=0.12,
            trade_size=50_000,        # $6,000 — triggers large_bet
            first_tx_ts=_days_ago(120),
            last_funded_ts=_hours_ago(14 * 24),  # 2 weeks ago
            prior_trade_count=50,
            distinct_markets=15,
        )

    def test_not_alert(self):
        self.assertFalse(self.result.is_alert)

    def test_no_new_wallet_signal(self):
        self.assertFalse(any(r.startswith("new_wallet") for r in self.result.reasons))

    def test_no_funded_signal(self):
        self.assertFalse(any(r.startswith("funded_") for r in self.result.reasons))

    def test_no_low_history_signal(self):
        self.assertFalse(any(r.startswith("low_history") for r in self.result.reasons))

    def test_no_single_market_signal(self):
        self.assertNotIn("single_market", self.result.reasons)


class TestNewWalletHighOddsLargeBet(unittest.TestCase):
    """
    New wallet bets $10k at $0.95/share — large_bet qualifies as trade-quality signal
    so suppression does NOT apply. Verifies large_bet alone passes the gate.
    """

    def setUp(self):
        self.result = score_wallet(
            address="0xF00D1111f00d1111f00d1111f00d1111f00d1111",
            trade_price=0.95,
            trade_size=11_000,        # $10,450 → triggers large_bet
            first_tx_ts=None,
            last_funded_ts=_hours_ago(10),
            prior_trade_count=0,
            distinct_markets=1,
        )

    def test_large_bet_passes_quality_gate(self):
        self.assertNotIn("suppressed_no_trade_quality", self.result.reasons)

    def test_large_bet_reason_present(self):
        self.assertTrue(any(r.startswith("large_bet") for r in self.result.reasons))

    def test_no_low_odds_reason(self):
        self.assertFalse(any(r.startswith("low_odds") for r in self.result.reasons))


# ── Keyword filter tests ──────────────────────────────────────────────────────

class TestKeywordFilter(unittest.TestCase):
    """
    Verify that all four real incident market titles are caught, and that
    unrelated markets are excluded.
    """

    def _matches(self, question: str) -> bool:
        q = question.lower()
        return (
            any(kw in q for kw in config.GEOPOLITICAL_KEYWORDS) or
            any(kw in q for kw in config.INVESTIGATION_KEYWORDS)
        )

    # ── Real incident titles ──────────────────────────────────────────────────

    def test_iran_strike_market(self):
        self.assertTrue(self._matches("Will US or Israel strike Iran on March 2, 2026?"))

    def test_maduro_short_title(self):
        # Actual Polymarket title — does NOT contain "president"
        self.assertTrue(self._matches("Maduro out by January 31, 2026?"))

    def test_maduro_long_title(self):
        # Alternative full phrasing
        self.assertTrue(self._matches("Will Venezuelan President Nicolás Maduro be removed from office by February 2026?"))

    def test_zachxbt_investigation_market(self):
        self.assertTrue(self._matches("Which crypto company will ZachXBT expose for insider trading?"))

    # ── General coverage ─────────────────────────────────────────────────────

    def test_generic_war_market(self):
        self.assertTrue(self._matches("Will Russia declare war on a NATO member in 2026?"))

    def test_sec_enforcement_market(self):
        self.assertTrue(self._matches("Will the SEC charge Binance with fraud in 2026?"))

    def test_resignation_market(self):
        self.assertTrue(self._matches("Will Prime Minister X resign before March 2026?"))

    # ── True negatives ────────────────────────────────────────────────────────

    def test_sports_market_excluded(self):
        self.assertFalse(self._matches("Who will win the NBA championship in 2026?"))

    def test_entertainment_market_excluded(self):
        self.assertFalse(self._matches("Will Taylor Swift release a new album in 2026?"))

    def test_unrelated_market_excluded(self):
        self.assertFalse(self._matches("Will the Super Bowl go to overtime in 2026?"))


if __name__ == "__main__":
    unittest.main()



# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> int:
    return int(time.time())


def _days_ago(days: float) -> int:
    return _now() - int(days * 86400)


def _hours_ago(hours: float) -> int:
    return _now() - int(hours * 3600)


# ── True positive tests ───────────────────────────────────────────────────────

class TestIranStrikeProfile(unittest.TestCase):
    """
    Feb 2026 US-Iran strike incident.
    Wallet: 27 days old, funded 24h ago, 0 prior trades, 1 market, $0.108/share, ~$60k spent.
    Expected: score=10, is_alert=True.
    """

    def setUp(self):
        self.result = score_wallet(
            address="0xABCD1234abcd1234abcd1234abcd1234abcd1234",
            trade_price=0.108,
            trade_size=560_680,
            first_tx_ts=_days_ago(27),
            last_funded_ts=_hours_ago(24),
            prior_trade_count=0,
            distinct_markets=1,
        )

    def test_is_alert(self):
        self.assertTrue(self.result.is_alert)

    def test_score(self):
        self.assertEqual(self.result.score, 12)

    def test_new_wallet_signal(self):
        self.assertTrue(any(r.startswith("new_wallet") for r in self.result.reasons))

    def test_funded_signal(self):
        self.assertTrue(any(r.startswith("funded_") for r in self.result.reasons))

    def test_low_history_signal(self):
        self.assertTrue(any(r.startswith("low_history") for r in self.result.reasons))

    def test_single_market_signal(self):
        self.assertIn("single_market", self.result.reasons)

    def test_low_odds_signal(self):
        self.assertTrue(any(r.startswith("low_odds") for r in self.result.reasons))

    def test_large_bet_signal(self):
        self.assertTrue(any(r.startswith("large_bet") for r in self.result.reasons))


class TestMaduroProfile(unittest.TestCase):
    """
    Jan 2026 Venezuela/Maduro removal incident.
    Brand-new wallet (no on-chain history), funded hours ago, ~$32k at $0.07/share.
    Expected: score=12 (max), is_alert=True.
    """

    def setUp(self):
        self.result = score_wallet(
            address="0xBEEF5678beef5678beef5678beef5678beef5678",
            trade_price=0.07,
            trade_size=457_143,       # ~$32k / $0.07
            first_tx_ts=None,         # brand-new — no on-chain history
            last_funded_ts=_hours_ago(6),
            prior_trade_count=0,
            distinct_markets=1,
        )

    def test_is_alert(self):
        self.assertTrue(self.result.is_alert)

    def test_max_score(self):
        self.assertEqual(self.result.score, 12)

    def test_no_history_signal(self):
        self.assertIn("new_wallet(no_history)", self.result.reasons)

    def test_low_odds_signal(self):
        self.assertTrue(any(r.startswith("low_odds") for r in self.result.reasons))

    def test_large_bet_signal(self):
        self.assertTrue(any(r.startswith("large_bet") for r in self.result.reasons))


class TestZachXBTAxiomProfile(unittest.TestCase):
    """
    Feb 2026 ZachXBT/Axiom investigation incident.
    Largest wallet: 477,415 shares at $0.14 average (~$66.8k spent).
    Brand-new wallet, funded hours before the bet.
    Expected: score=12, is_alert=True.
    """

    def setUp(self):
        self.result = score_wallet(
            address="0xCAFE9999cafe9999cafe9999cafe9999cafe9999",
            trade_price=0.14,
            trade_size=477_415,
            first_tx_ts=None,         # brand-new
            last_funded_ts=_hours_ago(3),
            prior_trade_count=0,
            distinct_markets=1,
        )

    def test_is_alert(self):
        self.assertTrue(self.result.is_alert)

    def test_max_score(self):
        self.assertEqual(self.result.score, 12)

    def test_all_signals_present(self):
        reasons = self.result.reasons
        self.assertIn("new_wallet(no_history)", reasons)
        self.assertTrue(any(r.startswith("funded_") for r in reasons))
        self.assertTrue(any(r.startswith("low_history") for r in reasons))
        self.assertIn("single_market", reasons)
        self.assertTrue(any(r.startswith("low_odds") for r in reasons))
        self.assertTrue(any(r.startswith("large_bet") for r in reasons))


# ── True negative tests ───────────────────────────────────────────────────────

class TestHighOddsBetSuppressed(unittest.TestCase):
    """
    Wallet seen in live run: new wallet, funded <48h, BUT betting at $0.98/share.
    This is a near-certainty bet with no directional insider edge.
    Expected: suppressed (score=0, is_alert=False).
    """

    def setUp(self):
        self.result = score_wallet(
            address="0x110edef01810239c23307ad3d4373e48bc9e8b11",
            trade_price=0.98,
            trade_size=2_000,         # $1,960 spent — above MIN_BET_USDC
            first_tx_ts=_days_ago(2),
            last_funded_ts=_hours_ago(7),
            prior_trade_count=0,
            distinct_markets=1,
        )

    def test_not_alert(self):
        self.assertFalse(self.result.is_alert)

    def test_score_is_zero(self):
        self.assertEqual(self.result.score, 0)

    def test_suppression_reason(self):
        self.assertIn("suppressed_no_trade_quality", self.result.reasons)


class TestEstablishedWalletLowOdds(unittest.TestCase):
    """
    Experienced trader: wallet 120 days old, funded 2 weeks ago, 50 prior trades
    across 15 markets. Makes a low-odds bet — not a new account, not recently
    funded, not low-history. Score should stay below threshold.
    Expected: is_alert=False.
    """

    def setUp(self):
        self.result = score_wallet(
            address="0xDEAD0000dead0000dead0000dead0000dead0000",
            trade_price=0.12,
            trade_size=50_000,        # $6,000 — triggers large_bet
            first_tx_ts=_days_ago(120),
            last_funded_ts=_hours_ago(14 * 24),  # 2 weeks ago
            prior_trade_count=50,
            distinct_markets=15,
        )

    def test_not_alert(self):
        self.assertFalse(self.result.is_alert)

    def test_no_new_wallet_signal(self):
        self.assertFalse(any(r.startswith("new_wallet") for r in self.result.reasons))

    def test_no_funded_signal(self):
        self.assertFalse(any(r.startswith("funded_") for r in self.result.reasons))

    def test_no_low_history_signal(self):
        self.assertFalse(any(r.startswith("low_history") for r in self.result.reasons))

    def test_no_single_market_signal(self):
        self.assertNotIn("single_market", self.result.reasons)


class TestNewWalletHighOddsLargeBet(unittest.TestCase):
    """
    New wallet bets $10k on a market at $0.95/share — high conviction but at
    near-certainty odds. Large bet signal fires but no low-odds; trade-quality
    gate is met (large_bet qualifies). However, without low_odds, this
    should only score on wallet signals + large_bet.
    Verifies large_bet alone is enough to pass the trade-quality gate.
    """

    def setUp(self):
        self.result = score_wallet(
            address="0xF00D1111f00d1111f00d1111f00d1111f00d1111",
            trade_price=0.95,
            trade_size=11_000,        # $10,450 → triggers large_bet
            first_tx_ts=None,
            last_funded_ts=_hours_ago(10),
            prior_trade_count=0,
            distinct_markets=1,
        )

    def test_large_bet_passes_quality_gate(self):
        # Should NOT be suppressed — large_bet is a trade-quality signal
        self.assertNotIn("suppressed_no_trade_quality", self.result.reasons)

    def test_large_bet_reason_present(self):
        self.assertTrue(any(r.startswith("large_bet") for r in self.result.reasons))

    def test_no_low_odds_reason(self):
        self.assertFalse(any(r.startswith("low_odds") for r in self.result.reasons))


# ── Keyword filter tests ──────────────────────────────────────────────────────

class TestGeopoliticalKeywords(unittest.TestCase):
    """Verify that known incident market questions are caught by keyword matching."""

    def _matches(self, question: str) -> bool:
        q = question.lower()
        return (
            any(kw in q for kw in config.GEOPOLITICAL_KEYWORDS) or
            any(kw in q for kw in config.INVESTIGATION_KEYWORDS)
        )

    def test_iran_strike_market(self):
        self.assertTrue(self._matches("Will US or Israel strike Iran on March 2, 2026?"))

    def test_maduro_removal_market(self):
        # Real Polymarket titles include "President" — which is in GEOPOLITICAL_KEYWORDS
        self.assertTrue(self._matches("Will Venezuelan President Nicolás Maduro be removed from office by February 2026?"))

    def test_zachxbt_investigation_market(self):
        self.assertTrue(self._matches("Which crypto company will ZachXBT expose for insider trading?"))

    def test_generic_war_market(self):
        self.assertTrue(self._matches("Will Russia declare war on a NATO member in 2026?"))

    def test_sec_enforcement_market(self):
        self.assertTrue(self._matches("Will the SEC charge Binance with fraud in 2026?"))

    def test_unrelated_market_excluded(self):
        self.assertFalse(self._matches("Will the Super Bowl go to overtime in 2026?"))

    def test_sports_market_excluded(self):
        self.assertFalse(self._matches("Who will win the NBA championship in 2026?"))

    def test_entertainment_market_excluded(self):
        self.assertFalse(self._matches("Will Taylor Swift release a new album in 2026?"))


if __name__ == "__main__":
    unittest.main()
