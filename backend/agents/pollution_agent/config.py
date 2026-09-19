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
