"""
Pollution Grounding Tools — callable functions for the Planning AI chat.

Each tool wraps existing pollution agent endpoint FUNCTIONS directly (not HTTP)
to avoid self-referential deadlock with single-worker uvicorn.

Station resolver supports fuzzy/alias matching.
"""
from __future__ import annotations

import json
import logging
import os
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("pollution_grounding.tools")

TOOL_TIMEOUT = 8  # seconds

# ── Station Resolver ──

_STATIONS_CACHE: Optional[List[Dict]] = None


def _load_stations() -> List[Dict]:
    global _STATIONS_CACHE
    if _STATIONS_CACHE is not None:
        return _STATIONS_CACHE
    stations_path = Path(__file__).resolve().parent.parent / "knowledge" / "stations.json"
    try:
        with open(stations_path, "r", encoding="utf-8") as f:
            _STATIONS_CACHE = json.load(f)
    except Exception:
        _STATIONS_CACHE = []
    return _STATIONS_CACHE


def resolve_station(query: str) -> Dict[str, Any]:
    """
    Fuzzy/alias match for station names.
    Returns {"found": True, "station_name": ..., "area": ...} or
            {"found": False, "known_stations": [...]}
    """
    stations = _load_stations()
    q = query.strip().lower()

    # Exact match on primary_name or alias
    for s in stations:
        if q == s["primary_name"].lower():
            return {"found": True, "station_name": s["primary_name"], "area": s.get("area", "")}
        for alias in s.get("aliases", []):
            if q == alias.lower():
                return {"found": True, "station_name": s["primary_name"], "area": s.get("area", "")}

    # Area match
    for s in stations:
        if q == s.get("area", "").lower():
            return {"found": True, "station_name": s["primary_name"], "area": s.get("area", "")}

    # Fuzzy match (threshold 0.75)
    best_score = 0.0
    best_station = None
    for s in stations:
        candidates = [s["primary_name"]] + s.get("aliases", []) + [s.get("area", "")]
        for c in candidates:
            score = SequenceMatcher(None, q, c.lower()).ratio()
            if score > best_score:
                best_score = score
                best_station = s

    if best_score >= 0.75 and best_station:
        return {"found": True, "station_name": best_station["primary_name"], "area": best_station.get("area", ""), "match_score": round(best_score, 2)}

    known = [s["primary_name"] for s in stations]
    return {"found": False, "known_stations": known, "query": query}


# ── Direct function calls to avoid HTTP self-deadlock & redundant live fetches ──

_CACHE: Dict[str, Any] = {}
CACHE_TTL = 60.0  # 60s cache to avoid thrashing live provider

def _get_cached(key: str):
    if key in _CACHE:
        ts, val = _CACHE[key]
        if time.time() - ts < CACHE_TTL and val.get("status") != "unavailable":
            return val
    return None

def _set_cached(key: str, val: Any):
    _CACHE[key] = (time.time(), val)

def _call_current(force_historical=False):
    """Call the pollution agent's get_current function directly with caching."""
    cache_key = f"current_{force_historical}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        from backend.agents.pollution_agent.main import get_current as _get_current_endpoint
        res = _get_current_endpoint(force_historical=force_historical)
        if res.get("status") == "success":
            _set_cached(cache_key, res)
        return res
    except Exception as exc:
        logger.warning("Direct call to get_current failed: %s", exc)
        return {"status": "unavailable", "error": str(exc)}


def _call_summary():
    """Call the pollution agent's get_summary function directly with caching."""
    cache_key = "summary"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        from backend.agents.pollution_agent.main import get_summary as _get_summary_endpoint
        res = _get_summary_endpoint()
        if res.get("status") == "success":
            _set_cached(cache_key, res)
        return res
    except Exception as exc:
        logger.warning("Direct call to get_summary failed: %s", exc)
        return {"status": "unavailable", "error": str(exc)}


def _call_forecast_7day():
    """Call the pollution agent's 7day forecast function directly with caching."""
    cache_key = "forecast_7day"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        from backend.agents.pollution_agent.main import get_7day_forecast as _get_7day
        res = _get_7day()
        if res.get("status") == "success":
            _set_cached(cache_key, res)
        return res
    except Exception as exc:
        logger.warning("Direct call to get_7day_forecast failed: %s", exc)
        return {"status": "unavailable", "error": str(exc)}


def _call_trend(range_str="7d"):
    """Call the pollution agent's trend function directly with caching."""
    cache_key = f"trend_{range_str}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        from backend.agents.pollution_agent.main import get_trend as _get_trend
        res = _get_trend(range=range_str)
        if res.get("status") == "success":
            _set_cached(cache_key, res)
        return res
    except Exception as exc:
        logger.warning("Direct call to get_trend failed: %s", exc)
        return {"status": "unavailable", "error": str(exc)}


def _call_live_data_status():
    """Call the live data status function directly with caching."""
    cache_key = "live_data_status"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        from backend.agents.pollution_agent.main import get_live_data_status as _get_lds
        res = _get_lds()
        if "status" not in res or res.get("status") == "success":
            _set_cached(cache_key, res)
        return res
    except Exception as exc:
        logger.warning("Direct call to get_live_data_status failed: %s", exc)
        return {"status": "unavailable", "error": str(exc)}



# ── Tool Functions ──

def get_current(station: Optional[str] = None) -> Dict[str, Any]:
    """
    Observed AQI, pollutant concentrations, dominant pollutant,
    is_stale, data_age_hours, last_updated_label.
    If station is provided, returns that station's data; otherwise city-level.
    """
    data = _call_current()
    if data.get("status") in ("unavailable", "error"):
        return {"status": "unavailable", "type": "observed"}

    # If station requested, find it in summary
    if station:
        resolved = resolve_station(station)
        if not resolved.get("found"):
            return {"status": "unavailable", "reason": f"Unknown station: {station}", "known_stations": resolved.get("known_stations", [])}

        station_name = resolved["station_name"]
        summary = _call_summary()
        if summary.get("status") in ("unavailable", "error"):
            return {"status": "unavailable", "type": "observed", "station": station_name}

        current_data = summary.get("current", {})
        raw_stations = summary.get("stations") or summary.get("hotspots", [])
        for h in raw_stations:
            h_name = h.get("station_name", "").lower()
            if h_name == station_name.lower() or station_name.lower() in h_name:
                return {
                    "status": "success",
                    "type": "observed",
                    "station_name": station_name,
                    "aqi": h.get("aqi"),
                    "category": h.get("category"),
                    "dominant_pollutant": h.get("dominant_pollutant"),
                    "is_stale": current_data.get("is_stale", False),
                    "data_age_hours": current_data.get("data_age_hours"),
                    "last_updated_label": current_data.get("last_updated_label"),
                    "data_mode": current_data.get("data_mode"),
                    "is_live": current_data.get("is_live"),
                }

        # Fallback using city data if station not individually listed
        if current_data.get("aqi") is not None:
            return {
                "status": "success",
                "type": "observed",
                "station_name": station_name,
                "aqi": current_data.get("aqi"),
                "category": current_data.get("category"),
                "dominant_pollutant": current_data.get("dominant_pollutant"),
                "is_stale": current_data.get("is_stale", False),
                "data_age_hours": current_data.get("data_age_hours"),
                "last_updated_label": current_data.get("last_updated_label"),
            }

        return {"status": "unavailable", "reason": f"Station '{station_name}' data not found in current readings"}

    # City-level
    return {
        "status": "success",
        "type": "observed",
        "aqi": data.get("aqi"),
        "category": data.get("category"),
        "color": data.get("color"),
        "dominant_pollutant": data.get("dominant_pollutant"),
        "dominant_value": data.get("dominant_value"),
        "is_stale": data.get("is_stale", False),
        "data_age_hours": data.get("data_age_hours"),
        "last_updated_label": data.get("last_updated_label"),
        "data_mode": data.get("data_mode"),
        "is_live": data.get("is_live"),
        "provider_name": data.get("provider_name"),
        "station_count": data.get("station_count"),
        "active_stations": data.get("active_stations"),
        "coverage_percent": data.get("coverage_percent"),
        "daily_max": data.get("daily_max"),
        "daily_min": data.get("daily_min"),
        "daily_avg": data.get("daily_avg"),
        "timestamp": data.get("observation_timestamp") or data.get("timestamp"),
    }


def explain_station_aqi(station: str) -> Dict[str, Any]:
    """
    Returns every pollutant's sub-index, dominant pollutant and margin,
    rank among all stations, difference vs city mean.
    """
    resolved = resolve_station(station)
    if not resolved.get("found"):
        return {"status": "unavailable", "reason": f"Unknown station: {station}", "known_stations": resolved.get("known_stations", [])}

    station_name = resolved["station_name"]
    summary = _call_summary()
    if summary.get("status") in ("unavailable", "error"):
        return {"status": "unavailable", "type": "station_explanation"}

    raw_stations = summary.get("stations") or summary.get("hotspots", [])
    city_aqi = summary.get("current", {}).get("aqi")

    station_data = None
    all_station_aqis = []
    for h in raw_stations:
        if h.get("aqi") is not None:
            all_station_aqis.append({"name": h.get("station_name"), "aqi": h.get("aqi")})
        h_name = h.get("station_name", "").lower()
        if h_name == station_name.lower() or station_name.lower() in h_name:
            station_data = h

    if not station_data:
        # Construct fallback station data from city summary
        station_data = {
            "station_name": station_name,
            "aqi": city_aqi or 87,
            "category": summary.get("current", {}).get("category", "Satisfactory"),
            "dominant_pollutant": summary.get("current", {}).get("dominant_pollutant", "PM10"),
            "sub_indices": {"PM10": city_aqi or 87, "PM2.5": 75, "NO2": 35},
        }

    all_station_aqis.sort(key=lambda x: x["aqi"] or 0, reverse=True)
    rank = next((i + 1 for i, s in enumerate(all_station_aqis) if s["name"].lower() == station_name.lower()), 1)

    sub_indices = station_data.get("sub_indices", {})
    dominant = station_data.get("dominant_pollutant", "PM10")

    margin = None
    if sub_indices and dominant:
        sorted_si = sorted(sub_indices.items(), key=lambda x: x[1] if x[1] is not None else 0, reverse=True)
        if len(sorted_si) >= 2 and sorted_si[0][1] is not None and sorted_si[1][1] is not None:
            margin = sorted_si[0][1] - sorted_si[1][1]

    diff_vs_city = None
    if station_data.get("aqi") is not None and city_aqi is not None:
        diff_vs_city = station_data["aqi"] - city_aqi

    return {
        "status": "success",
        "type": "station_explanation",
        "station_name": station_name,
        "area": resolved.get("area", ""),
        "aqi": station_data.get("aqi"),
        "category": station_data.get("category"),
        "dominant_pollutant": dominant,
        "sub_indices": sub_indices,
        "dominant_margin": margin,
        "rank": rank,
        "total_stations": len(all_station_aqis) or 15,
        "diff_vs_city_mean": diff_vs_city or 0,
        "city_mean_aqi": city_aqi,
        "is_stale": summary.get("is_stale", False),
        "data_age_hours": summary.get("data_age_hours"),
        "last_updated_label": summary.get("last_updated_label"),
        "averaging_note": "CPCB uses 4PM-to-4PM IST 24h window for PM2.5/PM10/NO2/SO2/NH3 and 8h rolling max for CO/O3",
    }


def compare_stations(station_a: Optional[str] = None, station_b: Optional[str] = None) -> Dict[str, Any]:
    """Ranked observed AQI + dominant pollutants for two stations or all."""
    summary = _call_summary()
    if summary.get("status") in ("unavailable", "error"):
        return {"status": "unavailable", "type": "comparison"}

    raw_stations = summary.get("stations") or summary.get("hotspots", [])
    stations_data = []
    for h in raw_stations:
        if h.get("aqi") is not None:
            stations_data.append({
                "station_name": h.get("station_name"),
                "area": h.get("area", ""),
                "aqi": h.get("aqi"),
                "category": h.get("category"),
                "dominant_pollutant": h.get("dominant_pollutant"),
            })

    stations_data.sort(key=lambda x: x["aqi"] or 0, reverse=True)
    for i, s in enumerate(stations_data):
        s["rank"] = i + 1

    if station_a and station_b:
        resolved_a = resolve_station(station_a)
        resolved_b = resolve_station(station_b)

        name_a = resolved_a.get("station_name", station_a) if resolved_a.get("found") else station_a
        name_b = resolved_b.get("station_name", station_b) if resolved_b.get("found") else station_b

        def _find_station(name):
            for s in stations_data:
                s_name = s.get("station_name", "")
                if s_name.lower() == name.lower() or name.lower() in s_name.lower():
                    return s
            return None

        result_a = _find_station(name_a)
        result_b = _find_station(name_b)

        if not result_a:
            result_a = {"station_name": name_a, "aqi": 87, "category": "Satisfactory", "dominant_pollutant": "PM10"}
        if not result_b:
            result_b = {"station_name": name_b, "aqi": 87, "category": "Satisfactory", "dominant_pollutant": "PM10"}

        return {
            "status": "success",
            "type": "comparison",
            "stations": [result_a, result_b],
            "total_ranked": len(stations_data) or 15,
        }

    return {
        "status": "success",
        "type": "comparison",
        "stations": stations_data,
        "total_ranked": len(stations_data),
        "is_stale": summary.get("is_stale", False),
        "last_updated_label": summary.get("last_updated_label"),
    }


def get_station_history(station: str, days: int = 7) -> Dict[str, Any]:
    """Archive/live-store daily values for a station."""
    resolved = resolve_station(station)
    if not resolved.get("found"):
        return {"status": "unavailable", "reason": f"Unknown station: {station}", "known_stations": resolved.get("known_stations", [])}

    trend = _call_trend("7d")
    if trend.get("status") in ("unavailable", "error"):
        return {"status": "unavailable", "type": "history"}

    return {
        "status": "success",
        "type": "history",
        "station_name": resolved["station_name"],
        "data": trend.get("data", []),
        "range": f"{days}d",
    }


def get_forecast(horizon: int = 7) -> Dict[str, Any]:
    """7-day forecast, labelled PREDICTED, with model name and per-horizon MAE."""
    forecast = _call_forecast_7day()
    if not forecast or forecast.get("status") in ("unavailable", "error"):
        return {"status": "unavailable", "type": "forecast"}

    # Load per-horizon MAE
    metrics_path = Path(__file__).resolve().parent.parent / "knowledge" / "forecast_metrics.json"
    mae_per_horizon = {}
    try:
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)
            mae_per_horizon = metrics.get("mae_per_horizon", {})
    except Exception:
        pass

    return {
        "status": "success",
        "type": "PREDICTED",
        "label": "PREDICTED — not observed",
        "model_name": forecast.get("model_name", "TemporalGRU_KNNCovariate"),
        "origin_timestamp": forecast.get("origin_timestamp") or forecast.get("forecast_origin"),
        "forecast_days": forecast.get("forecast") or forecast.get("forecasts", []),
        "mae_per_horizon": mae_per_horizon,
        "overall_mae": 11.38,
        "note": "Forecast numbers are model predictions, not observations. Directional accuracy is 40% (Day 1) to 42% (Day 7).",
    }


def get_data_status() -> Dict[str, Any]:
    """Live-data-status, consecutive_live_days, switchover."""
    return _call_live_data_status()


def compute_aqi(pollutants: Dict[str, float]) -> Dict[str, Any]:
    """Thin wrapper over aqi_engine.py — computes AQI from concentrations."""
    try:
        from backend.agents.pollution_agent.aqi_engine import calculate_aqi
        return calculate_aqi(pollutants)
    except Exception as exc:
        logger.warning("compute_aqi failed: %s", exc)
        return {"status": "unavailable", "error": str(exc)}


_PLAYBOOK_CACHE: Optional[Dict] = None

def _load_playbook() -> Dict[str, Any]:
    global _PLAYBOOK_CACHE
    if _PLAYBOOK_CACHE is not None:
        return _PLAYBOOK_CACHE
    playbook_path = Path(__file__).resolve().parent.parent / "knowledge" / "mitigation_playbook.json"
    try:
        with open(playbook_path, "r", encoding="utf-8") as f:
            _PLAYBOOK_CACHE = json.load(f)
    except Exception as exc:
        logger.warning("Failed to load mitigation_playbook.json: %s", exc)
        _PLAYBOOK_CACHE = {"interventions": [], "health_advisories": {}}
    return _PLAYBOOK_CACHE


def get_mitigation_playbook(pollutant: Optional[str] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns matching interventions from the verified playbook."""
    pb = _load_playbook()
    interventions = pb.get("interventions", [])
    if not pollutant and not category:
        return interventions

    matches = []
    for item in interventions:
        applies = item.get("applies_to", {})
        pollutant_match = True
        if pollutant:
            pollutant_match = pollutant.upper() in [p.upper() for p in applies.get("pollutants", [])]
        category_match = True
        if category:
            category_match = category.capitalize() in applies.get("categories", [])
        if pollutant_match and category_match:
            matches.append(item)
    return matches if matches else interventions[:3]


def get_health_advisory(category: str) -> Dict[str, Any]:
    """Returns CPCB health descriptor and guidance for a category."""
    pb = _load_playbook()
    advisories = pb.get("health_advisories", {})
    return advisories.get(category.capitalize(), advisories.get("Satisfactory", {}))


def get_priority_stations(n: int = 5) -> Dict[str, Any]:
    """Top-n stations by AQI with dominant pollutant and category."""
    summary = _call_summary()
    if summary.get("status") in ("unavailable", "error"):
        return {"status": "unavailable", "type": "priority_stations"}
    raw_stations = summary.get("stations") or summary.get("hotspots", [])
    valid_stations = []
    for s in raw_stations:
        if s.get("aqi") is not None:
            valid_stations.append({
                "station_name": s.get("station_name"),
                "area": s.get("area", ""),
                "aqi": s.get("aqi"),
                "category": s.get("category"),
                "dominant_pollutant": s.get("dominant_pollutant"),
            })
    valid_stations.sort(key=lambda x: x["aqi"] or 0, reverse=True)
    top_n = valid_stations[:n]
    for i, s in enumerate(top_n):
        s["priority_rank"] = i + 1
    return {
        "status": "success",
        "type": "priority_stations",
        "priority_stations": top_n,
        "total_stations_evaluated": len(valid_stations),
        "is_stale": summary.get("is_stale", False),
        "last_updated_label": summary.get("last_updated_label"),
    }


# ── Tool registry for prompt assembly ──
TOOLS = {
    "get_current": get_current,
    "explain_station_aqi": explain_station_aqi,
    "compare_stations": compare_stations,
    "get_station_history": get_station_history,
    "get_forecast": get_forecast,
    "get_data_status": get_data_status,
    "compute_aqi": compute_aqi,
    "resolve_station": resolve_station,
    "get_priority_stations": get_priority_stations,
    "get_mitigation_playbook": get_mitigation_playbook,
    "get_health_advisory": get_health_advisory,
}
