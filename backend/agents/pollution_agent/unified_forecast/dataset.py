"""
Spatial-Temporal Dataset for Hyderabad 13-Station CAAQMS Network.
Builds daily station-level and citywide tensors with zero data leakage.
"""
import glob
import os
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Tuple, Optional, Any

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler

from .config import (
    DATA_DIR,
    STATION_NAMES,
    NUM_STATIONS,
    PRIMARY_TARGETS,
    NUM_TARGETS,
    POLLUTANT_INPUTS,
    METEO_INPUTS,
    TEMPORAL_FEATURES,
    ALL_FEATURES,
    NUM_FEATURES,
    FORECAST_HORIZON,
    CONTEXT_LENGTH,
    TRAIN_START_DATE,
    TRAIN_END_DATE,
    VAL_START_DATE,
    VAL_END_DATE,
    TEST_START_DATE,
    TEST_END_DATE,
    BATCH_SIZE,
)

logger = logging.getLogger(__name__)


def load_all_station_daily_data() -> Dict[str, pd.DataFrame]:
    """
    Load raw 15-minute observations from all 13 TSPCB CSVs and aggregate to station-day level.
    """
    csv_files = sorted(glob.glob(str(DATA_DIR / "hyd-*-tspcb-2024-25.csv")))
    if len(csv_files) != NUM_STATIONS:
        logger.warning(f"Expected {NUM_STATIONS} CSV files, found {len(csv_files)}")

    station_data = {}

    for f in csv_files:
        df = pd.read_csv(f, on_bad_lines="skip", low_memory=False)
        base = os.path.basename(f)
        s_name = df["Station Name"].dropna().iloc[0] if "Station Name" in df.columns and len(df["Station Name"].dropna()) > 0 else base

        # Match to canonical station name
        matched_name = None
        for canonical in STATION_NAMES:
            if canonical == s_name or canonical.split(",")[0].strip() in s_name or s_name in canonical:
                matched_name = canonical
                break
        if not matched_name:
            matched_name = s_name

        ts_col = "Timestamp" if "Timestamp" in df.columns else "To Date"
        df["dt"] = pd.to_datetime(df[ts_col], errors="coerce", utc=True)
        df["date"] = df["dt"].dt.date

        # Column normalization
        col_map = {}
        for c in df.columns:
            prefix = c.split("(")[0].strip().lower()
            if prefix in ["pm2.5", "pm10", "no2", "so2", "co", "ozone", "o3", "nh3"]:
                canon = "O3" if prefix in ["ozone", "o3"] else "PM2.5" if prefix == "pm2.5" else "PM10" if prefix == "pm10" else prefix.upper()
                col_map[c] = canon
            elif prefix in ["at", "rh", "ws", "bp", "sr"]:
                col_map[c] = prefix.upper()
        df.rename(columns=col_map, inplace=True)

        # Physical validity bounds
        for p in POLLUTANT_INPUTS + METEO_INPUTS:
            if p in df.columns:
                s = pd.to_numeric(df[p], errors="coerce")
                df[p] = s.where((s >= 0) & np.isfinite(s), np.nan)

        # Aggregate to daily arithmetic mean
        avail_cols = [c for c in POLLUTANT_INPUTS + METEO_INPUTS if c in df.columns]
        daily = df.groupby("date")[avail_cols].mean()

        station_data[matched_name] = daily

    return station_data


def build_full_grid_tensors() -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[date]]:
    """
    Align all 13 stations across the continuous 731 calendar days (2024-01-01 to 2025-12-31).
    Returns:
        X_grid: (731, 13, 18) - (Days, Stations, Features)
        Y_grid: (731, 13, 6)  - (Days, Stations, Primary Targets)
        Y_city: (731, 6)      - (Days, Primary Targets) Citywide concentration-first mean
        all_dates: List of 731 date objects
    """
    station_data = load_all_station_daily_data()
    all_dates = [d.date() for d in pd.date_range("2024-01-01", "2025-12-31")]
    num_days = len(all_dates)

    X_grid = np.zeros((num_days, NUM_STATIONS, NUM_FEATURES), dtype=np.float32)
    Y_grid = np.zeros((num_days, NUM_STATIONS, NUM_TARGETS), dtype=np.float32)
    Y_city = np.zeros((num_days, NUM_TARGETS), dtype=np.float32)

    # 1. Fill raw pollutant and meteo features
    for s_idx, s_name in enumerate(STATION_NAMES):
        s_df = station_data.get(s_name, pd.DataFrame())

        for d_idx, dt in enumerate(all_dates):
            if dt in s_df.index:
                row = s_df.loc[dt]
                # Pollutants
                for p_idx, p in enumerate(POLLUTANT_INPUTS):
                    val = row.get(p, np.nan)
                    X_grid[d_idx, s_idx, p_idx] = float(val) if pd.notna(val) else np.nan

                # Meteo
                for m_idx, m in enumerate(METEO_INPUTS):
                    val = row.get(m, np.nan)
                    X_grid[d_idx, s_idx, len(POLLUTANT_INPUTS) + m_idx] = float(val) if pd.notna(val) else np.nan
            else:
                X_grid[d_idx, s_idx, :len(POLLUTANT_INPUTS) + len(METEO_INPUTS)] = np.nan

    # 2. Impute missing station sensor readings using robust spatial and temporal interpolation
    # For each pollutant/meteo feature:
    for f_idx in range(len(POLLUTANT_INPUTS) + len(METEO_INPUTS)):
        feature_slice = X_grid[:, :, f_idx]  # (731, 13)
        df_feat = pd.DataFrame(feature_slice, index=all_dates, columns=STATION_NAMES)

        # First interpolate temporally within each station
        df_feat = df_feat.interpolate(method="linear", limit_direction="both")

        # For stations completely lacking a sensor (e.g. Sanathnagar PM10),
        # fill using the spatial cross-station mean of reporting stations on that date
        spatial_mean = df_feat.mean(axis=1)
        for col in df_feat.columns:
            if df_feat[col].isnull().all():
                df_feat[col] = spatial_mean
            else:
                df_feat[col] = df_feat[col].fillna(spatial_mean)

        X_grid[:, :, f_idx] = df_feat.values.astype(np.float32)

    # 3. Add temporal cyclical features
    dt_series = pd.to_datetime(all_dates)
    m_sin = np.sin(2 * np.pi * dt_series.month / 12.0).values.astype(np.float32)
    m_cos = np.cos(2 * np.pi * dt_series.month / 12.0).values.astype(np.float32)
    dow_sin = np.sin(2 * np.pi * dt_series.dayofweek / 7.0).values.astype(np.float32)
    dow_cos = np.cos(2 * np.pi * dt_series.dayofweek / 7.0).values.astype(np.float32)
    doy_sin = np.sin(2 * np.pi * dt_series.dayofyear / 365.25).values.astype(np.float32)
    doy_cos = np.cos(2 * np.pi * dt_series.dayofyear / 365.25).values.astype(np.float32)

    temp_offset = len(POLLUTANT_INPUTS) + len(METEO_INPUTS)
    for s_idx in range(NUM_STATIONS):
        X_grid[:, s_idx, temp_offset + 0] = m_sin
        X_grid[:, s_idx, temp_offset + 1] = m_cos
        X_grid[:, s_idx, temp_offset + 2] = dow_sin
        X_grid[:, s_idx, temp_offset + 3] = dow_cos
        X_grid[:, s_idx, temp_offset + 4] = doy_sin
        X_grid[:, s_idx, temp_offset + 5] = doy_cos

    # 4. Extract Targets Y_grid (PM2.5, PM10, NO2, SO2, CO, O3)
    target_indices = [POLLUTANT_INPUTS.index(p) for p in PRIMARY_TARGETS]
    Y_grid = X_grid[:, :, target_indices].copy()

    # 5. Compute Citywide Target Y_city as unweighted mean across reporting stations
    Y_city = np.mean(Y_grid, axis=1)  # (731, 6)

    return X_grid, Y_grid, Y_city, all_dates


class SpatialTemporalDataset:
    """
    Generates supervised sliding-window sequences:
    Inputs:  X (Batch, Num_Stations=13, Context=14, Num_Features=18)
    Outputs: Y (Batch, Num_Stations=13, Horizon=7, Num_Targets=6)
    City Targets: Y_city (Batch, Horizon=7, Num_Targets=6)
    """

    def __init__(
        self,
        context_length: int = CONTEXT_LENGTH,
        horizon: int = FORECAST_HORIZON,
    ):
        self.context_length = context_length
        self.horizon = horizon

        self.feature_scaler = StandardScaler()
        self.target_scaler = StandardScaler()
        self.is_fitted = False

        self.train_windows = []
        self.val_windows = []
        self.test_windows = []

    def prepare(self):
        """Construct sliding windows and split strictly chronologically."""
        X_grid, Y_grid, Y_city, all_dates = build_full_grid_tensors()
        num_days = len(all_dates)
        total_len = self.context_length + self.horizon

        windows = []
        for i in range(num_days - total_len + 1):
            x_seq = X_grid[i : i + self.context_length]                    # (14, 13, 18)
            y_seq = Y_grid[i + self.context_length : i + total_len]        # (7, 13, 6)
            y_city_seq = Y_city[i + self.context_length : i + total_len]   # (7, 6)

            origin_date = all_dates[i + self.context_length - 1]
            target_dates = all_dates[i + self.context_length : i + total_len]

            # Transpose x to (13, 14, 18) and y to (13, 7, 6) for per-station representation
            x_nodes = np.transpose(x_seq, (1, 0, 2))  # (13, 14, 18)
            y_nodes = np.transpose(y_seq, (1, 0, 2))  # (13, 7, 6)

            windows.append({
                "x": x_nodes,
                "y": y_nodes,
                "y_city": y_city_seq,
                "origin_date": origin_date.isoformat(),
                "target_dates": [d.isoformat() for d in target_dates],
                "first_target_date": target_dates[0].isoformat(),
                "last_target_date": target_dates[-1].isoformat(),
            })

        # Chronological Partitioning (No future leakage)
        train = []
        val = []
        test = []

        for w in windows:
            last_t = w["last_target_date"]
            if last_t <= TRAIN_END_DATE:
                train.append(w)
            elif VAL_START_DATE <= w["first_target_date"] and last_t <= VAL_END_DATE:
                val.append(w)
            elif TEST_START_DATE <= w["first_target_date"] and last_t <= TEST_END_DATE:
                test.append(w)

        self.train_windows = train
        self.val_windows = val
        self.test_windows = test

        # Fit Scalers STRICTLY on Training Set features and targets
        # Flatten across batch, stations, context for features
        x_train_flat = np.concatenate([w["x"].reshape(-1, NUM_FEATURES) for w in train], axis=0)
        y_train_flat = np.concatenate([w["y"].reshape(-1, NUM_TARGETS) for w in train], axis=0)

        self.feature_scaler.fit(x_train_flat)
        self.target_scaler.fit(y_train_flat)
        self.is_fitted = True

        logger.info(
            f"SpatialTemporalDataset prepared: Train={len(train)}, Val={len(val)}, Test={len(test)} windows"
        )

    def get_torch_loaders(self, batch_size: int = BATCH_SIZE) -> Tuple[DataLoader, DataLoader, DataLoader]:
        """Convert windows to normalized PyTorch DataLoaders."""
        if not self.is_fitted:
            self.prepare()

        def process_split(split):
            xs, ys, y_cities = [], [], []
            for w in split:
                # Normalize x
                x_norm = self.feature_scaler.transform(w["x"].reshape(-1, NUM_FEATURES)).reshape(NUM_STATIONS, self.context_length, NUM_FEATURES)
                # Normalize y
                y_norm = self.target_scaler.transform(w["y"].reshape(-1, NUM_TARGETS)).reshape(NUM_STATIONS, self.horizon, NUM_TARGETS)

                xs.append(x_norm)
                ys.append(y_norm)
                y_cities.append(w["y_city"])

            x_t = torch.tensor(np.array(xs), dtype=torch.float32)
            y_t = torch.tensor(np.array(ys), dtype=torch.float32)
            yc_t = torch.tensor(np.array(y_cities), dtype=torch.float32)
            return DataLoader(torch.utils.data.TensorDataset(x_t, y_t, yc_t), batch_size=batch_size, shuffle=False)

        train_loader = process_split(self.train_windows)
        val_loader = process_split(self.val_windows)
        test_loader = process_split(self.test_windows)

        return train_loader, val_loader, test_loader
