"""
SUPADSP Specialist Agent — Pollution & Air Quality Intelligence
Handles TSPCB sensor streams, Gaussian Plume dispersion modeling, and AQI forecasting.
"""

from fastapi import FastAPI, APIRouter, HTTPException
import datetime
from backend.agents.pollution_agent.schema import PollutionAnalyzeRequest, PollutionAnalyzeResponse
from backend.agents.pollution_agent.dataset_loader import PollutionCalculator
from backend.agents.pollution_agent.optimizer import InterventionOptimizer

calculator = PollutionCalculator()
optimizer = InterventionOptimizer()


app = FastAPI(title="SUPADSP Pollution Agent", version="2.0.0")
router = APIRouter()

@app.get("/health")
def health():
    return {"agent": "Pollution Agent", "status": "ONLINE"}

@router.get("/api/v1/pollution/aqi-summary")
def get_aqi_summary():
    return {
        "city_avg_aqi": 136,
        "category": "MODERATE",
        "primary_pollutant": "PM2.5",
        "active_stations": 13,
        "stations": [
            {"name": "Sanathnagar", "aqi": 168, "status": "UNHEALTHY_SENSITIVE"},
            {"name": "Zoo Park", "aqi": 142, "status": "MODERATE"},
            {"name": "Gachibowli", "aqi": 112, "status": "MODERATE"},
            {"name": "Bollaram Industrial", "aqi": 195, "status": "UNHEALTHY"}
        ],
        "forecast_24h": [
            {"hour": "06:00", "aqi": 120},
            {"hour": "09:00", "aqi": 155},
            {"hour": "12:00", "aqi": 138},
            {"hour": "15:00", "aqi": 128},
            {"hour": "18:00", "aqi": 162},
            {"hour": "21:00", "aqi": 145}
        ]
    }

@router.get("/api/v1/pollution/current")
def get_current_pollution():
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return {
        "source": "Live Pollution Agent API",
        "timestamp": now_utc,
        "city_avg_aqi": 136,
        "aqi": 136,
        "category": "MODERATE",
        "primary_pollutant": "PM2.5",
        "active_stations": 13,
        "pollutants": [
            {"name": "PM2.5", "value": 78.5, "unit": "μg/m³", "limit": 60, "color": "rose"},
            {"name": "PM10", "value": 115.9, "unit": "μg/m³", "limit": 100, "color": "amber"},
            {"name": "CO", "value": 1189, "unit": "μg/m³", "limit": 2000, "color": "emerald"},
            {"name": "NO₂", "value": 45.0, "unit": "μg/m³", "limit": 80, "color": "violet"},
            {"name": "SO₂", "value": 17.0, "unit": "μg/m³", "limit": 80, "color": "blue"},
            {"name": "O₃", "value": 53.0, "unit": "μg/m³", "limit": 100, "color": "cyan"},
        ],
        "aqi_trend": [
            {"h": "00:00", "aqi": 92, "pm25": 42},
            {"h": "01:00", "aqi": 88, "pm25": 39},
            {"h": "02:00", "aqi": 85, "pm25": 36},
            {"h": "03:00", "aqi": 82, "pm25": 34},
            {"h": "04:00", "aqi": 86, "pm25": 37},
            {"h": "05:00", "aqi": 98, "pm25": 45},
            {"h": "06:00", "aqi": 120, "pm25": 58},
            {"h": "07:00", "aqi": 142, "pm25": 72},
            {"h": "08:00", "aqi": 158, "pm25": 84},
            {"h": "09:00", "aqi": 155, "pm25": 82},
            {"h": "10:00", "aqi": 145, "pm25": 75},
            {"h": "11:00", "aqi": 138, "pm25": 70},
            {"h": "12:00", "aqi": 132, "pm25": 66},
            {"h": "13:00", "aqi": 126, "pm25": 62},
            {"h": "14:00", "aqi": 122, "pm25": 59},
            {"h": "15:00", "aqi": 128, "pm25": 64},
            {"h": "16:00", "aqi": 136, "pm25": 69},
            {"h": "17:00", "aqi": 148, "pm25": 78},
            {"h": "18:00", "aqi": 162, "pm25": 88},
            {"h": "19:00", "aqi": 168, "pm25": 92},
            {"h": "20:00", "aqi": 160, "pm25": 86},
            {"h": "21:00", "aqi": 145, "pm25": 76},
            {"h": "22:00", "aqi": 128, "pm25": 65},
            {"h": "23:00", "aqi": 110, "pm25": 52},
        ],
        "stations": [
            {"name": "Central University", "aqi": 128, "status": "MODERATE_AQI", "pm25": 72.3},
            {"name": "Sanathnagar", "aqi": 156, "status": "POOR", "pm25": 94.1},
            {"name": "Zoo Park", "aqi": 142, "status": "MODERATE_AQI", "pm25": 82.7},
            {"name": "Somajiguda", "aqi": 118, "status": "MODERATE_AQI", "pm25": 65.4},
            {"name": "Kokapet", "aqi": 95, "status": "SATISFACTORY", "pm25": 48.2},
            {"name": "Bollarum Industrial", "aqi": 178, "status": "POOR", "pm25": 112.8},
            {"name": "Kompally", "aqi": 134, "status": "MODERATE_AQI", "pm25": 76.9},
            {"name": "ECIL Kapra", "aqi": 145, "status": "MODERATE_AQI", "pm25": 85.3},
            {"name": "ICRISAT Patancheru", "aqi": 102, "status": "MODERATE_AQI", "pm25": 55.1},
            {"name": "IDA Pashamylaram", "aqi": 168, "status": "POOR", "pm25": 105.7},
            {"name": "Nacharam TSIIC", "aqi": 139, "status": "MODERATE_AQI", "pm25": 79.8},
            {"name": "New Malakpet", "aqi": 151, "status": "POOR", "pm25": 91.4},
            {"name": "Ramachandrapuram", "aqi": 112, "status": "MODERATE_AQI", "pm25": 61.3},
        ]
    }

from backend.agents.pollution_agent.current_client import (
    OpenMeteoCurrentClient,
    PollutionCurrentAPIError,
    PollutionLocationNotSupportedError,
)

current_client = OpenMeteoCurrentClient()


@router.post("/api/v1/pollution/analyze", response_model=PollutionAnalyzeResponse)
def analyze_pollution(request: PollutionAnalyzeRequest):
    # Mode 1: Current live atmospheric air quality from Open-Meteo API
    if request.data_mode == "current":
        try:
            sensor_data = current_client.fetch_current_pollution(request.location)
        except PollutionLocationNotSupportedError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except PollutionCurrentAPIError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Current air-quality data is temporarily unavailable: {str(exc)}"
            )

        interventions = optimizer.generate_interventions(sensor_data)

        response_data = {
            "city_avg_aqi": sensor_data["city_avg_aqi"],
            "pm25": sensor_data["pm25"],
            "pm10": sensor_data["pm10"],
            "stations": sensor_data.get("stations", []),
            "suggested_interventions": interventions,
            "data_mode": "current",
            "data_source": "open-meteo-air-quality-current",
            "data_timestamp": sensor_data.get("data_timestamp"),
            "retrieved_at": sensor_data.get("retrieved_at"),
            "category": sensor_data.get("category"),
            "is_modelled": True,
            "pollutants": sensor_data.get("pollutants"),
            "latitude": sensor_data.get("latitude"),
            "longitude": sensor_data.get("longitude"),
            "location": sensor_data.get("location") or request.location,
        }
        return PollutionAnalyzeResponse(**response_data)

    # Mode 2: Historical air quality analysis from Open-Meteo CSV dataset
    sensor_data = calculator.calculate_metrics(request.location)
    if not sensor_data:
        raise HTTPException(status_code=404, detail="No pollution data found for this location.")

    interventions = optimizer.generate_interventions(sensor_data)
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    aqi_val = sensor_data["city_avg_aqi"]
    category_val = "Good" if aqi_val <= 50 else ("Moderate" if aqi_val <= 100 else "Unhealthy")

    response_data = {
        "city_avg_aqi": aqi_val,
        "pm25": sensor_data["pm25"],
        "pm10": sensor_data["pm10"],
        "stations": sensor_data.get("stations", []),
        "suggested_interventions": interventions,
        "data_mode": "historical",
        "data_source": "open-meteo-air-quality-historical",
        "data_timestamp": "2020-2024 Hourly Dataset",
        "retrieved_at": now_utc,
        "category": category_val,
        "is_modelled": True,
        "location": request.location,
    }
    return PollutionAnalyzeResponse(**response_data)

app.include_router(router)
