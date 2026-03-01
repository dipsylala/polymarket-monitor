# Plan: Polymarket Insider Trading Monitor

**TL;DR:** A Python CLI app that scans Polymarket on a schedule, scores wallets making large YES bets on geopolitical markets using a multi-signal risk model (wallet age, funding recency, trade concentration, bet size/odds), and logs alerts to the console. Blockchain wallet age is verified via PolygonScan API. All state persists in SQLite.

---

## Phase 1 — Project Scaffold

1. `requirements.txt`: `requests`, `python-dotenv`
2. `.env.example`: `POLYGONSCAN_API_KEY`
3. `config.py`: all tunable thresholds + geopolitical keyword list (see Phase 5)

## Phase 2 — Database Layer (`database.py`)

4. SQLite via stdlib `sqlite3`, 4 tables:
   - `markets(condition_id PK, question, slug, end_date, last_scanned_at)`
   - `trades(tx_hash PK, proxy_wallet, condition_id, side, outcome, size, price, timestamp, scored)`
   - `wallets(address PK, first_tx_ts, last_funded_ts, prior_trade_count, distinct_markets)`
   - `alerts(id PK, wallet_address, condition_id, score, reasons TEXT, created_at)`

## Phase 3 — Polymarket Client (`polymarket.py`)

5. `get_geopolitical_markets()` → calls `GET https://gamma-api.polymarket.com/markets?active=true&limit=500`, then filters in Python on `question` field for keywords: `strike, attack, war, military, bomb, conflict, invasion, regime, ceasefire, coup, nuclear, missile, president, election`
6. `get_recent_trades(since_ts, condition_ids)` → `GET https://data-api.polymarket.com/trades?limit=500`, filtered to known condition IDs and `timestamp >= since_ts`
7. `get_wallet_trades(address)` → `GET https://data-api.polymarket.com/trades?maker=<address>&limit=1000`, returns total trade count + distinct market count

## Phase 4 — PolygonScan Client (`polygon.py`)

8. `get_wallet_first_tx(address)` → calls `txlist` (sort=asc, offset=1) — first transaction timestamp = proxy wallet age
9. `get_wallet_last_usdc_in(address)` → calls `tokentx` with USDC contract `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` (sort=desc, filter `to==address`) — detects recent funding
10. Rate-limited to 4 req/s (under the free tier's 5 req/s cap)

## Phase 5 — Anomaly Detector (`detector.py`)

11. `score_wallet(...)` → integer score + reason list:

   | Signal | Points |
   |---|---|
   | Wallet first tx < 30 days ago | +3 |
   | Last USDC inbound < 48 hours ago | +3 |
   | Prior Polymarket trades < 10 | +2 |
   | Only one distinct market ever traded | +2 |
   | Trade price < $0.20/share | +1 |
   | Position size > $5,000 | +1 |

   Alert threshold: **score ≥ 5**

12. `detect_cluster(flagged_wallets, condition_id, window_hours=24)` — if ≥ 3 wallets hit threshold on the same market within 24 hrs, emit a cluster warning (mimics the Bubblemaps detection method)

## Phase 6 — Scan Orchestrator (in `main.py`)

13. `run_scan()` (in `main.py`) — the scan orchestrator:
    1. Refresh geopolitical market list → upsert DB
    2. Fetch trades since `last_scanned_at` for each tracked market
    3. Filter to `outcome=="Yes"` + `side=="BUY"` + USDC spent > `MIN_BET_USDC` (default $500)
    4. Skip already-seen `tx_hash`
    5. Fetch wallet context from Polymarket + PolygonScan
    6. Score → if threshold met, insert alert + log to console
    7. Run cluster check over new alerts
    8. Advance `last_scanned_at`

## Phase 7 — Entry Point & Output (`main.py`)

14. Designed for cron: runs `run_scan()` once and exits. `last_scanned_at` in SQLite persists the window between invocations — each run automatically covers the gap since the previous run.
15. Console alert format:
    ```
    [ALERT] Score=8 Wallet=0xABCD...
      Market: "US strikes Iran by Feb 28, 2026?"
      Reasons: new_wallet(27d), funded_24h, single_market, low_odds(18¢), large_bet($61k)
      tx=0x... — 560,680 YES shares @ $0.108 | potential profit ~$494k
    [CLUSTER] 3 wallets flagged on same market within 6h
    ```

---

## Project State

**Status: fully implemented and verified.** All phases complete. Ready to run.
- All source files have been created and import cleanly.
- A virtual environment exists at `.venv/`. Activate with `.venv\Scripts\Activate.ps1` (PowerShell) or `.venv/bin/activate` (bash/zsh).
- Dependencies are installed: `pip install -r requirements.txt` (or already done inside `.venv`).
- Copy `.env.example` → `.env` and fill in `POLYGONSCAN_API_KEY` before running.
- The app is **cron-job friendly**: each invocation scans for activity since the last run (tracked via `last_scanned_at` in SQLite) and then exits. No persistent process needed.
- Run manually: `python main.py`

### Scheduling

**Cron (Linux/macOS)** — add via `crontab -e`:
```
0 * * * * /path/to/.venv/bin/python /path/to/main.py >> /var/log/polymarket.log 2>&1
```

**Windows Task Scheduler:**
- Program: `E:\Github\PolymarketPoll\.venv\Scripts\python.exe`
- Arguments: `E:\Github\PolymarketPoll\main.py`
- Trigger: Daily, repeat every 1 hour

## Relevant Files (all new)

- `main.py` — entry point + scan orchestrator (`run_scan()`)
- `config.py` — thresholds, keywords, env vars
- `database.py` — SQLite init + CRUD
- `polymarket.py` — Gamma API + Data API clients
- `polygon.py` — PolygonScan API client
- `detector.py` — scoring logic + cluster detection
- `requirements.txt`
- `.env.example`

---

## Decisions

- **No API auth needed** — Gamma API and Data API are fully public
- **Keyword-based market filtering** — the Gamma API `category` field is inconsistently populated; keyword matching on `question` is more reliable and extensible
- `proxyWallet` address (from the Data API) is used as the identifier, not the underlying EOA — this matches how Polymarket account ages are tracked on-chain
- **No web UI in v1** — console/log output only
- Sports and crypto short-duration markets are excluded (high noise, not the target pattern)

---

## Verification

1. `python main.py` → confirms geopolitical markets are fetched and counted (check log output)
2. Inject a mock trade matching the known Iran-incident wallet addresses (from the Bubblemaps/CoinDesk reports) → confirm score ≥ 5
3. Call PolygonScan against a known flagged wallet → confirm first-tx date returns Feb 2026
4. Confirm SQLite schema created on first run, no duplicate `tx_hash` on second run

---

## Further Considerations

1. **`side` field semantics**: Live Data API shows `side=BUY/SELL` and a separate `outcome` field (`Yes`/`No`). Filter on both `side=="BUY"` AND `outcome=="Yes"` to isolate YES purchases. Worth confirming against a known YES trade.
2. **Wallet graph clustering (future)**: Bubblemaps detected the Iran cluster partly via *shared funding path* — multiple wallets funded from the same intermediate address. This requires building a graph of PolygonScan `tokentx` funding sources, which is out of v1 scope but could be added as a Phase 8.
3. **PolygonScan free tier limits**: At 4 req/s with hourly scans, this is well within limits *unless* a flood of suspicious trades all need wallet lookups simultaneously. Consider a queue with backoff.
