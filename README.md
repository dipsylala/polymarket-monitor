# Polymarket Monitor

## How it works

Each run fetches all YES trades on geopolitical markets since the previous run and scores the wallets behind them across six signals:

| Signal | Points |
| --- | --- |
| Wallet first on-chain tx < 30 days ago | +3 |
| Last USDC deposit < 48 hours ago | +3 |
| Fewer than 10 prior Polymarket trades | +2 |
| Only one market ever traded | +2 |
| Trade price < $0.20/share (low-odds bet) | +1 |
| USDC spent > $5,000 on single trade | +1 |

Wallets scoring **≥ 5** are printed as alerts. If **3 or more** flagged wallets hit the same market within 24 hours, a cluster warning is emitted.

In parallel, every run checks a **watchlist** of known insider-trading wallets (`WATCHLIST_WALLETS` in `config.py`). Any trade from a watchlist address on *any* market triggers an immediate alert regardless of score. On the first scan of a newly added wallet, the previous 30 days of trades are backfilled automatically.

On-chain wallet age and funding recency are verified on Polygon through
[Etherscan API V2](https://docs.etherscan.io/etherscan-v2).

## Setup

**Requirements:** Python 3.9+, [uv](https://docs.astral.sh/uv/)

```powershell
# Install uv (once, globally)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 1. Clone / navigate to the project
cd E:\Github\polymarket-monitor

# 2. Create a virtual environment
uv venv .venv

# 3. Install dependencies (uv auto-discovers .venv — no activation needed)
uv pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Edit .env and add your ETHERSCAN_API_KEY
```

Create a free Etherscan API key at
[https://etherscan.io/myapikey](https://etherscan.io/myapikey). Without it,
the app still runs, but wallet age and funding signals are omitted, reducing
the maximum possible score from 12 to 6.

The Polymarket Gamma and Data APIs used for market and trade monitoring are
public and do not require a Polymarket API key.

## Usage

```powershell
python main.py
```

Each invocation covers all activity since the last run — designed to be called by a scheduler rather than kept running.

### Private alert issues

GitHub Actions sends alert, cluster, and watchlist issues to the private
`dipsylala/polymarket-monitor-private` repository. Detailed alert data is
omitted from this public repository's Actions logs and job summaries.

Create a fine-grained personal access token scoped only to the private alert
repository with **Issues: Read and write**, then add it to this repository as
the Actions secret `PRIVATE_ALERT_REPO_TOKEN`. The workflow's built-in
`GITHUB_TOKEN` cannot create issues in another repository.

## Tests

```powershell
python -m pytest tests/ -v
```

The test suite covers the three known insider-trading incident profiles (US-Iran strike, Venezuela/Maduro, ZachXBT/Axiom) as true positives, plus true negatives for high-odds bets, established wallets, and the keyword market filter.

### Cron (Linux/macOS)

```cron
0 * * * * /path/to/.venv/bin/python /path/to/main.py >> /var/log/polymarket.log 2>&1
```

### Windows Task Scheduler

- **Program:** `E:\Github\polymarket-monitor\.venv\Scripts\python.exe`
- **Arguments:** `E:\Github\polymarket-monitor\main.py`
- **Trigger:** Daily, repeat every 1 hour

## Output

```plaintext
======================================================================
[ALERT] Score=8  Wallet=0xABCD...1234
  Market : US strikes Iran by February 28, 2026?
  Reasons: new_wallet(27d), funded_24h, single_market, low_odds($0.11/share), large_bet($61,000)
  Trade  : 560,680 YES shares @ $0.108  | USDC spent: $60,553  | Potential profit: $500,127
  Wallet : https://polygonscan.com/address/0xABCD...1234
  tx     : https://polygonscan.com/tx/0xd22c...
  Market : https://polymarket.com/event/us-strikes-iran-february-2026
======================================================================

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
[CLUSTER] 3 wallets flagged on same market within 24h
  Market  : US strikes Iran by February 28, 2026?
  Wallets : 0xABCD...1234, 0xEF01...5678, 0x9ABC...DEF0
  → Possible coordinated insider activity
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
```

Watchlist hits produce a distinct block:

```plaintext
**********************************************************************
[WATCHLIST HIT] Known insider active: 0xe31b...fb7 (ZachXBT/Axiom incident Feb 2026)
  Market : Will ZachXBT expose a major exchange by March 2026?
  Trade  : 10,000 YES shares @ $0.350 (BUY) | USDC: $3,500
  Wallet : https://polygonscan.com/address/0xe31b...
  tx     : https://polygonscan.com/tx/0xabc1...
**********************************************************************
```

Alerts and the retained 30-day watchlist-hit history are persisted to
`polymarket_monitor.db` (SQLite).

## Configuration

All thresholds are in [`config.py`](config.py):

| Variable | Default | Description |
| --- | --- | --- |
| `WALLET_AGE_DAYS` | 30 | Max wallet age (days) to flag as new |
| `FUNDING_RECENCY_HOURS` | 48 | Max hours since last USDC deposit to flag |
| `LOW_HISTORY_TRADES` | 10 | Trade count below which history is considered thin |
| `LOW_ODDS_PRICE` | 0.20 | Share price below which a bet is considered low-odds |
| `LARGE_BET_USDC` | 5000 | USDC spent threshold for large-bet signal |
| `MIN_BET_USDC` | 500 | Minimum USDC spent to even evaluate a trade |
| `SCAN_OVERLAP_HOURS` | 24 | Minimum recent window re-read on every scan |
| `ALERT_SCORE_THRESHOLD` | 5 | Minimum score to emit an alert |
| `CLUSTER_MIN_WALLETS` | 3 | Wallets required to trigger a cluster warning |
| `CLUSTER_WINDOW_HOURS` | 24 | Time window for cluster detection |
| `WATCHLIST_RETENTION_DAYS` | 30 | Watchlist backfill and persisted deduplication history |
| `DATABASE_COMPACT_THRESHOLD_MB` | 45 | Compact SQLite after pruning above this size |
| `GEOPOLITICAL_KEYWORDS` | *(see config.py)* | Keywords for armed conflict, military operations, and political instability markets |
| `INVESTIGATION_KEYWORDS` | *(see config.py)* | Keywords for crypto investigations, regulatory actions, and financial misconduct markets |
| `WATCHLIST_WALLETS` | *(see config.py)* | Known insider wallets; any trade triggers an immediate alert. New entries backfill retained history on first scan. |

## Project structure

```plaintext
main.py          Entry point + scan orchestrator
polymarket.py    Gamma API + Data API clients
polygon.py       Etherscan V2 Polygon wallet age/funding checks
detector.py      Scoring model + cluster detection
database.py      SQLite persistence (markets, trades, wallets, alerts,
                 watchlist_wallets, watchlist_hits)
config.py        All thresholds, keywords, and watchlist
```

## Disclaimer

This tool is for research and monitoring purposes only. Flagged wallets are anomalies, not confirmed cases of insider trading. All allegations require independent verification.
