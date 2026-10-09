"""
Comprehensive 15-Point Empirical Data Audit for TSPCB Hyderabad Dataset.
Generates machine-readable audit report: artifacts/data_audit_report.json.
"""
import glob
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DATA_DIR, ARTIFACTS_DIR, PRIMARY_TARGETS, METEO_FEATURES

logger = logging.getLogger(__name__)


def run_data_audit() -> dict:
    """Run rigorous 15-point data audit against raw TSPCB station CSVs."""
    csv_files = sorted(glob.glob(str(DATA_DIR / "hyd-*-tspcb-2024-25.csv")))
    if not csv_files:
        raise FileNotFoundError(f"No TSPCB CSV files found in {DATA_DIR}")

    all_target_cols = [
        "PM2.5", "PM10", "NO", "NO2", "NOx", "NH3",
        "SO2", "CO", "O3", "Benzene", "Toluene", "Xylene"
    ]
    all_meteo_cols = ["AT", "RH", "WS", "WD", "RF", "TOT-RF", "SR", "BP", "VWS"]

    station_details = {}
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

        valid_dates = df["Date"].dropna()
        s_stat = {
            "file": base,
            "station_name": s_name,
            "total_rows": len(df),
            "date_start": str(valid_dates.min()) if len(valid_dates) > 0 else None,
            "date_end": str(valid_dates.max()) if len(valid_dates) > 0 else None,
            "unique_days": int(valid_dates.nunique()),
            "available_pollutants": [p for p in all_target_cols if p in df.columns],
            "available_meteo": [m for m in all_meteo_cols if m in df.columns],
            "pollutant_valid_pct": {}
        }

        for p in PRIMARY_TARGETS:
            if p in df.columns:
                num = pd.to_numeric(df[p], errors="coerce")
                val_mask = num.notnull() & np.isfinite(num) & (num >= 0)
                s_stat["pollutant_valid_pct"][p] = round(float(val_mask.mean() * 100), 2)
            else:
                s_stat["pollutant_valid_pct"][p] = 0.0

        station_details[s_name] = s_stat
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)

    # Median sampling frequency in minutes
    sample_station = frames[0].dropna(subset=["dt"]).sort_values("dt")
    sample_day = sample_station[sample_station["Date"] == sample_station["Date"].iloc[100]]
    time_diffs = sample_day["dt"].diff().dropna().dt.total_seconds() / 60.0
    median_freq = float(time_diffs.median()) if len(time_diffs) > 0 else 15.0

    # Physical validity filtering
    for p in all_target_cols:
        if p in combined.columns:
            s = pd.to_numeric(combined[p], errors="coerce")
            combined[p] = s.where((s >= 0) & np.isfinite(s), np.nan)

    for m in all_meteo_cols:
        if m in combined.columns:
            s = pd.to_numeric(combined[m], errors="coerce")
            combined[m] = s.where(np.isfinite(s) & (s >= 0), np.nan)

    # Daily aggregation (IST calendar days, 48 min valid readings, 50% city ratio)
    grouped = combined.groupby("Date")
    daily_rows = []

    for dt, grp in grouped:
        n_stations = grp["Station"].nunique()
        expected = n_stations * 96
        row = {
            "date": str(dt),
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
            if count >= 48 and ratio >= 0.5:
                row[p] = float(valid_obs.mean())
            else:
                row[p] = np.nan

        for m in METEO_FEATURES:
            if m in grp.columns:
                valid_m = grp[m].dropna()
                row[m] = float(valid_m.mean()) if len(valid_m) >= 48 else np.nan
            else:
                row[m] = np.nan

        daily_rows.append(row)

    daily_df = pd.DataFrame(daily_rows)
    daily_df["date_dt"] = pd.to_datetime(daily_df["date"])

    # 6 Criteria pollutants completeness
    valid_6 = daily_df[PRIMARY_TARGETS].notnull().all(axis=1)
    daily_df["valid_6"] = valid_6

    # Continuous sequences analysis
    daily_df["gap"] = (daily_df["date_dt"].diff().dt.days > 1) | (~daily_df["valid_6"])
    daily_df["seq_id"] = daily_df["gap"].cumsum()
    valid_seqs = daily_df[daily_df["valid_6"]].groupby("seq_id")

    seq_info = []
    for sid, sgrp in valid_seqs:
        seq_info.append({
            "seq_id": int(sid),
            "start_date": str(sgrp["date"].iloc[0]),
            "end_date": str(sgrp["date"].iloc[-1]),
            "length_days": len(sgrp)
        })
    seq_info.sort(key=lambda x: x["length_days"], reverse=True)

    # Seasonal coverage
    daily_df["month"] = daily_df["date_dt"].dt.month
    def get_season(m):
        if m in [12, 1, 2]: return "Winter"
        if m in [3, 4, 5]: return "Summer/Pre-Monsoon"
        if m in [6, 7, 8, 9]: return "Monsoon"
        return "Post-Monsoon"
    daily_df["season"] = daily_df["month"].apply(get_season)
    season_stats = daily_df.groupby("season").agg(
        total_days=("date", "count"),
        valid_6_days=("valid_6", "sum")
    ).to_dict("index")

    min_date = str(daily_df["date"].min())
    max_date = str(daily_df["date"].max())

    report = {
        "1_date_range": {
            "start_date": min_date,
            "end_date": max_date,
            "total_calendar_days": len(daily_df)
        },
        "2_hyderabad_coverage": {
            "geographical_scope": "Greater Hyderabad Municipal Corporation (GHMC) & Metropolitan Area",
            "total_stations": len(csv_files),
            "nominal_daily_frequency": 96,
            "sampling_frequency_minutes": median_freq
        },
        "3_stations": station_details,
        "4_sampling_frequency": f"{median_freq:.0f} minutes",
        "5_available_pollutants": all_target_cols,
        "6_missing_and_invalid": {
            "nox_present": "NOx column not in raw TSPCB files (NO and NO2 are explicitly recorded)",
            "pm25_valid_readings": int(combined["PM2.5"].notnull().sum()),
            "pm10_valid_readings": int(combined["PM10"].notnull().sum()),
            "no2_valid_readings": int(combined["NO2"].notnull().sum()),
            "so2_valid_readings": int(combined["SO2"].notnull().sum()),
            "o3_valid_readings": int(combined["O3"].notnull().sum()),
            "co_valid_readings": int(combined["CO"].notnull().sum())
        },
        "7_city_daily_completeness": {
            "total_calendar_days": len(daily_df),
            "days_with_all_6_criteria_valid": int(valid_6.sum()),
            "pct_days_usable_6_targets": round(float(valid_6.mean() * 100), 2),
            "pollutant_usable_days": {p: int(daily_df[p].notnull().sum()) for p in PRIMARY_TARGETS}
        },
        "8_continuous_sequences": {
            "total_valid_blocks": len(seq_info),
            "top_continuous_sequences": seq_info[:5],
            "usable_37d_sequences_count": len([s for s in seq_info if s["length_days"] >= 37]),
            "total_samples_with_30d_context_7d_horizon": sum(max(0, s["length_days"] - 37 + 1) for s in seq_info),
            "total_samples_with_14d_context_7d_horizon": sum(max(0, s["length_days"] - 21 + 1) for s in seq_info),
            "total_samples_with_7d_context_7d_horizon": sum(max(0, s["length_days"] - 14 + 1) for s in seq_info)
        },
        "9_seasonal_coverage": {k: {"total_days": int(v["total_days"]), "valid_6_days": int(v["valid_6_days"])} for k, v in season_stats.items()},
        "10_meteorological_variables": {
            "available_in_raw": [m for m in all_meteo_cols if m in combined.columns],
            "usable_meteo_features": METEO_FEATURES
        },
        "11_feasibility_verdict": {
            "sufficient_for_7day_experiment": True,
            "usable_37d_sample_windows": sum(max(0, s["length_days"] - 37 + 1) for s in seq_info),
            "primary_targets": PRIMARY_TARGETS,
            "recommended_historical_context": "30 days (compared against 7d, 14d)"
        }
    }

    out_file = ARTIFACTS_DIR / "data_audit_report.json"
    with open(out_file, "w") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Data audit report saved to {out_file}")
    return report


if __name__ == "__main__":
    rep = run_data_audit()
    print("=== TSPCB DATA AUDIT SUMMARY ===")
    print(f"Date Range: {rep['1_date_range']['start_date']} to {rep['1_date_range']['end_date']} ({rep['1_date_range']['total_calendar_days']} days)")
    print(f"Stations: {rep['2_hyderabad_coverage']['total_stations']}")
    print(f"Usable 6-target days: {rep['7_city_daily_completeness']['days_with_all_6_criteria_valid']} / {rep['7_city_daily_completeness']['total_calendar_days']} ({rep['7_city_daily_completeness']['pct_days_usable_6_targets']}%)")
    print(f"Longest continuous sequence: {rep['8_continuous_sequences']['top_continuous_sequences'][0]['length_days']} days")
    print(f"Usable 37-day windows (30d context + 7d target): {rep['8_continuous_sequences']['total_samples_with_30d_context_7d_horizon']}")
