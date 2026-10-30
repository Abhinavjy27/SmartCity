"""
Unit and Integration Tests for WeatherAPI Air Quality Forecasting Pipeline.

Verifies:
1. Aggregation min-hours rules (>=16 for 24h mean, >=6 for 8h rolling mean).
2. CO conversion from µg/m³ to mg/m³ (divide by 1000) and CPCB breakpoint validation.
3. Missing pollutant handling (missing NH3 without imputing, CPCB sufficiency rules).
4. Unavailable path on HTTP 500 error, network exception, or missing key with NO fallback to archive model.
5. Exact identity: /forecast/daily Day-1 == /forecast/7day Day-1 == /summary Day-1.
6. Number of days returned matches actual available days (never padded).
7. Non-padded real numbers in pollutants (PM2.5, PM10) replacing placeholder dashes.
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock
import urllib.error
from fastapi.testclient import TestClient

from .main import app
from .weatherapi_forecast_provider import (
    aggregate_forecast_day,
    WeatherAPIForecastProvider,
    get_weatherapi_forecast_provider,
)
from .aqi_engine import calculate_aqi, calculate_sub_index


@pytest.fixture
def client():
    return TestClient(app)


def _generate_synthetic_hours(
    num_hours: int = 24,
    pm25_val: float = 45.0,
    pm10_val: float = 90.0,
    no2_val: float = 30.0,
    so2_val: float = 15.0,
    co_val: float = 1200.0,  # µg/m³
    o3_val: float = 50.0,
    drop_hours_pm25: int = 0,
    drop_hours_co: int = 0,
):
    """Generate 24 hours of synthetic air quality readings."""
    hours = []
    for h in range(num_hours):
        aq = {
            "pm2_5": pm25_val if h >= drop_hours_pm25 else None,
            "pm10": pm10_val,
            "no2": no2_val,
            "so2": so2_val,
            "co": co_val if h >= drop_hours_co else None,
            "o3": o3_val,
        }
        hours.append({
            "time": f"2026-10-15 {h:02d}:00",
            "time_epoch": 1792000000 + h * 3600,
            "air_quality": aq,
        })
    return hours


class TestWeatherAPIForecastProviderUnit:
    """Unit tests for aggregation, conversion, and sufficiency logic."""

    def test_aggregation_min_hours_rules_pm25(self):
        """PM2.5, PM10, NO2, SO2 require >= 16 valid hours."""
        # 16 valid hours (8 dropped out of 24) -> should be valid
        hours_16 = _generate_synthetic_hours(drop_hours_pm25=8)
        res_16 = aggregate_forecast_day({"date": "2026-10-15", "hour": hours_16})
        assert res_16 is not None
        assert "PM2.5" in res_16["concentrations"]
        assert res_16["concentrations"]["PM2.5"] == 45.0

        # 15 valid hours (9 dropped out of 24) -> PM2.5 dropped
        hours_15 = _generate_synthetic_hours(drop_hours_pm25=9)
        res_15 = aggregate_forecast_day({"date": "2026-10-15", "hour": hours_15})
        assert res_15 is not None
        assert "PM2.5" not in res_15["concentrations"]

    def test_aggregation_min_hours_rules_co_rolling(self):
        """CO requires >= 6 valid hours in at least one 8h rolling window."""
        # Drop first 19 hours of CO -> windows 0..16 have at most 5 valid CO readings
        hours_drop_co = _generate_synthetic_hours(drop_hours_co=19)
        res = aggregate_forecast_day({"date": "2026-10-15", "hour": hours_drop_co})
        assert res is not None
        # CO should be absent because no 8-hour window has >= 6 valid hours
        assert "CO" not in res["concentrations"]

        # Drop first 18 hours of CO -> window 16 (hours 16..23) has hours 18..23 valid (6 hours)
        hours_valid_co = _generate_synthetic_hours(drop_hours_co=18)
        res_valid = aggregate_forecast_day({"date": "2026-10-15", "hour": hours_valid_co})
        assert res_valid is not None
        assert "CO" in res_valid["concentrations"]
        assert res_valid["concentrations"]["CO"] == 1.2  # 1200 µg/m³ / 1000 = 1.2 mg/m³

    def test_co_conversion_to_mg_and_breakpoints(self):
        """CO must be converted from µg/m³ to mg/m³ (divide by 1000) and match CPCB breakpoints."""
        hours = _generate_synthetic_hours(co_val=1500.0)
        res = aggregate_forecast_day({"date": "2026-10-15", "hour": hours})
        assert res is not None
        assert res["concentrations"]["CO"] == 1.5  # 1500 / 1000 = 1.5 mg/m³

        # Verify CPCB breakpoint: 1.5 mg/m³ is in [1.0, 2.0] -> sub-index in [50, 100]
        sub_index = calculate_sub_index("CO", 1.5)
        assert sub_index is not None
        assert 50 <= sub_index <= 100
        # 1.5 is midpoint of 1.0..2.0, so sub-index should be 75
        assert sub_index == 75

    def test_missing_pollutant_handling_no_nh3(self):
        """WeatherAPI does not provide NH3; system computes CPCB AQI without imputing."""
        hours = _generate_synthetic_hours()
        res = aggregate_forecast_day({"date": "2026-10-15", "hour": hours})
        assert res is not None
        assert "NH3" not in res["concentrations"]
        # Valid CPCB AQI is still computed from remaining 5 pollutants
        assert res["aqi"] is not None
        assert res["category"] in ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]
        assert res["dominant_pollutant"] is not None

    def test_cpcb_sufficiency_rejection(self):
        """A day without particulate or with < 3 pollutants is returned as None (unavailable)."""
        # Strip all PM from hours
        hours = _generate_synthetic_hours()
        for h in hours:
            h["air_quality"]["pm2_5"] = None
            h["air_quality"]["pm10"] = None

        res = aggregate_forecast_day({"date": "2026-10-15", "hour": hours})
        # Fails particulate sufficiency -> must be None, never filled or interpolated
        assert res is None


class TestWeatherAPIForecastProviderNetworkAndFallback:
    """Tests for HTTP errors, missing key, and zero-fallback guarantees."""

    def test_unavailable_on_http_500_mock_no_fallback(self):
        """When WeatherAPI returns HTTP 500, provider returns status=unavailable with NO fallback to archive model."""
        provider = WeatherAPIForecastProvider(api_key="test_key")
        provider.clear_cache()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 500
            mock_urlopen.side_effect = urllib.error.HTTPError(
                url="http://test", code=500, msg="Internal Server Error", hdrs={}, fp=None
            )

            res = provider.get_forecast(force_refresh=True)

            assert res["status"] == "unavailable"
            assert res["daily"]["forecast_status"] == "unavailable"
            assert res["daily"]["forecast_aqi"] is None
            assert res["extended"]["status"] == "unavailable"
            assert res["extended"]["forecast"] == []
            # Assert NO fallback to archive model architecture or wording
            assert "TemporalGRU_KNNCovariate" not in str(res)
            assert "TSPCB" not in str(res)

    def test_unavailable_on_missing_api_key(self):
        """When WeatherAPI endpoint is configured without an API key, provider returns status=unavailable with zero fallback."""
        provider = WeatherAPIForecastProvider(api_key="", forecast_url="https://api.weatherapi.com/v1/forecast.json")
        provider.clear_cache()

        res = provider.get_forecast(force_refresh=True)
        assert res["status"] == "unavailable"
        assert res["daily"]["forecast_aqi"] is None
        assert "TemporalGRU_KNNCovariate" not in str(res)

    def test_cache_fallback_under_6_hours_only(self):
        """When provider fails, cached response is served only if age <= 6 hours."""
        provider = WeatherAPIForecastProvider(api_key="test_key")
        provider.clear_cache()

        good_payload = {
            "status": "success",
            "daily": {"forecast_aqi": 85, "forecast_status": "success"},
            "extended": {"status": "success", "forecast": [{"day": 1, "aqi": 85}]},
        }

        # Case A: cache is 2 hours old -> can be served
        provider._last_good_cache = (import_time := 1000.0, good_payload)
        with patch("time.time", return_value=1000.0 + 7200.0):  # 2 hours later
            with patch("urllib.request.urlopen", side_effect=Exception("Network down")):
                res = provider.get_forecast(force_refresh=True)
                assert res["status"] == "success"
                assert res["daily"]["forecast_aqi"] == 85

        # Case B: cache is 7 hours old (> 6h threshold) -> rejected, returns unavailable
        with patch("time.time", return_value=1000.0 + 25200.0):  # 7 hours later
            with patch("urllib.request.urlopen", side_effect=Exception("Network down")):
                res = provider.get_forecast(force_refresh=True)
                assert res["status"] == "unavailable"
                assert res["daily"]["forecast_aqi"] is None


class TestForecastEndpointsIntegration:
    """Integration tests verifying endpoint shapes, Day-1 identity, and non-padded counts."""

    def test_mocked_3day_forecast_identity_and_schema(self, client):
        """
        Verify that Day-1 in /forecast/daily == Day-1 in /forecast/7day == Day-1 in /summary.
        Verify that returning 3 days does NOT pad to 7 days.
        Verify that PM2.5 and PM10 in card pollutants are real numbers.
        """
        provider = get_weatherapi_forecast_provider()
        provider.clear_cache()

        # Build 3 synthetic forecast days
        d1_hours = _generate_synthetic_hours(pm25_val=42.0, pm10_val=88.0, co_val=1100.0)
        d2_hours = _generate_synthetic_hours(pm25_val=55.0, pm10_val=105.0, co_val=1300.0)
        d3_hours = _generate_synthetic_hours(pm25_val=35.0, pm10_val=70.0, co_val=900.0)

        synthetic_api_response = {
            "forecast": {
                "forecastday": [
                    {"date": "2026-10-12", "hour": d1_hours},
                    {"date": "2026-10-13", "hour": d2_hours},
                    {"date": "2026-10-14", "hour": d3_hours},
                ]
            }
        }

        with patch.object(provider, "get_forecast") as mock_get_forecast:
            # Let process_forecast_json compute real CPCB values from synthetic response
            real_computed = provider.process_forecast_json(synthetic_api_response)
            mock_get_forecast.return_value = real_computed

            daily_res = client.get("/api/pollution/forecast/daily").json()
            seven_res = client.get("/api/pollution/forecast/7day").json()
            summ_res = client.get("/api/pollution/summary").json()

            # 1. Assert status
            assert daily_res["status"] == "success"
            assert seven_res["status"] == "success"
            assert summ_res["status"] == "success"

            # 2. Assert Day-1 identity across /forecast/daily, /forecast/7day, and /summary
            d1_daily_aqi = daily_res["forecast"]["forecast_aqi"]
            d1_7day_aqi = seven_res["forecast"][0]["aqi"]
            d1_summ_daily_aqi = summ_res["forecast"]["forecast_aqi"]
            d1_summ_7day_aqi = summ_res["extended_forecast"]["forecast"][0]["aqi"]

            assert d1_daily_aqi == d1_7day_aqi
            assert d1_daily_aqi == d1_summ_daily_aqi
            assert d1_daily_aqi == d1_summ_7day_aqi

            # Target date match
            assert daily_res["forecast"]["forecast_date"] == "2026-10-12"
            assert seven_res["forecast"][0]["target_date"] == "2026-10-12"

            # 3. Assert number of entries: exactly 3 days, never padded to 7
            assert len(seven_res["forecast"]) == 3
            assert len(summ_res["extended_forecast"]["forecast"]) == 3

            # 4. Assert pollutants are real numbers (not '--')
            d1_card = seven_res["forecast"][0]
            assert "pollutants" in d1_card
            assert d1_card["pollutants"]["PM2.5"] == 42.0
            assert d1_card["pollutants"]["PM10"] == 88.0

            # 5. Assert descriptive fields are truthful and free of model wording
            assert daily_res["forecast"]["source"] == "External modeled air-quality forecast"
            assert daily_res["forecast"]["model_name"] == "External Model"
            assert seven_res["architecture"] == "External Model"
            assert "TemporalGRU_KNNCovariate" not in str(seven_res)
            assert "TSPCB" not in str(seven_res)

    def test_forecast_source_env_model_branch_safety(self, client):
        """When FORECAST_SOURCE=model is requested but live days < 14, returns unavailable without archive fallback."""
        with patch.dict(os.environ, {"FORECAST_SOURCE": "model"}):
            with patch("backend.agents.pollution_agent.live_accumulation.LiveAccumulationStore.get_status", return_value={"consecutive_live_days": 1}):
                res_daily = client.get("/api/pollution/forecast/daily").json()
                assert res_daily["status"] == "unavailable"
                assert res_daily["forecast"]["forecast_aqi"] is None
                assert "requires >= 14" in res_daily["forecast"]["reason"]
