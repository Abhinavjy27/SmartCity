"""
Focused unit & integration tests for the Next-Day Air Quality Forecast fix.
Validates:
1. Successful next-day baseline forecasting when unified model checkpoint is absent.
2. Clear labeling as a baseline forecast (not the unavailable unified model).
3. Neatly populated forecast AQI and criteria pollutant values (PM2.5, PM10, NO2, SO2, CO, O3).
4. Dynamic forecast date computation from observation timestamp.
5. Synchronization between /forecast/daily and /summary forecast fields.
6. Scope restriction preservation: 7-day extended forecast remains unchanged.
7. Clean unavailable state when historical context is insufficient (no fabricated data).
"""
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
import pandas as pd

from backend.agents.pollution_agent.main import app
from backend.agents.pollution_agent.unified_forecast.inference import UnifiedForecaster
from backend.agents.pollution_agent.data_provider import BasePollutionDataProvider, set_data_provider


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_next_day_forecast_returns_success_and_baseline_label(client):
    """Test that /api/pollution/forecast/daily returns success and is clearly labeled as baseline."""
    res = client.get("/api/pollution/forecast/daily")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    
    forecast = data["forecast"]
    assert forecast["forecast_status"] == "success"
    assert isinstance(forecast["forecast_aqi"], (int, float))
    assert forecast["forecast_aqi"] > 0
    
    # Must be clearly labeled as a baseline model, NOT the unavailable unified neural model
    assert forecast["is_baseline"] is True
    assert "Baseline" in forecast["model_name"]
    assert forecast["source"] == "historical_baseline_forecast"
    assert "Baseline" in forecast["confidence"]


def test_next_day_forecast_contains_predicted_criteria_pollutants(client):
    """Test that next-day forecast neatly includes all available criteria pollutant values."""
    res = client.get("/api/pollution/forecast/daily")
    data = res.json()
    forecast = data["forecast"]
    
    concs = forecast.get("predicted_concentrations")
    assert concs is not None
    assert isinstance(concs, dict)
    
    # Criteria pollutants required for CPCB NAQI calculation
    for p in ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"]:
        assert p in concs
        assert isinstance(concs[p], (int, float))
        assert concs[p] >= 0.0


def test_next_day_forecast_dynamically_sets_dates(client):
    """Test that forecast dates and display strings are properly generated for tomorrow."""
    from backend.agents.pollution_agent.date_utils import get_next_day_forecast_dates
    expected = get_next_day_forecast_dates()

    res = client.get("/api/pollution/forecast/daily")
    forecast = res.json()["forecast"]

    assert forecast["forecast_date"] == expected["target_date"]
    assert forecast["display_date"] == expected["display_date"]
    assert "target_timestamp" in forecast
    assert "origin_timestamp" in forecast


def test_forecast_target_date_must_be_tomorrow(client):
    """
    Regression test: Fails if forecast target date is not tomorrow relative to current date (IST).
    Prevents incorrectly using the last historical observation (e.g. Jan 2, 2024) as forecast target.
    """
    from datetime import datetime, timezone, timedelta
    from backend.agents.pollution_agent.date_utils import IST_OFFSET

    now_ist = datetime.now(timezone.utc).astimezone(IST_OFFSET)
    today_ist = now_ist.date()
    tomorrow_ist = today_ist + timedelta(days=1)
    expected_target_date = tomorrow_ist.isoformat()
    expected_display_date = f"{tomorrow_ist.strftime('%a')}, {tomorrow_ist.strftime('%b')} {tomorrow_ist.day}"

    res = client.get("/api/pollution/forecast/daily")
    data = res.json()
    forecast = data["forecast"]

    # Must match tomorrow's calendar date, not a historical date from years ago
    assert forecast["forecast_date"] == expected_target_date, (
        f"Forecast target date {forecast['forecast_date']} is not tomorrow ({expected_target_date})"
    )
    assert forecast["display_date"] == expected_display_date, (
        f"Forecast display date {forecast['display_date']} does not match expected ({expected_display_date})"
    )


def test_next_day_forecast_date_boundaries():
    """
    Regression test verifying year and month boundary cases for get_next_day_forecast_dates:
    - Year-end boundary (Dec 31 -> Jan 1)
    - Month-end 31-day boundary (Jan 31 -> Feb 1)
    - Month-end February non-leap boundary (Feb 28 -> Mar 1)
    - Month-end February leap-year boundary (Feb 28 -> Feb 29, Feb 29 -> Mar 1)
    """
    from backend.agents.pollution_agent.date_utils import get_next_day_forecast_dates

    # Year boundary: 2026-12-31 -> 2027-01-01
    y_res = get_next_day_forecast_dates("2026-12-31T18:00:00+05:30")
    assert y_res["target_date"] == "2027-01-01"
    assert y_res["display_date"] == "Fri, Jan 1"
    assert y_res["day_name"] == "Friday"

    # Month boundary (31 days): 2026-01-31 -> 2026-02-01
    m31_res = get_next_day_forecast_dates("2026-01-31T12:00:00+05:30")
    assert m31_res["target_date"] == "2026-02-01"
    assert m31_res["display_date"] == "Sun, Feb 1"

    # Month boundary (30 days): 2026-04-30 -> 2026-05-01
    m30_res = get_next_day_forecast_dates("2026-04-30T12:00:00+05:30")
    assert m30_res["target_date"] == "2026-05-01"
    assert m30_res["display_date"] == "Fri, May 1"

    # February non-leap: 2026-02-28 -> 2026-03-01
    feb_non_leap = get_next_day_forecast_dates("2026-02-28T12:00:00+05:30")
    assert feb_non_leap["target_date"] == "2026-03-01"
    assert feb_non_leap["display_date"] == "Sun, Mar 1"

    # February leap year: 2024-02-28 -> 2024-02-29 and 2024-02-29 -> 2024-03-01
    feb_leap_1 = get_next_day_forecast_dates("2024-02-28T12:00:00+05:30")
    assert feb_leap_1["target_date"] == "2024-02-29"
    assert feb_leap_1["display_date"] == "Thu, Feb 29"

    feb_leap_2 = get_next_day_forecast_dates("2024-02-29T12:00:00+05:30")
    assert feb_leap_2["target_date"] == "2024-03-01"
    assert feb_leap_2["display_date"] == "Fri, Mar 1"


def test_summary_and_daily_forecast_are_synchronized(client):
    """Test that /api/pollution/summary and /api/pollution/forecast/daily share the same next-day forecast."""
    daily_res = client.get("/api/pollution/forecast/daily").json()
    summary_res = client.get("/api/pollution/summary").json()
    
    assert daily_res["status"] == "success"
    assert summary_res["status"] == "success"
    
    daily_f = daily_res["forecast"]
    summary_f = summary_res["forecast"]
    
    assert daily_f["forecast_aqi"] == summary_f["forecast_aqi"]
    assert daily_f["forecast_date"] == summary_f["forecast_date"]
    assert daily_f["model_name"] == summary_f["model_name"]
    assert daily_f["predicted_concentrations"] == summary_f["predicted_concentrations"]


def test_extended_forecast_remains_unchanged(client):
    """Confirm scope restriction: 7-day extended forecast remains untouched/unavailable."""
    res = client.get("/api/pollution/forecast/7day")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "unavailable"
    assert len(data.get("forecast", [])) == 0


def test_forecast_clean_unavailable_state_when_context_insufficient():
    """Verify clean unavailable state when historical observations are insufficient (never fabricate data)."""
    class InsufficientDataProvider(BasePollutionDataProvider):
        @property
        def data_mode(self): return "historical"
        @property
        def is_live(self): return False
        @property
        def provider_name(self): return "Insufficient Test Provider"
        def get_station_names(self): return ["Test Station"]
        def get_latest_readings(self): return []
        def get_observations(self, **kwargs): return pd.DataFrame()
        def get_latest_observation_timestamp(self): return "2024-01-01T23:00:00+00:00"
        def get_daily_aggregates(self, n_days=30): return pd.DataFrame()
        def get_city_daily_aggregates(self, n_days=30, min_completeness_ratio=0.5):
            # Only 2 days of data (< 7 minimum required)
            return pd.DataFrame([
                {"date": "2024-01-01", "PM2.5": 50.0, "PM10": 80.0, "NO2": 10.0, "SO2": 10.0, "CO": 0.5, "O3": 50.0},
                {"date": "2024-01-02", "PM2.5": 52.0, "PM10": 82.0, "NO2": 11.0, "SO2": 10.5, "CO": 0.5, "O3": 52.0},
            ])
        def get_historical_trend(self, range_key="24h"): return []

    provider = InsufficientDataProvider()
    set_data_provider(provider)
    try:
        forecaster = UnifiedForecaster()
        forecaster.clear_cache()
        res = forecaster.predict()
        assert res["daily"]["forecast_status"] == "unavailable"
        assert res["daily"]["forecast_aqi"] is None
        assert "Insufficient historical context" in res["daily"]["reason"]
    finally:
        set_data_provider(None)


def test_forecast_clean_unavailable_state_when_criteria_pollutants_missing():
    """Verify clean unavailable state when criteria pollutants have gaps/missing values."""
    class MissingPollutantProvider(BasePollutionDataProvider):
        @property
        def data_mode(self): return "historical"
        @property
        def is_live(self): return False
        @property
        def provider_name(self): return "Missing Pollutant Test Provider"
        def get_station_names(self): return ["Test Station"]
        def get_latest_readings(self): return []
        def get_observations(self, **kwargs): return pd.DataFrame()
        def get_latest_observation_timestamp(self): return "2024-01-08T23:00:00+00:00"
        def get_daily_aggregates(self, n_days=30): return pd.DataFrame()
        def get_city_daily_aggregates(self, n_days=30, min_completeness_ratio=0.5):
            rows = []
            for i in range(8):
                rows.append({
                    "date": f"2024-01-0{i+1}",
                    "PM2.5": None if i == 2 else 50.0 + i,
                    "PM10": 80.0 + i,
                    "NO2": 10.0 + i,
                    "SO2": 10.0,
                    "CO": 0.5,
                    "O3": 50.0,
                })
            return pd.DataFrame(rows)
        def get_historical_trend(self, range_key="24h"): return []

    provider = MissingPollutantProvider()
    set_data_provider(provider)
    try:
        forecaster = UnifiedForecaster()
        forecaster.clear_cache()
        res = forecaster.predict()
        assert res["daily"]["forecast_status"] == "unavailable"
        assert res["daily"]["forecast_aqi"] is None
        assert "PM2.5" in res["daily"]["reason"]
    finally:
        set_data_provider(None)

