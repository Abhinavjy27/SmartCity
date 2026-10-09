"""
Domain router for Planning Assistant chat endpoint.
Analyzes question text to route to:
- pollution
- traffic
- energy
- weather (baseline simulation)

The frontend chip is used only as a tie-break hint.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

AIR_TERMS = [
    "aqi", "air quality", "pollution", "pollutant", "pollutants", "pm2.5", "pm10",
    "pm 2.5", "pm 10", "smog", "emission", "emissions", "so2", "no2", "co",
    "o3", "ozone", "sulfur dioxide", "nitrogen dioxide", "carbon monoxide", "ammonia",
    "nh3", "cpcb", "tspcb", "naqi", "sub-index", "sub-indices", "caaqms", "air index",
    "inversion", "inversions", "switchover"
]

TRAFFIC_TERMS = [
    "traffic", "congestion", "vehicle", "vehicles", "cars", "corridor",
    "signal", "signals", "signal timing", "traffic light", "jam", "gridlock",
    "flyover", "commute", "rerouting", "bottleneck", "divergence", "vehicles/hour",
    "traffic speed", "traffic flow", "transit"
]

ENERGY_TERMS = [
    "energy", "power", "grid", "electricity", "load", "substation", "transformer",
    "feeder", "megawatt", "mw", "peak load", "peak-load", "solar", "bess",
    "streetlights", "dimming", "power draw", "blackout", "voltage"
]

WEATHER_TERMS = [
    "weather", "temperature", "temp", "degrees", "celsius", "humidity", "rain",
    "raining", "rainfall", "monsoon", "precipitation", "precip", "wind speed",
    "wind direction", "wind", "breeze", "forecast weather", "weather forecast",
    "hot", "cold", "sunny", "cloudy", "overcast", "thunderstorm", "hail"
]


def classify_domains(question: str, chip_hint: Optional[str] = None) -> Tuple[str, List[str]]:
    """
    Classify question into primary domain and matched domains.
    Returns (primary_domain, matched_domains_list).
    """
    q = question.lower().strip()

    has_air = any(re.search(r"\b" + re.escape(term) + r"\b", q) for term in AIR_TERMS)
    has_traffic = any(re.search(r"\b" + re.escape(term) + r"\b", q) for term in TRAFFIC_TERMS)
    has_energy = any(re.search(r"\b" + re.escape(term) + r"\b", q) for term in ENERGY_TERMS)
    has_weather = any(re.search(r"\b" + re.escape(term) + r"\b", q) for term in WEATHER_TERMS)

    matched = []
    if has_air:
        matched.append("pollution")
    if has_traffic:
        matched.append("traffic")
    if has_energy:
        matched.append("energy")
    if has_weather:
        matched.append("weather")

    # Air quality takes precedence for pollution agent
    if has_air:
        return "pollution", matched

    # Traffic
    if has_traffic:
        return "traffic", matched

    # Energy
    if has_energy:
        return "energy", matched

    # Weather
    if has_weather:
        return "weather", matched

    # Station or location specific query without domain words
    from .tools import _load_stations
    stations = _load_stations()
    for s in stations:
        p_name = s.get("primary_name", "").lower()
        if p_name in q:
            if chip_hint and chip_hint.lower() in ("traffic", "energy", "weather"):
                return chip_hint.lower(), [chip_hint.lower()]
            return "pollution", ["pollution"]

    # Begumpet or other area query
    if "begumpet" in q:
        return "traffic", ["traffic"]

    # Multi-domain or planning queries
    if any(term in q for term in ["multi-domain", "operational action plan", "action plan", "urban planning"]):
        return "planning", ["planning"]

    # Fallback to chip hint if available
    if chip_hint:
        hint_lower = chip_hint.strip().lower()
        if hint_lower in ("air quality", "air", "pollution"):
            return "pollution", ["pollution"]
        if hint_lower in ("traffic", "energy", "weather", "planning"):
            return hint_lower, [hint_lower]

    return "pollution", ["pollution"]
