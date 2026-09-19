"""
Dataset generation and sequence creation for Hyderabad 7-day forecasting.
Strict chronological splitting and zero-leakage preprocessing.
"""
import glob
import os
import logging
from datetime import datetime, date
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from .config import (
    DATA_DIR,
    PRIMARY_TARGETS,
    METEO_FEATURES,
    TEMPORAL_FEATURES,
    FORECAST_HORIZON,
    DEFAULT_CONTEXT_LENGTH,
    TRAIN_START_DATE,
    TRAIN_END_DATE,
    VAL_START_DATE,
    VAL_END_DATE,
    TEST_START_DATE,
    TEST_END_DATE,
    MIN_DAILY_READINGS,
    MIN_COMPLETENESS_RATIO,
)

logger = logging.getLogger(__name__)


def build_city_daily_dataframe() -> pd.DataFrame:
    """
    Build clean city-level daily DataFrame from raw TSPCB files.
    Preserves verified production aggregation rules.
    """
    csv_files = sorted(glob.glob(str(DATA_DIR / "hyd-*-tspcb-2024-25.csv")))
    if not csv_files:
        raise FileNotFoundError(f"No TSPCB CSV files found in {DATA_DIR}")

    all_target_cols = [
        "PM2.5", "PM10", "NO", "NO2", "NOx", "NH3",
        "SO2", "CO", "O3", "Benzene", "Toluene", "Xylene"
    ]
    all_meteo_cols = ["AT", "RH", "WS", "WD", "RF", "TOT-RF", "SR", "BP", "VWS"]

    frames = []
    for f in csv_files:
        df = pd.read_csv(f, on_bad_lines="skip", low_memory=False)
        base = os.path.basename(f)
        stem = base.replace("hyd-", "").replace("-tspcb-2024-25.csv", "").replace("-", " ").title()
        s_name = df["Station Name"].dropna().iloc[0] if "Station Name" in df.columns and len(df["Station Name"].dropna()) > 0 else stem

        ts_col = "Timestamp" if "Timestamp" in df.columns else "To Date"
        df["dt"] = pd.to_datetime(df[ts_col], errors="coerce")
        df["Date"] = df["dt"].dt.date
        df["Station"] = s_name

        col_map = {}
        for c in df.columns:
            prefix = c.split("(")[0].strip().lower()
            if prefix in ["pm2.5", "pm10", "no", "no2", "nox", "nh3", "so2", "co", "ozone", "o3", "benzene", "toluene", "xylene"]:
                canon = "O3" if prefix in ["ozone", "o3"] else prefix.upper() if prefix in ["no", "no2", "nox", "nh3", "so2", "co"] else "PM2.5" if prefix == "pm2.5" else "PM10" if prefix == "pm10" else prefix.capitalize()
                col_map[c] = canon
            elif prefix in ["at", "rh", "ws", "wd", "rf", "tot-rf", "sr", "bp", "vws"]:
                col_map[c] = prefix.upper()
        df.rename(columns=col_map, inplace=True)

        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)

    # Physical validity checks (§2)
    for p in all_target_cols:
        if p in combined.columns:
            s = pd.to_numeric(combined[p], errors="coerce")
            combined[p] = s.where((s >= 0) & np.isfinite(s), np.nan)

    for m in all_meteo_cols:
        if m in combined.columns:
            s = pd.to_numeric(combined[m], errors="coerce")
            combined[m] = s.where(np.isfinite(s) & (s >= 0), np.nan)

    # Daily aggregation
    grouped = combined.groupby("Date")
    daily_rows = []

    for dt, grp in grouped:
        n_stations = grp["Station"].nunique()
        expected = n_stations * 96
        row = {
            "date": str(dt),
            "date_obj": dt,
            "stations_active": n_stations,
            "expected_obs": expected,
            "total_obs": len(grp)
        }
        for p in PRIMARY_TARGETS:
            valid_obs = grp[p].dropna()
            count = len(valid_obs)
            ratio = count / expected if expected > 0 else 0.0
            row[f"{p}_count"] = count
            row[f"{p}_ratio"] = round(ratio, 4)
            if count >= MIN_DAILY_READINGS and ratio >= MIN_COMPLETENESS_RATIO:
                row[p] = float(valid_obs.mean())
            else:
                row[p] = np.nan

        for m in METEO_FEATURES:
            if m in grp.columns:
                valid_m = grp[m].dropna()
                row[m] = float(valid_m.mean()) if len(valid_m) >= MIN_DAILY_READINGS else np.nan
            else:
                row[m] = np.nan

        daily_rows.append(row)

    df_daily = pd.DataFrame(daily_rows)
    df_daily.sort_values("date", inplace=True)
    df_daily.reset_index(drop=True, inplace=True)

    # Add cyclical calendar features
    dt_series = pd.to_datetime(df_daily["date"])
    months = dt_series.dt.month
    day_of_year = dt_series.dt.dayofyear
    day_of_week = dt_series.dt.dayofweek

    df_daily["month_sin"] = np.sin(2 * np.pi * months / 12.0)
    df_daily["month_cos"] = np.cos(2 * np.pi * months / 12.0)
    df_daily["day_of_year_sin"] = np.sin(2 * np.pi * day_of_year / 365.25)
    df_daily["day_of_year_cos"] = np.cos(2 * np.pi * day_of_year / 365.25)
    df_daily["day_of_week_sin"] = np.sin(2 * np.pi * day_of_week / 7.0)
    df_daily["day_of_week_cos"] = np.cos(2 * np.pi * day_of_week / 7.0)

    return df_daily


def extract_continuous_blocks(
    df: pd.DataFrame,
    required_cols: List[str]
) -> List[pd.DataFrame]:
    """
    Extract contiguous sub-DataFrames where all required_cols are valid
    and calendar dates have no gap (> 1 day).
    """
    df_sorted = df.sort_values("date").copy()
    valid_mask = df_sorted[required_cols].notnull().all(axis=1)

    dt_series = pd.to_datetime(df_sorted["date"])
    date_gap = dt_series.diff().dt.days > 1
    split_flag = date_gap | (~valid_mask)
    block_ids = split_flag.cumsum()

    blocks = []
    for bid, group in df_sorted[valid_mask].groupby(block_ids):
        if len(group) > 0:
            blocks.append(group.copy().reset_index(drop=True))

    return blocks


def get_feature_columns(ablation_type: str = "all") -> List[str]:
    """
    Return feature columns based on ablation mode:
    - 'pollutants': Criteria pollutants only (6 features)
    - 'temporal': Pollutants + Calendar cyclical features (12 features)
    - 'all': Pollutants + Calendar + In-situ Meteorology (17 features)
    """
    if ablation_type == "pollutants":
        return list(PRIMARY_TARGETS)
    elif ablation_type == "temporal":
        return list(PRIMARY_TARGETS) + list(TEMPORAL_FEATURES)
    elif ablation_type in ("all", "meteo"):
        return list(PRIMARY_TARGETS) + list(TEMPORAL_FEATURES) + list(METEO_FEATURES)
    else:
        raise ValueError(f"Unknown ablation type: {ablation_type}")


class ForecastingDataset:
    """
    Generates supervised sliding-window sequences for multi-horizon 7-day forecasting.
    Enforces strict chronological train/val/test splits and zero data leakage.
    """

    def __init__(
        self,
        context_length: int = DEFAULT_CONTEXT_LENGTH,
        horizon: int = FORECAST_HORIZON,
        ablation_type: str = "all"
    ):
        self.context_length = context_length
        self.horizon = horizon
        self.ablation_type = ablation_type
        self.feature_cols = get_feature_columns(ablation_type)
        self.target_cols = list(PRIMARY_TARGETS)

        self.feature_scaler = StandardScaler()
        self.target_scaler = StandardScaler()
        self.is_fitted = False

        self.df_daily = None
        self.samples = []
        self.train_samples = []
        self.val_samples = []
        self.test_samples = []

    def prepare_data(self):
        """Build daily data, extract continuous blocks, and construct windows."""
        self.df_daily = build_city_daily_dataframe()

        # Handle any remaining missing meteo by forward-fill within continuous blocks
        blocks = extract_continuous_blocks(self.df_daily, self.target_cols)

        all_windows = []
        window_size = self.context_length + self.horizon

        for block in blocks:
            # If meteo is used, forward fill and backward fill within the valid block
            if "AT" in self.feature_cols:
                for m in METEO_FEATURES:
                    if m in block.columns:
                        block[m] = block[m].ffill().bfill()

            if len(block) < window_size:
                continue

            for i in range(len(block) - window_size + 1):
                window = block.iloc[i : i + window_size]
                x_df = window.iloc[: self.context_length]
                y_df = window.iloc[self.context_length :]

                origin_date = str(x_df["date"].iloc[-1])
                target_dates = [str(d) for d in y_df["date"].tolist()]

                all_windows.append({
                    "x": x_df[self.feature_cols].values.astype(np.float32),
                    "y": y_df[self.target_cols].values.astype(np.float32),
                    "origin_date": origin_date,
                    "target_dates": target_dates,
                    "first_target_date": target_dates[0],
                    "last_target_date": target_dates[-1]
                })

        self.samples = all_windows

        # Chronological Split (§10)
        # Train: target dates within [TRAIN_START_DATE, TRAIN_END_DATE]
        # Val: target dates within [VAL_START_DATE, VAL_END_DATE]
        # Test: target dates within [TEST_START_DATE, TEST_END_DATE]
        train = []
        val = []
        test = []

        for s in all_windows:
            last_t = s["last_target_date"]
            if last_t <= TRAIN_END_DATE:
                train.append(s)
            elif VAL_START_DATE <= s["first_target_date"] and last_t <= VAL_END_DATE:
                val.append(s)
            elif TEST_START_DATE <= s["first_target_date"] and last_t <= TEST_END_DATE:
                test.append(s)

        self.train_samples = train
        self.val_samples = val
        self.test_samples = test

        # Fit Scalers STRICTLY on Training Set (§10, §11)
        if len(train) == 0:
            raise ValueError("No training samples found in defined date range!")

        x_train_flat = np.concatenate([s["x"] for s in train], axis=0)
        y_train_flat = np.concatenate([s["y"] for s in train], axis=0)

        self.feature_scaler.fit(x_train_flat)
        self.target_scaler.fit(y_train_flat)
        self.is_fitted = True

        logger.info(
            f"Dataset prepared (C={self.context_length}, H={self.horizon}, ablation={self.ablation_type}): "
            f"Train={len(train)}, Val={len(val)}, Test={len(test)}"
        )

    def get_arrays(self, split: str = "train", normalize: bool = True) -> Tuple[np.ndarray, np.ndarray, List[dict]]:
        """
        Return (X, Y, metadata) arrays for given split.
        X shape: (N, context_length, num_features)
        Y shape: (N, horizon, 6)
        """
        if not self.is_fitted:
            self.prepare_data()

        split_map = {
            "train": self.train_samples,
            "val": self.val_samples,
            "test": self.test_samples,
            "all": self.samples
        }
        samples = split_map.get(split, [])
        if not samples:
            return np.empty((0, self.context_length, len(self.feature_cols))), np.empty((0, self.horizon, 6)), []

        X = np.stack([s["x"] for s in samples], axis=0)
        Y = np.stack([s["y"] for s in samples], axis=0)

        if normalize:
            N, C, F = X.shape
            X_norm = self.feature_scaler.transform(X.reshape(-1, F)).reshape(N, C, F)
            N, H, T = Y.shape
            Y_norm = self.target_scaler.transform(Y.reshape(-1, T)).reshape(N, H, T)
            return X_norm.astype(np.float32), Y_norm.astype(np.float32), samples

        return X, Y, samples

    def inverse_transform_targets(self, Y_norm: np.ndarray) -> np.ndarray:
        """Denormalize multi-horizon target predictions back to physical units (µg/m³, mg/m³)."""
        orig_shape = Y_norm.shape
        if len(orig_shape) == 3:
            N, H, T = orig_shape
            Y_flat = Y_norm.reshape(-1, T)
            Y_real = self.target_scaler.inverse_transform(Y_flat)
            return np.clip(Y_real.reshape(N, H, T), 0, None)  # Physical pollutant concentrations >= 0
        elif len(orig_shape) == 2:
            Y_real = self.target_scaler.inverse_transform(Y_norm)
            return np.clip(Y_real, 0, None)
        else:
            raise ValueError(f"Unsupported shape for inverse_transform: {orig_shape}")
