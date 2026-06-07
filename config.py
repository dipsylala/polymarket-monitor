import os
from dotenv import load_dotenv

load_dotenv()

# ── API keys ──────────────────────────────────────────────────────────────────
ETHERSCAN_API_KEY: str = os.getenv("ETHERSCAN_API_KEY", "")

# ── API base URLs ─────────────────────────────────────────────────────────────
GAMMA_API_URL = "https://gamma-api.polymarket.com"
DATA_API_URL = "https://data-api.polymarket.com"
ETHERSCAN_API_URL = "https://api.etherscan.io/v2/api"
ETHERSCAN_CHAIN_ID = "137"  # Polygon Mainnet

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

# Re-read at least this much recent history on every scan. Database
# deduplication makes the overlap safe and lets a fixed/deferred API response
# recover on a later run.
SCAN_OVERLAP_HOURS: int = 24

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
    "detonat",   # covers "detonate", "detonation"
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
    # ── Iran-specific ─────────────────────────────────────────────────────────
    "iran",
    "tehran",
    "irgc",
    "khamenei",
    "mojtaba",
    "hormuz",
    "khomeini",
    "rouhani",
    "pezeshkian",
    # ── Ukraine / Russia-specific ─────────────────────────────────────────────
    "ukraine",
    "russia",
    "zelensky",
    "zelenskyy",
    "putin",
    "kyiv",
    "nato",
    "crimea",
    "donbas",
    "kharkiv",
    "zaporizhzhia",
    "mariupol",
    "kursk",
    "bakhmut",
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

# ── US Airport / airspace keywords ──────────────────────────────────────────
# Catches markets around attacks, closures, or restrictions affecting US
# airports and domestic airspace — an area where advance knowledge of a
# security incident or military action would confer a trading edge.
AIRPORT_KEYWORDS: list[str] = [
    "airport",
    "airspace",
    "no-fly zone",
    "no fly zone",
    "faa ",          # trailing space avoids "affair", "faan", etc.
    "flight ban",
    "airfield",
    "tsa",           # Transportation Security Administration
    "grounded",      # covers FAA ground stops
    "ground stop",
    "air traffic",
    "aviation",
]

# Markets containing a geopolitical named entity can still be unrelated sports
# questions (for example, "Will Iran win the FIFA World Cup?").
EXCLUDED_MARKET_KEYWORDS: list[str] = [
    "world cup",
    "fifa",
    "uefa",
    "champions league",
    "premier league",
    "super bowl",
    "nba",
    "nfl",
    "nhl",
    "mlb",
    "ufc",
    "grand slam",
    "formula 1",
]

# ── Etherscan rate limit ──────────────────────────────────────────────────────
# API V2 free tier allows 3 req/s; stay safely below.
ETHERSCAN_REQ_PER_SEC: float = 2.5

# ── Watchlist wallets ─────────────────────────────────────────────────────────
# Known insider-trading wallets identified from proven incidents.
# Any trade from these addresses on ANY market triggers an immediate alert,
# regardless of the scoring model.
# Keys are wallet addresses; values are human-readable labels for alerts.
WATCHLIST_WALLETS: dict[str, str] = {
    "0xe31b852756937aef6a047b8de0d36196804b3fb7": "ZachXBT/Axiom incident Feb 2026 (Lookonchain)",
    # "0x110edef01810239c23307ad3d4373e48bc9e8b11": "US-Iran strike market Feb/Mar 2026",
}
