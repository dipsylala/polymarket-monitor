"""
main.py — Entry point for the Polymarket monitoring system.
"""

import logging
import sys

from detector import scan_geopolitical_markets

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def get_alerts() -> list:
    """
    Public interface to retrieve active alerts.
    """
    try:
        alerts = scan_geopolitical_markets()
        logger.info("Generated %d alerts", len(alerts))
        return alerts
    except Exception as exc:
        logger.error("Failed to generate alerts: %s", exc)
        return []

if __name__ == "__main__":
    alerts = get_alerts()
    for alert in alerts:
        print(f"🚨 {alert['score']}/10 {alert['wallet'][:8]}... — {alert['market']}")