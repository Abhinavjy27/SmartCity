"""
Reproducible Training and Model Selection Pipeline for Hyderabad 7-Day Forecasting.
Runs benchmarks across all candidates, context lengths, and ablations.
Selects best model via validation set; evaluates final winner and baselines on held-out test set.
"""
import copy
import json
import logging
import random
import time
from pathlib import Path
from typing import Dict, Any, Tuple

import joblib
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from .config import (
    ARTIFACTS_DIR,
    RANDOM_SEED,
    BATCH_SIZE,
    LEARNING_RATE,
    NUM_EPOCHS,
    PATIENCE,
    WEIGHT_DECAY,
    PRIMARY_TARGETS,
    FORECAST_HORIZON,
    CONTEXT_LENGTHS,
    DEFAULT_CONTEXT_LENGTH,
    TRAIN_START_DATE,
    TRAIN_END_DATE,
    VAL_START_DATE,
    VAL_END_DATE,
    TEST_START_DATE,
    TEST_END_DATE,
)
from .dataset import ForecastingDataset
from .models import (
    PersistenceForecaster,
    SeasonalNaiveForecaster,
    RidgeForecaster,
    GRUForecaster,
    TCNForecaster,
    PatchTSTForecaster,
)
from .evaluate import (
    evaluate_pollutant_metrics,
    evaluate_cpcb_aqi_metrics,
    evaluate_ganesh_day1_baseline,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def set_seed(seed: int = RANDOM_SEED):
    """Ensure strict reproducibility across Python, NumPy, and PyTorch."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def train_torch_model(
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    num_epochs: int = NUM_EPOCHS,
    lr: float = LEARNING_RATE,
    patience: int = PATIENCE,
    weight_decay: float = WEIGHT_DECAY,
    device: str = "cpu",
) -> Tuple[nn.Module, float, float]:
    """Train PyTorch model using AdamW, MSE loss, and early stopping on validation loss."""
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    criterion = nn.MSELoss()

    best_val_loss = float("inf")
    best_weights = copy.deepcopy(model.state_dict())
    epochs_no_improve = 0

    start_time = time.time()

    for epoch in range(num_epochs):
        # Training loop
        model.train()
        train_loss = 0.0
        for bx, by in train_loader:
            bx, by = bx.to(device), by.to(device)
            optimizer.zero_grad()
            preds = model(bx)
            loss = criterion(preds, by)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            train_loss += loss.item() * len(bx)
        train_loss /= len(train_loader.dataset)

        # Validation loop
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for bx, by in val_loader:
                bx, by = bx.to(device), by.to(device)
                preds = model(bx)
                loss = criterion(preds, by)
                val_loss += loss.item() * len(bx)
        val_loss /= len(val_loader.dataset)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_weights = copy.deepcopy(model.state_dict())
            epochs_no_improve = 0
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= patience:
                break

    train_duration = time.time() - start_time
    model.load_state_dict(best_weights)
    return model, best_val_loss, train_duration


def run_experiments() -> Dict[str, Any]:
    """
    Executes the entire research experimentation suite:
    1. Context Length Comparison (7, 14, 30 days)
    2. Feature Ablation Study (Pollutants, Temporal, All)
    3. Baseline & Deep Learning Benchmarking
    4. Validation-based Model Selection
    5. Final Held-Out Test Evaluation & Ganesh Baseline Comparison
    6. Artifact Persistence
    """
    set_seed(RANDOM_SEED)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")

    results = {
        "metadata": {
            "random_seed": RANDOM_SEED,
            "train_period": [TRAIN_START_DATE, TRAIN_END_DATE],
            "val_period": [VAL_START_DATE, VAL_END_DATE],
            "test_period": [TEST_START_DATE, TEST_END_DATE],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "primary_targets": PRIMARY_TARGETS,
            "horizon": FORECAST_HORIZON,
        },
        "context_length_experiments": {},
        "ablation_experiments": {},
        "model_benchmarks_validation": {},
        "model_benchmarks_test": {},
        "best_model_selection": {},
    }

    # ──────────────────────────────────────────────────────────
    # 1. Context Length Ablation (Controlled across 7d, 14d, 30d on Pollution Features)
    # ──────────────────────────────────────────────────────────
    logger.info("=== 1. Evaluating Historical Context Lengths (7, 14, 30 days) ===")
    for ctx in CONTEXT_LENGTHS:
        ds = ForecastingDataset(context_length=ctx, ablation_type="pollutants")
        ds.prepare_data()
        X_tr, Y_tr, _ = ds.get_arrays("train")
        X_val, Y_val, _ = ds.get_arrays("val")

        # Train GRU
        gru_c = GRUForecaster(input_dim=X_tr.shape[2], hidden_dim=64, num_layers=2, dropout=0.2)
        train_loader = DataLoader(TensorDataset(torch.tensor(X_tr), torch.tensor(Y_tr)), batch_size=BATCH_SIZE, shuffle=True)
        val_loader = DataLoader(TensorDataset(torch.tensor(X_val), torch.tensor(Y_val)), batch_size=BATCH_SIZE, shuffle=False)
        gru_c, _, c_time = train_torch_model(gru_c, train_loader, val_loader, device=device)
        with torch.no_grad():
            gru_val_pred = gru_c(torch.tensor(X_val).to(device)).cpu().numpy()
        val_pred_real = ds.inverse_transform_targets(gru_val_pred)
        val_true_real = ds.inverse_transform_targets(Y_val)
        val_metrics = evaluate_pollutant_metrics(val_true_real, val_pred_real)
        val_aqi = evaluate_cpcb_aqi_metrics(val_true_real, val_pred_real)

        results["context_length_experiments"][f"context_{ctx}d"] = {
            "context_days": ctx,
            "train_samples": len(X_tr),
            "val_samples": len(X_val),
            "model_architecture": "MultiOutput_GRU",
            "feature_set": "pollutants_only (6 feats)",
            "val_macro_MAE": val_metrics["overall"]["macro_MAE"],
            "val_macro_RMSE": val_metrics["overall"]["macro_RMSE"],
            "val_macro_R2": val_metrics["overall"]["macro_R2"],
            "val_AQI_MAE": val_aqi["overall"]["AQI_MAE"],
            "val_category_accuracy_pct": val_aqi["overall"]["Category_Accuracy_Pct"],
            "train_time_sec": round(c_time, 2),
        }
        logger.info(
            f"Context {ctx}d (GRU): Val Macro MAE={val_metrics['overall']['macro_MAE']}, "
            f"Macro R2={val_metrics['overall']['macro_R2']}, AQI MAE={val_aqi['overall']['AQI_MAE']}"
        )

    # ──────────────────────────────────────────────────────────
    # 2. Feature Ablation Study (Controlled at C=14d on GRU)
    # ──────────────────────────────────────────────────────────
    logger.info("=== 2. Evaluating Feature Ablations (Pollutants, Temporal, All) ===")
    ablations = ["pollutants", "temporal", "all"]
    for ab in ablations:
        ds = ForecastingDataset(context_length=14, ablation_type=ab)
        ds.prepare_data()
        X_tr, Y_tr, _ = ds.get_arrays("train")
        X_val, Y_val, _ = ds.get_arrays("val")

        gru_ab = GRUForecaster(input_dim=X_tr.shape[2], hidden_dim=64, num_layers=2, dropout=0.2)
        train_loader = DataLoader(TensorDataset(torch.tensor(X_tr), torch.tensor(Y_tr)), batch_size=BATCH_SIZE, shuffle=True)
        val_loader = DataLoader(TensorDataset(torch.tensor(X_val), torch.tensor(Y_val)), batch_size=BATCH_SIZE, shuffle=False)
        gru_ab, _, ab_time = train_torch_model(gru_ab, train_loader, val_loader, device=device)
        with torch.no_grad():
            ab_val_pred = gru_ab(torch.tensor(X_val).to(device)).cpu().numpy()
        val_pred_real = ds.inverse_transform_targets(ab_val_pred)
        val_true_real = ds.inverse_transform_targets(Y_val)
        val_metrics = evaluate_pollutant_metrics(val_true_real, val_pred_real)
        val_aqi = evaluate_cpcb_aqi_metrics(val_true_real, val_pred_real)

        results["ablation_experiments"][ab] = {
            "feature_set": ab,
            "num_features": X_tr.shape[2],
            "context_days": 14,
            "model_architecture": "MultiOutput_GRU",
            "feature_columns": ds.feature_cols,
            "val_macro_MAE": val_metrics["overall"]["macro_MAE"],
            "val_macro_RMSE": val_metrics["overall"]["macro_RMSE"],
            "val_macro_R2": val_metrics["overall"]["macro_R2"],
            "val_AQI_MAE": val_aqi["overall"]["AQI_MAE"],
            "val_category_accuracy_pct": val_aqi["overall"]["Category_Accuracy_Pct"],
            "train_time_sec": round(ab_time, 2),
        }
        logger.info(
            f"Ablation '{ab}' ({X_tr.shape[2]} feats): Val Macro MAE={val_metrics['overall']['macro_MAE']}, "
            f"Macro R2={val_metrics['overall']['macro_R2']}, AQI MAE={val_aqi['overall']['AQI_MAE']}"
        )

    # ──────────────────────────────────────────────────────────
    # 3. Model Candidates Benchmarking (Strictly on Validation Set)
    # ──────────────────────────────────────────────────────────
    logger.info("=== 3. Benchmarking Candidate Models on Validation Set ===")
    # Primary dataset with 30-day context and all features (pollutants + cyclical + in-situ meteo)
    ds_main = ForecastingDataset(context_length=DEFAULT_CONTEXT_LENGTH, ablation_type="all")
    ds_main.prepare_data()

    X_train, Y_train, train_meta = ds_main.get_arrays("train", normalize=True)
    X_val, Y_val, val_meta = ds_main.get_arrays("val", normalize=True)
    X_test, Y_test, test_meta = ds_main.get_arrays("test", normalize=True)

    Y_val_real = ds_main.inverse_transform_targets(Y_val)
    Y_test_real = ds_main.inverse_transform_targets(Y_test)

    input_dim = X_train.shape[2]

    # DataLoader for PyTorch models
    train_dataset = TensorDataset(torch.tensor(X_train), torch.tensor(Y_train))
    val_dataset = TensorDataset(torch.tensor(X_val), torch.tensor(Y_val))
    test_dataset = TensorDataset(torch.tensor(X_test), torch.tensor(Y_test))

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False)

    candidates: Dict[str, Any] = {}

    # A. Persistence Baseline
    p_model = PersistenceForecaster()
    p_val_pred = ds_main.inverse_transform_targets(p_model.predict(X_val))
    candidates["Persistence"] = {
        "type": "baseline",
        "model_obj": p_model,
        "val_pred": p_val_pred,
        "train_time_sec": 0.0
    }

    # B. Seasonal-Naive Baseline
    sn_model = SeasonalNaiveForecaster()
    sn_val_pred = ds_main.inverse_transform_targets(sn_model.predict(X_val))
    candidates["Seasonal_Naive"] = {
        "type": "baseline",
        "model_obj": sn_model,
        "val_pred": sn_val_pred,
        "train_time_sec": 0.0
    }

    # C. Classical Multi-Output Ridge
    t0 = time.time()
    ridge_model = RidgeForecaster(alpha=10.0)
    ridge_model.fit(X_train, Y_train)
    r_time = time.time() - t0
    r_val_pred = ds_main.inverse_transform_targets(ridge_model.predict(X_val))
    candidates["Ridge_Regression"] = {
        "type": "classical",
        "model_obj": ridge_model,
        "val_pred": r_val_pred,
        "train_time_sec": round(r_time, 2)
    }

    # D. Multi-Output GRU
    logger.info("Training Multi-Output GRU...")
    gru_model = GRUForecaster(input_dim=input_dim, hidden_dim=64, num_layers=2, dropout=0.2)
    gru_model, _, gru_time = train_torch_model(gru_model, train_loader, val_loader, device=device)
    gru_model.eval()
    with torch.no_grad():
        gru_val_norm = gru_model(torch.tensor(X_val).to(device)).cpu().numpy()
    gru_val_pred = ds_main.inverse_transform_targets(gru_val_norm)
    candidates["MultiOutput_GRU"] = {
        "type": "deep_learning",
        "model_obj": gru_model,
        "val_pred": gru_val_pred,
        "train_time_sec": round(gru_time, 2)
    }

    # E. Temporal Convolutional Network (TCN)
    logger.info("Training Temporal Convolutional Network (TCN)...")
    tcn_model = TCNForecaster(input_dim=input_dim, num_channels=[32, 64, 64], kernel_size=3, dropout=0.2)
    tcn_model, _, tcn_time = train_torch_model(tcn_model, train_loader, val_loader, device=device)
    tcn_model.eval()
    with torch.no_grad():
        tcn_val_norm = tcn_model(torch.tensor(X_val).to(device)).cpu().numpy()
    tcn_val_pred = ds_main.inverse_transform_targets(tcn_val_norm)
    candidates["TCN"] = {
        "type": "deep_learning",
        "model_obj": tcn_model,
        "val_pred": tcn_val_pred,
        "train_time_sec": round(tcn_time, 2)
    }

    # F. PatchTST / Linear Transformer
    logger.info("Training PatchTST Transformer...")
    patchtst_model = PatchTSTForecaster(
        input_dim=input_dim,
        context_length=DEFAULT_CONTEXT_LENGTH,
        patch_len=6,
        stride=3,
        d_model=48,
        n_heads=4,
        num_layers=2,
        dropout=0.2,
    )
    patchtst_model, _, ptst_time = train_torch_model(patchtst_model, train_loader, val_loader, device=device)
    patchtst_model.eval()
    with torch.no_grad():
        ptst_val_norm = patchtst_model(torch.tensor(X_val).to(device)).cpu().numpy()
    ptst_val_pred = ds_main.inverse_transform_targets(ptst_val_norm)
    candidates["PatchTST"] = {
        "type": "modern_transformer",
        "model_obj": patchtst_model,
        "val_pred": ptst_val_pred,
        "train_time_sec": round(ptst_time, 2)
    }

    # Evaluate all candidates on Validation Set
    val_rankings = []
    for name, c_info in candidates.items():
        val_pred = c_info["val_pred"]
        p_metrics = evaluate_pollutant_metrics(Y_val_real, val_pred)
        aqi_metrics = evaluate_cpcb_aqi_metrics(Y_val_real, val_pred)

        summary_score = {
            "model": name,
            "type": c_info["type"],
            "training_time_seconds": c_info["train_time_sec"],
            "pollutant_metrics": p_metrics,
            "aqi_metrics": aqi_metrics,
            "overall_pollutant_MAE": p_metrics["overall"]["MAE"],
            "overall_pollutant_RMSE": p_metrics["overall"]["RMSE"],
            "overall_pollutant_R2": p_metrics["overall"]["R2"],
            "overall_AQI_MAE": aqi_metrics["overall"]["AQI_MAE"],
            "overall_Category_Accuracy_Pct": aqi_metrics["overall"]["Category_Accuracy_Pct"],
        }
        results["model_benchmarks_validation"][name] = summary_score
        val_rankings.append((name, p_metrics["overall"]["MAE"], aqi_metrics["overall"]["AQI_MAE"]))

        logger.info(
            f"Validation [{name}]: Pollutant MAE={p_metrics['overall']['MAE']}, "
            f"R2={p_metrics['overall']['R2']}, AQI MAE={aqi_metrics['overall']['AQI_MAE']}, "
            f"CatAcc={aqi_metrics['overall']['Category_Accuracy_Pct']}%"
        )

    # ──────────────────────────────────────────────────────────
    # 4. Model Selection (Based on Validation Performance)
    # ──────────────────────────────────────────────────────────
    # Select candidate with lowest Validation Pollutant MAE and highest Category Accuracy
    val_rankings.sort(key=lambda x: (x[1], x[2]))
    winner_name = val_rankings[0][0]
    winner_info = candidates[winner_name]

    results["best_model_selection"] = {
        "selected_model": winner_name,
        "selection_criterion": "Lowest Validation Pollutant MAE & CPCB AQI MAE without test set leakage",
        "validation_pollutant_MAE": results["model_benchmarks_validation"][winner_name]["overall_pollutant_MAE"],
        "validation_AQI_MAE": results["model_benchmarks_validation"][winner_name]["overall_AQI_MAE"],
        "validation_category_acc_pct": results["model_benchmarks_validation"][winner_name]["overall_Category_Accuracy_Pct"],
    }
    logger.info(f"=== WINNING MODEL SELECTED: {winner_name} ===")

    # ──────────────────────────────────────────────────────────
    # 5. Final Evaluation on Held-Out Test Set (Oct-Dec 2025)
    # ──────────────────────────────────────────────────────────
    logger.info("=== 5. Final Comparative Evaluation on Held-Out Test Set ===")
    for name, c_info in candidates.items():
        m_obj = c_info["model_obj"]
        if name in ("Persistence", "Seasonal_Naive"):
            test_pred_norm = m_obj.predict(X_test)
        elif name == "Ridge_Regression":
            test_pred_norm = m_obj.predict(X_test)
        else:
            m_obj.eval()
            with torch.no_grad():
                test_pred_norm = m_obj(torch.tensor(X_test).to(device)).cpu().numpy()

        test_pred_real = ds_main.inverse_transform_targets(test_pred_norm)
        test_p_metrics = evaluate_pollutant_metrics(Y_test_real, test_pred_real)
        test_aqi_metrics = evaluate_cpcb_aqi_metrics(Y_test_real, test_pred_real)

        results["model_benchmarks_test"][name] = {
            "model": name,
            "pollutant_metrics": test_p_metrics,
            "aqi_metrics": test_aqi_metrics,
            "overall_pollutant_MAE": test_p_metrics["overall"]["MAE"],
            "overall_pollutant_RMSE": test_p_metrics["overall"]["RMSE"],
            "overall_pollutant_R2": test_p_metrics["overall"]["R2"],
            "overall_AQI_MAE": test_aqi_metrics["overall"]["AQI_MAE"],
            "overall_Category_Accuracy_Pct": test_aqi_metrics["overall"]["Category_Accuracy_Pct"],
        }
        logger.info(
            f"Test [{name}]: Pollutant MAE={test_p_metrics['overall']['MAE']}, "
            f"R2={test_p_metrics['overall']['R2']}, AQI MAE={test_aqi_metrics['overall']['AQI_MAE']}, "
            f"CatAcc={test_aqi_metrics['overall']['Category_Accuracy_Pct']}%"
        )

    # ──────────────────────────────────────────────────────────
    # 6. Compare against Frozen Ganesh BiLSTM Baseline for Day 1
    # ──────────────────────────────────────────────────────────
    logger.info("Evaluating Frozen Ganesh BiLSTM on Test Set (Day 1)...")
    ganesh_res = evaluate_ganesh_day1_baseline(test_meta)
    results["ganesh_day1_comparison"] = {
        "ganesh_baseline": ganesh_res,
        "winning_model_day1": {
            "model": winner_name,
            "AQI_MAE": results["model_benchmarks_test"][winner_name]["aqi_metrics"]["by_horizon"]["D1"]["AQI_MAE"],
            "AQI_RMSE": results["model_benchmarks_test"][winner_name]["aqi_metrics"]["by_horizon"]["D1"]["AQI_RMSE"],
            "Category_Accuracy_Pct": results["model_benchmarks_test"][winner_name]["aqi_metrics"]["by_horizon"]["D1"]["Category_Accuracy_Pct"],
        }
    }

    # ──────────────────────────────────────────────────────────
    # 7. Save Artifacts for Production Inference
    # ──────────────────────────────────────────────────────────
    logger.info("=== 7. Saving Reproducible Model Artifacts ===")
    winner_model = winner_info["model_obj"]

    # Save model weights / estimator
    if isinstance(winner_model, nn.Module):
        model_path = ARTIFACTS_DIR / "best_model.pt"
        torch.save({
            "model_state_dict": winner_model.state_dict(),
            "model_architecture": winner_name,
            "input_dim": input_dim,
            "context_length": DEFAULT_CONTEXT_LENGTH,
            "horizon": FORECAST_HORIZON,
            "num_targets": len(PRIMARY_TARGETS),
        }, model_path)
    else:
        model_path = ARTIFACTS_DIR / "best_model.joblib"
        joblib.dump(winner_model, model_path)

    # Save scalers
    scalers_path = ARTIFACTS_DIR / "scalers.joblib"
    joblib.dump({
        "feature_scaler": ds_main.feature_scaler,
        "target_scaler": ds_main.target_scaler,
        "feature_cols": ds_main.feature_cols,
        "target_cols": ds_main.target_cols,
    }, scalers_path)

    # Save metadata
    meta_path = ARTIFACTS_DIR / "best_model_meta.json"
    meta_content = {
        "model_name": f"hyderabad_7day_{winner_name.lower()}",
        "architecture": winner_name,
        "version": "1.0.0",
        "provenance": "Trained from scratch on TSPCB Hyderabad CAAQMS observations (2024-2025)",
        "training_date_range": [TRAIN_START_DATE, TRAIN_END_DATE],
        "validation_date_range": [VAL_START_DATE, VAL_END_DATE],
        "test_date_range": [TEST_START_DATE, TEST_END_DATE],
        "context_length": DEFAULT_CONTEXT_LENGTH,
        "forecast_horizon": FORECAST_HORIZON,
        "primary_targets": PRIMARY_TARGETS,
        "feature_columns": ds_main.feature_cols,
        "random_seed": RANDOM_SEED,
        "test_metrics": results["model_benchmarks_test"][winner_name],
        "day1_vs_ganesh": results["ganesh_day1_comparison"],
    }
    with open(meta_path, "w") as f:
        json.dump(meta_content, f, indent=2)

    # Save complete experiment results
    results_path = ARTIFACTS_DIR / "experiment_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    logger.info(f"Artifacts successfully saved to {ARTIFACTS_DIR}")
    return results


if __name__ == "__main__":
    run_experiments()
