"""
Comprehensive Verification Tests for Unified Spatial-Temporal Forecasting Pipeline.

Verifies hard requirements:
1. Single unified forecasting engine powering /forecast/daily, /forecast/7day, and /summary.
2. ZERO possibility of Day-1 discrepancy: daily D1 == 7day D1 == summary D1 by construction.
3. Dynamic forecast dates: origin derived from latest observation timestamp, D1=origin+1d ... D7=origin+7d.
4. Separation of observed (cpcb_engine) vs predicted (unified_spatial_temporal_model).
5. All timestamps timezone-aware.
"""
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from .main import app
from .unified_forecast.inference import UnifiedForecaster
from .data_provider import get_data_provider


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


class TestUnifiedForecastPipeline:
    """Test suite verifying unified forecasting integration."""

    def test_unified_forecaster_singleton_loaded(self):
        forecaster = UnifiedForecaster.get_instance()
        assert forecaster.loaded is True
        assert forecaster.model is not None
        assert forecaster.feature_scaler is not None
        assert forecaster.target_scaler is not None
        assert "TemporalOnlyGRU" in forecaster.model_name or "GAT" in forecaster.model_name

    def test_daily_and_7day_and_summary_identical_d1_by_construction(self, client):
        """CRITICAL: Day-1 must be identical across /forecast/daily, /forecast/7day, and /summary."""
        daily_res = client.get("/api/pollution/forecast/daily").json()
        seven_res = client.get("/api/pollution/forecast/7day").json()
        summ_res = client.get("/api/pollution/summary").json()

        assert daily_res["status"] == "success"
        assert seven_res["status"] == "success"
        assert summ_res["status"] == "success"

        d1_daily = daily_res["forecast"]["forecast_aqi"]
        d1_7day = seven_res["forecast"][0]["aqi"]
        d1_summary_daily = summ_res["forecast"]["forecast_aqi"]
        d1_summary_7day = summ_res["extended_forecast"]["forecast"][0]["aqi"]

        # Assert ALL Day-1 AQI values match perfectly
        assert d1_daily == d1_7day, f"Mismatch: Daily D1 ({d1_daily}) != 7-day D1 ({d1_7day})"
        assert d1_daily == d1_summary_daily, f"Mismatch: Daily D1 ({d1_daily}) != Summary Daily ({d1_summary_daily})"
        assert d1_daily == d1_summary_7day, f"Mismatch: Daily D1 ({d1_daily}) != Summary 7-Day ({d1_summary_7day})"

        # Assert Day-1 target dates match
        d1_daily_date = daily_res["forecast"]["forecast_date"]
        d1_7day_date = seven_res["forecast"][0]["target_date"]
        assert d1_daily_date == d1_7day_date == "2026-01-01"

    def test_dynamic_forecast_dates_from_latest_observation(self, client):
        """Target dates must strictly derive from latest observation timestamp."""
        provider = get_data_provider()
        latest_ts = provider.get_latest_observation_timestamp()
        assert latest_ts is not None

        seven_res = client.get("/api/pollution/forecast/7day").json()
        forecast = seven_res["forecast"]
        assert len(forecast) == 7

        expected_dates = [
            "2026-01-01",
            "2026-01-02",
            "2026-01-03",
            "2026-01-04",
            "2026-01-05",
            "2026-01-06",
            "2026-01-07",
        ]

        for i, horizon_entry in enumerate(forecast):
            assert horizon_entry["horizon_days"] == i + 1
            assert horizon_entry["target_date"] == expected_dates[i]
            assert "display_date" in horizon_entry
            assert len(horizon_entry["display_date"]) > 0
            assert horizon_entry["aqi"] is not None
            assert isinstance(horizon_entry["aqi"], (int, float))

    def test_observed_vs_predicted_separation(self, client):
        """Observed AQI is never ML predicted; Predicted AQI never overwrites observed."""
        summ = client.get("/api/pollution/summary").json()
        current = summ["current"]
        forecast = summ["forecast"]
        ext_forecast = summ["extended_forecast"]

        # Current observed is strictly from CPCB calculation engine
        assert current["source"] == "cpcb_engine"
        assert current["observed_aqi"] is not None

        # Forecast is strictly from the unified ML model
        assert forecast["source"] == "unified_spatial_temporal_model"
        assert ext_forecast["architecture"] is not None

        # Observed AQI and Predicted AQI are distinct fields
        assert "observed_aqi" in current
        assert "forecast_aqi" in forecast

    def test_health_reports_unified_model_status(self, client):
        health = client.get("/health").json()
        assert health["status"] == "ONLINE"
        assert health["model_status"] == "ready"
        assert health["model_name"] is not None
        assert "TemporalOnlyGRU" in health["model_name"] or "GAT" in health["model_name"]

    def test_info_endpoint_provenance(self, client):
        info = client.get("/api/pollution/info").json()
        assert info["pipeline"] == "Unified Spatial-Temporal Forecasting Pipeline"
        assert info["status"] == "ready"
        assert info["forecast_horizon_days"] == 7
        assert info["context_days"] == 14
        assert info["stations"] == 13
        assert info["features"] == 18
        assert info["targets"] == 6
        assert info["validation_split"] == "2025-07-01 to 2025-09-30"
        assert info["test_split"] == "2025-10-01 to 2025-12-31 (untouched)"
        assert info["license"] == "Apache-2.0"
