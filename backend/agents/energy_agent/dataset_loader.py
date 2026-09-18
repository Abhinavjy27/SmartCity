"""
Dataset Ingestion & Historical Benchmark Processor for SUPADSP Energy Agent.
Ingests and aggregates the raw UCI Power Consumption time-series dataset located at
`datasets/raw/energy/household_power_consumption.txt` to derive empirical 24-hour diurnal curves,
load variance, and peak-to-average metrics.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple
import pandas as pd

logger = logging.getLogger("energy_agent.dataset_loader")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATASET_PATH = os.path.join(BASE_DIR, "datasets", "raw", "energy", "household_power_consumption.txt")

# In-memory cache for empirical profile
_CACHED_HOURLY_PROFILE: Optional[Dict[int, float]] = None
_CACHED_DATASET_STATS: Optional[Dict[str, float]] = None


def load_energy_dataset_stats(
    filepath: str = DATASET_PATH,
    sample_rows: int = 150000
) -> Tuple[Dict[int, float], Dict[str, float]]:
    """
    Loads raw power consumption measurements, calculates empirical 24h hourly weights,
    and returns (hourly_diurnal_weights, summary_statistics).
    """
    global _CACHED_HOURLY_PROFILE, _CACHED_DATASET_STATS
    
    if _CACHED_HOURLY_PROFILE is not None and _CACHED_DATASET_STATS is not None:
        return _CACHED_HOURLY_PROFILE, _CACHED_DATASET_STATS

    if not os.path.exists(filepath):
        logger.warning(f"Energy dataset not found at {filepath}. Using synthetic baseline fallback.")
        default_profile = {h: 1.0 for h in range(24)}
        default_stats = {"avg_active_power_kw": 1.15, "peak_active_power_kw": 4.8, "voltage_avg": 240.8}
        return default_profile, default_stats

    try:
        # Load sample from the benchmark dataset for rapid initialization
        df = pd.read_csv(
            filepath,
            sep=';',
            nrows=sample_rows,
            na_values=['?'],
            low_memory=False
        )

        df['Global_active_power'] = pd.to_numeric(df['Global_active_power'], errors='coerce')
        df['Voltage'] = pd.to_numeric(df['Voltage'], errors='coerce')
        df.dropna(subset=['Global_active_power', 'Time'], inplace=True)

        # Extract hour from Time column (HH:MM:SS)
        df['Hour'] = df['Time'].apply(lambda t: int(str(t).split(':')[0]) if ':' in str(t) else 0)

        # Group by hour to derive empirical hourly means
        hourly_means = df.groupby('Hour')['Global_active_power'].mean()
        overall_mean = df['Global_active_power'].mean()

        profile: Dict[int, float] = {}
        for h in range(24):
            val = float(hourly_means.get(h, overall_mean))
            # Normalized hourly weight centered at 1.0
            profile[h] = round(val / overall_mean, 4) if overall_mean > 0 else 1.0

        stats: Dict[str, float] = {
            "avg_active_power_kw": round(float(overall_mean), 3),
            "peak_active_power_kw": round(float(df['Global_active_power'].quantile(0.98)), 3),
            "voltage_avg": round(float(df['Voltage'].mean()), 1) if 'Voltage' in df else 240.0,
            "sample_records": float(len(df)),
        }

        _CACHED_HOURLY_PROFILE = profile
        _CACHED_DATASET_STATS = stats
        return profile, stats

    except Exception as exc:
        logger.error(f"Failed to process energy dataset: {exc}")
        default_profile = {h: 1.0 for h in range(24)}
        default_stats = {"avg_active_power_kw": 1.15, "peak_active_power_kw": 4.8, "voltage_avg": 240.8}
        return default_profile, default_stats


def get_empirical_hourly_factor(hour: int) -> float:
    """Returns normalized empirical hourly weight factor (0.6 - 1.4) for a given hour."""
    profile, _ = load_energy_dataset_stats()
    return profile.get(hour, 1.0)
