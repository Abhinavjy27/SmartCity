"""
Configuration for Unified Spatial-Temporal Hyderabad Pollution Forecaster.
"""
from pathlib import Path
import numpy as np

BASE_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"
WORKSPACE_DIR = Path(__file__).resolve().parents[4]
DATA_DIR = WORKSPACE_DIR / "datasets" / "raw" / "pollution"

# 13 Real Hyderabad TSPCB CAAQMS Stations with verified coordinates
STATION_COORDS = {
    "Bollaram Industrial Area, Hyderabad - TSPCB": (17.5380, 78.3459),
    "Central University, Hyderabad - TSPCB": (17.4618, 78.3340),
    "ECIL Kapra, Hyderabad - TSPCB": (17.4719, 78.5707),
    "ICRISAT Patancheru, Hyderabad - TSPCB": (17.4529, 78.2756),
    "IDA Pashamylaram, Hyderabad - TSPCB": (17.5335, 78.2082),
    "Kokapet, Hyderabad - TSPCB": (17.4083, 78.3508),
    "Kompally Municipal Office, Hyderabad - TSPCB": (17.5433, 78.4889),
    "Nacharam_TSIIC IALA, Hyderabad - TSPCB": (17.4282, 78.5522),
    "New Malakpet, Hyderabad - TSPCB": (17.3645, 78.4983),
    "Ramachandrapuram, Hyderabad - TSPCB": (17.4449, 78.2711),
    "Sanathnagar, Hyderabad - TSPCB": (17.4509, 78.4483),
    "Somajiguda, Hyderabad - TSPCB": (17.4235, 78.4650),
    "Zoo Park, Hyderabad - TSPCB": (17.3508, 78.4527),
}

STATION_NAMES = sorted(list(STATION_COORDS.keys()))
NUM_STATIONS = len(STATION_NAMES)  # 13

# Target Criteria Pollutants for CPCB AQI Engine
PRIMARY_TARGETS = ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"]
NUM_TARGETS = len(PRIMARY_TARGETS)  # 6

# Feature Set per station
POLLUTANT_INPUTS = ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3", "NH3"]
METEO_INPUTS = ["AT", "RH", "WS", "BP", "SR"]
TEMPORAL_FEATURES = [
    "month_sin", "month_cos",
    "day_of_week_sin", "day_of_week_cos",
    "day_of_year_sin", "day_of_year_cos"
]

ALL_FEATURES = POLLUTANT_INPUTS + METEO_INPUTS + TEMPORAL_FEATURES
NUM_FEATURES = len(ALL_FEATURES)  # 7 + 5 + 6 = 18

# Model Horizon and Context Window
FORECAST_HORIZON = 7      # D1 through D7
CONTEXT_LENGTH = 14        # 14 days of historical context

# Strict Chronological Splits (Zero Data Leakage)
TRAIN_START_DATE = "2024-01-01"
TRAIN_END_DATE = "2025-06-30"    # 547 calendar days (1.5 years)
VAL_START_DATE = "2025-07-01"
VAL_END_DATE = "2025-09-30"      # 92 calendar days (Monsoon transition)
TEST_START_DATE = "2025-10-01"
TEST_END_DATE = "2025-12-31"     # 92 calendar days (Winter regime, untouched)

# Training Hyperparameters
RANDOM_SEED = 42
BATCH_SIZE = 16
LEARNING_RATE = 1e-3
NUM_EPOCHS = 80
PATIENCE = 15
WEIGHT_DECAY = 1e-4

# Build Geodesic Distance Matrix (Haversine formula, km)
def compute_distance_matrix():
    lat_lon = np.array([STATION_COORDS[name] for name in STATION_NAMES])
    R = 6371.0  # Earth radius in km
    lat1 = np.radians(lat_lon[:, 0, None])
    lon1 = np.radians(lat_lon[:, 1, None])
    lat2 = np.radians(lat_lon[None, :, 0])
    lon2 = np.radians(lat_lon[None, :, 1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2)**2
    dists = 2 * R * np.arcsin(np.sqrt(a))
    return dists

DISTANCE_MATRIX = compute_distance_matrix()
