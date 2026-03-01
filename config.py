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
# Catches markets around armed conflict, military operations, political
# instability, and international crises where advance government or
# intelligence knowledge could confer a trading edge (e.g. US-Iran strikes,
# coup attempts, nuclear escalation).
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
    "airstr",    # covers "airstrike", "airstrikes"
    "ground troops",
    "naval",
    "siege",
    "annexed",
    "drone",
    "ballistic",
    "blockade",
    "embargo",
    "mobiliz",   # covers "mobilize", "mobilization"
    "escalat",   # covers "escalate", "escalation"
    "withdraw",  # covers "withdrawal"
    "rebel",
    "insurgent",
    "terrorist",
    "martial law",
    "state of emergency",
    "referendum",
    "impeach",
    "prime minister",
    "dictator",
    "uprising",
    "occupied",
    "sovereignty",
    "secession",
    "independence",
    "diplomat",  # covers "diplomatic", "diplomacy"
    "treaty",
    "warship",
    "frontline",
    "provocat",  # covers "provocation", "provocative"
    "detonат",
    "chemical weapon",
    "biological weapon",
    "resign",
    "ousted",
    "step down",
    "removed from office",
    "out by",        # covers "Maduro out by ...", "Leader X out by ..."
    "no longer",     # covers "no longer president/in power"
    "deposed",
    "exile",
]

# ── Investigation / financial misconduct keywords ─────────────────────────────
# Catches markets around crypto investigations, regulatory actions, and
# corporate misconduct where insider knowledge is plausible (e.g. ZachXBT,
# SEC enforcement, fraud allegations).
INVESTIGATION_KEYWORDS: list[str] = [
    "zachxbt",
    "investigat",    # covers "investigate", "investigation"
    "expose",
    "insider trading",
    "fraud",
    "sec ",          # trailing space avoids "second", "secret" etc.
    "cftc",
    "doj",
    "enforcement",
    "lawsuit",
    "indicted",
    "arrested",
    "charged with",
    "ponzi",
    "hack",
    "exploit",
    "rug pull",
    "exit scam",
    "bankrupt",
    "insolvent",
    "fine",
    "settlement",
    "whistleblow",   # covers "whistleblower", "whistleblowing"
    "subpoena",
    "money laundering",
    "sanction",      # also catches financial sanctions
]

# ── PolygonScan rate limit ────────────────────────────────────────────────────
# Free tier allows 5 req/s; stay safely below.
POLYGONSCAN_REQ_PER_SEC: float = 4.0
