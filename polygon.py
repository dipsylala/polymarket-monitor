"""
polygon.py — Utilities for interacting with Polygon blockchain data.
"""

import logging

import requests

logger = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update({"Accept": "application/json"})

def get_transaction_details(tx_hash: str) -> dict:
    """
    Fetch transaction details from PolygonScan.
    """
    try:
        resp = _SESSION.get(
            "https://api.polygonscan.com/api