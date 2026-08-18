"""
SUPADSP Specialist Agent — Weather Intelligence
Handles ambient temperature, humidity, wind vector telemetry, and severe weather alert correlations.
"""

from fastapi import FastAPI

app = FastAPI(title="SUPADSP Weather Agent", version="2.0.0")

@app.get("/health")
def health():
    return {"agent": "Weather Agent", "status": "ONLINE"}

@app.get("/api/v1/weather/current")
def get_current_weather():
    return {
        "city": "Hyderabad",
        "temperature_c": 31.5,
        "humidity_pct": 64,
        "wind_speed_kmh": 12.8,
        "wind_direction": "WSW",
        "precipitation_mm": 0.0,
        "condition": "Partly Cloudy"
    }
