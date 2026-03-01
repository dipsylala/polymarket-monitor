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
            if any(kw in question for kw in config.GEOPOLITICAL_KEYWORDS):
                markets.append(market)

        if len(page) < page_size:
            break

        offset += page_size
        logger.debug("Fetched %d markets so far (offset=%d)", len(markets), offset)

    logger.info("Found %d geopolitical markets", len(markets))
    return markets


# ── Data API ──────────────────────────────────────────────────────────────────

def get_recent_trades(since_ts: int, condition_ids: set[str]) -> list[dict]:
    """
    Fetch recent trades from the Data API and return those that:
      - belong to one of the watched condition IDs
      - have a timestamp >= since_ts
      - are BUY-side YES trades
      - have USDC spent (size * price) >= MIN_BET_USDC
    """
    results: list[dict] = []
    offset = 0
    page_size = 500
    exhausted = False

    while not exhausted:
        try:
            resp = _SESSION.get(
                f"{config.DATA_API_URL}/trades",
                params={"limit": page_size, "offset": offset},
                timeout=15,
            )
            if resp.status_code == 400:
                # API caps pagination; no more results available at this offset
                logger.debug("Data API pagination limit reached at offset=%d", offset)
                break
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Data API error fetching trades: %s", exc)
            break

        page: list[dict] = resp.json()
        if not page:
            break

        for trade in page:
            ts = trade.get("timestamp", 0)

            # Data API returns newest-first; stop paging once we go past since_ts
            if ts < since_ts:
                exhausted = True
                break

            condition_id = trade.get("conditionId", "")
            if condition_id not in condition_ids:
                continue

            if trade.get("side", "").upper() != "BUY":
                continue

            if trade.get("outcome", "").lower() != "yes":
                continue

            size = float(trade.get("size", 0))
            price = float(trade.get("price", 0))
            if size * price < config.MIN_BET_USDC:
                continue

            results.append(trade)

        if len(page) < page_size:
            break

        offset += page_size

    logger.info(
        "Found %d qualifying trades since ts=%d across %d markets",
        len(results), since_ts, len(condition_ids),
    )
    return results


def get_wallet_trade_history(address: str) -> tuple[int, int]:
    """
    Return (total_trade_count, distinct_market_count) for a given proxy wallet.
    Uses the Data API `trades` endpoint filtered by maker address.
    """
    total = 0
    markets: set[str] = set()
    offset = 0
    page_size = 500

    while True:
        try:
            resp = _SESSION.get(
                f"{config.DATA_API_URL}/trades",
                params={"maker": address, "limit": page_size, "offset": offset},
                timeout=15,
            )
            if resp.status_code == 400:
                logger.debug("Data API pagination limit reached for wallet %s at offset=%d", address, offset)
                break
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Data API error fetching wallet trades for %s: %s", address, exc)
            break

        page: list[dict] = resp.json()
        if not page:
            break

        for trade in page:
            total += 1
            cid = trade.get("conditionId")
            if cid:
                markets.add(cid)

        if len(page) < page_size:
            break

        offset += page_size

    return total, len(markets)
