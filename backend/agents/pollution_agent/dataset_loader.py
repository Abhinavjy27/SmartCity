import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Resolve repository root: backend/agents/pollution_agent/dataset_loader.py -> SmartCity/
_MODULE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _MODULE_DIR.parent.parent.parent

# Canonical target output of scripts/download_datasets.py
_OPEN_METEO_DATASET_PATH = str(_REPO_ROOT / "datasets" / "raw" / "pollution" / "hyderabad_air_quality_2020_2024.csv")
# Legacy dataset path
_LEGACY_DATASET_PATH = str(_REPO_ROOT / "datasets" / "pollution_telemetry.csv")


class PollutionCalculator:
    def __init__(self, dataset_path: Optional[str] = None):
        if dataset_path is None:
            env_path = os.getenv("POLLUTION_DATASET_PATH")
            if env_path:
                dataset_path = env_path
            elif os.path.exists(_OPEN_METEO_DATASET_PATH):
                dataset_path = _OPEN_METEO_DATASET_PATH
            elif os.path.exists(_LEGACY_DATASET_PATH):
                dataset_path = _LEGACY_DATASET_PATH
            else:
                dataset_path = _OPEN_METEO_DATASET_PATH
        self.dataset_path = self._resolve_dataset_path(dataset_path)

    @staticmethod
    def _resolve_dataset_path(path: str) -> str:
        """Resolve dataset path robustly against repository root or module directory."""
        if not path:
            return _OPEN_METEO_DATASET_PATH

        # 1. Direct path exists
        if os.path.exists(path):
            return os.path.abspath(path)

        # 2. Relative to repository root
        repo_candidate = _REPO_ROOT / path.lstrip("/\\")
        if repo_candidate.exists():
            return str(repo_candidate.resolve())

        # 3. Inside repo datasets/ directory or datasets/raw/pollution/
        for sub in ["datasets", os.path.join("datasets", "raw", "pollution")]:
            cand = _REPO_ROOT / sub / Path(path).name
            if cand.exists():
                return str(cand.resolve())

        # 4. Relative to module directory (legacy relative fallback)
        module_candidate = (_MODULE_DIR / path).resolve()
        if module_candidate.exists():
            return str(module_candidate)

        # 5. Handle filename keywords to canonical paths
        if "hyderabad_air_quality" in path:
            return _OPEN_METEO_DATASET_PATH
        if "pollution_telemetry.csv" in path:
            if os.path.exists(_OPEN_METEO_DATASET_PATH) and not os.path.exists(_LEGACY_DATASET_PATH):
                return _OPEN_METEO_DATASET_PATH
            return _LEGACY_DATASET_PATH

        return os.path.abspath(path) if not os.path.isabs(path) else path

    def is_dataset_available(self) -> bool:
        """Check whether the underlying pollution telemetry dataset file exists on disk."""
        return os.path.exists(self.dataset_path)

    def _apply_dispersion_multiplier(self, base_val: float, hour: int) -> float:
        """
        Simplified deterministic dispersion physics model.
        Pollutants concentrate more heavily at night/early morning due to lower inversion layers
        and lower wind dispersion (approximated here by time-of-day).
        """
        # A sinusoidal multiplier where pollution is higher early morning and late night.
        # Peaks around 4 AM (1.3x), lowest around 4 PM (0.7x)
        time_factor = 1.0 + 0.3 * np.cos((hour - 4) * np.pi / 12)
        return float(base_val * time_factor)

    def calculate_metrics(self, location: str, hour: int = None) -> dict:
        try:
            # Check if file has Open-Meteo metadata header lines before data table
            skip_idx = 0
            if isinstance(self.dataset_path, str) and os.path.exists(self.dataset_path):
                try:
                    with open(self.dataset_path, "r", encoding="utf-8", errors="ignore") as f:
                        for idx in range(15):
                            line = f.readline()
                            if not line:
                                break
                            line_lower = line.lower()
                            if "time" in line_lower and any(k in line_lower for k in ["pm10", "pm2_5", "us_aqi", "aqi"]):
                                skip_idx = idx
                                break
                except Exception:
                    skip_idx = 0

            if skip_idx > 0:
                df = pd.read_csv(self.dataset_path, skiprows=skip_idx)
            else:
                df = pd.read_csv(self.dataset_path)
        except FileNotFoundError:
            logger.warning(
                f"[PollutionCalculator] Dataset file not found at '{self.dataset_path}'. "
                f"No pollution telemetry dataset exists in the repository. "
                f"Returning empty metrics for location '{location}'."
            )
            return {}
        except Exception as exc:
            logger.error(f"[PollutionCalculator] Error reading dataset at '{self.dataset_path}': {exc}")
            return {}

        # Adapt Open-Meteo column names:
        # us_aqi / us_aqi (USAQI) -> aqi
        # pm2_5 / pm2_5 (μg/m³) -> pm25
        # pm10 / pm10 (μg/m³) -> pm10
        rename_map = {}
        for col in df.columns:
            clean_col = str(col).strip().lower()
            if ("us_aqi" in clean_col or "aqi" in clean_col) and "aqi" not in df.columns:
                rename_map[col] = "aqi"
            elif ("pm2_5" in clean_col or "pm25" in clean_col or "pm2.5" in clean_col) and "pm25" not in df.columns:
                rename_map[col] = "pm25"
            elif "pm10" in clean_col and "pm10" not in df.columns:
                rename_map[col] = "pm10"
        if rename_map:
            df = df.rename(columns=rename_map)

        # Handle location filtering and Open-Meteo default location:
        # The Open-Meteo dataset has no location column because it represents the fixed Hyderabad coordinate:
        # latitude=17.3850, longitude=78.4867.
        req_loc = str(location or "").strip().lower()
        if "location" not in df.columns:
            # Regional dataset defaults to "Hyderabad"
            if "hyderabad" in req_loc:
                df_filtered = df
            else:
                logger.warning(
                    f"[PollutionCalculator] Dataset '{self.dataset_path}' has no 'location' column "
                    f"and defaults to 'Hyderabad'. Requested location '{location}' does not match."
                )
                return {}
        else:
            df_filtered = df[df["location"].astype(str).str.lower() == req_loc]
            # If exact match empty and query includes city after comma (e.g. 'Narayanguda, Hyderabad')
            if df_filtered.empty and "," in req_loc:
                city_part = req_loc.split(",")[-1].strip()
                df_filtered = df[df["location"].astype(str).str.lower() == city_part]

        if df_filtered.empty:
            return {}

        avg_aqi = df_filtered["aqi"].mean() if "aqi" in df_filtered.columns else 0
        avg_pm25 = df_filtered["pm25"].mean() if "pm25" in df_filtered.columns else 0.0
        avg_pm10 = df_filtered["pm10"].mean() if "pm10" in df_filtered.columns else 0.0

        stations = []
        if "station_name" in df_filtered.columns:
            stations = df_filtered["station_name"].dropna().unique().tolist()

        # Apply deterministic physics dispersion based on current hour
        if hour is None:
            hour = datetime.now().hour

        computed_aqi = int(self._apply_dispersion_multiplier(avg_aqi, hour)) if pd.notna(avg_aqi) else 0
        computed_pm25 = self._apply_dispersion_multiplier(avg_pm25, hour) if pd.notna(avg_pm25) else 0.0
        computed_pm10 = self._apply_dispersion_multiplier(avg_pm10, hour) if pd.notna(avg_pm10) else 0.0

        return {
            "city_avg_aqi": computed_aqi,
            "pm25": round(computed_pm25, 1),
            "pm10": round(computed_pm10, 1),
            "stations": stations,
        }
