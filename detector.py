"""
detector.py — Wallet anomaly scoring and cluster detection.

Scoring model
-------------
Each signal contributes points toward a total risk score.
A wallet that reaches ALERT_SCORE_THRESHOLD is emitted as an alert.

Signal                                  Points
------                                  ------
Wallet first tx < WALLET_AGE_DAYS ago     +3
Last USDC inbound < FUNDING_RECENCY_HOURS +3
Prior Polymarket trades < LOW_HISTORY      +2
Only one distinct market ever traded       +2
Trade price < LOW_ODDS_PRICE               +1
USDC spent on trade > LARGE_BET_USDC       +1
                                           --
Max possible                               12

Cluster detection
-----------------
If CLUSTER_MIN_WALLETS or more distinct wallets each cross the alert threshold
on the *same* market within CLUSTER_WINDOW_HOURS, a cluster warning is emitted.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import config
import database

logger = logging.getLogger(__name__)


@dataclass
class ScoreResult:
    score: int
    reasons: list[str] = field(default_factory=list)

    @property
    def is_alert(self) -> bool:
        return self.score >= config.ALERT_SCORE_THRESHOLD


def score_wallet(
    address: str,
    trade_price: float,
    trade_size: float,
    first_tx_ts: Optional[int],
    last_funded_ts: Optional[int],
    prior_trade_count: int,
    distinct_markets: int,
) -> ScoreResult:
    """
    Score a single wallet based on the signals defined in the plan.

    Parameters
    ----------
    address          : proxy wallet address (for logging only)
    trade_price      : price per share of the trade being evaluated (0–1)
    trade_size       : number of shares bought
    first_tx_ts      : Unix timestamp of first on-chain transaction
    last_funded_ts   : Unix timestamp of most recent inbound USDC
    prior_trade_count: total Polymarket trades (all markets, all time)
    distinct_markets : number of distinct Polymarket markets ever traded
    """
    now = int(time.time())
    score = 0
    reasons: list[str] = []

    # ── Signal 1: New wallet ──────────────────────────────────────────────────
    if first_tx_ts is not None:
        age_days = (now - first_tx_ts) / 86400
        if age_days < config.WALLET_AGE_DAYS:
            score += 3
            reasons.append(f"new_wallet({int(age_days)}d)")
    else:
        # No on-chain history at all — treat as brand-new
        score += 3
        reasons.append("new_wallet(no_history)")

    # ── Signal 2: Recently funded ─────────────────────────────────────────────
    if last_funded_ts is not None:
        funded_hours_ago = (now - last_funded_ts) / 3600
        if funded_hours_ago < config.FUNDING_RECENCY_HOURS:
            score += 3
            reasons.append(f"funded_{int(funded_hours_ago)}h_ago")
    else:
        # Can't determine funding — slight uplift (uncertainty)
        score += 1
        reasons.append("funding_unknown")

    # ── Signal 3: Low trade history ───────────────────────────────────────────
    if prior_trade_count < config.LOW_HISTORY_TRADES:
        score += 2
        reasons.append(f"low_history({prior_trade_count}_trades)")

    # ── Signal 4: Single-market trader ───────────────────────────────────────
    if distinct_markets <= config.SINGLE_MARKET_THRESHOLD:
        score += 2
        reasons.append("single_market")

    # ── Signal 5: Low odds (bet at low probability) ───────────────────────────
    if trade_price < config.LOW_ODDS_PRICE:
        score += 1
        reasons.append(f"low_odds(${trade_price:.2f}/share)")

    # ── Signal 6: Large bet ───────────────────────────────────────────────────
    usdc_spent = trade_price * trade_size
    if usdc_spent > config.LARGE_BET_USDC:
        score += 1
        reasons.append(f"large_bet(${usdc_spent:,.0f})")

    result = ScoreResult(score=score, reasons=reasons)
    logger.debug(
        "Scored wallet %s: %d %s",
        address[:10] + "...",
        score,
        reasons,
    )
    return result


def process_trade(trade: dict, wallet_data: dict) -> Optional[ScoreResult]:
    """
    Score a trade + its wallet info, persist alert if threshold met,
    and return the ScoreResult.

    Parameters
    ----------
    trade       : dict from Data API (proxyWallet, conditionId, price, size, etc.)
    wallet_data : dict with keys: first_tx_ts, last_funded_ts, prior_trade_count,
                  distinct_markets (populated by scheduler from poly + polygonscan)
    """
    address = trade["proxyWallet"]
    price = float(trade.get("price", 0))
    size = float(trade.get("size", 0))
    condition_id = trade.get("conditionId", "")
    tx_hash = trade.get("transactionHash", "")

    result = score_wallet(
        address=address,
        trade_price=price,
        trade_size=size,
        first_tx_ts=wallet_data.get("first_tx_ts"),
        last_funded_ts=wallet_data.get("last_funded_ts"),
        prior_trade_count=wallet_data.get("prior_trade_count", 0),
        distinct_markets=wallet_data.get("distinct_markets", 0),
    )

    if result.is_alert:
        database.insert_alert(
            wallet_address=address,
            condition_id=condition_id,
            tx_hash=tx_hash,
            score=result.score,
            reasons=json.dumps(result.reasons),
        )

    database.mark_trade_scored(tx_hash)
    return result


def detect_clusters(condition_id: str) -> Optional[list[str]]:
    """
    Check whether CLUSTER_MIN_WALLETS or more distinct wallets have been
    flagged on the same market within CLUSTER_WINDOW_HOURS.

    Returns a list of wallet addresses in the cluster if detected, else None.
    """
    since_ts = int(time.time()) - config.CLUSTER_WINDOW_HOURS * 3600
    recent_alerts = database.get_recent_alerts(condition_id, since_ts)

    wallets = list({row["wallet_address"] for row in recent_alerts})
    if len(wallets) >= config.CLUSTER_MIN_WALLETS:
        return wallets
    return None
