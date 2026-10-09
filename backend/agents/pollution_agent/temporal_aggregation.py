"""
CPCB Temporal Aggregation Engine — Indian National Air Quality Index.

Implements official pollutant-specific averaging windows and data sufficiency thresholds:
- 24-hour arithmetic mean: PM2.5, PM10, NO2, SO2, NH3 (minimum valid duration: >= 16 hours)
- 8-hour rolling arithmetic mean: CO, O3 (minimum valid duration: >= 6 hours)
- For 15-minute resolution telemetry:
    - 24-hour window: 96 nominal readings; 16 hours requires >= 64 valid readings.
    - 8-hour window: 32 nominal readings; 6 hours requires >= 24 valid readings.

SUFFICIENCY RULE:
If valid observations in the required window are below the duration threshold,
the concentration is strictly returned as None (unavailable).
NO silent zero imputation, NO median imputation, NO forward-filling of outages.
"""
from typing import Optional, Dict, Any, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from .data_provider import POLLUTANT_FEATURES, STATION_METADATA
from .aqi_engine import calculate_sub_index, calculate_aqi, BREAKPOINTS

# CPCB Pollutant Temporal Window Specification
# (window_hours, min_duration_hours, nominal_15min_readings, min_15min_readings)
WINDOW_SPECS = {
    "PM2.5": {"window_hours": 24, "min_hours": 16.0, "nominal_readings": 96, "min_readings": 64},
    "PM10": {"window_hours": 24, "min_hours": 16.0, "nominal_readings": 96, "min_readings": 64},
    "NO2": {"window_hours": 24, "min_hours": 16.0, "nominal_readings": 96, "min_readings": 64},
    "SO2": {"window_hours": 24, "min_hours": 16.0, "nominal_readings": 96, "min_readings": 64},
    "NH3": {"window_hours": 24, "min_hours": 16.0, "nominal_readings": 96, "min_readings": 64},
    "CO": {"window_hours": 8, "min_hours": 6.0, "nominal_readings": 32, "min_readings": 24},
    "O3": {"window_hours": 8, "min_hours": 6.0, "nominal_readings": 32, "min_readings": 24},
}

AVERAGING_WINDOWS_DESCRIPTION = {
    "PM2.5": "24-hour arithmetic mean (min 16 hours / 64 readings)",
    "PM10": "24-hour arithmetic mean (min 16 hours / 64 readings)",
    "NO2": "24-hour arithmetic mean (min 16 hours / 64 readings)",
    "SO2": "24-hour arithmetic mean (min 16 hours / 64 readings)",
    "NH3": "24-hour arithmetic mean (min 16 hours / 64 readings)",
    "CO": "8-hour rolling mean (min 6 hours / 24 readings)",
    "O3": "8-hour rolling mean (min 6 hours / 24 readings)",
}


def compute_pollutant_window_mean(
    series: pd.Series,
    pollutant: str,
    resolution_minutes: int = 15,
) -> Tuple[Optional[float], Dict[str, Any]]:
    """
    Compute CPCB temporal window mean for a single pollutant series.
    Enforces minimum valid duration requirement.
    """
    spec = WINDOW_SPECS.get(pollutant, {"window_hours": 24, "min_hours": 16.0, "nominal_readings": 96, "min_readings": 64})
    valid_series = series.dropna()
    valid_count = len(valid_series)
    valid_hours = valid_count * (resolution_minutes / 60.0)
    is_sufficient = valid_count >= spec["min_readings"]

    metadata = {
        "pollutant": pollutant,
        "window_hours": spec["window_hours"],
        "required_hours": spec["min_hours"],
        "valid_count": int(valid_count),
        "nominal_readings": spec["nominal_readings"],
        "min_readings": spec["min_readings"],
        "valid_hours": round(valid_hours, 2),
        "completeness_ratio": round(valid_count / spec["nominal_readings"], 4) if spec["nominal_readings"] > 0 else 0.0,
        "is_sufficient": bool(is_sufficient),
    }

    if is_sufficient:
        mean_val = float(valid_series.mean())
        return round(mean_val, 2), metadata
    else:
        return None, metadata


def compute_station_window_aggregates(
    station_df: pd.DataFrame,
    anchor_time: Optional[datetime] = None,
    station_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compute CPCB temporal window aggregates for a single station.

    For particulates (PM2.5, PM10) and acid gases (NO2, SO2, NH3):
      slices [anchor_time - 24 hours, anchor_time] -> requires >= 16h valid data.
    For CO and O3:
      slices [anchor_time - 8 hours, anchor_time] -> requires >= 6h valid data.
    """
    if station_df.empty or "timestamp" not in station_df.columns:
        return {
            "station_name": station_name or "Unknown",
            "anchor_timestamp": None,
            "status": "unavailable",
            "concentrations": {},
            "sub_indices": {},
            "completeness": {},
            "aqi": None,
            "category": "Unavailable",
            "color": "#999999",
            "dominant_pollutant": None,
            "dominant_value": None,
        }

    st_name = station_name or station_df["station_name"].iloc[0] if "station_name" in station_df.columns else "Unknown"

    # Anchor time: latest timestamp in station data if not provided
    if anchor_time is None:
        anchor_time = station_df["timestamp"].max()

    t_24h_start = anchor_time - timedelta(hours=24)
    t_8h_start = anchor_time - timedelta(hours=8)

    df_24h = station_df[(station_df["timestamp"] >= t_24h_start) & (station_df["timestamp"] <= anchor_time)]
    df_8h = station_df[(station_df["timestamp"] >= t_8h_start) & (station_df["timestamp"] <= anchor_time)]

    concentrations = {}
    completeness = {}

    for p in ["PM2.5", "PM10", "NO2", "SO2", "NH3", "CO", "O3", "NO", "NOx", "Benzene", "Toluene", "Xylene"]:
        spec = WINDOW_SPECS.get(p, {"window_hours": 24, "min_hours": 16.0, "nominal_readings": 96, "min_readings": 64})
        target_df = df_8h if spec["window_hours"] == 8 else df_24h

        if p in target_df.columns:
            mean_val, meta = compute_pollutant_window_mean(target_df[p], p)
            completeness[p] = meta
            if mean_val is not None:
                concentrations[p] = mean_val
        else:
            completeness[p] = {
                "pollutant": p,
                "window_hours": spec["window_hours"],
                "required_hours": spec["min_hours"],
                "valid_count": 0,
                "nominal_readings": spec["nominal_readings"],
                "min_readings": spec["min_readings"],
                "valid_hours": 0.0,
                "completeness_ratio": 0.0,
                "is_sufficient": False,
            }

    # Evaluate CPCB AQI for station from window-averaged concentrations
    aqi_res = calculate_aqi(concentrations)

    return {
        "station_name": st_name,
        "anchor_timestamp": anchor_time.isoformat() if pd.notna(anchor_time) else None,
        "status": "success" if aqi_res.get("aqi") is not None else "unavailable",
        "concentrations": concentrations,
        "sub_indices": aqi_res.get("sub_indices", {}),
        "completeness": completeness,
        "aqi": aqi_res.get("aqi"),
        "category": aqi_res.get("category", "Unavailable"),
        "color": aqi_res.get("color", "#999999"),
        "dominant_pollutant": aqi_res.get("dominant_pollutant"),
        "dominant_value": aqi_res.get("dominant_value"),
        "area": STATION_METADATA.get(st_name, {}).get("area", st_name),
        "lat": STATION_METADATA.get(st_name, {}).get("lat"),
        "lon": STATION_METADATA.get(st_name, {}).get("lon"),
    }


def compute_city_temporal_aggregates(
    raw_df: pd.DataFrame,
    anchor_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Compute citywide temporal window aggregates across all reporting stations.
    
    Returns:
    - station_aggregates: list of dicts per station with window-averaged values
    - city_concentrations: arithmetic mean of station-window concentrations
    - active_stations: count of stations with sufficient data
    - total_stations: total stations present in raw_df
    - coverage_percent: active_stations / total_stations * 100
    - anchor_timestamp: ISO timestamp of the evaluation window anchor
    """
    if raw_df.empty or "timestamp" not in raw_df.columns:
        return {
            "status": "unavailable",
            "anchor_timestamp": None,
            "station_aggregates": [],
            "city_concentrations": {},
            "active_stations": 0,
            "total_stations": 0,
            "coverage_percent": 0.0,
            "averaging_windows": AVERAGING_WINDOWS_DESCRIPTION,
        }

    if anchor_time is None:
        anchor_time = raw_df["timestamp"].max()

    station_aggregates = []
    total_stations = raw_df["station_name"].nunique() if "station_name" in raw_df.columns else 1

    for st_name, st_df in raw_df.groupby("station_name"):
        agg = compute_station_window_aggregates(st_df, anchor_time=anchor_time, station_name=st_name)
        station_aggregates.append(agg)

    # City-level pollutant concentration aggregation:
    # arithmetic mean of valid station-window concentrations
    city_concentrations = {}
    for p in ["PM2.5", "PM10", "NO2", "SO2", "NH3", "CO", "O3", "NO", "NOx", "Benzene", "Toluene", "Xylene"]:
        vals = [
            s["concentrations"][p]
            for s in station_aggregates
            if p in s["concentrations"] and s["concentrations"][p] is not None
        ]
        if vals:
            city_concentrations[p] = round(float(np.mean(vals)), 2)

    # Active stations: stations that have sufficient data to produce a valid station AQI
    valid_station_aqis = [s["aqi"] for s in station_aggregates if s.get("aqi") is not None]
    active_stations = len(valid_station_aqis)
    coverage_pct = round((active_stations / total_stations * 100.0), 1) if total_stations > 0 else 0.0

    return {
        "status": "success" if city_concentrations else "unavailable",
        "anchor_timestamp": anchor_time.isoformat() if pd.notna(anchor_time) else None,
        "station_aggregates": station_aggregates,
        "city_concentrations": city_concentrations,
        "active_stations": active_stations,
        "total_stations": total_stations,
        "coverage_percent": coverage_pct,
        "averaging_windows": AVERAGING_WINDOWS_DESCRIPTION,
    }
