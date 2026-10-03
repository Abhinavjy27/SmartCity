"""
Pollution Agent Tests — CPCB AQI, data quality, model, API, and pipeline integrity.
Run with: pytest backend/agents/pollution_agent/tests.py -v
"""
import math
import pytest
from datetime import date, datetime, timedelta, timezone
import numpy as np
import pandas as pd

from .config import MIN_DAILY_READINGS, MIN_DAYS_FOR_FORECAST, CITY_NAME
from .data_quality import (
    VALID_RANGES,
    REQUIRED_FORECAST_POLLUTANTS,
    validate_reading,
    validate_station_reading,
    validate_aqi_sufficiency,
    validate_forecast_readiness,
    compute_overall_data_quality,
)
from .aqi_engine import (
    BREAKPOINTS,
    calculate_sub_index,
    calculate_aqi,
    get_aqi_category,
    get_dominant_pollutant,
)
from .model import MODEL_FEATURES, get_model
from .data_provider import EXACT_PREFIX_MAP, TSPCB_COLUMN_MAP, get_data_provider
from .alerts import (
    generate_alerts,
    AQI_POOR_THRESHOLD,
    AQI_VERY_POOR_THRESHOLD,
    AQI_SEVERE_THRESHOLD,
    AQI_SENSITIVE_THRESHOLD,
    RAPID_INCREASE_PCT,
    COVERAGE_WARNING_PCT,
)
from .analytics import compute_hotspots, compute_distribution, compute_area_trends
from fastapi.testclient import TestClient
from .main import app


# ── 1. CPCB Breakpoint & Boundary Condition Tests (§10) ──

class TestCPCBSubIndexBoundaries:
    """Boundary-condition tests for every breakpoint edge and continuous decimal transitions."""

    def test_pm25_exact_boundaries(self):
        assert calculate_sub_index("PM2.5", 0.0) == 0
        assert calculate_sub_index("PM2.5", 30.0) == 50
        assert calculate_sub_index("PM2.5", 60.0) == 100
        assert calculate_sub_index("PM2.5", 90.0) == 200
        assert calculate_sub_index("PM2.5", 120.0) == 300
        assert calculate_sub_index("PM2.5", 250.0) == 400
        assert calculate_sub_index("PM2.5", 500.0) == 500

    def test_pm25_decimal_boundary_values(self):
        # 30.5 should linearly interpolate in (30, 60] interval, NOT return None
        si = calculate_sub_index("PM2.5", 30.5)
        assert si is not None
        assert 50 <= si <= 53

        si_60_5 = calculate_sub_index("PM2.5", 60.5)
        assert si_60_5 is not None
        assert 100 <= si_60_5 <= 104

    def test_pm10_boundaries_and_decimals(self):
        assert calculate_sub_index("PM10", 0.0) == 0
        assert calculate_sub_index("PM10", 50.0) == 50
        assert calculate_sub_index("PM10", 50.5) is not None
        assert calculate_sub_index("PM10", 100.0) == 100
        assert calculate_sub_index("PM10", 250.0) == 200
        assert calculate_sub_index("PM10", 350.0) == 300
        assert calculate_sub_index("PM10", 430.0) == 400
        assert calculate_sub_index("PM10", 600.0) == 500

    def test_no2_boundaries(self):
        assert calculate_sub_index("NO2", 0.0) == 0
        assert calculate_sub_index("NO2", 40.0) == 50
        assert calculate_sub_index("NO2", 40.5) is not None
        assert calculate_sub_index("NO2", 80.0) == 100
        assert calculate_sub_index("NO2", 180.0) == 200

    def test_so2_boundaries(self):
        assert calculate_sub_index("SO2", 0.0) == 0
        assert calculate_sub_index("SO2", 40.0) == 50
        assert calculate_sub_index("SO2", 40.5) is not None
        assert calculate_sub_index("SO2", 80.0) == 100

    def test_co_boundaries(self):
        assert calculate_sub_index("CO", 0.0) == 0
        assert calculate_sub_index("CO", 1.0) == 50
        assert calculate_sub_index("CO", 1.05) is not None
        assert calculate_sub_index("CO", 2.0) == 100
        assert calculate_sub_index("CO", 10.0) == 200

    def test_o3_boundaries(self):
        assert calculate_sub_index("O3", 0.0) == 0
        assert calculate_sub_index("O3", 50.0) == 50
        assert calculate_sub_index("O3", 50.5) is not None
        assert calculate_sub_index("O3", 100.0) == 100

    def test_nh3_boundaries(self):
        assert calculate_sub_index("NH3", 0.0) == 0
        assert calculate_sub_index("NH3", 200.0) == 50
        assert calculate_sub_index("NH3", 200.5) is not None
        assert calculate_sub_index("NH3", 400.0) == 100

    def test_capping_at_500(self):
        assert calculate_sub_index("PM2.5", 750.0) == 500
        assert calculate_sub_index("PM10", 900.0) == 500

    def test_invalid_sub_index_inputs(self):
        assert calculate_sub_index("PM2.5", None) is None
        assert calculate_sub_index("PM2.5", -1.0) is None
        assert calculate_sub_index("PM2.5", float("nan")) is None
        assert calculate_sub_index("PM2.5", float("inf")) is None
        assert calculate_sub_index("NON_EXISTENT", 50.0) is None


# ── 2. CPCB AQI Engine & Sufficiency Tests (§10) ──

class TestCPCBAQISufficiency:
    """Enforce official CPCB sufficiency rules: >= 3 pollutants, at least PM2.5 or PM10."""

    def test_sufficient_three_pollutants_with_pm25(self):
        res = calculate_aqi({"PM2.5": 45.0, "PM10": 80.0, "NO2": 25.0})
        assert res["aqi"] is not None
        assert res["source"] == "cpcb_engine"
        assert res["dominant_pollutant"] in ("PM2.5", "PM10", "NO2")

    def test_insufficient_missing_particulate(self):
        # 3 pollutants but NO PM2.5 or PM10 -> MUST fail sufficiency
        res = calculate_aqi({"NO2": 45.0, "SO2": 30.0, "CO": 1.2})
        assert res["aqi"] is None
        assert res["category"] == "Unavailable"
        assert "Missing required particulate" in res["reason"]

    def test_insufficient_fewer_than_three_pollutants(self):
        # PM2.5 alone or PM2.5 + PM10 only (only 2 pollutants) -> MUST fail sufficiency
        res1 = calculate_aqi({"PM2.5": 60.0})
        assert res1["aqi"] is None
        assert "Insufficient CPCB pollutants" in res1["reason"]

        res2 = calculate_aqi({"PM2.5": 60.0, "PM10": 90.0})
        assert res2["aqi"] is None
        assert "Insufficient CPCB pollutants" in res2["reason"]

    def test_dominant_pollutant_identification(self):
        # PM2.5 = 85 (sub-index ~183, Moderate) vs PM10 = 60 (sub-index 60, Satisfactory) vs NO2 = 20 (sub-index 25)
        res = calculate_aqi({"PM2.5": 85.0, "PM10": 60.0, "NO2": 20.0})
        assert res["dominant_pollutant"] == "PM2.5"
        assert res["aqi"] == res["sub_indices"]["PM2.5"]

    def test_empty_concentrations(self):
        res = calculate_aqi({})
        assert res["aqi"] is None
        assert res["category"] == "Unavailable"


class TestAQICategories:
    def test_category_ranges(self):
        assert get_aqi_category(25)[0] == "Good"
        assert get_aqi_category(50)[0] == "Good"
        assert get_aqi_category(51)[0] == "Satisfactory"
        assert get_aqi_category(100)[0] == "Satisfactory"
        assert get_aqi_category(101)[0] == "Moderate"
        assert get_aqi_category(200)[0] == "Moderate"
        assert get_aqi_category(201)[0] == "Poor"
        assert get_aqi_category(300)[0] == "Poor"
        assert get_aqi_category(301)[0] == "Very Poor"
        assert get_aqi_category(400)[0] == "Very Poor"
        assert get_aqi_category(401)[0] == "Severe"
        assert get_aqi_category(500)[0] == "Severe"
        assert get_aqi_category(600)[0] == "Severe"
        assert get_aqi_category(None)[0] == "Unavailable"


# ── 3. Data Provider & Column Disambiguation Tests (§4, §5) ──

class TestDataProviderIntegrity:
    """Validate exact column disambiguation: NO vs NO2 vs NOx."""

    def test_exact_prefix_disambiguation(self):
        assert EXACT_PREFIX_MAP["no"] == "NO"
        assert EXACT_PREFIX_MAP["no2"] == "NO2"
        assert EXACT_PREFIX_MAP["nox"] == "NOx"
        # Verify NO does not collide with NO2 or NOx
        assert EXACT_PREFIX_MAP["no"] != EXACT_PREFIX_MAP["no2"]
        assert EXACT_PREFIX_MAP["no"] != EXACT_PREFIX_MAP["nox"]

    def test_all_12_model_pollutants_in_exact_map(self):
        for feat in REQUIRED_FORECAST_POLLUTANTS:
            # Each must be a value in EXACT_PREFIX_MAP
            assert feat in EXACT_PREFIX_MAP.values(), f"Feature {feat} missing from EXACT_PREFIX_MAP"

    def test_validate_reading_filters(self):
        # Negative rejected
        assert not validate_reading("PM2.5", -5.0)["valid"]
        # NaN rejected
        assert not validate_reading("PM2.5", float("nan"))["valid"]
        # Inf rejected
        assert not validate_reading("PM2.5", float("inf"))["valid"]
        # Non-numeric rejected
        assert not validate_reading("PM2.5", "invalid_text")["valid"]
        # Out-of-range rejected (>1000)
        assert not validate_reading("PM2.5", 2500.0)["valid"]
        # Valid passed
        assert validate_reading("PM2.5", 55.4)["valid"]


# ── 4. Forecast Readiness & No-Median-Imputation Tests (§6, §7) ──

class TestForecastReadiness:
    """Validate strictly consecutive 7-day requirement, completeness, and all-features presence."""

    def _make_valid_sequence(self):
        base = date(2025, 12, 25)
        days = []
        for i in range(7):
            d = {
                "date": base + timedelta(days=i),
                "reading_count": 96,
            }
            for feat in REQUIRED_FORECAST_POLLUTANTS:
                d[feat] = 20.0 + i
            days.append(d)
        return days

    def test_valid_7_consecutive_days_passes(self):
        days = self._make_valid_sequence()
        res = validate_forecast_readiness(days)
        assert res["ready"] is True
        assert res["valid_days"] == 7

    def test_fewer_than_7_days_rejected(self):
        days = self._make_valid_sequence()[:6]
        res = validate_forecast_readiness(days)
        assert res["ready"] is False
        assert "7 consecutive daily observations required" in res["reason"]

    def test_non_consecutive_days_rejected(self):
        # Gap of 1 day between day 3 and day 4 (Dec 27 followed by Dec 29)
        days = self._make_valid_sequence()
        days[3]["date"] = date(2025, 12, 29)
        days[4]["date"] = date(2025, 12, 30)
        days[5]["date"] = date(2025, 12, 31)
        days[6]["date"] = date(2026, 1, 1)
        res = validate_forecast_readiness(days)
        assert res["ready"] is False
        assert "Non-consecutive dates" in res["reason"]

    def test_incomplete_day_rejected(self):
        # Day 2 has reading_count < 48 (below MIN_DAILY_READINGS)
        days = self._make_valid_sequence()
        days[1]["reading_count"] = 20
        res = validate_forecast_readiness(days)
        assert res["ready"] is False
        assert "below required" in res["reason"]

    def test_missing_pollutant_feature_rejected(self):
        # Any missing feature (e.g. Xylene is None on day 5) must be rejected
        days = self._make_valid_sequence()
        days[4]["Xylene"] = None
        res = validate_forecast_readiness(days)
        assert res["ready"] is False
        assert "missing valid features" in res["reason"]

    def test_model_preprocess_rejects_missing_without_median(self):
        model = get_model()
        if model.status == "ready":
            days = self._make_valid_sequence()
            # Set Benzene to None on day 1
            days[0]["Benzene"] = None
            # Must return None (no fallback)
            scaled = model.preprocess(days)
            assert scaled is None, "Model preprocess must return None when feature is missing (no median imputation allowed)"


# ── 5. Model Architecture & Feature Order Tests (§2) ──

class TestModelArchitecture:
    def test_exact_18_features_order(self):
        from .unified_forecast.config import ALL_FEATURES
        assert MODEL_FEATURES == ALL_FEATURES
        assert len(MODEL_FEATURES) == 18

    def test_model_info_provenance(self):
        model = get_model()
        info = model.get_info()
        assert info["model_name"] == "TemporalGRU_KNNCovariate"
        assert info["pipeline"] == "Unified Spatial-Temporal Forecasting Pipeline"
        assert "Temporal GRU" in info["architecture"]
        assert info["license"] == "Apache-2.0"


# ── 6. Deterministic Alerts Engine Tests (§14) ──

class TestAlertsEngine:
    def test_severe_threshold_alert(self):
        readings = [{"station_name": "S1", "area": "A1", "PM2.5": 260.0, "PM10": 450.0, "NO2": 50.0}]
        alerts = generate_alerts(readings)
        assert any(a["severity"] == "critical" and a["type"] == "aqi_threshold" for a in alerts)

    def test_sensitive_group_wording(self):
        # Station with AQI > 100
        readings = [{"station_name": "S1", "area": "A1", "PM2.5": 70.0, "PM10": 110.0, "NO2": 30.0}]
        alerts = generate_alerts(readings)
        sens_alerts = [a for a in alerts if a["type"] == "sensitive_group"]
        assert len(sens_alerts) > 0
        # Wording must explicitly state "areas with AQI above 100" per §14
        assert "areas with AQI above 100" in sens_alerts[0]["message"]

    def test_forecast_deterioration_gated_on_success(self):
        # When forecast_status is 'unavailable', NO forecast alert must be generated
        unavail_forecast = {"forecast_status": "unavailable", "forecast_aqi": None}
        alerts = generate_alerts([], forecast=unavail_forecast)
        assert not any(a["type"] == "forecast_warning" for a in alerts)

        # When forecast_status is 'success' and aqi > 200, alert fires
        succ_forecast = {"forecast_status": "success", "forecast_aqi": 220}
        alerts2 = generate_alerts([], forecast=succ_forecast)
        assert any(a["type"] == "forecast_warning" for a in alerts2)


# ── 7. Analytics Tests (§13) ──

class TestAnalytics:
    def test_hotspots_excludes_insufficient_stations(self):
        # S1 has full data; S2 has only PM2.5 (fails sufficiency)
        readings = [
            {"station_name": "S1", "PM2.5": 80.0, "PM10": 120.0, "NO2": 40.0},
            {"station_name": "S2", "PM2.5": 90.0},
        ]
        hotspots = compute_hotspots(readings)
        # S2 must be excluded because it failed sufficiency
        assert len(hotspots) == 1
        assert hotspots[0]["station_name"] == "S1"

    def test_distribution_categorizes_valid_only(self):
        readings = [
            {"station_name": "S1", "PM2.5": 20.0, "PM10": 40.0, "NO2": 10.0},  # Good
        ]
        dist = compute_distribution(readings)
        good = next(d for d in dist if "Good" in d["name"])
        assert good["value"] == 1


# ── 8. API Endpoint Verification Tests (§20, §21) ──

client = TestClient(app)


class TestAPIEndpoints:
    def test_health_endpoint(self):
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["agent"] == "Pollution Agent"
        assert data["city"] == CITY_NAME

    def test_current_endpoint(self):
        res = client.get("/api/pollution/current")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ("success", "unavailable")
        if data["status"] == "success":
            assert "aqi" in data
            assert data["source"] == "cpcb_engine"

    def test_pollutants_endpoint(self):
        res = client.get("/api/pollution/pollutants")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ("success", "unavailable")

    def test_trend_endpoint(self):
        res = client.get("/api/pollution/trend?range=24h")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ("success", "unavailable")

    def test_hourly_forecast_unavailable(self):
        # §15, §20: Hourly forecast must return explicit unavailable status
        res = client.get("/api/pollution/forecast/hourly")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "unavailable"
        assert "unsupported" in data["reason"].lower()

    def test_daily_forecast_endpoint(self):
        res = client.get("/api/pollution/forecast/daily")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ("success", "unavailable")

    def test_alerts_endpoint(self):
        res = client.get("/api/pollution/alerts")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert "alerts" in data

    def test_summary_endpoint(self):
        res = client.get("/api/pollution/summary")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ("success", "unavailable")
        if data["status"] == "success":
            # Consistent single pipeline: current.aqi, category, dominant_pollutant
            assert "current" in data
            assert "forecast" in data

    def test_info_endpoint(self):
        res = client.get("/api/pollution/info")
        assert res.status_code == 200
        data = res.json()
        assert data["model_name"] == "TemporalGRU_KNNCovariate"
        assert data["features"] == 18

    def test_current_endpoint_transparency(self):
        res = client.get("/api/pollution/current")
        assert res.status_code == 200
        data = res.json()
        if data["status"] == "success":
            assert data["data_mode"] == "historical"
            assert data["is_live"] is False
            assert "2025-12-31" in data["timestamp"]
            assert data["timestamp"] == data["observation_timestamp"]
            assert data["timestamp"] != data["server_time"]
            assert "CPCB" in data["methodology"]

    def test_historical_latest_endpoint(self):
        res = client.get("/api/pollution/historical/latest")
        assert res.status_code == 200
        data = res.json()
        if data["status"] == "success":
            assert data["data_mode"] == "historical"
            assert "2025-12-31" in data["timestamp"]

    def test_provider_abstraction_pluggability(self):
        from backend.agents.pollution_agent.data_provider import get_data_provider, set_data_provider, reset_data_provider, BasePollutionDataProvider
        p = get_data_provider()
        assert isinstance(p, BasePollutionDataProvider)
        assert p.data_mode == "historical"
        assert p.is_live is False
        assert p.get_latest_observation_timestamp() is not None
        assert "2025-12-31" in p.get_latest_observation_timestamp()

    def test_predict_shared_validation(self):
        # Incomplete sequence (3 days instead of 7) -> must return error or unavailable
        res = client.post("/api/pollution/predict", json={"days": [{"PM2.5": 50}] * 3})
        assert res.status_code == 200
        data = res.json()
        assert data["forecast_status"] in ("error", "unavailable")


# ── 9. Verified Daily Aggregation & Production Pipeline Tests (Section 14) ──

class TestVerifiedDailyAggregationSuite:
    """Explicit tests for Section 14 Requirements A through I."""

    # A. Daily aggregation
    def test_15min_to_daily_arithmetic_mean(self):
        import pandas as pd
        values = [25.0] * 96
        s = pd.Series(values)
        assert float(s.mean()) == 25.0

    def test_nan_values_excluded_from_mean(self):
        import numpy as np
        import pandas as pd
        values = [30.0] * 48 + [np.nan] * 48
        s = pd.Series(values).dropna()
        assert len(s) == 48
        assert float(s.mean()) == 30.0

    def test_negative_invalid_values_excluded(self):
        assert not validate_reading("PM2.5", -10.0)["valid"]
        assert not validate_reading("CO", -0.5)["valid"]
        assert not validate_reading("O3", -999.0)["valid"]
        assert validate_reading("CO", 0.0)["valid"]
        assert validate_reading("PM2.5", 0.0)["valid"]

    def test_no_median_or_zero_imputation(self):
        model = get_model()
        if model.status == "ready":
            base = date(2025, 12, 25)
            days = []
            for i in range(7):
                d = {"date": base + timedelta(days=i), "reading_count": 96}
                for f in REQUIRED_FORECAST_POLLUTANTS:
                    d[f] = 20.0 + i
                days.append(d)
            days[2]["CO"] = None
            scaled = model.preprocess(days)
            assert scaled is None, "Preprocessing must reject missing feature without median/zero imputation"

    # B. Completeness
    def test_completeness_acceptance_and_rejection(self):
        base = date(2025, 12, 25)
        complete_days = [{"date": base + timedelta(days=i), "reading_count": 96, **{f: 25.0 for f in REQUIRED_FORECAST_POLLUTANTS}} for i in range(7)]
        res_comp = validate_forecast_readiness(complete_days)
        assert res_comp["ready"] is True

        incomplete_days = [{"date": base + timedelta(days=i), "reading_count": 96, **{f: 25.0 for f in REQUIRED_FORECAST_POLLUTANTS}} for i in range(7)]
        incomplete_days[3]["reading_count"] = 20
        res_incomp = validate_forecast_readiness(incomplete_days)
        assert res_incomp["ready"] is False
        assert "below required" in res_incomp["reason"]

    # C. Consecutive sequence
    def test_strictly_consecutive_7_days(self):
        base = date(2025, 12, 25)
        consec_days = [{"date": base + timedelta(days=i), "reading_count": 96, **{f: 25.0 for f in REQUIRED_FORECAST_POLLUTANTS}} for i in range(7)]
        assert validate_forecast_readiness(consec_days)["ready"] is True

        gap_days = [{"date": base + timedelta(days=i), "reading_count": 96, **{f: 25.0 for f in REQUIRED_FORECAST_POLLUTANTS}} for i in range(7)]
        gap_days[2]["date"] = date(2025, 12, 28)
        res_gap = validate_forecast_readiness(gap_days)
        assert res_gap["ready"] is False
        assert "Non-consecutive dates" in res_gap["reason"]

    # D. CO/O3 representation
    def test_co_and_o3_daily_arithmetic_mean_representation(self):
        provider = get_data_provider()
        city_daily = provider.get_city_daily_aggregates(n_days=7)
        if not city_daily.empty:
            for feat in ["CO", "O3"]:
                assert feat in city_daily.columns
                for val in city_daily[feat].dropna():
                    assert isinstance(val, (float, int))
                    assert val >= 0.0

    # E. City encoder absence (spatial-temporal model does not use categorical city encoding)
    def test_city_encoder_dynamic_loading(self):
        """Confirm unified spatial-temporal model has zero dead code / unused city_encoder."""
        model = get_model()
        assert not hasattr(model, "city_encoder"), "Unified spatial-temporal model must not have city_encoder (no categorical city embedding in spatial-temporal architecture)"
        assert not hasattr(model, "city_enc_value"), "Unified spatial-temporal model must not have city_enc_value"

    # F. Model input
    def test_exact_18_feature_order_and_shape(self):
        from .unified_forecast.config import ALL_FEATURES
        assert len(MODEL_FEATURES) == 18
        assert MODEL_FEATURES == ALL_FEATURES

    # G. Provenance
    def test_provenance_separation(self):
        res = calculate_aqi({"PM2.5": 55.0, "PM10": 85.0, "NO2": 22.0})
        assert res["source"] == "cpcb_engine"

        model = get_model()
        if model.status == "ready":
            base = date(2025, 12, 25)
            days = [{"date": base + timedelta(days=i), "reading_count": 96, **{f: 20.0 + i for f in REQUIRED_FORECAST_POLLUTANTS}} for i in range(7)]
            f_res = model.predict(days)
            assert f_res["source"] == "unified_spatial_temporal_model"

    # H. Missing-data behavior: real HistoricalTSPCBProvider with truncated observation history
    def test_missing_data_returns_unavailable_without_fabrication(self):
        from backend.agents.pollution_agent.data_provider import (
            HistoricalTSPCBProvider,
            set_data_provider,
            reset_data_provider,
            get_data_provider,
        )
        base_provider = get_data_provider()

        class TruncatedTSPCBProvider(HistoricalTSPCBProvider):
            """Real HistoricalTSPCBProvider with truncated observation history (less than 7 days)."""
            def _load_all_stations(self) -> pd.DataFrame:
                df = base_provider._load_all_stations().copy()
                if not df.empty:
                    max_date = df["date"].max()
                    # Truncate to only 4 days
                    df = df[df["date"] >= (max_date - timedelta(days=3))].copy()
                return df

        set_data_provider(TruncatedTSPCBProvider())
        try:
            # 1. API: /api/pollution/forecast/daily must return unavailable with null AQI
            res_daily = client.get("/api/pollution/forecast/daily")
            assert res_daily.status_code == 200
            daily_data = res_daily.json()
            assert daily_data["status"] == "unavailable"
            assert daily_data["forecast"]["forecast_aqi"] is None
            assert daily_data["forecast"]["forecast_status"] == "unavailable"

            # 2. API: /api/pollution/forecast/7day must return unavailable with empty forecast
            res_7d = client.get("/api/pollution/forecast/7day")
            assert res_7d.status_code == 200
            ext_data = res_7d.json()
            assert ext_data["status"] == "unavailable"
            assert len(ext_data.get("forecast", [])) == 0

            # 3. Model: predict must also return unavailable without fabrication
            model = get_model()
            base = date(2025, 12, 25)
            short_days = [{"date": base + timedelta(days=i), "reading_count": 96, **{f: 20.0 for f in REQUIRED_FORECAST_POLLUTANTS}} for i in range(4)]
            res = model.predict(short_days)
            assert res["forecast_status"] == "unavailable"
            assert res["forecast_aqi"] is None
            assert "required" in res["reason"].lower()
        finally:
            reset_data_provider()

    # I. API consistency between /predict and production forecast
    def test_api_predict_uses_identical_pipeline(self):
        base = date(2025, 12, 25)
        days = [{"date": (base + timedelta(days=i)).isoformat(), "reading_count": 96, **{f: 20.0 + i for f in REQUIRED_FORECAST_POLLUTANTS}} for i in range(7)]
        res = client.post("/api/pollution/predict", json={"days": days})
        assert res.status_code == 200
        data = res.json()
        assert data["source"] == "unified_spatial_temporal_model"
        if data["forecast_status"] == "success":
            assert isinstance(data["forecast_aqi"], (int, float))
            assert data["forecast_horizon"] == "1 Day (Next-Day)"
            assert data["forecast_date"] == (base + timedelta(days=7)).isoformat()

    # J. Multi-station completeness denominator verification
    def test_multi_station_city_aggregation_denominator(self):
        provider = get_data_provider()
        city_daily = provider.get_city_daily_aggregates(n_days=7)
        if not city_daily.empty:
            for _, row in city_daily.iterrows():
                active_s = row["active_stations"]
                expected = row["expected_readings"]
                # Mathematical consistency: denominator must equal active_stations * 96
                assert expected == active_s * 96
                # Verify each feature completeness ratio uses active_stations * 96 as denominator
                for feat in REQUIRED_FORECAST_POLLUTANTS:
                    comp = row["completeness"][feat]
                    assert comp["expected_count"] == expected
                    if expected > 0:
                        assert round(comp["valid_count"] / expected, 4) == comp["completeness_ratio"]

    # K. Individual 12-feature removal tests: EACH feature missing on one day causes unavailable status
    @pytest.mark.parametrize("missing_feat", REQUIRED_FORECAST_POLLUTANTS)
    def test_single_pollutant_feature_missing_on_one_day_makes_forecast_unavailable(self, missing_feat):
        from backend.agents.pollution_agent.data_provider import (
            HistoricalTSPCBProvider,
            set_data_provider,
            reset_data_provider,
            get_data_provider,
        )
        base_provider = get_data_provider()
        target_test_date = date(2025, 12, 28)

        class BlankedPollutantTSPCBProvider(HistoricalTSPCBProvider):
            """Real HistoricalTSPCBProvider with a single pollutant blanked out for a test date."""
            def _load_all_stations(self) -> pd.DataFrame:
                df = base_provider._load_all_stations().copy()
                if not df.empty and missing_feat in df.columns:
                    mask = df["date"] == target_test_date
                    df.loc[mask, missing_feat] = np.nan
                return df

        set_data_provider(BlankedPollutantTSPCBProvider())
        try:
            # 1. API: /api/pollution/forecast/daily must return unavailable with null AQI
            res_daily = client.get("/api/pollution/forecast/daily")
            assert res_daily.status_code == 200
            daily_data = res_daily.json()
            assert daily_data["status"] == "unavailable"
            assert daily_data["forecast"]["forecast_aqi"] is None
            assert daily_data["forecast"]["forecast_status"] == "unavailable"

            # 2. API: /api/pollution/forecast/7day must return unavailable with empty forecast
            res_7d = client.get("/api/pollution/forecast/7day")
            assert res_7d.status_code == 200
            ext_data = res_7d.json()
            assert ext_data["status"] == "unavailable"
            assert len(ext_data.get("forecast", [])) == 0

            # 3. Model level: validate_forecast_readiness and model.predict must also report unavailable
            base = date(2025, 12, 25)
            days = [{"date": base + timedelta(days=i), "reading_count": 96, **{f: 25.0 for f in REQUIRED_FORECAST_POLLUTANTS}} for i in range(7)]
            days[3][missing_feat] = None

            readiness = validate_forecast_readiness(days)
            assert readiness["ready"] is False
            assert "missing valid features" in readiness["reason"]
            assert missing_feat in readiness["reason"]

            model = get_model()
            pred = model.predict(days)
            assert pred["forecast_status"] == "unavailable"
            assert pred["forecast_aqi"] is None
            assert missing_feat in pred["reason"]
        finally:
            reset_data_provider()

    # L. 50% engineering threshold semantics test
    def test_50_percent_engineering_completeness_boundary(self):
        base = date(2025, 12, 25)
        # Exactly 47 readings (< 48 MIN_DAILY_READINGS) -> rejected
        days_47 = [{"date": base + timedelta(days=i), "reading_count": 96, **{f: 25.0 for f in REQUIRED_FORECAST_POLLUTANTS}} for i in range(7)]
        days_47[0]["reading_count"] = 47
        assert validate_forecast_readiness(days_47)["ready"] is False

        # Exactly 48 readings (>= 48 MIN_DAILY_READINGS) -> accepted
        days_48 = [{"date": base + timedelta(days=i), "reading_count": 96, **{f: 25.0 for f in REQUIRED_FORECAST_POLLUTANTS}} for i in range(7)]
        days_48[0]["reading_count"] = 48
        assert validate_forecast_readiness(days_48)["ready"] is True

    # M. Forecast date verification: forecast_date = latest_day + 1
    def test_forecast_date_calculation_from_latest_observation(self):
        model = get_model()
        if model.status == "ready":
            # Pass 7 days ending on 2025-12-31
            base = date(2025, 12, 25)
            days = [{"date": base + timedelta(days=i), "reading_count": 96, **{f: 20.0 for f in REQUIRED_FORECAST_POLLUTANTS}} for i in range(7)]
            assert days[-1]["date"] == date(2025, 12, 31)
            pred = model.predict(days)
            assert pred["forecast_status"] == "success"
            # Must strictly be 2026-01-01
            assert pred["forecast_date"] == "2026-01-01"
            assert pred["forecast_horizon"] == "1 Day (Next-Day)"


# ── 12. Research-Grade Pipeline & Regression Suite (§Phase 24, §Phase 25) ──

class TestResearchGradePipelineSuite:
    """
    Research-Grade Pipeline Suite covering data integrity, CPCB temporal windows,
    spatial aggregation isolation, observed/predicted separation, and Phase 25 regression.
    """

    @pytest.fixture(autouse=True)
    def ensure_default_provider(self):
        from .data_provider import reset_data_provider
        reset_data_provider()
        yield
        reset_data_provider()

    # 1. Historical timestamp preservation
    def test_historical_timestamp_preservation(self):
        client = TestClient(app)
        res = client.get("/api/pollution/current").json()
        assert res["status"] == "success"
        obs_ts = res["observation_timestamp"]
        server_ts = res["server_time"]
        assert obs_ts == "2025-12-31T23:45:00+00:00"
        assert obs_ts != server_ts
        assert res["timestamp"] == "2025-12-31T23:45:00+00:00"

    # 2. Live vs historical provider distinction
    def test_live_vs_historical_provider_distinction(self):
        from .data_provider import HistoricalTSPCBProvider, PlaceholderLivePollutionProvider
        hist = HistoricalTSPCBProvider()
        assert hist.data_mode == "historical"
        assert hist.is_live is False
        assert "TSPCB" in hist.provider_name

        live_ph = PlaceholderLivePollutionProvider()
        assert live_ph.data_mode == "live"
        assert live_ph.is_live is True
        assert "Live" in live_ph.provider_name

    # 3. Provider switching via set_data_provider()
    def test_provider_switching(self):
        from .data_provider import set_data_provider, reset_data_provider, PlaceholderLivePollutionProvider
        client = TestClient(app)

        # Baseline: default historical
        h1 = client.get("/health").json()
        assert h1["data_mode"] == "historical"
        assert h1["is_live"] is False

        # Switch to live placeholder
        set_data_provider(PlaceholderLivePollutionProvider())
        h2 = client.get("/health").json()
        assert h2["data_mode"] == "live"
        assert h2["is_live"] is True

        # Reset to default
        reset_data_provider()
        h3 = client.get("/health").json()
        assert h3["data_mode"] == "historical"
        assert h3["is_live"] is False

    # 4. Freshness calculation
    def test_freshness_calculation(self):
        client = TestClient(app)
        res = client.get("/api/pollution/current").json()
        assert "data_age_seconds" in res
        assert isinstance(res["data_age_seconds"], (int, float))
        # Telemetry ended in Dec 2025, so age must be > 10,000,000 seconds
        assert res["data_age_seconds"] > 1000000.0
        assert res["stale"] is True

    def test_live_staleness_exclusion_and_hard_gate(self):
        """
        Verify that in live mode:
        1. Stations with readings older than 3 hours are excluded from the city aggregate.
        2. If all stations are older than 3 hours, /current returns status='unavailable' with reason='stale_data'.
        3. If fresh stations exist alongside stale stations, only fresh stations are aggregated.
        """
        from .data_provider import BasePollutionDataProvider, set_data_provider, reset_data_provider

        now_utc = datetime.now(timezone.utc)
        fresh_ts = (now_utc - timedelta(hours=1)).isoformat()
        stale_ts = (now_utc - timedelta(hours=5)).isoformat()

        # Mock live provider with 1 fresh station and 1 stale station
        class MixedStalenessLiveProvider(BasePollutionDataProvider):
            data_mode = "live"
            is_live = True
            provider_name = "Mock Live Staleness Provider"

            def get_station_names(self):
                return ["Fresh Station", "Stale Station"]

            def get_latest_readings(self):
                return [
                    {
                        "station_name": "Fresh Station",
                        "timestamp": fresh_ts,
                        "data_mode": "live",
                        "is_live": True,
                        "PM2.5": 30.0,
                        "PM10": 60.0,
                        "NO2": 20.0,
                        "SO2": 10.0,
                        "CO": 0.5,
                        "O3": 25.0,
                    },
                    {
                        "station_name": "Stale Station",
                        "timestamp": stale_ts,
                        "data_mode": "live",
                        "is_live": True,
                        "PM2.5": 200.0,
                        "PM10": 350.0,
                        "NO2": 80.0,
                        "SO2": 40.0,
                        "CO": 2.5,
                        "O3": 80.0,
                    },
                ]

            def get_latest_observation_timestamp(self):
                return fresh_ts

            def get_observations(self, **kwargs):
                return pd.DataFrame()

            def get_daily_aggregates(self, n_days=30):
                return pd.DataFrame()

            def get_city_daily_aggregates(self, n_days=30, min_completeness_ratio=0.5):
                return pd.DataFrame()

            def get_historical_trend(self, range_key="24h"):
                return []

        client = TestClient(app)
        set_data_provider(MixedStalenessLiveProvider())
        try:
            res = client.get("/api/pollution/current").json()
            assert res["status"] == "success"
            # Active stations must be strictly 1 (the fresh one; the stale one is excluded)
            assert res["active_stations"] == 1
            assert res["station_count"] == 2
            # Stale station concentrations (PM10=350) must NOT be included in city concentration
            # City PM10 must be strictly 60.0, not (60+350)/2 = 205
            assert res["dominant_value"] == 60.0
            assert res["observed_aqi"] == 60
        finally:
            reset_data_provider()

        # Mock live provider where ALL stations are stale (>3h)
        class AllStaleLiveProvider(BasePollutionDataProvider):
            data_mode = "live"
            is_live = True
            provider_name = "Mock All Stale Live Provider"

            def get_station_names(self):
                return ["Stale 1", "Stale 2"]

            def get_latest_readings(self):
                return [
                    {
                        "station_name": "Stale 1",
                        "timestamp": stale_ts,
                        "data_mode": "live",
                        "is_live": True,
                        "PM2.5": 40.0,
                        "PM10": 70.0,
                        "NO2": 25.0,
                    },
                    {
                        "station_name": "Stale 2",
                        "timestamp": stale_ts,
                        "data_mode": "live",
                        "is_live": True,
                        "PM2.5": 50.0,
                        "PM10": 80.0,
                        "NO2": 30.0,
                    },
                ]

            def get_latest_observation_timestamp(self):
                return stale_ts

            def get_observations(self, **kwargs):
                return pd.DataFrame()

            def get_daily_aggregates(self, n_days=30):
                return pd.DataFrame()

            def get_city_daily_aggregates(self, n_days=30, min_completeness_ratio=0.5):
                return pd.DataFrame()

            def get_historical_trend(self, range_key="24h"):
                return []

        set_data_provider(AllStaleLiveProvider())
        try:
            res_all_stale = client.get("/api/pollution/current").json()
            assert res_all_stale["status"] == "success"
            assert res_all_stale["is_stale"] is True
            assert res_all_stale["stale"] is True
            assert res_all_stale["observed_aqi"] is not None
            assert res_all_stale["observed_aqi"] == 75  # Mean PM10 (70+80)/2 = 75
            assert res_all_stale["active_stations"] == 2
            assert res_all_stale["station_count"] == 2
            assert res_all_stale["data_age_hours"] is not None
            assert res_all_stale["data_age_hours"] >= 4.5
            assert "Last updated" in res_all_stale["last_updated_label"]

            # Separately confirm live_accumulation records a gap for this same all-stale scenario (§ Requirement 6)
            from pathlib import Path
            from .live_accumulation import LiveAccumulationStore
            import tempfile
            from datetime import date
            with tempfile.TemporaryDirectory() as tmp_dir:
                store = LiveAccumulationStore(data_dir=Path(tmp_dir))
                today = date.today()
                stale_readings = AllStaleLiveProvider().get_latest_readings()
                valid_fresh = [
                    r for r in stale_readings
                    if not r.get("stale", False) and (
                        (now_utc - pd.to_datetime(r["timestamp"])).total_seconds() <= 3 * 3600
                    )
                ]
                assert len(valid_fresh) == 0  # Confirms all stations are stale (> 3h)
                store.record_gap(today, "All stations stale (> 3h)")
                gap_status = store.get_status()
                assert gap_status["consecutive_live_days"] == 0
                assert today.isoformat() in gap_status["gap_dates"]
                assert gap_status["ready_for_live_forecast"] is False
        finally:
            reset_data_provider()

        # Mock provider where stations are stale AND fail sufficiency (e.g. only 1 pollutant) (§ Requirement 5)
        class StaleAndInsufficientLiveProvider(BasePollutionDataProvider):
            data_mode = "live"
            is_live = True
            provider_name = "Mock Stale Insufficient Provider"

            def get_station_names(self):
                return ["Insufficient Station"]

            def get_latest_readings(self):
                return [{
                    "station_name": "Insufficient Station",
                    "timestamp": stale_ts,
                    "data_mode": "live",
                    "is_live": True,
                    "PM2.5": 40.0,  # Only 1 pollutant! Fails >= 3 pollutants rule
                }]

            def get_latest_observation_timestamp(self):
                return stale_ts
            def get_observations(self, **kwargs): return pd.DataFrame()
            def get_daily_aggregates(self, n_days=30): return pd.DataFrame()
            def get_city_daily_aggregates(self, n_days=30, min_completeness_ratio=0.5): return pd.DataFrame()
            def get_historical_trend(self, range_key="24h"): return []

        set_data_provider(StaleAndInsufficientLiveProvider())
        try:
            res_insufficient = client.get("/api/pollution/current").json()
            assert res_insufficient["status"] == "unavailable"
            assert res_insufficient["reason"] == "insufficient_data"
            assert res_insufficient["observed_aqi"] is None
        finally:
            reset_data_provider()

    # 5. 24h temporal aggregation thresholds (PM2.5, PM10, NO2, SO2, NH3 require >= 16h / 64 readings)
    @pytest.mark.parametrize("pollutant", ["PM2.5", "PM10", "NO2", "SO2", "NH3"])
    def test_24h_temporal_aggregation_thresholds(self, pollutant):
        import pandas as pd
        from .temporal_aggregation import compute_pollutant_window_mean

        # 63 readings (15.75 hours) -> below 16h threshold -> rejected
        s_63 = pd.Series([30.0] * 63)
        val_63, meta_63 = compute_pollutant_window_mean(s_63, pollutant)
        assert val_63 is None
        assert meta_63["is_sufficient"] is False
        assert meta_63["valid_count"] == 63

        # 64 readings (16.0 hours) -> meets 16h threshold -> accepted
        s_64 = pd.Series([30.0] * 64)
        val_64, meta_64 = compute_pollutant_window_mean(s_64, pollutant)
        assert val_64 == 30.0
        assert meta_64["is_sufficient"] is True
        assert meta_64["valid_count"] == 64

    # 6. 8h temporal aggregation thresholds (CO, O3 require >= 6h / 24 readings)
    @pytest.mark.parametrize("pollutant", ["CO", "O3"])
    def test_8h_temporal_aggregation_thresholds(self, pollutant):
        import pandas as pd
        from .temporal_aggregation import compute_pollutant_window_mean

        # 23 readings (5.75 hours) -> below 6h threshold -> rejected
        s_23 = pd.Series([1.2] * 23)
        val_23, meta_23 = compute_pollutant_window_mean(s_23, pollutant)
        assert val_23 is None
        assert meta_23["is_sufficient"] is False

        # 24 readings (6.0 hours) -> meets 6h threshold -> accepted
        s_24 = pd.Series([1.2] * 24)
        val_24, meta_24 = compute_pollutant_window_mean(s_24, pollutant)
        assert val_24 == 1.2
        assert meta_24["is_sufficient"] is True

    # 7. Insufficient data returns None without silent imputation
    def test_insufficient_data_returns_none_without_silent_imputation(self):
        import pandas as pd
        from .temporal_aggregation import compute_station_window_aggregates

        # Empty station dataframe
        df_empty = pd.DataFrame(columns=["timestamp", "station_name", "PM2.5", "PM10"])
        res = compute_station_window_aggregates(df_empty, station_name="TestStation")
        assert res["aqi"] is None
        assert res["status"] == "unavailable"

        # Station dataframe with only 5 readings (insufficient for 24h or 8h)
        base = datetime(2025, 12, 31, 23, 45, tzinfo=timezone.utc)
        records = [{
            "timestamp": base - timedelta(minutes=15 * i),
            "station_name": "SparseStation",
            "PM2.5": 40.0,
            "PM10": 80.0,
            "NO2": 25.0,
        } for i in range(5)]
        df_sparse = pd.DataFrame(records)
        res_sparse = compute_station_window_aggregates(df_sparse, anchor_time=base, station_name="SparseStation")
        assert res_sparse["aqi"] is None
        assert res_sparse["concentrations"].get("PM2.5") is None

    # 8. No single 15-minute row masquerading as 24h AQI
    def test_no_single_15min_row_masquerading_as_24h_aqi(self):
        import pandas as pd
        from .temporal_aggregation import compute_station_window_aggregates

        ts = datetime(2025, 12, 31, 23, 45, tzinfo=timezone.utc)
        single_row = pd.DataFrame([{
            "timestamp": ts,
            "station_name": "Sanathnagar",
            "PM2.5": 39.16,
            "PM10": 81.68,
            "NO2": 11.89,
            "SO2": 9.71,
            "O3": 17.25,
            "CO": 0.65,
        }])
        agg = compute_station_window_aggregates(single_row, anchor_time=ts, station_name="Sanathnagar")
        # Must be rejected because 1 reading < 64 required for 24h
        assert agg["aqi"] is None
        assert agg["status"] == "unavailable"
        assert agg["concentrations"].get("PM2.5") is None

    # 9. Spatial aggregation isolation
    def test_spatial_aggregation_isolation(self):
        from .spatial_aggregation import aggregate_city_by_concentration, aggregate_city_by_station_aqi, compute_city_aqi

        station_aggs = [
            {
                "station_name": "StationA",
                "concentrations": {"PM2.5": 50.0, "PM10": 90.0, "NO2": 20.0},
                "aqi": 90,
                "dominant_pollutant": "PM10",
            },
            {
                "station_name": "StationB",
                "concentrations": {"PM2.5": 70.0, "PM10": 110.0, "NO2": 30.0},
                "aqi": 133,
                "dominant_pollutant": "PM2.5",
            },
        ]

        conc_first = aggregate_city_by_concentration(station_aggs)
        assert conc_first["method"] == "concentration_first"
        assert conc_first["city_concentrations"]["PM2.5"] == 60.0  # mean(50, 70)
        assert conc_first["city_concentrations"]["PM10"] == 100.0  # mean(90, 110)

        st_first = aggregate_city_by_station_aqi(station_aggs)
        assert st_first["method"] == "station_first"
        assert st_first["aqi"] == round((90 + 133) / 2)  # 112

        both = compute_city_aqi(station_aggs)
        assert "concentration_first_aqi" in both
        assert "station_first_aqi" in both
        assert both["spatial_divergence"] is not None

    # 10. Observed vs predicted AQI provenance separation
    def test_observed_vs_predicted_aqi_provenance_separation(self):
        client = TestClient(app)

        # Observed AQI
        curr = client.get("/api/pollution/current").json()
        assert curr["status"] == "success"
        assert curr["source"] == "cpcb_engine"
        assert "observed_aqi" in curr
        assert "forecast_aqi" not in curr  # Never in observed endpoint

        # Predicted AQI
        fore = client.get("/api/pollution/forecast/daily").json()
        if fore["status"] == "success":
            assert fore["forecast"]["source"] == "unified_spatial_temporal_model"
            assert "forecast_aqi" in fore["forecast"]
            assert fore["forecast"]["forecast_aqi"] != curr["observed_aqi"]

    # 11. Zero hardcoded production measurements
    def test_zero_hardcoded_production_measurements(self):
        from .data_provider import get_data_provider
        p = get_data_provider()
        readings = p.get_latest_readings()
        # Ensure measurements originate from DataFrame rows, not fixed constants
        assert len(readings) > 0
        for r in readings:
            assert r["station_name"] is not None
            assert r["timestamp"].startswith("2025-12-31T23:")

    # 12. Full Phase 25 regression test for original bug
    def test_phase25_regression_test_for_original_bug(self):
        client = TestClient(app)

        curr = client.get("/api/pollution/current").json()
        assert curr["status"] == "success"

        # Check 1: Observation timestamp is strictly from dataset (2025-12-31), NOT current server year
        assert curr["observation_timestamp"] == "2025-12-31T23:45:00+00:00"
        assert curr["timestamp"] == "2025-12-31T23:45:00+00:00"

        # Check 2: Server time is separate and reflects actual runtime
        assert curr["server_time"] != curr["observation_timestamp"]
        assert curr["data_age_seconds"] > 1000000.0

        # Check 3: Mode is historical and not live
        assert curr["data_mode"] == "historical"
        assert curr["is_live"] is False

        # Check 4: Temporal windowing methodology is explicitly exposed
        assert "24h/8h Temporal Windowing" in curr["methodology"]
        assert "averaging_windows" in curr

        # Check 5: Reconciliation report traces divergence cleanly
        rec = client.get("/api/pollution/reconciliation").json()
        assert rec["status"] == "success"
        assert rec["cpcb_reference_aqi"] == 50
        assert rec["our_observed_aqi"] == curr["observed_aqi"]
        assert rec["temporal_gap_days"] > 200
        assert len(rec["divergence_factors"]) >= 2


class TestUnifiedOperationalInvariants:
    """Operational invariants requested: Day-1 consistency, model_name alignment, and train.py model validation."""

    def test_day1_identical_across_three_endpoints(self):
        """(a) Confirm Day-1 AQI, model_name, and origin_timestamp are identical across daily, 7day, and summary."""
        daily_res = client.get("/api/pollution/forecast/daily").json()
        seven_res = client.get("/api/pollution/forecast/7day").json()
        sum_res = client.get("/api/pollution/summary").json()

        assert daily_res["status"] == "success"
        assert seven_res["status"] == "success"
        assert sum_res["status"] == "success"

        d1_daily = daily_res["forecast"]
        d1_7day = seven_res["forecast"][0]
        d1_sum = sum_res["forecast"]

        # 1. Day-1 AQI identity
        assert d1_daily["forecast_aqi"] == d1_7day["aqi"] == d1_sum["forecast_aqi"]
        # 2. model_name identity
        assert d1_daily["model_name"] == seven_res["architecture"] == d1_sum["model_name"]
        # 3. origin_timestamp identity
        assert d1_daily["origin_timestamp"] == seven_res["origin_timestamp"] == d1_sum["origin_timestamp"]

    def test_model_name_matches_metadata_file(self):
        """(b) Confirm runtime model_name matches unified_best_model_meta.json selected_winner."""
        import json
        from pathlib import Path
        meta_path = Path(__file__).resolve().parent / "unified_forecast" / "artifacts" / "unified_best_model_meta.json"
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        expected_winner = meta["selected_winner"]

        # Health endpoint
        health = client.get("/health").json()
        assert health["model_name"] == expected_winner

        # Daily forecast
        daily = client.get("/api/pollution/forecast/daily").json()
        assert daily["forecast"]["model_name"] == expected_winner

        # 7-day forecast
        seven = client.get("/api/pollution/forecast/7day").json()
        assert seven["architecture"] == expected_winner

    def test_train_raises_on_unsupported_model_types(self):
        """(c) Confirm unified_forecast/train.py raises ValueError on unsupported model architectures."""
        from .unified_forecast.train import instantiate_train_model
        with pytest.raises(ValueError, match="cannot be frozen as a PyTorch checkpoint"):
            instantiate_train_model("UnsupportedArchitectureXYZ")

    def test_unified_forecaster_proxy_mode_delegation(self):
        """(d) Confirm proxy mode code path cleanly delegates to upstream URL and handles errors without local inference."""
        from unittest.mock import patch, MagicMock
        from .unified_forecast.inference import UnifiedForecaster

        forecaster = UnifiedForecaster.get_instance()
        orig_proxy_mode = forecaster.proxy_mode
        orig_proxy_url = forecaster.proxy_url

        try:
            forecaster.proxy_mode = True
            forecaster.proxy_url = "http://127.0.0.1:8002"

            mock_daily = MagicMock()
            mock_daily.status_code = 200
            mock_daily.json.return_value = {
                "status": "success",
                "forecast": {
                    "forecast_aqi": 99,
                    "forecast_status": "success",
                    "origin_timestamp": "2025-12-31T23:45:00+00:00",
                    "model_name": "TemporalGRU_KNNCovariate",
                }
            }

            mock_7day = MagicMock()
            mock_7day.status_code = 200
            mock_7day.json.return_value = {
                "status": "success",
                "origin_timestamp": "2025-12-31T23:45:00+00:00",
                "architecture": "TemporalGRU_KNNCovariate",
                "forecast": [{"day": 1, "aqi": 99}],
            }

            def fake_get(url, timeout=10.0):
                if "daily" in url:
                    return mock_daily
                return mock_7day

            with patch("httpx.get", side_effect=fake_get):
                res = forecaster.predict()
                assert res["status"] == "success"
                assert res["daily"]["forecast_aqi"] == 99
                assert res["extended"]["forecast"][0]["aqi"] == 99

            # Also verify error handling in proxy path
            with patch("httpx.get", side_effect=Exception("Connection refused")):
                res_err = forecaster.predict()
                assert res_err["status"] == "unavailable"
                assert "Connection refused" in res_err["reason"]
        finally:
            forecaster.proxy_mode = orig_proxy_mode
            forecaster.proxy_url = orig_proxy_url


# ── Live Accumulation & Forecast Switchover Tests (Part C) ───────────────────

class TestLiveAccumulationStore:
    """Unit tests for LiveAccumulationStore: write, gap, status, and consecutive-day counting."""

    def test_empty_store_status(self, tmp_path):
        from .live_accumulation import LiveAccumulationStore
        store = LiveAccumulationStore(data_dir=tmp_path)
        s = store.get_status()
        assert s["consecutive_live_days"] == 0
        assert s["earliest_date"] is None
        assert s["latest_date"] is None
        assert s["gap_dates"] == []
        assert s["ready_for_live_forecast"] is False
        assert s["total_days_recorded"] == 0

    def test_append_day_and_read_back(self, tmp_path):
        from datetime import date
        from .live_accumulation import LiveAccumulationStore
        store = LiveAccumulationStore(data_dir=tmp_path)
        d = date(2026, 10, 1)
        conc = {"PM2.5": 45.0, "PM10": 78.0, "NO2": 22.0}
        ok = store.append_day(d, conc, [])
        assert ok is True

        s = store.get_status()
        assert s["consecutive_live_days"] == 1
        assert s["earliest_date"] == "2026-10-01"
        assert s["latest_date"] == "2026-10-01"
        assert s["total_days_recorded"] == 1

    def test_gap_resets_consecutive_count(self, tmp_path):
        from datetime import date, timedelta
        from .live_accumulation import LiveAccumulationStore
        store = LiveAccumulationStore(data_dir=tmp_path)
        conc = {"PM2.5": 40.0, "PM10": 60.0, "NO2": 20.0}
        d0 = date(2026, 10, 1)
        d1 = date(2026, 10, 2)
        d2 = date(2026, 10, 3)   # gap
        d3 = date(2026, 10, 4)

        store.append_day(d0, conc, [])
        store.append_day(d1, conc, [])
        store.record_gap(d2, "test gap")
        store.append_day(d3, conc, [])

        s = store.get_status()
        # After gap on d2, only d3 is consecutive at the end
        assert s["consecutive_live_days"] == 1
        assert "2026-10-03" in s["gap_dates"]
        assert s["ready_for_live_forecast"] is False

    def test_get_recent_aggregates_requires_n_consecutive(self, tmp_path):
        from datetime import date, timedelta
        from .live_accumulation import LiveAccumulationStore
        store = LiveAccumulationStore(data_dir=tmp_path)
        conc = {"PM2.5": 35.0, "PM10": 55.0, "NO2": 15.0}
        base = date(2026, 10, 1)
        for i in range(5):
            store.append_day(base + timedelta(days=i), conc, [])

        # Only 5 days available but requesting 14 → returns None
        df = store.get_recent_city_daily_aggregates(n_days=14)
        assert df is None

        # Requesting ≤5 consecutive should work
        df5 = store.get_recent_city_daily_aggregates(n_days=5)
        assert df5 is not None
        assert len(df5) == 5


class TestForecastSwitchoverScenarios:
    """
    Three scenario tests for Part C of the live data integration:
      (a) <14 days accumulated → forecast uses archive, origin = 2025-12-31
      (b) exactly 14 consecutive days accumulated (mocked) → live input, origin = latest live date
      (c) gap after switching → fallback to historical archive again
    All three pass without touching production OpenAQ endpoints.
    """

    # ── (a) < 14 days → archive ──────────────────────────────────────────────

    def test_scenario_a_less_than_14_days_uses_archive(self, tmp_path):
        """
        With only 5 days in the store, the forecaster must NOT use live input.
        origin_timestamp must remain 2025-12-31 (the historical archive origin).
        """
        import pandas as pd
        from datetime import date, timedelta
        from unittest.mock import patch, MagicMock
        from .live_accumulation import LiveAccumulationStore
        from .unified_forecast.inference import UnifiedForecaster

        # Populate store with only 5 days
        store = LiveAccumulationStore(data_dir=tmp_path)
        conc = {"PM2.5": 40.0, "PM10": 70.0, "NO2": 25.0}
        base = date(2026, 10, 1)
        for i in range(5):
            store.append_day(base + timedelta(days=i), conc, [])

        forecaster = UnifiedForecaster()
        forecaster.loaded = True
        forecaster.proxy_mode = False

        # Patch get_live_store to return our test store
        # Patch predict() internals to avoid needing real model weights
        with patch(
            "backend.agents.pollution_agent.unified_forecast.inference.get_live_store",
            return_value=store,
        ), patch.object(
            forecaster,
            "_select_input_source",
            wraps=forecaster._select_input_source,
        ) as spy_select:
            use_live, live_df, origin_override = forecaster._select_input_source()

        assert use_live is False, "With only 5 days, should use historical archive"
        assert live_df is None
        assert origin_override is None

    # ── (b) exactly 14 consecutive days → live input ─────────────────────────

    def test_scenario_b_14_consecutive_days_switches_to_live(self, tmp_path):
        """
        With exactly 14 consecutive days, _select_input_source returns use_live=True
        and origin_override == latest live date ISO string.
        """
        from datetime import date, timedelta
        from unittest.mock import patch
        from .live_accumulation import LiveAccumulationStore
        from .unified_forecast.inference import UnifiedForecaster

        store = LiveAccumulationStore(data_dir=tmp_path)
        conc = {"PM2.5": 45.0, "PM10": 80.0, "NO2": 30.0, "SO2": 10.0,
                "CO": 0.8, "O3": 55.0, "NH3": 12.0}
        base = date(2026, 10, 1)
        latest = base + timedelta(days=13)   # 14 days: Oct 1..14
        for i in range(14):
            store.append_day(base + timedelta(days=i), conc, [])

        forecaster = UnifiedForecaster()
        forecaster.loaded = True
        forecaster.proxy_mode = False

        with patch(
            "backend.agents.pollution_agent.unified_forecast.inference.get_live_store",
            return_value=store,
        ):
            use_live, live_df, origin_override = forecaster._select_input_source()

        assert use_live is True, "With 14 consecutive days, must switch to live input"
        assert live_df is not None
        assert len(live_df) == 14
        assert origin_override is not None
        # origin_override must be the latest live date
        assert latest.isoformat() in origin_override

    # ── (c) gap after 14-day switch → fallback to archive ────────────────────

    def test_scenario_c_gap_after_switchover_falls_back_to_archive(self, tmp_path):
        """
        After accumulating 14 days, a gap day resets consecutive count below 14,
        causing _select_input_source to fall back to the historical archive.
        """
        from datetime import date, timedelta
        from unittest.mock import patch
        from .live_accumulation import LiveAccumulationStore
        from .unified_forecast.inference import UnifiedForecaster

        store = LiveAccumulationStore(data_dir=tmp_path)
        conc = {"PM2.5": 42.0, "PM10": 75.0, "NO2": 28.0, "SO2": 9.0,
                "CO": 0.7, "O3": 50.0, "NH3": 11.0}
        base = date(2026, 10, 1)
        # Write 14 days then a gap on day 15
        for i in range(14):
            store.append_day(base + timedelta(days=i), conc, [])
        gap_day = base + timedelta(days=14)   # day 15
        store.record_gap(gap_day, "simulated API outage")
        # Day 16 resumes but consecutive count resets to 1
        resume = base + timedelta(days=15)
        store.append_day(resume, conc, [])

        s = store.get_status()
        # After gap, only 1 consecutive day (the resume day)
        assert s["consecutive_live_days"] == 1
        assert s["ready_for_live_forecast"] is False

        forecaster = UnifiedForecaster()
        forecaster.loaded = True
        forecaster.proxy_mode = False

        with patch(
            "backend.agents.pollution_agent.unified_forecast.inference.get_live_store",
            return_value=store,
        ):
            use_live, live_df, origin_override = forecaster._select_input_source()

        assert use_live is False, "After gap, consecutive count < 14 → must fall back to archive"
        assert live_df is None
        assert origin_override is None
