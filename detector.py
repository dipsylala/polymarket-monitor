"""
detector.py — Core logic for detecting suspicious trading patterns.
"""

import logging
from typing import Dict, List

import polymarket
import database

logger = logging.getLogger(__name__)

class ScoreResult:
    """
    Encapsulates the result of a scoring operation.
    """
    def __init__(self, score: int, signals: List[str]):
        self.score = score
        self.signals = signals

    def is_suspicious(self, threshold: int = 7) -> bool:
        return self.score >= threshold

def analyze_wallet_trading_behavior(wallet: str) -> ScoreResult:
    """
    Analyze a wallet's trading history for suspicious signals.
    """
    signals = []
    score = 0

    # Fetch wallet history
    if not database.has_wallet_data(wallet):
        trades = polymarket.get_wallet_trading_history(wallet, limit=100)
        database.store_wallet_trades(wallet, trades)
    else:
        trades = database.get_wallet_trades(wallet)

    # Signal: new_wallet(no_history)
    if len(trades) == 0:
        signals.append("new_wallet(no_history)")
        score += 3
    else:
        # Signal: low_history(1_trades)
        if len(trades) < config.MIN_HISTORY_TRADES:
            signals.append(f"low_history({len(trades)}_trades)")
            score += 2

        # Signal: single_market
        market_ids = {t["market"] for t in trades}
        if len(market_ids) <= config.ALLOWED_MARKETS_PER_WALLET:
            signals.append("single_market")
            score += 2

    # Signal: funding_unknown (cannot trace origin of funds)
    # We assume we cannot verify funding sources for now
    signals.append("funding_unknown")
    score += 1

    return ScoreResult(score=score, signals=signals)

def detect_suspicious_trade(market: dict, trade: dict) -> Dict:
    """
    Evaluate a single trade for suspicious activity.
    Returns alert dict if suspicious, None otherwise.
    """
    market_question = market["question"]
    price = trade["price"]
    wallet = trade["trader"]
    direction = trade["type"]  # "buy" or "sell"
    shares = trade["quantity"]

    # Only analyze buy orders on YES shares
    if direction != "buy":
        return None

    # Focus on low-odds markets
    if price > config.MIN_SHARE_PRICE_SUSPICIOUS:
        return None

    # Analyze wallet
    wallet_analysis = analyze_wallet_trading_behavior(wallet)

    # Check if this trade exceeds threshold
    if shares > config.MAX_ALLOWED_NEW_WALLET_SHARES:
        wallet_analysis.score += 3
        wallet_analysis.signals.append(f"large_position({shares}_shares)")

    # Build alert if suspicious
    if wallet_analysis.is_suspicious():
        return {
            "market": market_question,
            "wallet": wallet,
            "shares": f"{shares} YES @ ${price:.3f}",
            "usdc_spent": round(shares * price, 2),
            "potential_profit": round(shares * (1 - price), 2),
            "transaction": trade.get("transaction_hash", "unknown"),
            "signals": ", ".join(wallet_analysis.signals),
            "score": wallet_analysis.score,
        }

    return None

def scan_geopolitical_markets() -> List[Dict]:
    """
    Main entry point: scan all geopolitical markets for suspicious trades.
    """
    alerts = []
    markets = polymarket.get_geopolitical_markets()

    for market in markets:
        market_id = market["id"]
        logger.debug("Scanning market: %s", market["question"])

        # Fetch recent trades
        if not database.has_wallet_data(market_id):
            trades = polymarket.get_trades_for_market(market_id, limit=50)
            database.store_market_trades(market_id, trades)
        else:
            trades = database.get_market_trades(market_id)

        # Analyze each trade
        for trade in trades:
            alert = detect_suspicious_trade(market, trade)
            if alert:
                alerts.append(alert)

    return alerts