"""
Contract test suite for supervisor and specialist routes.
Validates status codes and required response keys.
"""

import pytest
from fastapi.testclient import TestClient
from backend.supervisor.main import app

client = TestClient(app)


def test_supervisor_health_contract():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "service" in data
    assert data["service"] == "supervisor-contract"


def test_pollution_health_contract():
    resp = client.get("/api/pollution/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "agent" in data
    assert "status" in data
    assert "city" in data
    assert data["city"] == "Hyderabad"


def test_pollution_current_contract():
    resp = client.get("/api/pollution/current")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "observed_aqi" in data or "city_avg_aqi" in data or "aqi" in data
    assert "category" in data
    assert "data_mode" in data


def test_pollution_summary_contract():
    resp = client.get("/api/pollution/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "current" in data
    assert "stations" in data
    assert "category" in data["current"]


def test_pollution_live_data_status_contract():
    resp = client.get("/api/pollution/live-data-status")
    assert resp.status_code == 200
    data = resp.json()
    assert "consecutive_live_days" in data
    assert "ready_for_live_forecast" in data
    assert "forecast_input_source" in data


def test_pollution_forecast_7day_contract():
    resp = client.get("/api/pollution/forecast/7day")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "forecast_origin_date" in data or "forecast" in data or "forecast_days" in data
    assert "forecast_input_source" in data


def test_weather_current_contract():
    resp = client.get("/api/v1/weather/current")
    assert resp.status_code == 200
    data = resp.json()
    assert "city" in data
    assert "temperature_c" in data
    assert "humidity_pct" in data
    assert "condition" in data


def test_energy_grid_status_contract():
    resp = client.get("/energy/grid-status")
    assert resp.status_code in (200, 404, 503)
    if resp.status_code == 200:
        data = resp.json()
        assert "status" in data or "grid_load_mw" in data


def test_planning_request_lifecycle_contract():
    payload = {
        "objective": "traffic_flow_maximization",
        "location": "Madhapur",
        "time_horizon": "peak-hour",
        "planner": {
            "planner_id": "test_planner_1",
            "department": "Traffic Management",
            "role": "Traffic Engineer"
        },
        "requested_domains": ["traffic"]
    }
    resp = client.post("/planning/requests", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "request_id" in data
    assert "status" in data
    req_id = data["request_id"]

    get_resp = client.get(f"/planning/requests/{req_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["request_id"] == req_id
    assert get_data["location"] == "Madhapur"


def test_planning_chat_contract_pollution():
    resp = client.post(
        "/api/planning/chat",
        json={"question": "What is the current city AQI?", "domain": "pollution"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data
    assert "insights" in data
    assert "suggestions" in data
    assert len(data["insights"]) > 0
    assert len(data["suggestions"]) == 3


def test_planning_chat_contract_traffic_baseline():
    resp = client.post(
        "/api/planning/chat",
        json={"question": "how to reduce traffic along Begumpet", "domain": "traffic"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data
    assert "insights" in data
    assert "suggestions" in data
    assert "Begumpet" in data["text"]


def test_planning_chat_contract_energy_baseline():
    resp = client.post(
        "/api/planning/chat",
        json={"question": "what is the power load status on the grid", "domain": "energy"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data
    assert "insights" in data
    assert "suggestions" in data
    assert "energy" in data["text"]
