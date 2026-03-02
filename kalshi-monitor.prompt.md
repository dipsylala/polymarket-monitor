# Plan: Add Kalshi Market Monitoring

## TL;DR
Extend the existing Polymarket insider-trading monitor to also scan Kalshi's prediction markets. Because Kalshi is a centralised exchange with no on-chain wallet data, the existing wallet-scoring pipeline cannot apply. Instead, Kalshi monitoring uses a **market-level anomaly model**: volume spikes, unusual price movements, and abnormally large individual trades are scored per market rather than per wallet. The two pipelines coexist — Polymarket keeps its wallet-scoring model, Kalshi gets its own.

---

## Phase 1 — Config & Infrastructure

**Step 1.** Add Kalshi constants to `config.py`:
- `KALSHI_API_URL = "https://api.elections.kalshi.com/trade-api/v2"`
- `KALSHI_MIN_BET_USD: float = 500.0`
- `KALSHI_LARGE_BET_USD: float = 5_000.0`
- `KALSHI_LOW_ODDS_PRICE: float = 0.20`
- `KALSHI_VOLUME_SPIKE_FACTOR: float = 3.0`
- `KALSHI_PRICE_MOVE_PCT: float = 0.15`
- `KALSHI_MARKET_ALERT_SCORE_THRESHOLD: int = 3`

**Step 2.** Extend `database.py` schema (additive — no existing tables touched):
- Add `source TEXT DEFAULT 'polymarket'` column to `markets` table
- New `kalshi_trades` table: `trade_id TEXT PRIMARY KEY, ticker TEXT, price_cents INT, price_dollars TEXT, count INT, count_fp TEXT, taker_side TEXT, created_time TEXT, scored INT DEFAULT 0`
- New `kalshi_market_snapshots` table: `ticker TEXT PRIMARY KEY, volume_24h INT, last_price_cents INT, updated_at INT`
- New `kalshi_alerts` table: `id INTEGER PK AUTOINCREMENT, ticker TEXT, event_ticker TEXT, score INT, reasons TEXT, created_at INT`
- Add CRUD functions: `upsert_kalshi_market`, `insert_kalshi_trade`, `kalshi_trade_exists`, `upsert_kalshi_snapshot`, `get_kalshi_snapshot`, `insert_kalshi_alert`, `get_recent_kalshi_alerts`

---

## Phase 2 — Kalshi API Client

**Step 3.** Create `kalshi.py` (modelled on `polymarket.py`):

`get_geopolitical_markets() -> list[dict]`:
- `GET /markets?status=open&limit=1000` with cursor pagination
- Filter on `title`, `subtitle`, `rules_primary` against `config.GEOPOLITICAL_KEYWORDS` and `config.INVESTIGATION_KEYWORDS` (reused from Polymarket)
- Returns list of Kalshi market dicts; key fields: `ticker`, `event_ticker`, `title`, `subtitle`, `close_time`, `status`, `volume_24h`, `last_price`, `previous_price`

`get_recent_trades(since_ts: int, tickers: set[str]) -> list[dict]`:
- `GET /markets/trades?min_ts={since_ts}&limit=1000` with cursor pagination
- Filter to `tickers`; filter `count × yes_price_dollars >= KALSHI_MIN_BET_USD`
- Use `yes_price_dollars` string variant throughout to avoid cent/dollar confusion

`get_market(ticker: str) -> dict`:
- `GET /markets/{ticker}` — for fetching fresh volume/price snapshot at scan time

---

## Phase 3 — Kalshi Anomaly Detector

**Step 4.** Create `kalshi_detector.py` with `score_kalshi_trade(trade, market, snapshot)`:

| Signal | Condition | Points |
| --- | --- | --- |
| Large bet | `count × yes_price_dollars > KALSHI_LARGE_BET_USD` | +2 |
| Low-odds bet | `yes_price_dollars < KALSHI_LOW_ODDS_PRICE` | +2 |
| Volume spike | `market.volume_24h > snapshot.volume_24h × KALSHI_VOLUME_SPIKE_FACTOR` | +2 |
| Price momentum | `abs(last_price − previous_price) / previous_price > KALSHI_PRICE_MOVE_PCT` | +1 |
| **Max possible** | | **7** |

Alert if score ≥ `KALSHI_MARKET_ALERT_SCORE_THRESHOLD` (default 3).

Also add `detect_kalshi_clusters(ticker, event_ticker)`:
- If multiple tickers sharing the same `event_ticker` have recent alerts within `CLUSTER_WINDOW_HOURS`, emit a compound cluster warning.

---

## Phase 4 — Main Scan Integration

**Step 5.** Add `run_kalshi_scan()` to `main.py`:
- Step A: `kalshi.get_geopolitical_markets()` → upsert to `markets` (`source='kalshi'`); upsert snapshots to `kalshi_market_snapshots`
- Step B: Determine `since_ts` per ticker from `get_market_last_scanned`
- Step C: `kalshi.get_recent_trades(since_ts, tickers)` → filter already-seen `trade_id`s
- Step D: For each new trade, fetch current market snapshot, call `kalshi_detector.score_kalshi_trade`, persist alerts
- Step E: Cluster detection across related tickers (same `event_ticker`)
- Step F: Advance `last_scanned_at` per ticker
- Step G: Extend `_write_step_summary` to include Kalshi alerts section

**Step 6.** Update `main()` entry point:
```python
run_scan()         # existing Polymarket
run_kalshi_scan()  # new Kalshi
```

---

## Phase 5 — GitHub Actions

**Step 7.** No new secrets needed for public read endpoints. Document that `KALSHI_API_KEY` can be added to the workflow later if rate limiting requires authentication.

---

## Relevant Files

| File | Change |
| --- | --- |
| `config.py` | Add Kalshi constants |
| `database.py` | New tables + CRUD helpers |
| `polymarket.py` | Reference/template only |
| `kalshi.py` | **New** — Kalshi API client |
| `kalshi_detector.py` | **New** — Kalshi anomaly scoring |
| `main.py` | Add `run_kalshi_scan()`, wire into entry point, extend step summary |
| `.github/workflows/monitor.yml` | Update if `KALSHI_API_KEY` secret added |

---

## Verification

1. Smoke-test `python -c "import kalshi; print(kalshi.get_geopolitical_markets()[:2])"` — API reachable, keyword filter works
2. Smoke-test `kalshi.get_recent_trades()` against a known active ticker
3. Unit tests in `tests/` for `score_kalshi_trade()` covering each signal independently
4. Full `python main.py` — both scans complete without errors; `kalshi_alerts` table populated
5. Trigger a low-threshold test run (`KALSHI_MARKET_ALERT_SCORE_THRESHOLD=1`) and confirm GitHub Actions step summary shows a Kalshi section

---

## Decisions

- **No wallet identity on Kalshi** → pivots to market-level anomaly scoring; wallet pipeline and `polygon.py` untouched
- **Keyword lists reused** from `GEOPOLITICAL_KEYWORDS` / `INVESTIGATION_KEYWORDS` — Kalshi market titles are English prose, same matching works
- **Always use `_dollars` variants** from Kalshi API to avoid cent/dollar unit bugs
- **Separate `run_kalshi_scan()`** rather than merging — keeps pipelines independently debuggable
- **Baseline cold-start**: skip volume-spike signal on first scan for a ticker (no stored baseline yet); seed on second scan
- **Separate `kalshi_detector.py`**: keeps the two scoring models cleanly isolated

---

## Further Considerations

1. **Rate limits**: Kalshi doesn't publish limits for public endpoints. If 429s occur, add exponential backoff to `kalshi.py` following the same `_SESSION` pattern as `polymarket.py`.
2. **Historical cutoff**: Kalshi splits live vs archived data at a rolling cutoff timestamp. Polling `GET /markets/trades` only returns live data — fine for monitoring, but worth noting for future historical backfills.
3. **Kalshi API key**: Currently not required for read endpoints. If Kalshi adds auth requirements, the key will need RSASSA-PSS signing (their standard auth scheme) — a non-trivial addition.
