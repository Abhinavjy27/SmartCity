"""
Dynamic hotspot computation, AQI distribution, and area trend analysis.
All computed from real TSPCB observations through the centralized CPCB AQI engine.
Adheres strictly to §13: Stations with insufficient data are excluded, never fabricated.
"""
import logging
from typing import Optional
from datetime import datetime, timedelta

from .aqi_engine import calculate_aqi, get_aqi_category, AQI_CATEGORIES
from .data_provider import get_data_provider, STATION_METADATA

logger = logging.getLogger(__name__)


def compute_hotspots(readings: list, top_n: int = 5) -> list:
    """
    Compute AQI hotspots dynamically from latest station readings (§13).
    Only stations with valid CPCB AQI (meeting sufficiency) are ranked.
    Stations with insufficient data are excluded, never fabricated.
    """
    scored = []
    for r in readings:
        conc = {}
        for p in ["PM2.5", "PM10", "NO2", "SO2", "O3", "CO", "NH3"]:
            val = r.get(p)
            if val is not None:
                conc[p] = val

        if not conc:
            continue

        aqi_result = calculate_aqi(conc)
        # Exclude stations failing CPCB sufficiency
        if aqi_result.get("aqi") is None:
            continue

        station_name = r.get("station_name", "Unknown")
        meta = STATION_METADATA.get(station_name, {})
        area = meta.get("area", r.get("area", station_name))

        scored.append({
            "area": area,
            "station_name": station_name,
            "aqi": aqi_result["aqi"],
            "category": aqi_result["category"],
            "color": aqi_result["color"],
            "dominant_pollutant": aqi_result["dominant_pollutant"],
            "pm25": conc.get("PM2.5"),
            "lat": meta.get("lat", r.get("lat")),
            "lon": meta.get("lon", r.get("lon")),
            "timestamp": r.get("timestamp"),
            "source": "cpcb_engine",
        })

    scored.sort(key=lambda x: x["aqi"], reverse=True)
    return scored[:top_n]


def compute_distribution(readings: list) -> list:
    """
    Compute AQI category distribution across stations (§13).
    Classifies only stations with valid CPCB AQI.
    Never counts invalid/unavailable stations into a real category.
    """
    category_counts = {}
    for lo, hi, cat, color in AQI_CATEGORIES:
        category_counts[cat] = {"name": f"{cat} ({lo}-{hi})", "value": 0, "color": color}

    total_valid = 0
    for r in readings:
        conc = {}
        for p in ["PM2.5", "PM10", "NO2", "SO2", "O3", "CO", "NH3"]:
            val = r.get(p)
            if val is not None:
                conc[p] = val

        if not conc:
            continue

        aqi_result = calculate_aqi(conc)
        if aqi_result.get("aqi") is None:
            continue

        total_valid += 1
        cat = aqi_result["category"]
        if cat in category_counts:
            category_counts[cat]["value"] += 1

    result = []
    for cat_info in category_counts.values():
        cat_info["pct"] = round(cat_info["value"] / total_valid * 100, 1) if total_valid > 0 else 0.0
        result.append(cat_info)

    return result


def compute_area_trends(provider=None) -> list:
    """
    Compute AQI trend vs previous period for each station/area (§13).
    Requires both current and previous period to have valid CPCB AQI.
    Protects against divide-by-zero.
    """
    if provider is None:
        provider = get_data_provider()

    daily = provider.get_daily_aggregates(n_days=3)
    if daily.empty:
        return []

    dates = sorted(daily["date"].unique())
    if len(dates) < 2:
        return []

    current_date = dates[-1]
    prev_date = dates[-2]

    trends = []
    for station in daily["station_name"].unique():
        curr = daily[(daily["station_name"] == station) & (daily["date"] == current_date)]
        prev = daily[(daily["station_name"] == station) & (daily["date"] == prev_date)]

        if curr.empty or prev.empty:
            continue

        curr_row = curr.iloc[0]
        prev_row = prev.iloc[0]

        curr_conc = {}
        prev_conc = {}
        for p in ["PM2.5", "PM10", "NO2", "SO2", "O3", "CO", "NH3"]:
            if p in curr_row and curr_row[p] is not None:
                try:
                    val = float(curr_row[p])
                    if not (val != val):  # not nan
                        curr_conc[p] = val
                except (ValueError, TypeError):
                    pass
            if p in prev_row and prev_row[p] is not None:
                try:
                    val = float(prev_row[p])
                    if not (val != val):
                        prev_conc[p] = val
                except (ValueError, TypeError):
                    pass

        if not curr_conc or not prev_conc:
            continue

        curr_result = calculate_aqi(curr_conc)
        prev_result = calculate_aqi(prev_conc)

        curr_aqi = curr_result.get("aqi")
        prev_aqi = prev_result.get("aqi")

        # Must both have valid AQI, guard divide by zero
        if curr_aqi is None or prev_aqi is None or prev_aqi <= 0:
            continue

        change_pct = round((curr_aqi - prev_aqi) / prev_aqi * 100, 1)
        meta = STATION_METADATA.get(station, {})
        area = meta.get("area", station)

        trends.append({
            "area": area,
            "station_name": station,
            "current_aqi": curr_aqi,
            "previous_aqi": prev_aqi,
            "change": abs(change_pct),
            "dir": "up" if change_pct > 0 else "down",
            "source": "cpcb_engine",
        })

    trends.sort(key=lambda x: x["change"], reverse=True)
    return trends
