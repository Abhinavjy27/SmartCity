"""
Conversational Question-Answering and Natural Language Reasoning Engine
for the SUPADSP Weather Agent.
Provides grounded, real-time meteorological answers for any Hyderabad locality or query.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.agents.weather_agent.alerts import compute_air_comfort, generate_weather_alerts
from backend.agents.weather_agent.provider import (
    LOCALITY_COORDINATES,
    get_weather_provider,
    resolve_location,
)

logger = logging.getLogger("weather_agent.chat")


def extract_locality_from_query(query: str, default: str = "Hyderabad") -> Tuple[str, float, float]:
    """Identify if the user asked about a specific locality in Hyderabad or any other location."""
    q_lower = query.lower()

    # 1. Direct registry lookup (prioritizing longer names first)
    for loc_name in sorted(LOCALITY_COORDINATES.keys(), key=len, reverse=True):
        if re.search(r"\b" + re.escape(loc_name) + r"\b", q_lower):
            return resolve_location(loc_name)

    # 2. Extract prepositional location phrases ("in Kukatpally", "for Madhapur", "near Shamshabad")
    prep_match = re.search(
        r"\b(?:in|at|for|around|near)\s+([A-Za-z\s\-]+?)(?:\s+(?:today|tomorrow|now|right now|currently|this|tonight|please|\?|$)|[?,.]|$)",
        query,
        re.IGNORECASE,
    )
    if prep_match:
        candidate = prep_match.group(1).strip()
        stop_words = {"the city", "detail", "celsius", "general", "advance", "today", "tomorrow", "now", "here"}
        if candidate and len(candidate) > 2 and candidate.lower() not in stop_words:
            resolved_name, lat, lon = resolve_location(candidate)
            return resolved_name, lat, lon

    return resolve_location(default)


def answer_weather_question(
    question: str,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    default_location: str = "Hyderabad",
) -> Dict[str, Any]:
    """
    Answer natural-language questions about current weather, rain, forecast,
    alerts, humidity, wind, or cross-domain impacts for a specific area.
    """
    q_lower = question.lower().strip()
    locality, lat, lon = extract_locality_from_query(question, default=default_location)

    # 1. Fetch live telemetry for the resolved locality
    provider = get_weather_provider()
    weather = provider.get_weather(locality)
    alerts = generate_weather_alerts(weather)
    comfort = compute_air_comfort(weather)

    temp = weather.get("temperature_c", 30.0)
    feels_like = weather.get("feels_like_c", temp + 2.0)
    condition = weather.get("condition", "Partly Cloudy")
    humidity = weather.get("humidity_pct", 50)
    wind_spd = weather.get("wind_speed_kmh", 10.0)
    wind_dir = weather.get("wind_direction", "WSW")
    precip_mm = weather.get("precipitation_mm", 0.0)
    provider_name = weather.get("provider", "Live Telemetry")
    forecast_7d = weather.get("forecast_7d", [])

    # 2. Classify intent
    is_rain_query = any(w in q_lower for w in ["rain", "raining", "rainfall", "shower", "umbrella", "precipitation", "wet"])
    is_temp_query = any(w in q_lower for w in ["temperature", "temp", "hot", "cold", "warm", "degrees", "celsius", "how hot", "feels like"])
    is_forecast_query = any(w in q_lower for w in ["forecast", "tomorrow", "this week", "next week", "upcoming", "7 day", "7-day", "weekend", "sunday", "saturday"])
    is_alert_query = any(w in q_lower for w in ["alert", "warning", "storm", "thunderstorm", "heatwave", "danger", "severe", "safe"])
    is_wind_query = any(w in q_lower for w in ["wind", "breeze", "gust", "wind speed", "wind direction", "dispersion"])
    is_humidity_query = any(w in q_lower for w in ["humidity", "humid", "dew point", "pressure", "sweat", "muggy"])
    is_outdoor_query = any(w in q_lower for w in ["run", "running", "jogging", "outdoor", "walk", "sports", "pollen", "air comfort", "asthma"])
    is_cross_domain_query = any(w in q_lower for w in ["traffic", "pollution", "energy", "grid", "congestion", "aqi"])

    # Extract rain probability for today & tomorrow
    today_rain_prob = 10
    tomorrow_rain_prob = 15
    tomorrow_cond = "Partly Cloudy"
    tomorrow_high = round(temp + 1)
    tomorrow_low = round(temp - 7)

    if forecast_7d and len(forecast_7d) > 0:
        try:
            today_rain_prob = int(str(forecast_7d[0].get("rain", "10")).replace("%", "") or "10")
        except Exception:
            pass
    if forecast_7d and len(forecast_7d) > 1:
        try:
            tomorrow_rain_prob = int(str(forecast_7d[1].get("rain", "15")).replace("%", "") or "15")
            tomorrow_cond = forecast_7d[1].get("condition", "Partly Cloudy")
            tomorrow_high = forecast_7d[1].get("high", 33)
            tomorrow_low = forecast_7d[1].get("low", 24)
        except Exception:
            pass

    # 3. Formulate response based on intent
    if is_rain_query:
        if precip_mm > 0.0 or today_rain_prob >= 50:
            text = (
                f"Yes, precipitation is likely in {locality}. Current precipitation is {precip_mm} mm with a "
                f"{today_rain_prob}% probability of rain today. Tomorrow's rain chance is {tomorrow_rain_prob}% ({tomorrow_cond})."
            )
        else:
            text = (
                f"Rain is unlikely right now in {locality}. Current precipitation is {precip_mm} mm with only a "
                f"{today_rain_prob}% chance of rain today under {condition.lower()} conditions. Tomorrow has a {tomorrow_rain_prob}% chance."
            )
        insights = [
            f"Precipitation chance in {locality}: {today_rain_prob}% (Current: {precip_mm} mm).",
            f"Tomorrow's rain forecast: {tomorrow_rain_prob}% with {tomorrow_cond.lower()} skies.",
            f"Live Telemetry Source: {provider_name}.",
        ]
        suggestions = [
            f"Show 7-day forecast for {locality}",
            f"What is the temperature in {locality}?",
            f"Are there thunderstorm alerts in Hyderabad?",
        ]

    elif is_temp_query:
        text = (
            f"The current temperature in {locality} is {temp}°C (feels like {feels_like}°C) with {condition.lower()} skies. "
            f"Today's high is expected to reach {forecast_7d[0].get('high', 34) if forecast_7d else 34}°C with a low of "
            f"{forecast_7d[0].get('low', 24) if forecast_7d else 24}°C."
        )
        insights = [
            f"Current temperature: {temp}°C (Apparent: {feels_like}°C).",
            f"Humidity: {humidity}% | Surface Pressure: {weather.get('pressure_hpa', 1012)} hPa.",
            f"Diurnal range: High {forecast_7d[0].get('high', 34) if forecast_7d else 34}°C / Low {forecast_7d[0].get('low', 24) if forecast_7d else 24}°C.",
        ]
        suggestions = [
            f"Is it going to rain in {locality}?",
            f"Show wind speed in {locality}",
            f"7-day weather outlook",
        ]

    elif is_forecast_query:
        days_summary = []
        for d in forecast_7d[:5]:
            days_summary.append(f"{d.get('day')}: {d.get('high')}°/{d.get('low')}°C ({d.get('condition')}, {d.get('rain')} rain)")
        text = (
            f"Here is the weather outlook for {locality}: Currently {temp}°C with {condition.lower()}. "
            f"Tomorrow will be {tomorrow_cond} with highs of {tomorrow_high}°C and lows of {tomorrow_low}°C ({tomorrow_rain_prob}% rain)."
        )
        insights = [
            f"Today: {forecast_7d[0].get('high', 34) if forecast_7d else 34}°/{forecast_7d[0].get('low', 24) if forecast_7d else 24}°C, {condition}.",
            f"Tomorrow: {tomorrow_high}°/{tomorrow_low}°C, {tomorrow_cond} ({tomorrow_rain_prob}% rain).",
            f"5-day outlook: {', '.join(days_summary[:3])}.",
        ]
        suggestions = [
            f"Will it rain this weekend in {locality}?",
            f"Check weather alerts for Hyderabad",
            f"Current temperature in {locality}",
        ]

    elif is_alert_query:
        primary_alert = alerts.get("primary_risk", "None")
        risk_lvl = alerts.get("risk_level", "Low")
        alert_items = alerts.get("alerts", [])
        if alert_items and risk_lvl in ("Moderate", "High", "Critical"):
            top_a = alert_items[0]
            text = (
                f"The current meteorological risk level for {locality} is {risk_lvl}. "
                f"Active alert: {top_a.get('title')} — {top_a.get('desc')} (Probability: {alerts.get('probability_pct', 45)}%)."
            )
        else:
            text = (
                f"No severe weather warnings are active for {locality}. Conditions are nominal with "
                f"{temp}°C, {humidity}% humidity, and {condition.lower()} skies."
            )
        insights = [
            f"Risk Level: {risk_lvl} (Primary Hazard: {primary_alert}).",
            f"Rain / Storm probability: {alerts.get('probability_pct', 10)}% (Time Window: {alerts.get('time_window', 'All Day')}).",
            f"Wind gusts: {wind_spd} km/h {wind_dir}.",
        ]
        suggestions = [
            f"What is the rainfall chance in {locality}?",
            f"Show 24-hour weather curve",
            f"Weather impact on traffic",
        ]

    elif is_wind_query:
        dispersion_quality = "Advective / Favorable" if wind_spd >= 10.0 else "Low / Poor Dispersion"
        text = (
            f"Current wind speed in {locality} is {wind_spd} km/h blowing from the {wind_dir}. "
            f"Atmospheric dispersion capacity is currently rated as {dispersion_quality}."
        )
        insights = [
            f"Wind speed: {wind_spd} km/h (Direction: {wind_dir}).",
            f"Pollutant dispersion condition: {dispersion_quality}.",
            f"Corridor air clearing rate: {'Accelerated by prevailing wind' if wind_spd >= 12 else 'Accumulating local emissions'}.",
        ]
        suggestions = [
            f"How does wind speed affect AQI in {locality}?",
            f"Current temperature in {locality}",
            f"Check weather alerts",
        ]

    elif is_outdoor_query:
        text = (
            f"Outdoor conditions in {locality} are currently rated as {comfort.get('outdoor_activity', 'Good')}. "
            f"Temperature is {temp}°C with {humidity}% humidity, air comfort is {comfort.get('air_comfort', 'Good')}, "
            f"and pollen count is {comfort.get('pollen_count', 32)} ({comfort.get('pollen_level', 'Low')})."
        )
        insights = [
            f"Outdoor activity rating: {comfort.get('outdoor_activity', 'Good')}.",
            f"Thermal comfort: {comfort.get('air_comfort', 'Good')} (Asthma risk: {comfort.get('asthma_risk', 'Low')}).",
            f"Pollen level: {comfort.get('pollen_count', 32)} ({comfort.get('pollen_level', 'Low')}).",
        ]
        suggestions = [
            f"What is the UV index in {locality}?",
            f"Will it rain later today in {locality}?",
            f"7-day weather outlook",
        ]

    elif is_cross_domain_query:
        precip_impact = "Normal corridor speeds" if precip_mm == 0 else f"Corridor speeds slowed by 10-15% due to {precip_mm} mm rain"
        cooling_impact = "Elevated HVAC electricity load" if temp >= 32 else "Normal grid cooling load"
        text = (
            f"Current meteorological conditions in {locality} ({temp}°C, {humidity}% humidity, {wind_spd} km/h wind): "
            f"{precip_impact}; {cooling_impact}; wind ({wind_dir}) provides {'good' if wind_spd >= 10 else 'weak'} pollutant dispersion."
        )
        insights = [
            f"Traffic: {precip_impact}.",
            f"Energy Grid: {cooling_impact} (Ambient: {temp}°C).",
            f"Air Quality: Wind ({wind_spd} km/h {wind_dir}) {'disperses' if wind_spd >= 10 else 'stagnates'} corridor PM2.5.",
        ]
        suggestions = [
            f"Check traffic congestion in {locality}",
            f"Check air quality in {locality}",
            f"Show weather forecast for {locality}",
        ]

    else:
        # General comprehensive overview for the locality
        text = (
            f"In {locality}, current weather is {condition} at {temp}°C (feels like {feels_like}°C). "
            f"Humidity is {humidity}%, wind is blowing at {wind_spd} km/h from {wind_dir}, and precipitation is {precip_mm} mm."
        )
        insights = [
            f"Live Telemetry ({locality}): {temp}°C, {condition}, feels like {feels_like}°C.",
            f"Atmospheric stats: Humidity {humidity}%, Wind {wind_spd} km/h {wind_dir}, Pressure {weather.get('pressure_hpa', 1012)} hPa.",
            f"Precipitation probability: {today_rain_prob}% today, {tomorrow_rain_prob}% tomorrow ({tomorrow_cond}).",
        ]
        suggestions = [
            f"Is it going to rain today in {locality}?",
            f"Show 7-day forecast for {locality}",
            f"Are there any weather alerts?",
        ]

    return {
        "text": text,
        "insights": insights,
        "suggestions": suggestions,
        "data": {
            "locality": locality,
            "latitude": lat,
            "longitude": lon,
            "temperature_c": temp,
            "feels_like_c": feels_like,
            "condition": condition,
            "humidity_pct": humidity,
            "wind_speed_kmh": wind_spd,
            "wind_direction": wind_dir,
            "precipitation_mm": precip_mm,
            "rain_probability_pct": today_rain_prob,
            "is_live": weather.get("is_live", True),
            "provider": provider_name,
        },
    }
