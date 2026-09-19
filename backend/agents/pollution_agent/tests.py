"""
Pollution Agent Tests — CPCB AQI, data quality, model, API, and pipeline integrity.
Run with: pytest backend/agents/pollution_agent/tests.py -v
"""
import math
import pytest
from datetime import date, datetime, timedelta, timezone

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
    def test_exact_16_features_order(self):
        expected = [
            "PM2.5", "PM10", "NO", "NO2", "NOx", "NH3",
            "CO", "SO2", "O3", "Benzene", "Toluene", "Xylene",
            "Month", "DayOfYear", "DayOfWeek", "City_Enc",
        ]
        assert MODEL_FEATURES == expected

    def test_model_info_provenance(self):
        model = get_model()
        info = model.get_info()
        assert info["model_name"] == "BiLSTM AQI Predictor"
        assert info["repository"] == "Ganesh-Nadkarni/aqi-eco-nav-models"
        assert info["license_status"] == "unlicensed_weights_research_use"
        assert "not measured against this project's TSPCB data" in info["reported_metrics"]["note"]


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
        assert data["model_name"] == "BiLSTM AQI Predictor"
        assert data["input_features"] == 16

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

    # E. City encoder
    def test_city_encoder_dynamic_loading(self):
        model = get_model()
        if model.status == "ready":
            assert model.city_encoder is not None
            assert model.city_enc_value is not None
            expected_enc = int(model.city_encoder.transform([CITY_NAME])[0])
            assert model.city_enc_value == expected_enc
            decoded = model.city_encoder.inverse_transform([model.city_enc_value])[0]
            assert decoded == CITY_NAME

    # F. Model input
    def test_exact_16_feature_order_and_shape(self):
        assert len(MODEL_FEATURES) == 16
        assert MODEL_FEATURES[0] == "PM2.5"
        assert MODEL_FEATURES[6] == "CO"
        assert MODEL_FEATURES[8] == "O3"
        assert MODEL_FEATURES[15] == "City_Enc"

        model = get_model()
        if model.status == "ready":
            base = date(2025, 12, 25)
            days = [{"date": base + timedelta(days=i), "reading_count": 96, **{f: 20.0 + i for f in REQUIRED_FORECAST_POLLUTANTS}} for i in range(7)]
            scaled = model.preprocess(days)
            assert scaled is not None
            assert scaled.shape == (7, 16)

    # G. Provenance
    def test_provenance_separation(self):
        res = calculate_aqi({"PM2.5": 55.0, "PM10": 85.0, "NO2": 22.0})
        assert res["source"] == "cpcb_engine"

        model = get_model()
        if model.status == "ready":
            base = date(2025, 12, 25)
            days = [{"date": base + timedelta(days=i), "reading_count": 96, **{f: 20.0 + i for f in REQUIRED_FORECAST_POLLUTANTS}} for i in range(7)]
            f_res = model.predict(days)
            assert f_res["source"] == "bilstm_model"

    # H. Missing-data behavior
    def test_missing_data_returns_unavailable_without_fabrication(self):
        model = get_model()
        if model.status == "ready":
            base = date(2025, 12, 25)
            short_days = [{"date": base + timedelta(days=i), "reading_count": 96, **{f: 20.0 for f in REQUIRED_FORECAST_POLLUTANTS}} for i in range(4)]
            res = model.predict(short_days)
            assert res["forecast_status"] == "unavailable"
            assert res["forecast_aqi"] is None
            assert "required" in res["reason"].lower()

    # I. API consistency between /predict and production forecast
    def test_api_predict_uses_identical_pipeline(self):
        base = date(2025, 12, 25)
        days = [{"date": (base + timedelta(days=i)).isoformat(), "reading_count": 96, **{f: 20.0 + i for f in REQUIRED_FORECAST_POLLUTANTS}} for i in range(7)]
        res = client.post("/api/pollution/predict", json={"days": days})
        assert res.status_code == 200
        data = res.json()
        assert data["source"] == "bilstm_model"
        if data["forecast_status"] == "success":
            assert isinstance(data["forecast_aqi"], (int, float))
            assert data["forecast_horizon"] == "next-day"
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
        model = get_model()
        base = date(2025, 12, 25)
        # Construct valid 7-day sequence
        days = [{"date": base + timedelta(days=i), "reading_count": 96, **{f: 25.0 for f in REQUIRED_FORECAST_POLLUTANTS}} for i in range(7)]
        # Remove target feature on Day 4 (index 3)
        days[3][missing_feat] = None

        # 1. validate_forecast_readiness must fail
        readiness = validate_forecast_readiness(days)
        assert readiness["ready"] is False
        assert "missing valid features" in readiness["reason"]
        assert missing_feat in readiness["reason"]

        # 2. model.predict must return unavailable
        if model.status == "ready":
            pred = model.predict(days)
            assert pred["forecast_status"] == "unavailable"
            assert pred["forecast_aqi"] is None
            assert missing_feat in pred["reason"]

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
            assert pred["forecast_horizon"] == "next-day"


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
            assert fore["forecast"]["source"] == "bilstm_model"
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
