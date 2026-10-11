"""
SUPADSP Specialist Agent — Weather Intelligence
Handles ambient temperature, humidity, wind vector telemetry, severe alerts, and cross-domain correlation.
Powered by live Open-Meteo & WeatherAPI telemetry with full offline fallback.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, Optional
from fastapi import APIRouter, FastAPI, Query

from backend.agents.weather_agent.alerts import compute_air_comfort, generate_weather_alerts
from backend.agents.weather_agent.provider import get_weather_provider
from backend.agents.weather_agent.schemas import (
    WeatherAlertsResponse,
    WeatherAnalyzeRequest,
    WeatherAnalyzeResponse,
    WeatherCurrentResponse,
    WeatherForecastResponse,
)

app = FastAPI(
    title="SUPADSP Weather Agent",
    version="2.1.0",
    description="Specialist AI Agent for Meteorological Telemetry, Severe Weather Alerts, and Atmospheric Dispersion Analysis.",
)
router = APIRouter()


@app.get("/health", tags=["System"], summary="Weather agent health check")
def health() -> Dict[str, Any]:
    provider = get_weather_provider()
    # Check if live data is accessible
    sample = provider.get_weather("Hyderabad")
    return {
        "agent": "Weather Agent",
        "status": "ONLINE",
        "active_provider": sample.get("provider", "Open-Meteo"),
        "is_live": sample.get("is_live", False),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


@router.get(
    "/api/v1/weather/current",
    tags=["Weather Telemetry"],
    response_model=WeatherCurrentResponse,
    summary="Get current real-time weather telemetry",
)
def get_current_weather(
    location: Optional[str] = Query(
        default="Hyderabad",
        description="Location name, corridor, or locality (e.g. 'Narayanguda', 'Gachibowli', 'Begumpet', 'Hyderabad')",
    ),
    city: Optional[str] = Query(
        default=None,
        description="Optional city alias",
    ),
) -> Dict[str, Any]:
    loc_query = location or city or "Hyderabad"
    provider = get_weather_provider()
    data = provider.get_weather(loc_query)
    return data


@router.get(
    "/api/v1/weather/forecast",
    tags=["Weather Telemetry"],
    summary="Get 7-day and hourly weather forecasts",
)
def get_weather_forecast(
    location: Optional[str] = Query(default="Hyderabad", description="Location name or corridor"),
) -> Dict[str, Any]:
    provider = get_weather_provider()
    data = provider.get_weather(location or "Hyderabad")
    return {
        "source": data.get("source"),
        "provider": data.get("provider"),
        "is_live": data.get("is_live"),
        "timestamp": data.get("timestamp"),
        "city": data.get("city"),
        "forecast_7d": data.get("forecast_7d", []),
        "hourly": data.get("hourly_temp", []),
        "weekly_precipitation": data.get("weekly_precipitation", []),
    }


@router.get(
    "/api/v1/weather/alerts",
    tags=["Weather Alerts"],
    summary="Get active weather alerts and air comfort indices",
)
def get_weather_alerts(
    location: Optional[str] = Query(default="Hyderabad", description="Target location"),
) -> Dict[str, Any]:
    provider = get_weather_provider()
    data = provider.get_weather(location or "Hyderabad")
    alerts_data = generate_weather_alerts(data)
    comfort_data = compute_air_comfort(data)
    alerts_data.update(comfort_data)
    return alerts_data


@router.post(
    "/api/v1/weather/analyze",
    tags=["Analysis"],
    response_model=WeatherAnalyzeResponse,
    summary="Analyze weather impacts for planning scenario",
)
def analyze_weather(req: Optional[WeatherAnalyzeRequest] = None) -> Dict[str, Any]:
    req = req or WeatherAnalyzeRequest()
    loc = req.location or "Hyderabad"
    provider = get_weather_provider()
    weather_data = provider.get_weather(loc)

    temp = float(weather_data.get("temperature_c", 30.0))
    wind = float(weather_data.get("wind_speed_kmh", 10.0))
    precip = float(weather_data.get("precipitation_mm", 0.0))

    impacts = {
        "traffic_impact": {
            "speed_reduction_pct": 15.0 if precip > 5.0 else (8.0 if precip > 0 else 0.0),
            "friction_coefficient": "LOW" if precip > 2.0 else "NORMAL",
            "drainage_risk": "HIGH" if precip > 20.0 else "NOMINAL",
        },
        "energy_impact": {
            "cooling_demand_factor": round(1.0 + max(0.0, (temp - 25.0) * 0.04), 2),
            "hvac_peak_stress": "HIGH" if temp >= 38.0 else ("ELEVATED" if temp >= 32.0 else "NORMAL"),
        },
        "pollution_impact": {
            "dispersion_condition": "POOR" if wind < 5.0 else ("FAVORABLE" if wind > 15.0 else "MODERATE"),
            "ozone_formation_risk": "HIGH" if temp > 33.0 else "MODERATE",
        },
    }

    recommendations = []
    if precip > 10.0:
        recommendations.append("Activate monsoon stormwater pumps in low-lying corridors (Begumpet, Narayanguda).")
        recommendations.append("Implement traffic signal extension for wet pavement braking distances.")
    if temp >= 35.0:
        recommendations.append("Alert distribution substations for afternoon transformer peak cooling load.")
    if wind < 5.0:
        recommendations.append("Enforce temporary dust-suppression watering in industrial corridors due to low dispersion.")

    if not recommendations:
        recommendations.append("Atmospheric conditions nominal; standard operational schedules recommended.")

    return {
        "location": loc,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "weather": weather_data,
        "cross_domain_impacts": impacts,
        "recommendations": recommendations,
    }


@router.post(
    "/api/v1/weather/chat",
    tags=["Weather Conversational AI"],
    summary="Answer natural-language questions about weather in a specific area",
)
def weather_chat(data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from backend.agents.weather_agent.chat import answer_weather_question

    payload = data or {}
    question = str(payload.get("question") or payload.get("text") or payload.get("query") or "").strip()
    location = str(payload.get("location") or "Hyderabad").strip()
    if not question:
        question = f"What is the weather in {location}?"

    return answer_weather_question(question=question, default_location=location)


app.include_router(router)
