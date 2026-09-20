import pytest
from fastapi.testclient import TestClient
import pandas as pd
from unittest.mock import patch

from backend.agents.pollution_agent.main import app, calculator, optimizer

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"agent": "Pollution Agent", "status": "ONLINE"}

def test_get_aqi_summary():
    response = client.get("/api/v1/pollution/aqi-summary")
    assert response.status_code == 200
    data = response.json()
    assert "city_avg_aqi" in data
    assert "forecast_24h" in data

def test_calculator_file_not_found():
    with patch("pandas.read_csv") as mock_read_csv:
        mock_read_csv.side_effect = FileNotFoundError()
        data = calculator.calculate_metrics("NonExistentCity")
        assert data == {}

def test_calculator_success():
    mock_df = pd.DataFrame({
        "location": ["TestCity", "TestCity", "OtherCity"],
        "aqi": [100, 150, 50],
        "pm25": [50.0, 75.0, 20.0],
        "pm10": [100.0, 150.0, 40.0],
        "station_name": ["Station A", "Station B", "Station C"]
    })
    
    with patch("pandas.read_csv", return_value=mock_df):
        # We explicitly pass hour=4 to force a deterministic 1.3x multiplier
        data = calculator.calculate_metrics("TestCity", hour=4)
        # avg_aqi = 125, * 1.3 = 162.5 -> int -> 162
        assert data["city_avg_aqi"] == 162
        # pm25 = 62.5, * 1.3 = 81.25 -> 81.2
        assert data["pm25"] == 81.2
        # pm10 = 125.0, * 1.3 = 162.5 -> 162.5
        assert data["pm10"] == 162.5
        assert set(data["stations"]) == {"Station A", "Station B"}

def test_analyze_pollution_no_data():
    with patch.object(calculator, "calculate_metrics", return_value={}):
        response = client.post("/api/v1/pollution/analyze", json={
            "objective": "Reduce PM2.5",
            "location": "UnknownCity"
        })
        assert response.status_code == 404
        assert response.json()["detail"] == "No pollution data found for this location."

def test_analyze_pollution_success():
    # Pass moderate pollution thresholds
    mock_sensor_data = {
        "city_avg_aqi": 120,
        "pm25": 45.0,
        "pm10": 90.0,
        "stations": ["Station A"]
    }
    
    with patch.object(calculator, "calculate_metrics", return_value=mock_sensor_data):
        response = client.post("/api/v1/pollution/analyze", json={
            "objective": "Reduce pollution",
            "location": "TestCity"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["city_avg_aqi"] == 120
        # Moderate rule should trigger 2 interventions
        assert len(data["suggested_interventions"]) == 2
        
        actions = [i["action_type"] for i in data["suggested_interventions"]]
        assert "PUBLIC_TRANSIT_BOOST" in actions
        assert "SMART_TRAFFIC_LIGHTS" in actions


def test_open_meteo_path_discovery():
    """Verify that the Open-Meteo CSV path is recognized as canonical path."""
    from backend.agents.pollution_agent.dataset_loader import PollutionCalculator
    calc = PollutionCalculator()
    assert "hyderabad_air_quality_2020_2024.csv" in calc.dataset_path


def test_open_meteo_schema_adaptation_and_location():
    """Verify that Open-Meteo columns (pm2_5, us_aqi) and missing location column are adapted to Hyderabad."""
    mock_open_meteo_df = pd.DataFrame({
        "time": ["2023-01-01T00:00", "2023-01-01T01:00"],
        "us_aqi": [100, 150],
        "pm2_5": [50.0, 75.0],
        "pm10": [100.0, 150.0],
        "carbon_monoxide": [400, 500],
        "nitrogen_dioxide": [30, 45],
        "sulphur_dioxide": [10, 15],
        "ozone": [40, 50]
    })

    with patch("pandas.read_csv", return_value=mock_open_meteo_df):
        # hour=4 applies a deterministic 1.3x multiplier
        data = calculator.calculate_metrics("Hyderabad", hour=4)
        assert data != {}
        # avg us_aqi = 125 * 1.3 = 162.5 -> int 162
        assert data["city_avg_aqi"] == 162
        # avg pm2_5 = 62.5 * 1.3 = 81.25 -> round 81.2
        assert data["pm25"] == 81.2
        # avg pm10 = 125.0 * 1.3 = 162.5 -> round 162.5
        assert data["pm10"] == 162.5
        # stations should be empty (no fabrication)
        assert data["stations"] == []


def test_open_meteo_location_corridor_matching():
    """Verify that a corridor query like 'Narayanguda, Hyderabad' matches the Hyderabad regional dataset."""
    mock_open_meteo_df = pd.DataFrame({
        "time": ["2023-01-01T00:00"],
        "us_aqi": [120],
        "pm2_5": [45.0],
        "pm10": [90.0]
    })
    with patch("pandas.read_csv", return_value=mock_open_meteo_df):
        data = calculator.calculate_metrics("Narayanguda, Hyderabad", hour=4)
        assert data != {}
        assert data["city_avg_aqi"] > 0
        assert data["stations"] == []


def test_open_meteo_unrelated_city_returns_empty():
    """Verify that an unrelated city does not match the Hyderabad regional dataset."""
    mock_open_meteo_df = pd.DataFrame({
        "time": ["2023-01-01T00:00"],
        "us_aqi": [120],
        "pm2_5": [45.0],
        "pm10": [90.0]
    })
    with patch("pandas.read_csv", return_value=mock_open_meteo_df):
        data = calculator.calculate_metrics("Bengaluru", hour=4)
        assert data == {}


def test_analyze_endpoint_with_open_meteo_dataset():
    """Verify that POST /api/v1/pollution/analyze works end-to-end when Open-Meteo data is loaded."""
    mock_open_meteo_df = pd.DataFrame({
        "time": ["2023-01-01T00:00"],
        "us_aqi": [160],
        "pm2_5": [85.0],
        "pm10": [120.0]
    })
    with patch("pandas.read_csv", return_value=mock_open_meteo_df):
        response = client.post("/api/v1/pollution/analyze", json={
            "objective": "Reduce emissions",
            "location": "Narayanguda, Hyderabad"
        })
        assert response.status_code == 200
        res = response.json()
        assert res["city_avg_aqi"] > 0
        assert res["pm25"] > 0
        assert res["pm10"] > 0
        assert res["stations"] == []
        assert len(res["suggested_interventions"]) > 0

