"""
main.py — Entry point for the Polymarket insider-trading monitor.

Designed to be run as a cron job (or Windows Task Scheduler task).
Each invocation processes all activity since the previous run, as
tracked by `last_scanned_at` in the SQLite database, then exits.

Usage
-----
  python main.py

Cron example (every hour):
  0 * * * * /path/to/.venv/bin/python /path/to/main.py >> /var/log/polymarket.log 2>&1

Windows Task Scheduler:
  Program : E:/Github/PolymarketPoll/.venv/Scripts/python.exe
  Arguments: E:/Github/PolymarketPoll/main.py
  Trigger  : Daily, repeat every 1 hour
"""

import logging
import sys
import time

import config
import database
import detector
import polygon
import polymarket

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def _format_alert(trade: dict, result: detector.ScoreResult) -> str:
    address = trade.get("proxyWallet", "")
    question = trade.get("title", trade.get("conditionId", "unknown market"))
    price = float(trade.get("price", 0))
    size = float(trade.get("size", 0))
    usdc_spent = price * size
    potential_profit = size - usdc_spent  # profit if resolves YES at $1
    tx_hash = trade.get("transactionHash", "n/a")
    reasons_str = ", ".join(result.reasons)
    short_addr = address[:6] + "..." + address[-4:] if len(address) > 10 else address

    return (
        f"\n{'='*70}\n"
        f"[ALERT] Score={result.score}  Wallet={short_addr}\n"
        f"  Market : {question}\n"
        f"  Reasons: {reasons_str}\n"
        f"  Trade  : {size:,.0f} YES shares @ ${price:.3f}  "
        f"| USDC spent: ${usdc_spent:,.0f}  "
        f"| Potential profit: ${potential_profit:,.0f}\n"
        f"  tx     : {tx_hash}\n"
        f"{'='*70}"
    )


def run_scan() -> None:
    """
    Execute one full monitoring scan:
      1. Refresh geopolitical market list and upsert to DB
      2. For each market, fetch trades since last scan
      3. Score qualifying trades; emit alerts for high-score wallets
      4. Run cluster detection per market
      5. Advance last_scanned_at for each market
    """
    scan_start = int(time.time())
    logger.info("── Scan started at %s ──", time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(scan_start)))

    # ── Step 1: Refresh market list ───────────────────────────────────────────
    geo_markets = polymarket.get_geopolitical_markets()
    if not geo_markets:
        logger.warning("No geopolitical markets returned; skipping scan")
        return

    condition_ids: set[str] = set()
    for m in geo_markets:
        condition_id = m.get("conditionId") or m.get("condition_id", "")
        if not condition_id:
            continue
        database.upsert_market(
            condition_id=condition_id,
            question=m.get("question", ""),
            slug=m.get("slug", ""),
            end_date=m.get("endDate") or m.get("end_date", ""),
        )
        condition_ids.add(condition_id)

    logger.info("Monitoring %d geopolitical markets", len(condition_ids))

    # ── Step 2: Determine global since_ts (earliest last_scanned across markets) ──
    # We fetch all trades since the oldest un-scanned timestamp to use a single
    # Data API call, then filter per-market in memory.
    per_market_since: dict[str, int] = {cid: database.get_market_last_scanned(cid) for cid in condition_ids}
    global_since = min(per_market_since.values()) if per_market_since else 0

    # ── Step 3: Fetch qualifying trades ───────────────────────────────────────
    trades = polymarket.get_recent_trades(since_ts=global_since, condition_ids=condition_ids)
    new_trades = [t for t in trades if not database.trade_exists(t.get("transactionHash", ""))]
    logger.info("%d new qualifying trades to process", len(new_trades))

    # ── Step 4: Score each trade ──────────────────────────────────────────────
    alerted_conditions: set[str] = set()

    for trade in new_trades:
        address: str = trade.get("proxyWallet", "")
        condition_id: str = trade.get("conditionId", "")
        tx_hash: str = trade.get("transactionHash", "")
        price = float(trade.get("price", 0))
        size = float(trade.get("size", 0))
        ts = int(trade.get("timestamp", scan_start))

        database.insert_trade(
            tx_hash=tx_hash,
            proxy_wallet=address,
            condition_id=condition_id,
            side=trade.get("side", ""),
            outcome=trade.get("outcome", ""),
            size=size,
            price=price,
            timestamp=ts,
        )

        # Fetch / refresh wallet data (cache for 1 hour)
        cached = database.get_wallet(address)
        should_refresh = cached is None or (scan_start - (cached["updated_at"] or 0)) > 3600

        if should_refresh:
            poly_count, poly_markets = polymarket.get_wallet_trade_history(address)
            first_tx_ts = polygon.get_wallet_first_tx(address)
            last_funded_ts = polygon.get_wallet_last_usdc_in(address)
            database.upsert_wallet(
                address=address,
                first_tx_ts=first_tx_ts,
                last_funded_ts=last_funded_ts,
                prior_trade_count=poly_count,
                distinct_markets=poly_markets,
            )
        else:
            first_tx_ts = cached["first_tx_ts"]
            last_funded_ts = cached["last_funded_ts"]
            poly_count = cached["prior_trade_count"]
            poly_markets = cached["distinct_markets"]

        wallet_data = {
            "first_tx_ts": first_tx_ts,
            "last_funded_ts": last_funded_ts,
            "prior_trade_count": poly_count,
            "distinct_markets": poly_markets,
        }

        result = detector.process_trade(trade, wallet_data)
        if result and result.is_alert:
            print(_format_alert(trade, result))
            alerted_conditions.add(condition_id)

    # ── Step 5: Cluster detection ─────────────────────────────────────────────
    for condition_id in alerted_conditions:
        cluster_wallets = detector.detect_clusters(condition_id)
        if cluster_wallets:
            market_row = next(
                (m for m in geo_markets if (m.get("conditionId") or m.get("condition_id")) == condition_id),
                None,
            )
            question = market_row.get("question", condition_id) if market_row else condition_id
            short_wallets = [w[:6] + "..." + w[-4:] for w in cluster_wallets]
            print(
                f"\n{'!'*70}\n"
                f"[CLUSTER] {len(cluster_wallets)} wallets flagged on same market "
                f"within {config.CLUSTER_WINDOW_HOURS}h\n"
                f"  Market  : {question}\n"
                f"  Wallets : {', '.join(short_wallets)}\n"
                f"  → Possible coordinated insider activity\n"
                f"{'!'*70}"
            )

    # ── Step 6: Advance last_scanned_at for all markets ─────────────────────
    for cid in condition_ids:
        database.set_market_last_scanned(cid, scan_start)

    logger.info(
        "── Scan complete. %d trades processed, %d alerts ──",
        len(new_trades),
        len(alerted_conditions),
    )


def main() -> None:
    _setup_logging()
    database.init_db()
    logging.info("Database: %s", database.DB_PATH)
    run_scan()


if __name__ == "__main__":
    main()
