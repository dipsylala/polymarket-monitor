"""
database.py — SQLite persistence layer.

Tables
------
markets       : geopolitical markets being monitored
trades        : individual trades seen during each scan
wallets       : wallet metadata fetched from Polymarket + PolygonScan
alerts        : scored wallets that crossed the alert threshold
"""

import sqlite3
import time
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "polymarket_monitor.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS markets (
                condition_id   TEXT PRIMARY KEY,
                question       TEXT NOT NULL,
                slug           TEXT,
                end_date       TEXT,
                last_scanned_at INTEGER DEFAULT 0   -- unix timestamp
            );

            CREATE TABLE IF NOT EXISTS trades (
                tx_hash       TEXT PRIMARY KEY,
                proxy_wallet  TEXT NOT NULL,
                condition_id  TEXT NOT NULL,
                side          TEXT,               -- BUY / SELL
                outcome       TEXT,               -- Yes / No
                size          REAL,               -- shares
                price         REAL,               -- dollars per share (0–1)
                timestamp     INTEGER,            -- unix timestamp
                scored        INTEGER DEFAULT 0   -- 0=pending, 1=done
            );

            CREATE INDEX IF NOT EXISTS idx_trades_wallet
                ON trades(proxy_wallet);
            CREATE INDEX IF NOT EXISTS idx_trades_condition
                ON trades(condition_id);

            CREATE TABLE IF NOT EXISTS wallets (
                address            TEXT PRIMARY KEY,
                first_tx_ts        INTEGER,   -- unix ts of first on-chain tx
                last_funded_ts     INTEGER,   -- unix ts of last inbound USDC
                prior_trade_count  INTEGER,   -- total Polymarket trades (all markets)
                distinct_markets   INTEGER,   -- how many distinct markets traded
                updated_at         INTEGER    -- unix ts of last refresh
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address  TEXT NOT NULL,
                condition_id    TEXT NOT NULL,
                tx_hash         TEXT,
                score           INTEGER NOT NULL,
                reasons         TEXT,          -- JSON array of reason strings
                created_at      INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_alerts_condition
                ON alerts(condition_id);
            CREATE INDEX IF NOT EXISTS idx_alerts_wallet
                ON alerts(wallet_address);
        """)


# ── Markets ───────────────────────────────────────────────────────────────────

def upsert_market(condition_id: str, question: str, slug: str, end_date: str) -> None:
    with _connect() as conn:
        conn.execute("""
            INSERT INTO markets(condition_id, question, slug, end_date)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(condition_id) DO UPDATE SET
                question = excluded.question,
                slug     = excluded.slug,
                end_date = excluded.end_date
        """, (condition_id, question, slug, end_date))


def get_market_last_scanned(condition_id: str) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT last_scanned_at FROM markets WHERE condition_id = ?",
            (condition_id,)
        ).fetchone()
    return row["last_scanned_at"] if row else 0


def set_market_last_scanned(condition_id: str, ts: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE markets SET last_scanned_at = ? WHERE condition_id = ?",
            (ts, condition_id)
        )


def get_all_markets() -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute("SELECT * FROM markets").fetchall()


# ── Trades ────────────────────────────────────────────────────────────────────

def trade_exists(tx_hash: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM trades WHERE tx_hash = ?", (tx_hash,)
        ).fetchone()
    return row is not None


def insert_trade(
    tx_hash: str,
    proxy_wallet: str,
    condition_id: str,
    side: str,
    outcome: str,
    size: float,
    price: float,
    timestamp: int,
) -> None:
    with _connect() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO trades
                (tx_hash, proxy_wallet, condition_id, side, outcome, size, price, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (tx_hash, proxy_wallet, condition_id, side, outcome, size, price, timestamp))


def mark_trade_scored(tx_hash: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE trades SET scored = 1 WHERE tx_hash = ?", (tx_hash,))


# ── Wallets ───────────────────────────────────────────────────────────────────

def upsert_wallet(
    address: str,
    first_tx_ts: Optional[int],
    last_funded_ts: Optional[int],
    prior_trade_count: int,
    distinct_markets: int,
) -> None:
    with _connect() as conn:
        conn.execute("""
            INSERT INTO wallets
                (address, first_tx_ts, last_funded_ts, prior_trade_count, distinct_markets, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(address) DO UPDATE SET
                first_tx_ts       = excluded.first_tx_ts,
                last_funded_ts    = excluded.last_funded_ts,
                prior_trade_count = excluded.prior_trade_count,
                distinct_markets  = excluded.distinct_markets,
                updated_at        = excluded.updated_at
        """, (address, first_tx_ts, last_funded_ts, prior_trade_count, distinct_markets, int(time.time())))


def get_wallet(address: str) -> Optional[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM wallets WHERE address = ?", (address,)
        ).fetchone()


# ── Alerts ────────────────────────────────────────────────────────────────────

def insert_alert(
    wallet_address: str,
    condition_id: str,
    tx_hash: str,
    score: int,
    reasons: str,  # JSON string
) -> None:
    with _connect() as conn:
        conn.execute("""
            INSERT INTO alerts (wallet_address, condition_id, tx_hash, score, reasons, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (wallet_address, condition_id, tx_hash, score, reasons, int(time.time())))


def get_recent_alerts(condition_id: str, since_ts: int) -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute("""
            SELECT * FROM alerts
            WHERE condition_id = ? AND created_at >= ?
        """, (condition_id, since_ts)).fetchall()
