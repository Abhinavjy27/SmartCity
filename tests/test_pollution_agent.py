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
