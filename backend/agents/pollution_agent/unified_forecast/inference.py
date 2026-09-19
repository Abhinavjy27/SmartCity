"""
Unified Inference Engine for Hyderabad Air Quality Forecasting.
Consolidates single-horizon (Next-Day) and multi-horizon (7-Day) forecasting
into ONE shared model instance and pipeline.

Guarantees:
1. Daily D1 == 7-day D1 == summary D1 by construction.
2. Forecast dates dynamically derived from latest observation timestamp.
3. Observed AQI and Predicted AQI strictly decoupled.
4. Predicted pollutant concentrations pass through official CPCB engine.
"""
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

import joblib
import numpy as np
import pandas as pd
import torch

from ..aqi_engine import calculate_aqi, get_aqi_category
from ..data_provider import get_data_provider
from ..date_utils import get_forecast_dates
from .config import (
    ARTIFACTS_DIR,
    STATION_NAMES,
    PRIMARY_TARGETS,
    CONTEXT_LENGTH,
    FORECAST_HORIZON,
    NUM_FEATURES,
    NUM_TARGETS,
    NUM_STATIONS,
    POLLUTANT_INPUTS,
    METEO_INPUTS,
)
from .models import SpatialTemporalGATGRU, TemporalOnlyGRU, TemporalGRU_KNNCovariate

logger = logging.getLogger(__name__)


class UnifiedForecaster:
    """
    Singleton unified forecaster running the selected best model.
    """
    _instance: Optional["UnifiedForecaster"] = None

    def __init__(self):
        self.model: Optional[torch.nn.Module] = None
        self.model_name: str = "Unavailable"
        self.feature_scaler = None
        self.target_scaler = None
        self.loaded: bool = False
        self.error_message: Optional[str] = None
        self._cached_forecast: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[str] = None

    @classmethod
    def get_instance(cls) -> "UnifiedForecaster":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.load()
        return cls._instance

    def load(self) -> bool:
        """Loads frozen best model weights and scalers."""
        model_path = ARTIFACTS_DIR / "unified_best_model.pt"
        scalers_path = ARTIFACTS_DIR / "scalers.joblib"

        if not model_path.exists() or not scalers_path.exists():
            self.loaded = False
            self.error_message = f"Unified model artifacts not found at {model_path}"
            logger.warning(self.error_message)
            return False

        try:
            # Load scalers
            scalers = joblib.load(scalers_path)
            self.feature_scaler = scalers["feature_scaler"]
            self.target_scaler = scalers["target_scaler"]

            # Load model checkpoint
            checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
            self.model_name = checkpoint.get("model_name", "UnifiedSpatialTemporalModel")

            if "GAT" in self.model_name:
                self.model = SpatialTemporalGATGRU(
                    in_features=checkpoint.get("in_features", NUM_FEATURES),
                    hidden_dim=checkpoint.get("hidden_dim", 64),
                    num_stations=checkpoint.get("num_stations", NUM_STATIONS),
                    horizon=checkpoint.get("horizon", FORECAST_HORIZON),
                    num_targets=checkpoint.get("num_targets", NUM_TARGETS),
                )
            elif "KNN" in self.model_name:
                self.model = TemporalGRU_KNNCovariate(
                    num_stations=checkpoint.get("num_stations", NUM_STATIONS),
                    base_features=checkpoint.get("in_features", NUM_FEATURES),
                    knn_features=checkpoint.get("num_targets", NUM_TARGETS),
                    hidden_dim=checkpoint.get("hidden_dim", 64),
                    horizon=checkpoint.get("horizon", FORECAST_HORIZON),
                    num_targets=checkpoint.get("num_targets", NUM_TARGETS),
                )
            else:
                self.model = TemporalOnlyGRU(
                    in_features=checkpoint.get("in_features", NUM_FEATURES),
                    hidden_dim=checkpoint.get("hidden_dim", 64),
                    num_stations=checkpoint.get("num_stations", NUM_STATIONS),
                    horizon=checkpoint.get("horizon", FORECAST_HORIZON),
                    num_targets=checkpoint.get("num_targets", NUM_TARGETS),
                )

            self.model.load_state_dict(checkpoint["state_dict"])
            self.model.eval()
            self.loaded = True
            logger.info(f"UnifiedForecaster successfully loaded: {self.model_name}")
            return True
        except Exception as e:
            self.loaded = False
            self.error_message = f"Failed to load unified forecaster: {e}"
            logger.error(self.error_message)
            return False

    def predict(self) -> Dict[str, Any]:
        """
        Executes single unified inference pass and returns synchronized
        daily and 7-day extended forecasts.
        """
        if not self.loaded:
            if not self.load():
                return self._unavailable_response(f"Model unavailable: {self.error_message}")

        provider = get_data_provider()
        latest_ts = provider.get_latest_observation_timestamp()

        # Check in-memory cache if data hasn't updated
        if self._cached_forecast is not None and self._cache_timestamp == latest_ts:
            return self._cached_forecast

        try:
            # 1. Fetch latest 14 days of station observations
            from .dataset import build_full_grid_tensors
            X_grid, _, _, all_dates = build_full_grid_tensors()
            
            # The last 14 days of X_grid represent the most recent available context window
            # X has shape (TotalDays=731, Stations=13, Features=18)
            context_raw = X_grid[-CONTEXT_LENGTH:, :, :]  # (14, 13, 18)
            
            # Scale features
            T, S, F = context_raw.shape
            context_flat = context_raw.reshape(-1, F)
            context_norm = self.feature_scaler.transform(context_flat).reshape(T, S, F)
            
            # Transpose to (Batch=1, Stations=13, Context=14, Features=18)
            input_tensor = torch.tensor(
                np.transpose(context_norm, (1, 0, 2))[np.newaxis, :, :, :],
                dtype=torch.float32
            )

            # 2. Run Forward Pass
            with torch.no_grad():
                pred_norm = self.model(input_tensor).numpy()  # (1, 13, 7, 6)

            # 3. Denormalize Predictions
            pred_norm_flat = pred_norm.reshape(-1, NUM_TARGETS)
            pred_real_flat = self.target_scaler.inverse_transform(pred_norm_flat)
            pred_real = np.clip(pred_real_flat.reshape(NUM_STATIONS, FORECAST_HORIZON, NUM_TARGETS), 0.0, None)
            # pred_real: (Stations=13, Horizon=7, Targets=6)

            # 4. Compute Citywide Daily Predictions per Horizon
            # Average across stations for each horizon
            city_preds = np.mean(pred_real, axis=0)  # (Horizon=7, Targets=6)

            # 5. Dynamic Date Generation
            date_info = get_forecast_dates(latest_ts, horizon_days=FORECAST_HORIZON)
            horizons = date_info["horizons"]
            origin_ts = date_info["origin_timestamp"]
            origin_date = date_info["origin_date"]

            extended_days = []
            for h_idx in range(FORECAST_HORIZON):
                h_num = h_idx + 1
                date_meta = horizons[h_idx]
                
                conc_dict = {
                    PRIMARY_TARGETS[i]: round(float(city_preds[h_idx, i]), 2)
                    for i in range(NUM_TARGETS)
                }
                
                # Official CPCB AQI Calculation on predicted concentrations
                aqi_res = calculate_aqi(conc_dict)
                h_aqi = aqi_res.get("aqi")
                h_cat = aqi_res.get("category", "Moderate")
                h_col = aqi_res.get("color", "#F4A62A")
                h_dom = aqi_res.get("dominant_pollutant", "PM2.5")

                extended_days.append({
                    "day": h_num,
                    "horizon_days": h_num,
                    "target_date": date_meta["target_date"],
                    "target_timestamp": date_meta["target_timestamp"],
                    "display_date": date_meta["display_date"],
                    "aqi": h_aqi,
                    "predicted_aqi": h_aqi,
                    "category": h_cat,
                    "color": h_col,
                    "dominant_pollutant": h_dom,
                    "concentrations": conc_dict,
                    "model": self.model_name,
                })

            # Day 1 is the exact first horizon
            d1 = extended_days[0]

            daily_forecast = {
                "forecast_aqi": d1["aqi"],
                "forecast_status": "success",
                "source": "unified_spatial_temporal_model",
                "model_name": self.model_name,
                "forecast_horizon": "1 Day (Next-Day)",
                "forecast_date": d1["target_date"],
                "display_date": d1["display_date"],
                "target_timestamp": d1["target_timestamp"],
                "origin_timestamp": origin_ts,
                "sequence_days": CONTEXT_LENGTH,
                "category": d1["category"],
                "color": d1["color"],
                "dominant_pollutant": d1["dominant_pollutant"],
                "predicted_concentrations": d1["concentrations"],
                "confidence": "High (Unified CPCB Spatial-Temporal Model)",
                "methodology": "Unified Spatial-Temporal Deep Learning with CPCB Engine",
            }

            extended_forecast = {
                "status": "success",
                "architecture": self.model_name,
                "forecast_origin_date": origin_date,
                "origin_timestamp": origin_ts,
                "forecast": extended_days,
            }

            result = {
                "status": "success",
                "origin_timestamp": origin_ts,
                "daily": daily_forecast,
                "extended": extended_forecast,
            }

            self._cached_forecast = result
            self._cache_timestamp = latest_ts
            return result

        except Exception as e:
            logger.error(f"Error during unified forecasting inference: {e}", exc_info=True)
            return self._unavailable_response(str(e))

    def _unavailable_response(self, reason: str) -> Dict[str, Any]:
        return {
            "status": "unavailable",
            "reason": reason,
            "daily": {
                "forecast_aqi": None,
                "forecast_status": "unavailable",
                "source": "unified_spatial_temporal_model",
                "reason": reason,
            },
            "extended": {
                "status": "unavailable",
                "reason": reason,
                "forecast": [],
            }
        }
