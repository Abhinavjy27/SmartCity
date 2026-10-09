"""
Spatial Aggregation Module — City-Wide Air Quality Aggregation.

Isolates and transparently evaluates the two primary spatial aggregation methodologies:

METHOD A: Concentration-First Aggregation (Project Default)
  1. For each pollutant, compute the arithmetic mean concentration across all active reporting stations.
  2. Pass composite city pollutant concentrations into the CPCB AQI engine.
  3. City AQI = max(valid CPCB sub-indices of citywide mean concentrations).

METHOD B: Station-First Aggregation (Station AQI Averaging)
  1. Compute CPCB AQI individually at each monitoring station from that station's windowed concentrations.
  2. City AQI = arithmetic mean of valid station AQIs: round( (1/M) * sum(AQI_s) ).

RESEARCH NOTE:
Both spatial aggregation strategies are implemented and evaluated. The project default
(concentration-first) is retained for compatibility, while the research evaluation compares
the effect of each method on observed-AQI reconciliation and forecasting performance.
The implementation must not claim that either method is universally the official CPCB operational
aggregation method for Hyderabad without explicit evidence.
"""
from typing import List, Dict, Any, Optional
import numpy as np

from .aqi_engine import calculate_aqi, get_aqi_category


def aggregate_city_by_concentration(station_aggregates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Method A: City-level pollutant concentration mean -> CPCB AQI engine.
    """
    if not station_aggregates:
        return {
            "method": "concentration_first",
            "aqi": None,
            "category": "Unavailable",
            "color": "#999999",
            "dominant_pollutant": None,
            "dominant_value": None,
            "sub_indices": {},
            "city_concentrations": {},
            "reporting_station_count": 0,
            "reason": "No station aggregates provided",
        }

    # Aggregate pollutant concentrations across reporting stations
    city_conc = {}
    for p in ["PM2.5", "PM10", "NO2", "SO2", "NH3", "CO", "O3", "NO", "NOx", "Benzene", "Toluene", "Xylene"]:
        vals = [
            s["concentrations"][p]
            for s in station_aggregates
            if "concentrations" in s and p in s["concentrations"] and s["concentrations"][p] is not None
        ]
        if vals:
            city_conc[p] = round(float(np.mean(vals)), 2)

    # Calculate AQI via CPCB engine
    aqi_res = calculate_aqi(city_conc)

    valid_stations = [s for s in station_aggregates if s.get("aqi") is not None]

    return {
        "method": "concentration_first",
        "description": "Citywide pollutant concentration mean -> CPCB AQI breakpoint interpolation",
        "aqi": aqi_res.get("aqi"),
        "category": aqi_res.get("category", "Unavailable"),
        "color": aqi_res.get("color", "#999999"),
        "dominant_pollutant": aqi_res.get("dominant_pollutant"),
        "dominant_value": aqi_res.get("dominant_value"),
        "sub_indices": aqi_res.get("sub_indices", {}),
        "city_concentrations": city_conc,
        "reporting_station_count": len(valid_stations),
        "reason": aqi_res.get("reason"),
    }


def aggregate_city_by_station_aqi(station_aggregates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Method B: Station AQI calculation -> arithmetic mean of valid station AQIs.
    """
    if not station_aggregates:
        return {
            "method": "station_first",
            "aqi": None,
            "category": "Unavailable",
            "color": "#999999",
            "dominant_pollutant": None,
            "station_aqis": [],
            "reporting_station_count": 0,
            "reason": "No station aggregates provided",
        }

    valid_station_aqis = [
        s["aqi"] for s in station_aggregates if s.get("aqi") is not None and isinstance(s["aqi"], (int, float))
    ]

    if not valid_station_aqis:
        return {
            "method": "station_first",
            "description": "Station CPCB AQI -> arithmetic mean across stations",
            "aqi": None,
            "category": "Unavailable",
            "color": "#999999",
            "dominant_pollutant": None,
            "station_aqis": [],
            "reporting_station_count": 0,
            "reason": "No station met CPCB sufficiency criteria to compute station AQI",
        }

    mean_aqi = int(round(float(np.mean(valid_station_aqis))))
    category, color = get_aqi_category(mean_aqi)

    # Determine most frequent dominant pollutant across reporting stations
    dom_pollutants = [s["dominant_pollutant"] for s in station_aggregates if s.get("dominant_pollutant")]
    dominant = max(set(dom_pollutants), key=dom_pollutants.count) if dom_pollutants else None

    return {
        "method": "station_first",
        "description": "Station CPCB AQI -> arithmetic mean across stations",
        "aqi": mean_aqi,
        "category": category,
        "color": color,
        "dominant_pollutant": dominant,
        "station_aqis": valid_station_aqis,
        "station_min": min(valid_station_aqis),
        "station_max": max(valid_station_aqis),
        "reporting_station_count": len(valid_station_aqis),
        "reason": None,
    }


def compute_city_aqi(
    station_aggregates: List[Dict[str, Any]],
    primary_method: str = "concentration_first",
) -> Dict[str, Any]:
    """
    Compute city AQI with full transparency across both spatial aggregation methods.
    
    Returns primary calculation as well as the alternative calculation for comparative analysis.
    """
    conc_first = aggregate_city_by_concentration(station_aggregates)
    station_first = aggregate_city_by_station_aqi(station_aggregates)

    if primary_method == "station_first":
        primary = station_first
        alternative = conc_first
    else:
        primary = conc_first
        alternative = station_first

    return {
        "primary": primary,
        "alternative": alternative,
        "concentration_first_aqi": conc_first.get("aqi"),
        "station_first_aqi": station_first.get("aqi"),
        "spatial_divergence": (
            abs(conc_first["aqi"] - station_first["aqi"])
            if conc_first.get("aqi") is not None and station_first.get("aqi") is not None
            else None
        ),
        "methodology_note": (
            "Both spatial aggregation methods are computed. Concentration-first evaluates citywide "
            "pollutant means before applying CPCB breakpoints; station-first averages individual station AQIs."
        ),
    }
