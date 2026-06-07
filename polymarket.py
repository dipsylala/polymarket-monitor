"""
polymarket.py — Clients for the Gamma API and Data API.

Both APIs are fully public (no authentication required).
"""

import logging
import time
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update({"Accept": "application/json"})

_DATA_API_PAGE_SIZE = 500
_DATA_API_MAX_OFFSET = 3000
_DATA_API_MAX_ATTEMPTS = 3
_RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class TradeFetchError(RuntimeError):
    """Raised when a trade window cannot be fetched completely."""


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
            excluded = any(kw in question for kw in config.EXCLUDED_MARKET_KEYWORDS)
            if not excluded and (
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

def _get_trade_page(params: dict, context: str) -> list[dict]:
    """Fetch one Data API page, retrying transient failures."""
    last_error: Optional[Exception] = None

    for attempt in range(1, _DATA_API_MAX_ATTEMPTS + 1):
        try:
            resp = _SESSION.get(
                f"{config.DATA_API_URL}/trades",
                params=params,
                timeout=15,
            )
            if resp.status_code in _RETRYABLE_STATUS_CODES:
                raise requests.HTTPError(
                    f"HTTP {resp.status_code}: {resp.text[:200]}",
                    response=resp,
                )
            resp.raise_for_status()
            page = resp.json()
            if not isinstance(page, list):
                raise TradeFetchError(
                    f"Data API returned an unexpected payload for {context}"
                )
            return page
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt == _DATA_API_MAX_ATTEMPTS:
                break
            delay = 2 ** (attempt - 1)
            logger.warning(
                "Data API error fetching %s (attempt %d/%d): %s; retrying in %ds",
                context,
                attempt,
                _DATA_API_MAX_ATTEMPTS,
                exc,
                delay,
            )
            time.sleep(delay)

    raise TradeFetchError(
        f"Data API failed while fetching {context}: {last_error}"
    ) from last_error


def get_recent_trades(since_by_market: dict[str, int]) -> list[dict]:
    """
    Fetch recent trades from the Data API and return those that:
      - belong to one of the watched condition IDs
      - have a timestamp >= that market's last successful scan
      - are BUY-side YES trades
      - have USDC spent (size * price) >= MIN_BET_USDC

    Each market is queried separately. The platform-wide feed can contain more
    than the Data API's 3,000-record pagination window in a few seconds, and
    comma-separated market filters currently time out. Server-side side and
    cash filters keep each individual market window small.

    Raises TradeFetchError rather than returning partial data. Callers must not
    advance scan timestamps after this exception.
    """
    results: list[dict] = []
    for condition_id in sorted(since_by_market):
        since_ts = since_by_market[condition_id]
        offset = 0

        while True:
            params = {
                "market": condition_id,
                "limit": _DATA_API_PAGE_SIZE,
                "offset": offset,
                "takerOnly": "false",
                "side": "BUY",
                "filterType": "CASH",
                "filterAmount": config.MIN_BET_USDC,
            }
            page = _get_trade_page(
                params,
                context=f"market {condition_id} at offset {offset}",
            )
            if not page:
                break

            reached_previous_scan = False
            for trade in page:
                try:
                    ts = int(trade.get("timestamp", 0))
                except (TypeError, ValueError):
                    logger.warning(
                        "Skipping trade with invalid timestamp on market %s",
                        condition_id,
                    )
                    continue

                # Data API returns newest-first for a single market.
                if ts < since_ts:
                    reached_previous_scan = True
                    break

                if trade.get("conditionId", "") != condition_id:
                    continue
                if trade.get("side", "").upper() != "BUY":
                    continue
                if trade.get("outcome", "").lower() != "yes":
                    continue

                try:
                    size = float(trade.get("size", 0))
                    price = float(trade.get("price", 0))
                except (TypeError, ValueError):
                    logger.warning(
                        "Skipping trade with invalid size/price on market %s",
                        condition_id,
                    )
                    continue
                if size * price < config.MIN_BET_USDC:
                    continue

                results.append(trade)

            if reached_previous_scan or len(page) < _DATA_API_PAGE_SIZE:
                break

            next_offset = offset + _DATA_API_PAGE_SIZE
            if next_offset > _DATA_API_MAX_OFFSET:
                raise TradeFetchError(
                    "Data API pagination limit reached before the previous "
                    f"scan for market {condition_id} (since_ts={since_ts})"
                )
            offset = next_offset

    logger.info(
        "Found %d qualifying trades across %d markets",
        len(results),
        len(since_by_market),
    )
    return results


def get_wallet_trade_history(address: str) -> tuple[int, int]:
    """
    Return (total_trade_count, distinct_market_count) for a given proxy wallet.
    Uses the Data API `trades` endpoint filtered by user address.
    """
    total = 0
    markets: set[str] = set()
    offset = 0
    page_size = 500

    while True:
        try:
            resp = _SESSION.get(
                f"{config.DATA_API_URL}/trades",
                params={"user": address, "limit": page_size, "offset": offset, "takerOnly": "false"},
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


def get_watchlist_recent_trades(address: str, since_ts: int) -> list[dict]:
    """
    Return all trades by `address` since `since_ts`, across any market.
    Unlike get_recent_trades, no keyword or condition_id filtering is applied —
    watchlisted wallets are monitored on every market they touch.
    """
    results: list[dict] = []
    offset = 0
    page_size = 500
    exhausted = False

    while not exhausted:
        try:
            resp = _SESSION.get(
                f"{config.DATA_API_URL}/trades",
                params={"user": address, "limit": page_size, "offset": offset, "takerOnly": "false"},
                timeout=15,
            )
            if resp.status_code == 400:
                logger.debug(
                    "Data API pagination limit for watchlist wallet %s at offset=%d",
                    address, offset,
                )
                break
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Data API error fetching watchlist trades for %s: %s", address, exc)
            break

        page: list[dict] = resp.json()
        if not page:
            break

        for trade in page:
            ts = trade.get("timestamp", 0)
            if ts < since_ts:
                exhausted = True
                break
            results.append(trade)

        if len(page) < page_size:
            break

        offset += page_size

    logger.debug("Found %d watchlist trades for %s since ts=%d", len(results), address[:10] + "...", since_ts)
    return results
