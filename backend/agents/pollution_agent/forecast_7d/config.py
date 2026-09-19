"""
Configuration parameters for the 7-Day Hyderabad Multi-Horizon Forecasting Pipeline.
Strictly isolated within the Pollution Agent.
"""
from pathlib import Path

# Paths
MODULE_DIR = Path(__file__).resolve().parent
AGENT_DIR = MODULE_DIR.parent
BACKEND_DIR = AGENT_DIR.parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "datasets" / "raw" / "pollution"
ARTIFACTS_DIR = MODULE_DIR / "artifacts"

# Ensure artifacts directory exists
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# Primary forecasting targets (6 CPCB criteria pollutants)
PRIMARY_TARGETS = ["PM2.5", "PM10", "NO2", "SO2", "O3", "CO"]
NUM_TARGETS = len(PRIMARY_TARGETS)

# In-situ meteorological variables present in TSPCB CAAQMS files
METEO_FEATURES = ["AT", "RH", "WS", "BP", "SR"]

# Temporal cyclical features
TEMPORAL_FEATURES = [
    "month_sin", "month_cos",
    "day_of_year_sin", "day_of_year_cos",
    "day_of_week_sin", "day_of_week_cos"
]

# Forecast parameters
FORECAST_HORIZON = 7  # Multi-horizon Direct: D1 to D7
CONTEXT_LENGTHS = [7, 14, 30]
DEFAULT_CONTEXT_LENGTH = 30

# Chronological Train / Validation / Test boundaries
# Strict temporal ordering: older -> train, middle -> val, most recent -> test
TRAIN_START_DATE = "2024-01-01"
TRAIN_END_DATE = "2025-06-30"

VAL_START_DATE = "2025-07-01"
VAL_END_DATE = "2025-09-30"

TEST_START_DATE = "2025-10-01"
TEST_END_DATE = "2025-12-31"

# Reproducibility
RANDOM_SEED = 42

# Training Hyperparameters
BATCH_SIZE = 32
LEARNING_RATE = 1e-3
NUM_EPOCHS = 100
PATIENCE = 15
WEIGHT_DECAY = 1e-4

# Completeness threshold for daily city aggregation (matching production)
MIN_DAILY_READINGS = 48  # Minimum valid 15-minute readings (out of expected 96/station)
MIN_COMPLETENESS_RATIO = 0.5  # 50% city coverage ratio
