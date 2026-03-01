import os
from dotenv import load_dotenv

load_dotenv()

# ── API keys ──────────────────────────────────────────────────────────────────
POLYGONSCAN_API_KEY: str = os.getenv("POLYGONSCAN_API_KEY", "")

# ── API base URLs ─────────────────────────────────────────────────────────────
GAMMA_API_URL = "https://gamma-api.polymarket.com"
DATA_API_URL = "https://data-api.polymarket.com"
POLYGONSCAN_API_URL = "https://api.etherscan.io/v2/api"
POLYGONSCAN_CHAIN_ID = "137"  # Polygon Mainnet

# USDC on Polygon
USDC_CONTRACT = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

# ── Scoring thresholds ────────────────────────────────────────────────────────
# Wallet first transaction within this many days → new wallet signal
WALLET_AGE_DAYS: int = 30

# Last USDC inbound transfer within this many hours → recently funded signal
FUNDING_RECENCY_HOURS: int = 48

# Fewer than this many prior Polymarket trades → low-history signal
LOW_HISTORY_TRADES: int = 10

# Only one distinct market ever traded → single-market signal
SINGLE_MARKET_THRESHOLD: int = 1

# Trade odds below this price (in dollars, 0–1) → low-odds signal
LOW_ODDS_PRICE: float = 0.20

# USDC spent on a single trade above this → large-bet signal
LARGE_BET_USDC: float = 5_000.0

# Minimum USDC spent on a trade to even consider it for scoring
MIN_BET_USDC: float = 500.0

# Alert when wallet score reaches or exceeds this value
ALERT_SCORE_THRESHOLD: int = 5

# ── Cluster detection ─────────────────────────────────────────────────────────
# Minimum distinct flagged wallets on the same market within the window
CLUSTER_MIN_WALLETS: int = 3

# Time window (hours) to check for co-occurring flagged wallets
CLUSTER_WINDOW_HOURS: int = 24

# ── Geopolitical market keywords ──────────────────────────────────────────────
# Case-insensitive substring match against the market `question` field.
GEOPOLITICAL_KEYWORDS: list[str] = [
    "strike",
    "attack",
    "war",
    "military",
    "bomb",
    "conflict",
    "invasion",
    "regime",
    "ceasefire",
    "coup",
    "nuclear",
    "missile",
    "president",
    "election",
    "assassination",
    "sanctions",
    "troops",
    "hostage",
    "troops",
    "airstr",    # covers "airstrike", "airstrikes"
    "ground troops",
    "naval",
    "siege",
    "annexed",
]

# ── PolygonScan rate limit ────────────────────────────────────────────────────
# Free tier allows 5 req/s; stay safely below.
POLYGONSCAN_REQ_PER_SEC: float = 4.0
