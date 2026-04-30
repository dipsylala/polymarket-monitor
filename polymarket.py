"""
polymarket.py — Clients for the Gamma API and Data API.

Both APIs are fully public (no authentication required).
"""

import logging
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update({"Accept": "application/json"})

# ── Gamma API ─────────────────────────────────────────────────────────────────

def get_geopolitical_markets() -> list[dict]:
    """
    Fetch active markets from the Gamma API and return those whose
    question text contains at least one geopolitical keyword.
    """
    markets: list[dict] = []
    offset = 0
    page_size = 500

    while True:
        try:
            resp = _SESSION.get(
                f"{config.GAMMA_API_URL}/markets",
                params={
                    "active": "true",
                    "closed": "false",
                    "limit": page_size,
                    "offset": offset,
                },
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Gamma API error fetching markets: %s", exc)
            break

        page: list[dict] = resp.json()
        if not page:
            break

        for market in page:
            question: str = market.get("question", "").lower()
            if (
                any(kw in question for kw in config.GEOPOLITICAL_KEYWORDS)
                or any(kw in question for kw in config.INVESTIGATION_KEYWORDS)
                or any(kw in question for kw in config.AIRPORT_KEYWORDS)
            ):
                markets.append(market)

        if len(page) < page_size:
            break

        offset += page_size
        logger.debug("Fetched %d markets so far (offset=%d)", len(markets), offset)

    logger.info("Found %d geopolitical markets", len(markets))
    return markets

# ── Data API ──────────────────────────────────────────────────────────────────

def get_trades_for_market(market_id: str, limit: int = 1000) -> list[dict]:
    """
    Fetch recent trades for a given market ID.
    """
    try:
        resp = _SESSION.get(
            f"{config.DATA_API_URL}/trades",
            params={
                "market": market_id,
                "limit": limit,
                "order_by": "timestamp",
                "sort_direction": "desc",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.error("Data API error fetching trades for market %s: %s", market_id, exc)
        return []

def get_wallet_trading_history(wallet: str, limit: int = 100) -> list[dict]:
    """
    Fetch trading history for a given wallet address.
    """
    try:
        resp = _SESSION.get(
            f"{config.DATA_API_URL}/trades",
            params={"trader": wallet, "limit": limit},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.error("Data API error fetching wallet history for %s: %s", wallet, exc)
        return []