"""
Comprehensive tests for Open-Meteo Current Air Quality Integration.
Verifies all 10 requirements of Step 8:
1. Current Open-Meteo response parsing using mocked HTTP response.
2. Current AQI request returns data_mode = "current".
3. Historical request still uses the existing CSV.
4. Current request does NOT read the historical CSV.
5. Current API failure does NOT silently fall back to historical data.
6. Pollution-only query dispatches only to Pollution Agent.
7. Traffic evidence does not appear in a pollution-only response.
8. Current AQI values are taken from API response, not hardcoded.
9. Response contains source and timestamp metadata.
10. Existing pollution behavior and backward compatibility continue to pass.
"""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.agents.pollution_agent.current_client import (
    OpenMeteoCurrentClient,
    PollutionCurrentAPIError,
    PollutionLocationNotSupportedError,
)
from backend.agents.pollution_agent.main import app as pollution_app
from backend.supervisor.main import app as supervisor_app

pollution_client = TestClient(pollution_app)
supervisor_client = TestClient(supervisor_app)

@pytest.fixture(autouse=True)
def ensure_mock_llm(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")

SAMPLE_OPEN_METEO_RESPONSE = {
    "latitude": 17.385,
    "longitude": 78.4867,
    "generationtime_ms": 0.12,
    "utc_offset_seconds": 19800,
    "timezone": "Asia/Kolkata",
    "timezone_abbreviation": "IST",
    "current": {
        "time": "2026-09-20T18:00",
        "interval": 3600,
        "us_aqi": 73,
        "pm2_5": 22.4,
        "pm10": 34.6,
        "carbon_monoxide": 312.0,
        "nitrogen_dioxide": 16.5,
        "sulphur_dioxide": 5.2,
        "ozone": 41.8,
    },
}


def test_1_current_open_meteo_response_parsing_mocked():
    """1. Test current Open-Meteo response parsing using a mocked HTTP response."""
    client = OpenMeteoCurrentClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_OPEN_METEO_RESPONSE

    with patch("requests.get", return_value=mock_resp):
        res = client.fetch_current_pollution("Narayanguda, Hyderabad")

    assert res["data_mode"] == "current"
    assert res["data_source"] == "open-meteo-air-quality-current"
    assert res["city_avg_aqi"] == 73
    assert res["pm25"] == 22.4
    assert res["pm10"] == 34.6
    assert res["category"] == "Moderate"
    assert res["data_timestamp"] == "2026-09-20T18:00"
    assert res["is_modelled"] is True
    assert res["pollutants"]["carbon_monoxide"] == 312.0
    assert res["pollutants"]["nitrogen_dioxide"] == 16.5
    assert res["pollutants"]["sulphur_dioxide"] == 5.2
    assert res["pollutants"]["ozone"] == 41.8


def test_2_current_aqi_request_returns_data_mode_current():
    """2. Current AQI request returns data_mode = 'current'."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_OPEN_METEO_RESPONSE

    with patch("requests.get", return_value=mock_resp):
        resp = pollution_client.post(
            "/api/v1/pollution/analyze",
            json={
                "objective": "What is the current AQI?",
                "location": "Narayanguda, Hyderabad",
                "data_mode": "current",
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["data_mode"] == "current"
    assert data["data_source"] == "open-meteo-air-quality-current"
    assert data["city_avg_aqi"] == 73
    assert data["pm25"] == 22.4
    assert data["pm10"] == 34.6


def test_3_historical_request_still_uses_existing_csv():
    """3. Historical request still uses the existing CSV."""
    resp = pollution_client.post(
        "/api/v1/pollution/analyze",
        json={
            "objective": "Analyze historical AQI trends",
            "location": "Narayanguda, Hyderabad",
            "data_mode": "historical",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["data_mode"] == "historical"
    assert data["data_source"] == "open-meteo-air-quality-historical"
    assert data["city_avg_aqi"] > 0
    assert data["pm25"] > 0


def test_4_current_request_does_not_read_historical_csv():
    """4. Current request does NOT read the historical CSV."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_OPEN_METEO_RESPONSE

    with patch("requests.get", return_value=mock_resp):
        with patch("backend.agents.pollution_agent.main.calculator.calculate_metrics") as mock_calc:
            resp = pollution_client.post(
                "/api/v1/pollution/analyze",
                json={
                    "objective": "What is the current AQI?",
                    "location": "Narayanguda, Hyderabad",
                    "data_mode": "current",
                },
            )
            assert resp.status_code == 200
            # calculator.calculate_metrics must NOT be called for current requests
            mock_calc.assert_not_called()


def test_5_current_api_failure_does_not_silently_fallback():
    """5. Current API failure does NOT silently fall back to historical data."""
    with patch("requests.get", side_effect=Exception("Connection refused to Open-Meteo")):
        with patch("backend.agents.pollution_agent.main.calculator.calculate_metrics") as mock_calc:
            resp = pollution_client.post(
                "/api/v1/pollution/analyze",
                json={
                    "objective": "What is the current AQI?",
                    "location": "Narayanguda, Hyderabad",
                    "data_mode": "current",
                },
            )
            assert resp.status_code == 503
            assert "Current air-quality data is temporarily unavailable" in resp.json()["detail"]
            # Must never fall back to CSV
            mock_calc.assert_not_called()


def test_6_pollution_only_query_dispatches_only_to_pollution_agent():
    """6. Pollution-only query dispatches only to Pollution Agent."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_OPEN_METEO_RESPONSE

    with patch("requests.get", return_value=mock_resp):
        resp = supervisor_client.post(
            "/agents/planner/execute",
            json={
                "query": "What is the current AQI?",
                "objective": "What is the current AQI?",
                "location": "Narayanguda, Hyderabad",
                "conversation_history": [],
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["dispatched_agents"] == ["pollution_agent"]
    assert "traffic_agent" not in data["dispatched_agents"]
    assert "simulation_agent" not in data["dispatched_agents"]


def test_7_traffic_evidence_does_not_appear_in_pollution_only_response():
    """7. Traffic evidence does not appear in a pollution-only response."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_OPEN_METEO_RESPONSE

    with patch("requests.get", return_value=mock_resp):
        resp = supervisor_client.post(
            "/agents/planner/execute",
            json={
                "query": "What is the current AQI?",
                "objective": "What is the current AQI?",
                "location": "Narayanguda, Hyderabad",
                "conversation_history": [],
            },
        )
    data = resp.json()
    assert "traffic" not in data.get("agent_results", {})
    summary = data.get("final_response", {}).get("summary", "")
    assert "bottleneck" not in summary.lower()
    assert "speed" not in summary.lower()
    assert "congestion" not in summary.lower()
    assert "AQI" in summary


def test_8_current_aqi_values_taken_from_api_response_not_hardcoded():
    """8. Current AQI values are taken from the API response, not hardcoded."""
    # Scenario A: AQI 52, PM2.5 13.1, PM10 24.2
    resp_a = {
        "current": {
            "time": "2026-09-20T19:00",
            "us_aqi": 52,
            "pm2_5": 13.1,
            "pm10": 24.2,
        }
    }
    mock_a = MagicMock()
    mock_a.status_code = 200
    mock_a.json.return_value = resp_a

    with patch("requests.get", return_value=mock_a):
        res_a = pollution_client.post(
            "/api/v1/pollution/analyze",
            json={"objective": "What is the current AQI?", "location": "Hyderabad", "data_mode": "current"},
        ).json()

    # Scenario B: AQI 165, PM2.5 82.7, PM10 119.4
    resp_b = {
        "current": {
            "time": "2026-09-20T20:00",
            "us_aqi": 165,
            "pm2_5": 82.7,
            "pm10": 119.4,
        }
    }
    mock_b = MagicMock()
    mock_b.status_code = 200
    mock_b.json.return_value = resp_b

    with patch("requests.get", return_value=mock_b):
        res_b = pollution_client.post(
            "/api/v1/pollution/analyze",
            json={"objective": "What is the current AQI?", "location": "Hyderabad", "data_mode": "current"},
        ).json()

    assert res_a["city_avg_aqi"] == 52
    assert res_a["pm25"] == 13.1
    assert res_b["city_avg_aqi"] == 165
    assert res_b["pm25"] == 82.7
    assert res_a["city_avg_aqi"] != res_b["city_avg_aqi"]


def test_9_response_contains_source_and_timestamp_metadata():
    """9. Response contains source and timestamp metadata."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_OPEN_METEO_RESPONSE

    with patch("requests.get", return_value=mock_resp):
        res = pollution_client.post(
            "/api/v1/pollution/analyze",
            json={"objective": "What is the current AQI?", "location": "Hyderabad", "data_mode": "current"},
        ).json()

    assert res["data_source"] == "open-meteo-air-quality-current"
    assert res["data_mode"] == "current"
    assert res["data_timestamp"] == "2026-09-20T18:00"
    assert "retrieved_at" in res
    assert res["is_modelled"] is True


def test_10_existing_historical_tests_continue_to_pass():
    """10. Existing pollution behavior and backward compatibility continue to pass."""
    # When data_mode is omitted, defaults to historical CSV behavior
    res = pollution_client.post(
        "/api/v1/pollution/analyze",
        json={"objective": "Analyze pollution in Narayanguda", "location": "Narayanguda, Hyderabad"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["data_mode"] == "historical"
    assert data["city_avg_aqi"] > 0
    assert data["pm25"] > 0
    assert len(data["suggested_interventions"]) > 0
