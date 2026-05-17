"""
database.py — Lightweight in-memory state tracking for wallet activity.

In production, this would connect to Redis or a relational DB.
For now, we use a simple dictionary-based cache.
"""

from typing import Dict, List, Optional

# Simulated in-memory storage
_wallet_trades: Dict[str, List[dict]] = {}
_market_trades: Dict[str, List[dict]] = {}

def store_wallet_trades(wallet: str, trades: List[dict]) -> None:
    """
    Store recent trades for a wallet.
    """
    _wallet_trades[wallet] = trades

def get_wallet_trades(wallet: str) -> List[dict]:
    """
    Retrieve stored trades for a wallet.
    """
    return _wallet_trades.get(wallet, [])

def store_market_trades(market_id: str, trades: List[dict]) -> None:
    """
    Store recent trades for a market.
    """
    _market_trades[market_id] = trades

def get_market_trades(market_id: str) -> List[dict]:
    """
    Retrieve stored trades for a market.
    """
    return _market_trades.get(market_id, [])

def has_wallet_data(wallet: str) -> bool:
    """
    Check if we have cached data for this wallet.
    """
    return wallet in _wallet_trades