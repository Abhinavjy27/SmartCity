"""
Comprehensive test suite for the research-grade 7-day multi-horizon forecasting pipeline.
Validates data integrity, leakage prevention, model dimensions, CPCB AQI conversion,
provenance separation, and API contracts.
Run with: pytest backend/agents/pollution_agent/test_forecast_7d.py -v
"""
import pytest
import numpy as np
import torch
from datetime import date, timedelta
from fastapi.testclient import TestClient

from .main import app
from .forecast_7d.config import (
    PRIMARY_TARGETS,
    FORECAST_HORIZON,
    DEFAULT_CONTEXT_LENGTH,
    TRAIN_START_DATE,
    TRAIN_END_DATE,
    VAL_START_DATE,
    VAL_END_DATE,
    TEST_START_DATE,
    TEST_END_DATE,
)
from .forecast_7d.dataset import (
    build_city_daily_dataframe,
    extract_continuous_blocks,
    ForecastingDataset,
    get_feature_columns,
)
from .forecast_7d.models import (
    PersistenceForecaster,
    SeasonalNaiveForecaster,
    RidgeForecaster,
    GRUForecaster,
    TCNForecaster,
    PatchTSTForecaster,
)
from .forecast_7d.evaluate import (
    evaluate_pollutant_metrics,
    evaluate_cpcb_aqi_metrics,
    compute_smape,
    compute_directional_accuracy,
)
from .unified_forecast.inference import UnifiedForecaster
from .aqi_engine import calculate_aqi, get_aqi_category


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ── 1. Data Integrity & Completeness Tests ──
class TestDataIntegrityAndSplits:
    """Verifies daily aggregation logic, continuous sequences, and strict chronological splits."""

    def test_city_daily_dataframe_columns_and_dates(self):
        df = build_city_daily_dataframe()
        assert not df.empty
        assert "date" in df.columns
        for p in PRIMARY_TARGETS:
            assert p in df.columns
        assert len(df) >= 700  # 731 calendar days across 2024-2025

    def test_continuous_blocks_extraction_no_gaps(self):
        df = build_city_daily_dataframe()
        blocks = extract_continuous_blocks(df, PRIMARY_TARGETS)
        assert len(blocks) >= 1
        for block in blocks:
            dt_series = (df_block := block["date"].apply(lambda d: date.fromisoformat(str(d)))).tolist()
            for i in range(len(dt_series) - 1):
                diff = (dt_series[i + 1] - dt_series[i]).days
                assert diff == 1, f"Found gap of {diff} days within supposed continuous block"

    def test_chronological_splits_are_disjoint_and_ordered(self):
        ds = ForecastingDataset(context_length=DEFAULT_CONTEXT_LENGTH, ablation_type="all")
        ds.prepare_data()

        assert len(ds.train_samples) > 0
        assert len(ds.val_samples) > 0
        assert len(ds.test_samples) > 0

        # Verify train targets are all <= TRAIN_END_DATE
        for s in ds.train_samples:
            assert s["last_target_date"] <= TRAIN_END_DATE

        # Verify val targets are strictly within [VAL_START_DATE, VAL_END_DATE]
        for s in ds.val_samples:
            assert s["first_target_date"] >= VAL_START_DATE
            assert s["last_target_date"] <= VAL_END_DATE

        # Verify test targets are strictly within [TEST_START_DATE, TEST_END_DATE]
        for s in ds.test_samples:
            assert s["first_target_date"] >= TEST_START_DATE
            assert s["last_target_date"] <= TEST_END_DATE

        # Verify max train target date is strictly before min val target date
        max_train_date = max(s["last_target_date"] for s in ds.train_samples)
        min_val_date = min(s["first_target_date"] for s in ds.val_samples)
        assert max_train_date < min_val_date

        max_val_date = max(s["last_target_date"] for s in ds.val_samples)
        min_test_date = min(s["first_target_date"] for s in ds.test_samples)
        assert max_val_date < min_test_date


# ── 2. Leakage Prevention Tests ──
class TestLeakagePrevention:
    """Verifies that scalers and preprocessors are fit strictly on training data only."""

    def test_scaler_fitted_strictly_on_train(self):
        ds = ForecastingDataset(context_length=DEFAULT_CONTEXT_LENGTH, ablation_type="all")
        ds.prepare_data()

        # Compute train-only statistics manually
        x_train_flat = np.concatenate([s["x"] for s in ds.train_samples], axis=0)
        expected_mean = np.mean(x_train_flat, axis=0)
        expected_scale = np.std(x_train_flat, axis=0)

        # Scaler means must match train data exactly
        np.testing.assert_allclose(ds.feature_scaler.mean_, expected_mean, rtol=1e-4)
        np.testing.assert_allclose(ds.feature_scaler.scale_, expected_scale, rtol=1e-4)

        # Scaler must NOT equal full-dataset statistics (which would indicate leakage)
        x_all_flat = np.concatenate([s["x"] for s in ds.samples], axis=0)
        all_mean = np.mean(x_all_flat, axis=0)
        assert not np.allclose(ds.feature_scaler.mean_, all_mean, rtol=1e-2), "Scaler leaked full dataset mean!"

    def test_no_future_observation_in_input_features(self):
        ds = ForecastingDataset(context_length=DEFAULT_CONTEXT_LENGTH)
        ds.prepare_data()

        for s in ds.samples[:20]:
            origin_dt = date.fromisoformat(s["origin_date"])
            first_target_dt = date.fromisoformat(s["first_target_date"])
            # Target must be strictly in the future of the origin date
            assert (first_target_dt - origin_dt).days == 1


# ── 3. Model Architecture & Dimensionality Tests ──
class TestModelArchitectures:
    """Verifies that all candidate models adhere to the exact 7x6 multi-horizon contract."""

    @pytest.fixture
    def synthetic_batch(self):
        B, C, F = 8, 30, 17
        X = np.random.randn(B, C, F).astype(np.float32)
        Y = np.random.uniform(10, 150, (B, 7, 6)).astype(np.float32)
        return X, Y

    def test_persistence_shape(self, synthetic_batch):
        X, _ = synthetic_batch
        p = PersistenceForecaster(horizon=7)
        preds = p.predict(X)
        assert preds.shape == (8, 7, 6)

    def test_seasonal_naive_shape(self, synthetic_batch):
        X, _ = synthetic_batch
        sn = SeasonalNaiveForecaster(horizon=7)
        preds = sn.predict(X)
        assert preds.shape == (8, 7, 6)

    def test_ridge_shape(self, synthetic_batch):
        X, Y = synthetic_batch
        rf = RidgeForecaster(horizon=7)
        rf.fit(X, Y)
        preds = rf.predict(X)
        assert preds.shape == (8, 7, 6)

    def test_gru_shape_and_gradient(self, synthetic_batch):
        X, Y = synthetic_batch
        gru = GRUForecaster(input_dim=17, horizon=7, num_targets=6)
        xt = torch.tensor(X, requires_grad=True)
        out = gru(xt)
        assert out.shape == (8, 7, 6)
        loss = out.sum()
        loss.backward()
        assert xt.grad is not None

    def test_tcn_shape(self, synthetic_batch):
        X, _ = synthetic_batch
        tcn = TCNForecaster(input_dim=17, horizon=7, num_targets=6)
        xt = torch.tensor(X)
        out = tcn(xt)
        assert out.shape == (8, 7, 6)

    def test_patchtst_shape(self, synthetic_batch):
        X, _ = synthetic_batch
        ptst = PatchTSTForecaster(input_dim=17, context_length=30, horizon=7, num_targets=6)
        xt = torch.tensor(X)
        out = ptst(xt)
        assert out.shape == (8, 7, 6)


# ── 4. CPCB AQI Engine Integration Tests ──
class TestCPCBAQIIntegration:
    """Verifies that predicted pollutant concentrations deterministically map to CPCB AQI."""

    def test_predicted_pollutants_convert_to_valid_aqi(self):
        # Realistic sample concentrations: PM2.5=45, PM10=85, NO2=25, SO2=12, O3=30, CO=0.8
        sample_concs = {
            "PM2.5": 45.0,
            "PM10": 85.0,
            "NO2": 25.0,
            "SO2": 12.0,
            "O3": 30.0,
            "CO": 0.8,
        }
        res = calculate_aqi(sample_concs)
        assert res.get("aqi") is not None
        assert res["category"] in ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]
        assert res["dominant_pollutant"] in ["PM2.5", "PM10"]

    def test_evaluation_metric_functions(self):
        y_true = np.ones((10, 7, 6)) * 50.0
        y_pred = np.ones((10, 7, 6)) * 55.0
        smape = compute_smape(y_true, y_pred)
        assert 9.0 <= smape <= 10.0

        p_metrics = evaluate_pollutant_metrics(y_true, y_pred)
        assert p_metrics["overall"]["MAE"] == 5.0
        assert "D1" in p_metrics["by_horizon"]
        assert "PM2.5" in p_metrics["by_pollutant"]


# ── 5. Production API & Provenance Separation Tests ──
class TestProduction7DayAPI:
    """Tests the /api/pollution/forecast/7day endpoint and provenance separation."""

    def test_7day_endpoint_contract(self, client):
        res = client.get("/api/pollution/forecast/7day")
        assert res.status_code == 200
        data = res.json()

        assert data["status"] == "success"
        assert "TemporalGRU_KNNCovariate" in data["architecture"] or "TemporalOnlyGRU" in data["architecture"]
        assert "forecast_origin_date" in data
        assert "forecast" in data
        assert len(data["forecast"]) == 7


        # Verify each horizon structure
        for h_idx, entry in enumerate(data["forecast"]):
            assert entry["horizon_days"] == h_idx + 1
            assert "target_date" in entry
            assert "concentrations" in entry
            for p in PRIMARY_TARGETS:
                assert p in entry["concentrations"]
                assert entry["concentrations"][p] >= 0.0  # Physical concentration >= 0
            assert entry["aqi"] is not None
            assert entry["category"] in ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]
            assert entry["dominant_pollutant"] is not None

    def test_summary_includes_extended_forecast(self, client):
        res = client.get("/api/pollution/summary")
        assert res.status_code == 200
        data = res.json()

        assert "extended_forecast" in data
        ext = data["extended_forecast"]
        assert ext["status"] == "success"
        assert len(ext["forecast"]) == 7

    def test_observed_vs_forecast_separation(self, client):
        summary = client.get("/api/pollution/summary").json()
        current = summary["current"]
        daily_forecast = summary["forecast"]
        extended_forecast = summary["extended_forecast"]

        # Current is measured observations via CPCB
        assert current["source"] == "cpcb_engine"
        # Next-day forecast is unified_spatial_temporal_model
        assert daily_forecast["source"] == "unified_spatial_temporal_model"
        # Day 1 in daily equals Day 1 in extended forecast by construction
        assert daily_forecast["forecast_aqi"] == extended_forecast["forecast"][0]["aqi"]
