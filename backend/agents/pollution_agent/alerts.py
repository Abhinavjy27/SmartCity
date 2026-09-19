"""
Deterministic rule-based alert engine for pollution data.
No LLM-generated or invented alerts — all based on measurable conditions (§14).
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from .aqi_engine import calculate_aqi, get_aqi_category

logger = logging.getLogger(__name__)

# Alert thresholds
AQI_POOR_THRESHOLD = 200
AQI_VERY_POOR_THRESHOLD = 300
AQI_SEVERE_THRESHOLD = 400
AQI_SENSITIVE_THRESHOLD = 100
RAPID_INCREASE_PCT = 20
COVERAGE_WARNING_PCT = 70


def generate_alerts(
    current_readings: list,
    distribution: list = None,
    area_trends: list = None,
    forecast: dict = None,
    data_quality: dict = None,
) -> list:
    """
    Generate deterministic alerts from real conditions (§14).
    All timestamps are timezone-aware UTC.
    """
    alerts = []
    now = datetime.now(timezone.utc).isoformat()

    # 1. AQI threshold breach alerts (per station with valid AQI)
    for r in current_readings:
        conc = {}
        for p in ["PM2.5", "PM10", "NO2", "SO2", "O3", "CO", "NH3"]:
            val = r.get(p)
            if val is not None:
                conc[p] = val

        if not conc:
            continue

        result = calculate_aqi(conc)
        aqi = result.get("aqi")
        if aqi is None:
            continue  # Sufficiency failed or no data — do not fire

        area = r.get("area", r.get("station_name", "Unknown"))

        if aqi >= AQI_SEVERE_THRESHOLD:
            alerts.append({
                "type": "aqi_threshold",
                "severity": "critical",
                "area": area,
                "message": f"Severe air quality alert: AQI {aqi} at {area}",
                "reason": f"AQI exceeds severe threshold ({AQI_SEVERE_THRESHOLD})",
                "timestamp": now,
                "source": "cpcb_engine",
                "trigger": {"aqi": aqi, "threshold": AQI_SEVERE_THRESHOLD},
                "color": "#5C0029",
            })
        elif aqi >= AQI_VERY_POOR_THRESHOLD:
            alerts.append({
                "type": "aqi_threshold",
                "severity": "high",
                "area": area,
                "message": f"Very poor air quality: AQI {aqi} at {area}",
                "reason": f"AQI exceeds very poor threshold ({AQI_VERY_POOR_THRESHOLD})",
                "timestamp": now,
                "source": "cpcb_engine",
                "trigger": {"aqi": aqi, "threshold": AQI_VERY_POOR_THRESHOLD},
                "color": "#8B0000",
            })
        elif aqi >= AQI_POOR_THRESHOLD:
            alerts.append({
                "type": "aqi_threshold",
                "severity": "medium",
                "area": area,
                "message": f"Poor air quality: AQI {aqi} at {area}",
                "reason": f"AQI exceeds poor threshold ({AQI_POOR_THRESHOLD})",
                "timestamp": now,
                "source": "cpcb_engine",
                "trigger": {"aqi": aqi, "threshold": AQI_POOR_THRESHOLD},
                "color": "#E5483F",
            })

    # 2. Sensitive group advisory when any station has valid AQI > 100 (§14)
    sensitive_stations = []
    for r in current_readings:
        conc = {p: r[p] for p in ["PM2.5", "PM10", "NO2", "SO2", "O3", "CO", "NH3"] if r.get(p) is not None}
        if conc:
            res = calculate_aqi(conc)
            if res.get("aqi") is not None and res["aqi"] > AQI_SENSITIVE_THRESHOLD:
                sensitive_stations.append(r.get("area", r.get("station_name")))

    if sensitive_stations:
        alerts.append({
            "type": "sensitive_group",
            "severity": "medium",
            "area": "City-wide",
            "message": f"Health advisory: {len(sensitive_stations)} areas with AQI above 100. Sensitive groups should limit outdoor exertion.",
            "reason": f"Stations exceeding AQI {AQI_SENSITIVE_THRESHOLD}: {', '.join(sensitive_stations[:3])}",
            "timestamp": now,
            "source": "cpcb_engine",
            "trigger": {"station_count": len(sensitive_stations), "threshold": AQI_SENSITIVE_THRESHOLD},
            "color": "#F4A62A",
        })

    # 3. Rapid increase alerts from area trends
    if area_trends:
        for t in area_trends:
            curr = t.get("current_aqi")
            prev = t.get("previous_aqi")
            chg = t.get("change")
            if (
                t.get("dir") == "up"
                and chg is not None and chg >= RAPID_INCREASE_PCT
                and curr is not None and prev is not None and prev > 0
            ):
                alerts.append({
                    "type": "rapid_increase",
                    "severity": "medium",
                    "area": t.get("area", "Unknown"),
                    "message": f"Rapid AQI increase at {t.get('area')}: +{chg}% vs yesterday",
                    "reason": f"AQI rose from {prev} to {curr}",
                    "timestamp": now,
                    "source": "cpcb_engine",
                    "trigger": {"change_pct": chg, "threshold": RAPID_INCREASE_PCT},
                    "color": "#E5483F",
                })

    # 4. Forecast deterioration alert (§14)
    # Fires ONLY if forecast_status == "success" and forecast_aqi exceeds configured threshold.
    # If forecast is unavailable, NO alert is generated.
    if forecast and forecast.get("forecast_status") == "success":
        f_aqi = forecast.get("forecast_aqi")
        if f_aqi is not None and f_aqi > AQI_POOR_THRESHOLD:
            cat, color = get_aqi_category(f_aqi)
            alerts.append({
                "type": "forecast_warning",
                "severity": "medium",
                "area": "City-wide",
                "message": f"Forecast: AQI may reach {f_aqi} ({cat}) tomorrow",
                "reason": f"Unified model next-day forecast exceeds threshold ({AQI_POOR_THRESHOLD})",
                "timestamp": now,
                "source": "unified_spatial_temporal_model",
                "trigger": {"forecast_aqi": f_aqi, "threshold": AQI_POOR_THRESHOLD},
                "color": color,
            })

    # 5. Data coverage warning (§14)
    if data_quality and data_quality.get("coverage_percent", 100) < COVERAGE_WARNING_PCT:
        alerts.append({
            "type": "data_coverage",
            "severity": "low",
            "area": "System",
            "message": f"Station coverage at {data_quality['coverage_percent']}% — {data_quality['active_stations']}/{data_quality['total_stations']} reporting",
            "reason": f"Coverage below {COVERAGE_WARNING_PCT}% threshold",
            "timestamp": now,
            "source": "tspcb",
            "trigger": {"coverage": data_quality["coverage_percent"], "threshold": COVERAGE_WARNING_PCT},
            "color": "#6C8FC5",
        })

    # Sort deterministically by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    alerts.sort(key=lambda a: severity_order.get(a.get("severity"), 4))

    return alerts
