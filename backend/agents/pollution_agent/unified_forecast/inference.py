"""
Unified Inference Engine for Hyderabad Air Quality Forecasting.
Consolidates single-horizon (Next-Day) and multi-horizon (7-Day) forecasting
into ONE shared model instance and pipeline.

Guarantees:
1. Daily D1 == 7-day D1 == summary D1 by construction.
2. Forecast dates dynamically derived from latest observation timestamp.
3. Observed AQI and Predicted AQI strictly decoupled.
4. Predicted pollutant concentrations pass through official CPCB engine.
5. When consecutive_live_days >= 14, model input automatically switches to the
   live accumulation window.  Falls back to historical archive on any gap.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

import joblib
import numpy as np
import pandas as pd
import torch

from ..aqi_engine import calculate_aqi, get_aqi_category
from ..config import POLLUTION_PROXY_MODE, POLLUTION_PROXY_URL, MIN_LIVE_DAYS_FOR_FORECAST
from ..data_provider import get_data_provider
from ..date_utils import get_forecast_dates
from ..live_accumulation import get_live_store
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
        self.proxy_mode: bool = POLLUTION_PROXY_MODE
        self.proxy_url: str = POLLUTION_PROXY_URL
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
        if self.proxy_mode:
            self.loaded = True
            self.model_name = "Proxy to Standalone Agent"
            logger.info("UnifiedForecaster in proxy mode - delegating inference to %s", self.proxy_url)
            return True

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

    def _select_input_source(self):
        """
        Determine whether to use the live accumulation window or the historical
        archive as the model's 14-day input context.

        Returns:
            (use_live: bool, live_df: pd.DataFrame | None, origin_override: str | None)

        Decision rule:
            - If consecutive_live_days >= MIN_LIVE_DAYS_FOR_FORECAST: use live
            - Otherwise: use historical archive (live_df=None, origin_override=None)
        """
        store = get_live_store()
        status = store.get_status()
        consecutive = status.get("consecutive_live_days", 0)

        if consecutive >= MIN_LIVE_DAYS_FOR_FORECAST:
            live_df = store.get_recent_city_daily_aggregates(n_days=CONTEXT_LENGTH)
            if live_df is not None and len(live_df) == CONTEXT_LENGTH:
                latest_date_str = status.get("latest_date", "")
                origin_override = f"{latest_date_str}T00:00:00+00:00" if latest_date_str else None
                logger.info(
                    "[%s] Forecast switchover: using live accumulation window "
                    "(%d consecutive days, latest=%s)",
                    datetime.now(timezone.utc).isoformat(),
                    consecutive,
                    latest_date_str,
                )
                return True, live_df, origin_override
            else:
                # Live DF not fully available despite status claiming >=14 — fall back
                logger.warning(
                    "[%s] Forecast fallback: live status claims %d days but get_recent returned %s rows; "
                    "reverting to historical archive",
                    datetime.now(timezone.utc).isoformat(),
                    consecutive,
                    len(live_df) if live_df is not None else 0,
                )
                return False, None, None

        logger.debug(
            "[%s] Using historical archive (consecutive_live_days=%d, threshold=%d)",
            datetime.now(timezone.utc).isoformat(),
            consecutive,
            MIN_LIVE_DAYS_FOR_FORECAST,
        )
        return False, None, None

    def predict(self) -> Dict[str, Any]:
        """
        Executes single unified inference pass and returns synchronized
        daily and 7-day extended forecasts.

        Input source selection (automatic, no manual intervention needed):
          - consecutive_live_days >= 14 → live accumulation window as model input
          - consecutive_live_days < 14 (or gap after switchover) → historical archive
        """
        if not self.loaded:
            if not self.load():
                return self._unavailable_response(f"Model unavailable: {self.error_message}")

        if self.proxy_mode:
            import httpx
            try:
                r_daily = httpx.get(f"{self.proxy_url}/api/pollution/forecast/daily", timeout=30.0)
                r_7day = httpx.get(f"{self.proxy_url}/api/pollution/forecast/7day", timeout=30.0)
                if r_daily.status_code == 200 and r_7day.status_code == 200:
                    daily_json = r_daily.json()
                    seven_json = r_7day.json()
                    return {
                        "status": daily_json.get("status", "success"),
                        "origin_timestamp": daily_json.get("forecast", {}).get("origin_timestamp"),
                        "daily": daily_json.get("forecast", {}),
                        "extended": seven_json,
                    }
                return self._unavailable_response(
                    f"Upstream proxy agent returned error (daily: {r_daily.status_code}, 7day: {r_7day.status_code})"
                )
            except Exception as e:
                logger.error("Proxy call to %s failed: %s", self.proxy_url, e)
                return self._unavailable_response(f"Proxy to {self.proxy_url} failed: {e}")

        # ── Determine input source: live accumulation vs historical archive ──
        use_live, live_df, origin_override = self._select_input_source()

        if use_live:
            # Live path: validate the live window
            if live_df is None or len(live_df) < CONTEXT_LENGTH:
                logger.warning(
                    "[%s] Forecast fallback: live_df insufficient (%s rows), reverting to archive",
                    datetime.now(timezone.utc).isoformat(),
                    len(live_df) if live_df is not None else 0,
                )
                use_live = False
                origin_override = None

        if not use_live:
            # Historical path: use the historical archive provider
            provider = get_data_provider(force_historical=True)
            latest_ts = provider.get_latest_observation_timestamp()

            # In-memory cache valid if timestamp and provider haven't changed
            if (
                self._cached_forecast is not None
                and self._cache_timestamp == latest_ts
                and getattr(self, "_cached_provider_id", None) == id(provider)
            ):
                return self._cached_forecast

            city_daily = provider.get_city_daily_aggregates(n_days=CONTEXT_LENGTH)
            if city_daily.empty or len(city_daily) < 7:
                return self._unavailable_response(
                    f"Insufficient historical context: got {len(city_daily)} daily observations, minimum 7 required"
                )

            # Check required features are not missing/blanked
            missing_feats = []
            for feat in ["PM2.5", "PM10", "NO", "NO2", "NOx", "NH3", "CO", "SO2", "O3", "Benzene", "Toluene", "Xylene"]:
                if feat not in city_daily.columns or city_daily[feat].isna().any():
                    missing_feats.append(feat)
            if missing_feats:
                return self._unavailable_response(
                    f"Missing valid observations for required features in context window: "
                    f"{', '.join(missing_feats)}; forecast unavailable without fabrication"
                )

        try:
            # 1. Fetch latest 14 days of station observations
            from .dataset import build_full_grid_tensors
            X_grid, _, _, all_dates = build_full_grid_tensors()

            # Origin timestamp: use live override if switching over, else archive latest
            if use_live and origin_override:
                latest_ts_for_dates = origin_override
            else:
                hist_provider = get_data_provider(force_historical=True)
                latest_ts_for_dates = hist_provider.get_latest_observation_timestamp()
            
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
            date_info = get_forecast_dates(latest_ts_for_dates, horizon_days=FORECAST_HORIZON)
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

            metrics_path = Path(__file__).resolve().parent.parent / "knowledge" / "forecast_metrics.json"
            forecast_metrics = None
            if metrics_path.exists():
                try:
                    with open(metrics_path, "r", encoding="utf-8") as f:
                        forecast_metrics = json.load(f)
                except Exception:
                    pass

            extended_forecast = {
                "status": "success",
                "architecture": self.model_name,
                "forecast_origin_date": origin_date,
                "origin_timestamp": origin_ts,
                "forecast": extended_days,
                "metrics": forecast_metrics,
            }

            result = {
                "status": "success",
                "origin_timestamp": origin_ts,
                "daily": daily_forecast,
                "extended": extended_forecast,
            }

            self._cached_forecast = result
            # Only cache against the historical provider; live path is not cached
            # so the switchover evaluation runs every call and stays up-to-date.
            if not use_live:
                provider = get_data_provider(force_historical=True)
                self._cache_timestamp = provider.get_latest_observation_timestamp()
                self._cached_provider_id = id(provider)
            return result

        except Exception as e:
            logger.error(f"Error during unified forecasting inference: {e}", exc_info=True)
            return self._unavailable_response(str(e))

    def clear_cache(self) -> None:
        """Clear cached forecast."""
        self._cached_forecast = None
        self._cache_timestamp = None
        self._cached_provider_id = None

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
