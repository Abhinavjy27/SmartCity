"""
Dynamic Weather Alerts and Meteorological Risk Engine for SUPADSP Weather Agent.
Computes alerts, severe weather warnings, and health/comfort advisories based on live telemetry.
"""

from typing import Any, Dict, List
import datetime


def generate_weather_alerts(weather_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate deterministic meteorological alerts based on live temperature,
    humidity, wind vectors, and precipitation forecasts.
    """
    temp_c = float(weather_data.get("temperature_c", 30.0))
    humidity = int(weather_data.get("humidity_pct", 50))
    wind_kmh = float(weather_data.get("wind_speed_kmh", 10.0))
    precip_mm = float(weather_data.get("precipitation_mm", 0.0))
    cond = str(weather_data.get("condition", "")).lower()

    alerts: List[Dict[str, Any]] = []
    now_str = datetime.datetime.now().strftime("%I:%M %p")

    # 1. High Temperature / Heatwave Alert
    if temp_c >= 40.0:
        alerts.append({
            "title": "Severe Heatwave Warning",
            "desc": f"Extreme daytime temperatures reaching {temp_c}°C. Avoid outdoor activity between 12 PM and 4 PM.",
            "time": now_str,
            "color": "#E5483F",
            "severity": "CRITICAL",
        })
    elif temp_c >= 35.0:
        alerts.append({
            "title": "High Temperature Alert",
            "desc": f"Day temperatures expected to peak at {temp_c}°C. High hydration advisories in effect.",
            "time": now_str,
            "color": "#F4A62A",
            "severity": "MODERATE",
        })

    # 2. Thunderstorm / Monsoon Inundation Watch
    forecast_7d = weather_data.get("forecast_7d", [])
    has_storm_forecast = False
    max_rain_prob = 0
    for day in forecast_7d[:2]:
        rain_prob = int(str(day.get("rain", "0")).replace("%", "") or "0")
        if rain_prob > max_rain_prob:
            max_rain_prob = rain_prob
        if "thunder" in str(day.get("condition", "")).lower() or rain_prob >= 60:
            has_storm_forecast = True

    if "thunder" in cond or (precip_mm > 15.0):
        alerts.append({
            "title": "Active Thunderstorm Alert",
            "desc": "Active convective thunderstorm with heavy showers detected over urban catchment zones.",
            "time": now_str,
            "color": "#E5483F",
            "severity": "HIGH",
        })
    elif has_storm_forecast or max_rain_prob >= 50:
        alerts.append({
            "title": "Thunderstorm Watch",
            "desc": f"Convective cloud build-up likely in Hyderabad. Precipitation probability {max_rain_prob}%.",
            "time": now_str,
            "color": "#F4A62A",
            "severity": "MODERATE",
        })

    # 3. High Wind Advisory
    if wind_kmh >= 35.0:
        alerts.append({
            "title": "High Wind Advisory",
            "desc": f"Sustained wind gusts reaching {wind_kmh} km/h. Caution advised for high-profile vehicles.",
            "time": now_str,
            "color": "#F4A62A",
            "severity": "MODERATE",
        })

    # Fallback advisory if no extreme alert is active
    if not alerts:
        alerts.append({
            "title": "Favorable Atmospheric Conditions",
            "desc": f"Normal seasonal conditions ({temp_c}°C, {humidity}% humidity). No severe weather warnings active.",
            "time": now_str,
            "color": "#2F8F72",
            "severity": "LOW",
        })

    # Assess overall risk level
    if any(a.get("severity") in ("CRITICAL", "HIGH") for a in alerts):
        risk_level = "High"
        primary_risk = "Thunderstorms & Heavy Rain" if max_rain_prob >= 50 else "Extreme Temperature"
    elif any(a.get("severity") == "MODERATE" for a in alerts):
        risk_level = "Moderate"
        primary_risk = "Thunderstorms" if max_rain_prob >= 40 else "High Daytime Temperature"
    else:
        risk_level = "Low"
        primary_risk = "None"

    return {
        "source": "SUPADSP Meteorological Risk Engine",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "alerts": alerts,
        "risk_level": risk_level,
        "primary_risk": primary_risk,
        "probability_pct": max_rain_prob,
        "time_window": "2 PM - 10 PM" if max_rain_prob >= 40 else "All Day",
    }


def compute_air_comfort(weather_data: Dict[str, Any]) -> Dict[str, Any]:
    """Compute pollen, heat index, and outdoor comfort indicators."""
    temp_c = float(weather_data.get("temperature_c", 30.0))
    humidity = int(weather_data.get("humidity_pct", 50))

    # Basic thermal comfort classification
    if 20.0 <= temp_c <= 28.0 and 30 <= humidity <= 60:
        comfort = "Optimal"
        comfort_color = "#2F8F72"
        outdoor = "Ideal"
    elif temp_c > 35.0 or (temp_c > 30.0 and humidity > 70):
        comfort = "Oppressive"
        comfort_color = "#E5483F"
        outdoor = "Limited"
    else:
        comfort = "Good"
        comfort_color = "#2F8F72"
        outdoor = "Good"

    # Pollen approximation based on humidity & season
    pollen_count = 28 if humidity > 60 else (45 if temp_c > 32 else 32)
    pollen_level = "Low" if pollen_count < 40 else "Moderate"

    return {
        "pollen_count": pollen_count,
        "pollen_level": pollen_level,
        "air_comfort": comfort,
        "air_comfort_color": comfort_color,
        "outdoor_activity": outdoor,
        "asthma_risk": "Low" if pollen_count < 40 and humidity < 75 else "Moderate",
    }
