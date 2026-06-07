"""
polygon.py — Etherscan API V2 client for Polygon on-chain wallet data.

Used to determine:
  - When a proxy wallet was first active on Polygon (wallet age)
  - When it last received a USDC deposit (recently funded signal)

Rate-limited to ETHERSCAN_REQ_PER_SEC to stay inside the free tier (3 req/s).
"""

import logging
import time
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update({"Accept": "application/json"})

_last_request_ts: float = 0.0


def _throttle() -> None:
    """Enforce the configured per-second rate limit."""
    global _last_request_ts
    min_gap = 1.0 / config.ETHERSCAN_REQ_PER_SEC
    elapsed = time.monotonic() - _last_request_ts
    if elapsed < min_gap:
        time.sleep(min_gap - elapsed)
    _last_request_ts = time.monotonic()


def _get(params: dict) -> Optional[dict]:
    """Execute an Etherscan API V2 call and return parsed JSON, or None on error."""
    if not config.ETHERSCAN_API_KEY:
        logger.warning("ETHERSCAN_API_KEY not set; skipping on-chain lookup")
        return None

    _throttle()
    params["apikey"] = config.ETHERSCAN_API_KEY
    params["chainid"] = config.ETHERSCAN_CHAIN_ID

    try:
        resp = _SESSION.get(config.ETHERSCAN_API_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.error("Etherscan request error: %s", exc)
        return None

    if data.get("status") != "1":
        # Preserve a confirmed empty result so callers can distinguish a new
        # wallet from a missing key or failed lookup.
        msg = data.get("message", "")
        if "No transactions found" in msg:
            return data
        logger.debug("Etherscan non-success: %s", data.get("message"))
        return None

    return data


def get_wallet_first_tx(address: str) -> Optional[int]:
    """
    Return the Unix timestamp of the wallet's first Polygon transaction,
    0 if the API confirms no transactions exist, or None if the lookup could
    not be completed.

    The first transaction timestamp serves as a reliable "wallet age" proxy
    because Polymarket proxy wallets are created on-chain at first use.
    """
    data = _get({
        "module": "account",
        "action": "txlist",
        "address": address,
        "startblock": "0",
        "endblock": "99999999",
        "page": "1",
        "offset": "1",        # only need the very first tx
        "sort": "asc",
    })
    if data is None:
        return None

    txns: list[dict] = data.get("result", [])
    if not txns:
        return 0

    try:
        return int(txns[0]["timeStamp"])
    except (KeyError, ValueError):
        return None


def get_wallet_last_usdc_in(address: str) -> Optional[int]:
    """
    Return the Unix timestamp of the most recent inbound USDC transfer to
    this wallet, or None if no transfers exist.

    Filters token transfer events on the Polygon USDC contract
    (0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174) where `to == address`.
    """
    data = _get({
        "module": "account",
        "action": "tokentx",
        "address": address,
        "contractaddress": config.USDC_CONTRACT,
        "page": "1",
        "offset": "50",       # most recent 50 token transfers
        "sort": "desc",
    })
    if not data:
        return None

    txns: list[dict] = data.get("result", [])
    for tx in txns:
        if tx.get("to", "").lower() == address.lower():
            try:
                return int(tx["timeStamp"])
            except (KeyError, ValueError):
                continue

    return None
