"""
Configuration for Pollution Intelligence Agent.
All settings via environment variables — no hardcoded secrets.
"""
import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent.parent
DATASETS_DIR = PROJECT_ROOT / "datasets" / "raw" / "pollution"

# MongoDB
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://admin:changeme@localhost:27017/supadsp?authSource=admin")
MONGODB_DB = os.getenv("MONGODB_DB", "supadsp")

# HuggingFace model
HF_MODEL_REPO = "Ganesh-Nadkarni/aqi-eco-nav-models"
HF_MODEL_SUBDIR = "dl"
MODEL_CACHE_DIR = os.getenv("MODEL_CACHE_DIR", "")

# Pollution Agent server
POLLUTION_AGENT_PORT = int(os.getenv("POLLUTION_AGENT_PORT", "8002"))

# Cache TTLs (seconds)
CACHE_TTL_CURRENT = 300       # 5 min
CACHE_TTL_HISTORICAL = 900    # 15 min
CACHE_TTL_FORECAST = 1800     # 30 min
CACHE_TTL_METADATA = 3600     # 1 hour

# Data quality thresholds
MIN_DAILY_READINGS = 48       # Project engineering completeness threshold: at least 48 of 96 possible 15-min readings (50% threshold, not a CPCB statutory mandate)
MIN_DAYS_FOR_FORECAST = 7     # Need 7 consecutive valid days
STATION_STALE_THRESHOLD_HOURS = 6

# City for this deployment
CITY_NAME = os.getenv("POLLUTION_CITY", "Hyderabad")

# Proxy mode configuration:
# When enabled (via POLLUTION_PROXY_MODE=true or passing proxy_mode=True),
# UnifiedForecaster acts as an HTTP proxy delegating inference to POLLUTION_PROXY_URL
# rather than loading PyTorch model checkpoints into local memory.
POLLUTION_PROXY_MODE = os.getenv("POLLUTION_PROXY_MODE", "").lower() in ("true", "1", "yes")
POLLUTION_PROXY_URL = os.getenv("POLLUTION_PROXY_URL", "http://127.0.0.1:8002").rstrip("/")

# ── OpenAQ Live Data Configuration ──
# Try loading from .env if OPENAQ_API_KEY not already in os.environ
if not os.getenv("OPENAQ_API_KEY"):
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        try:
            with open(env_file, "r", encoding="utf-8") as _f:
                for _line in _f:
                    _line = _line.strip()
                    if not _line or _line.startswith("#"):
                        continue
                    if _line.startswith("OPENAQ_API_KEY"):
                        _sep = "=" if "=" in _line else (":" if ":" in _line else None)
                        if _sep:
                            _, _val = _line.split(_sep, 1)
                            os.environ["OPENAQ_API_KEY"] = _val.strip().strip("'\"")
                            break
        except Exception:
            pass

# API key via env var ONLY — never hardcode.
OPENAQ_API_KEY: str = os.getenv("OPENAQ_API_KEY", "")

# When POLLUTION_LIVE_MODE=true, the /api/pollution/current endpoint switches to
# OpenAQLiveProvider for the OBSERVED card. Historical archive stays accessible.
POLLUTION_LIVE_MODE: bool = os.getenv("POLLUTION_LIVE_MODE", "").lower() in ("true", "1", "yes")

# Live accumulation store — dated JSON files, one per calendar day.
# This path is relative to the pollution_agent package; created on first write.
LIVE_DATA_DIR: Path = BASE_DIR / "data" / "live_accumulation"

# Minimum consecutive live days before the forecast model automatically
# switches its INPUT SOURCE from the historical archive to live accumulation.
MIN_LIVE_DAYS_FOR_FORECAST: int = 14

# Maximum age of a live OpenAQ measurement before it is considered stale.
# Default is strictly 3 hours per Requirement 5.
OPENAQ_STALE_HOURS: int = int(os.getenv("OPENAQ_STALE_HOURS", "3"))


