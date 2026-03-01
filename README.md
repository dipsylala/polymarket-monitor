# PolymarketPoll

Monitors the [Polymarket](https://polymarket.com) prediction market API for suspicious trading activity on geopolitical markets — patterns consistent with insider knowledge, as documented in the [February 2026 US-Iran strike incident](https://www.ibtimes.co.uk/suspected-insider-trading-polymarket-us-iran-1782274).

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

On-chain wallet age and funding recency are verified via the [PolygonScan API](https://polygonscan.com/apis) (free tier).

## Setup

**Requirements:** Python 3.9+, [uv](https://docs.astral.sh/uv/)

```powershell
# Install uv (once, globally)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 1. Clone / navigate to the project
cd E:\Github\PolymarketMonitor

# 2. Create a virtual environment
uv venv .venv

# 3. Install dependencies (uv auto-discovers .venv — no activation needed)
uv pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Edit .env and add your POLYGONSCAN_API_KEY
```

Get a free PolygonScan API key at [https://polygonscan.com/apis](https://polygonscan.com/apis). Without it the app still runs, but wallet age and funding checks are skipped (lower max score).

## Usage

```powershell
python main.py
```

Each invocation covers all activity since the last run — designed to be called by a scheduler rather than kept running.

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

- **Program:** `E:\Github\PolymarketPoll\.venv\Scripts\python.exe`
- **Arguments:** `E:\Github\PolymarketPoll\main.py`
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

All alerts are also persisted to `polymarket_monitor.db` (SQLite).

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
| `ALERT_SCORE_THRESHOLD` | 5 | Minimum score to emit an alert |
| `CLUSTER_MIN_WALLETS` | 3 | Wallets required to trigger a cluster warning |
| `CLUSTER_WINDOW_HOURS` | 24 | Time window for cluster detection |
| `GEOPOLITICAL_KEYWORDS` | *(see config.py)* | Keywords for armed conflict, military operations, and political instability markets |
| `INVESTIGATION_KEYWORDS` | *(see config.py)* | Keywords for crypto investigations, regulatory actions, and financial misconduct markets |

## Project structure

```plaintext
main.py          Entry point + scan orchestrator
polymarket.py    Gamma API + Data API clients
polygon.py       PolygonScan wallet age/funding checks
detector.py      Scoring model + cluster detection
database.py      SQLite persistence
config.py        All thresholds and settings
```

## Disclaimer

This tool is for research and monitoring purposes only. Flagged wallets are anomalies, not confirmed cases of insider trading. All allegations require independent verification.
