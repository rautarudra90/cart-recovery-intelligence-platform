"""
Global configuration settings for CartRecover-AI platform.
Contains deterministic seeds, window thresholds, scale configurations,
and database file paths.
"""
from pathlib import Path
from dataclasses import dataclass

# Project base paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DOCS_DIR = PROJECT_ROOT / "docs"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Primary database path
DEFAULT_DB_PATH = DATA_DIR / "cart_recover.db"

# Deterministic Seed as mandated by assessment rules
DETERMINISTIC_SEED = 20261022

# Business Rules Engine Parameters
ABANDONMENT_INACTIVITY_MINUTES = 60       # 60 min inactivity marks cart as abandoned
FREQUENCY_CAP_HOURS = 24                   # Max 1 message per customer per channel per 24 hours
ATTRIBUTION_WINDOW_HOURS = 168             # 7 days (168h) last-touch conversion window
TAX_RATE = 0.08                           # 8% standard sales tax
CURRENCY = "USD"

# Scale configurations
@dataclass(frozen=True)
class ScaleConfig:
    total_customers: int
    total_carts: int
    target_abandoned_carts: int
    target_sends: int
    anomaly_count: int

SCALE_PRESETS = {
    "starter": ScaleConfig(
        total_customers=600,
        total_carts=1000,
        target_abandoned_carts=400,
        target_sends=200,
        anomaly_count=20
    ),
    "medium": ScaleConfig(
        total_customers=6000,
        total_carts=10000,
        target_abandoned_carts=4000,
        target_sends=2000,
        anomaly_count=100
    ),
    "full": ScaleConfig(
        total_customers=30000,
        total_carts=50000,
        target_abandoned_carts=20000,
        target_sends=10000,
        anomaly_count=400
    )
}
