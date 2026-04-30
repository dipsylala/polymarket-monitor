"""
config.py — Configuration constants for the Polymarket monitoring system.
"""

# API endpoints
GAMMA_API_URL = "https://gamma-api.polymarket.com"
DATA_API_URL = "https://data-api.polymarket.com"

# Geopolitical keywords to flag markets for deeper analysis
GEOPOLITICAL_KEYWORDS = [
    "iran",
    "iranian",
    "russia",
    "russian",
    "ukraine",
    "china",
    "taiwan",
    "north korea",
    "syria",
    "israel",
    "palestine",
    "gaza",
    "india",
    "pakistan",
    "turkey",
    "suez",
    "strait",
    "kharg",
    "oil",
    "energy",
    "sanction",
    "nuclear",
]

# Keywords indicating need for manual investigation
INVESTIGATION_KEYWORDS = [
    "attack",
    "war",
    "conflict",
    "seized",
    "hijack",
    "explosion",
    "regime",
    "coup",
    "assassination",
    "terror",
    "military",
    "invasion",
]

# Airport-related keywords (for context filtering)
AIRPORT_KEYWORDS = [
    "airport",
    "flight",
    "airline",
    "aviation",
    "runway",
    "air traffic",
]

# Scoring thresholds for suspicious activity
SCORE_THRESHOLD_HIGH = 7  # Score above this triggers high-priority alert

# Wallet and trading behavior thresholds
MAX_ALLOWED_NEW_WALLET_SHARES = 5000  # Max YES/NO shares for new wallets
MIN_SHARE_PRICE_SUSPICIOUS = 0.20  # Below this price is low confidence
MIN_HISTORY_TRADES = 5  # Minimum number of past trades to be considered "experienced"
ALLOWED_MARKETS_PER_WALLET = 3  # Max distinct markets a wallet should trade in