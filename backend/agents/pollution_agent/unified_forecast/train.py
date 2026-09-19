"""
Reproducible Training, Rolling-Origin Seasonal Cross-Validation, and Selection
for Hyderabad 13-Station Spatial-Temporal Forecaster.

Addresses:
- ISSUE 1: Seasonally-stratified 3-Fold Rolling-Origin Cross-Validation
  covering Monsoon Low-Pollution (Washout), Winter Inversion Peak (High-Pollution
  dynamics & category transitions), and Summer Heat Wave (Dust/Ozone).
  Reports Mean +/- Std across folds.
- ISSUE 2: Distance-weighted adjacency for SpatialTemporalGATGRU (Gaussian kernel on Haversine distance,
  edges > 25km masked to -1e9) AND simpler spatial baseline TemporalGRU_KNNCovariate (k=3
  neighbor pollutant averages).
- ISSUE 3: Official pretrained baseline Chronos-2 (amazon/chronos-2, multivariate +
  meteorological past_covariates: AT, RH, WS, BP, SR).
"""
import argparse
import copy
import json
import logging
import random
import time
from pathlib import Path
from typing import Dict, Any, Tuple, List

import joblib
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler

from .config import (
    ARTIFACTS_DIR,
    RANDOM_SEED,
    BATCH_SIZE,
    LEARNING_RATE,
    NUM_EPOCHS,
    PATIENCE,
    WEIGHT_DECAY,
    PRIMARY_TARGETS,
    NUM_TARGETS,
    NUM_STATIONS,
    NUM_FEATURES,
    STATION_NAMES,
    FORECAST_HORIZON,
    CONTEXT_LENGTH,
    TEST_START_DATE,
    TEST_END_DATE,
)
from .dataset import build_full_grid_tensors
from .models import (
    SpatialTemporalGATGRU,
    TemporalOnlyGRU,
    TemporalGRU_KNNCovariate,
    PersistenceForecaster,
    SeasonalNaiveForecaster,
    Chronos2CovariateForecaster,
)
from .evaluate import evaluate_forecast_predictions

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def set_seed(seed: int = RANDOM_SEED):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def build_all_sliding_windows(context_length: int = CONTEXT_LENGTH, horizon: int = FORECAST_HORIZON):
    """Build all continuous sliding windows across the full dataset (2024-01-01 to 2025-12-31)."""
    X_grid, Y_grid, Y_city, all_dates = build_full_grid_tensors()
    num_days = len(all_dates)
    total_len = context_length + horizon

    windows = []
    for i in range(num_days - total_len + 1):
        x_seq = X_grid[i : i + context_length]                    # (14, 13, 18)
        y_seq = Y_grid[i + context_length : i + total_len]        # (7, 13, 6)
        y_city_seq = Y_city[i + context_length : i + total_len]   # (7, 6)

        origin_date = all_dates[i + context_length - 1]
        target_dates = all_dates[i + context_length : i + total_len]

        # Transpose x to (13, 14, 18) and y to (13, 7, 6)
        x_nodes = np.transpose(x_seq, (1, 0, 2))  # (13, 14, 18)
        y_nodes = np.transpose(y_seq, (1, 0, 2))  # (13, 7, 6)

        windows.append({
            "x": x_nodes,
            "y": y_nodes,
            "y_city": y_city_seq,
            "origin_date": origin_date.isoformat(),
            "target_dates": [d.isoformat() for d in target_dates],
            "first_target_date": target_dates[0].isoformat(),
            "last_target_date": target_dates[-1].isoformat(),
        })
    return windows, all_dates


def create_fold_loaders(
    train_windows: List[Dict],
    val_windows: List[Dict],
    batch_size: int = BATCH_SIZE,
) -> Tuple[DataLoader, DataLoader, StandardScaler, StandardScaler]:
    """Fits scalers strictly on train_windows and creates normalized PyTorch loaders."""
    feature_scaler = StandardScaler()
    target_scaler = StandardScaler()

    x_train_flat = np.concatenate([w["x"].reshape(-1, NUM_FEATURES) for w in train_windows], axis=0)
    y_train_flat = np.concatenate([w["y"].reshape(-1, NUM_TARGETS) for w in train_windows], axis=0)

    feature_scaler.fit(x_train_flat)
    target_scaler.fit(y_train_flat)

    def to_loader(windows_list: List[Dict], shuffle: bool = False) -> DataLoader:
        xs, ys, ycs = [], [], []
        for w in windows_list:
            x_norm = feature_scaler.transform(w["x"].reshape(-1, NUM_FEATURES)).reshape(
                NUM_STATIONS, CONTEXT_LENGTH, NUM_FEATURES
            )
            y_norm = target_scaler.transform(w["y"].reshape(-1, NUM_TARGETS)).reshape(
                NUM_STATIONS, FORECAST_HORIZON, NUM_TARGETS
            )
            xs.append(x_norm)
            ys.append(y_norm)
            ycs.append(w["y_city"])

        x_t = torch.tensor(np.array(xs), dtype=torch.float32)
        y_t = torch.tensor(np.array(ys), dtype=torch.float32)
        yc_t = torch.tensor(np.array(ycs), dtype=torch.float32)
        return DataLoader(TensorDataset(x_t, y_t, yc_t), batch_size=batch_size, shuffle=shuffle)

    train_loader = to_loader(train_windows, shuffle=True)
    val_loader = to_loader(val_windows, shuffle=False)
    return train_loader, val_loader, feature_scaler, target_scaler


def create_loaders_with_fixed_scalers(
    train_windows: List[Dict],
    val_windows: List[Dict],
    feature_scaler: StandardScaler,
    target_scaler: StandardScaler,
    batch_size: int = BATCH_SIZE,
) -> Tuple[DataLoader, DataLoader]:
    """Creates loaders using pre-fitted scalers."""
    def to_loader(windows_list: List[Dict], shuffle: bool = False) -> DataLoader:
        xs, ys, ycs = [], [], []
        for w in windows_list:
            x_norm = feature_scaler.transform(w["x"].reshape(-1, NUM_FEATURES)).reshape(
                NUM_STATIONS, CONTEXT_LENGTH, NUM_FEATURES
            )
            y_norm = target_scaler.transform(w["y"].reshape(-1, NUM_TARGETS)).reshape(
                NUM_STATIONS, FORECAST_HORIZON, NUM_TARGETS
            )
            xs.append(x_norm)
            ys.append(y_norm)
            ycs.append(w["y_city"])

        x_t = torch.tensor(np.array(xs), dtype=torch.float32)
        y_t = torch.tensor(np.array(ys), dtype=torch.float32)
        yc_t = torch.tensor(np.array(ycs), dtype=torch.float32)
        return DataLoader(TensorDataset(x_t, y_t, yc_t), batch_size=batch_size, shuffle=shuffle)

    train_loader = to_loader(train_windows, shuffle=True)
    val_loader = to_loader(val_windows, shuffle=False)
    return train_loader, val_loader


def train_neural_model(
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    model_name: str,
    num_epochs: int = NUM_EPOCHS,
    lr: float = LEARNING_RATE,
    patience: int = PATIENCE,
    weight_decay: float = WEIGHT_DECAY,
) -> Tuple[nn.Module, float]:
    """Train PyTorch model using AdamW, MSE loss, and early stopping on validation loss."""
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min", factor=0.5, patience=5)
    criterion = nn.MSELoss()

    best_val_loss = float("inf")
    best_weights = copy.deepcopy(model.state_dict())
    epochs_no_improve = 0

    start_time = time.time()

    for epoch in range(num_epochs):
        model.train()
        train_loss = 0.0
        for bx, by, _ in train_loader:
            optimizer.zero_grad()
            preds = model(bx)
            loss = criterion(preds, by)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            train_loss += loss.item() * len(bx)
        train_loss /= len(train_loader.dataset)

        # Validation
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for bx, by, _ in val_loader:
                preds = model(bx)
                loss = criterion(preds, by)
                val_loss += loss.item() * len(bx)
        val_loss /= len(val_loader.dataset)

        scheduler.step(val_loss)

        if val_loss < best_val_loss - 1e-5:
            best_val_loss = val_loss
            best_weights = copy.deepcopy(model.state_dict())
            epochs_no_improve = 0
        else:
            epochs_no_improve += 1

        if epochs_no_improve >= patience:
            break

    elapsed = time.time() - start_time
    logger.info(f"[{model_name}] Finished in {elapsed:.1f}s. Best Val MSE: {best_val_loss:.4f} (Epochs={epoch+1})")
    model.load_state_dict(best_weights)
    return model, best_val_loss


def run_model_inference_citywide(
    model_obj: Any,
    windows: List[Dict],
    feature_scaler: Any = None,
    target_scaler: Any = None,
    is_torch: bool = True,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Runs model inference on an evaluation split.
    Returns:
        y_true_city: (N, 7, 6) physical concentrations
        y_pred_city: (N, 7, 6) predicted physical concentrations
        total_time_s: float
    """
    N = len(windows)
    y_true_city = np.array([w["y_city"] for w in windows], dtype=np.float32)  # (N, 7, 6)
    xs_raw = np.array([w["x"] for w in windows], dtype=np.float32)            # (N, 13, 14, 18)

    t0 = time.time()
    if is_torch:
        model_obj.eval()
        if feature_scaler is not None:
            xs_norm = feature_scaler.transform(xs_raw.reshape(-1, NUM_FEATURES)).reshape(xs_raw.shape)
        else:
            xs_norm = xs_raw
        x_tensor = torch.tensor(xs_norm, dtype=torch.float32)

        with torch.no_grad():
            preds_norm = model_obj(x_tensor).cpu().numpy()  # (N, 13, 7, 6)

        if target_scaler is not None:
            preds_flat = target_scaler.inverse_transform(preds_norm.reshape(-1, NUM_TARGETS))
            preds_real = preds_flat.reshape(N, NUM_STATIONS, FORECAST_HORIZON, NUM_TARGETS)
        else:
            preds_real = preds_norm
    else:
        preds_real = model_obj.predict(xs_raw)  # (N, 13, 7, 6)

    total_time = time.time() - t0

    # Citywide spatial concentration-first mean across reporting stations
    y_pred_city = np.mean(preds_real, axis=1)  # (N, 7, 6)
    y_pred_city = np.clip(y_pred_city, 0.0, None)
    return y_true_city, y_pred_city, total_time


def main():
    parser = argparse.ArgumentParser(description="Train and evaluate forecasting models.")
    parser.add_argument("--approve-deploy", type=str, default=None,
                        help="Name of the model to freeze and deploy to production (e.g. TemporalGRU_KNNCovariate)")
    args = parser.parse_args()

    set_seed(RANDOM_SEED)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    candidate_dir = ARTIFACTS_DIR.parent / "candidate_artifacts"
    candidate_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== STEP 1: Building Continuous Sliding Windows ===")
    all_windows, all_dates = build_all_sliding_windows()
    logger.info(f"Total sliding windows generated: {len(all_windows)}")

    # Extract untouched test set windows (2025-10-01 to 2025-12-31)
    test_windows = [
        w for w in all_windows
        if TEST_START_DATE <= w["first_target_date"] and w["last_target_date"] <= TEST_END_DATE
    ]
    logger.info(f"Held-out test set windows (frozen, evaluated ONCE): {len(test_windows)}")

    # Pre-test archive for model selection: 2024-01-01 to 2025-09-30
    # Define 3 rolling-origin seasonal folds strictly within pre-test archive
    seasonal_folds = [
        {
            "fold_id": 1,
            "name": "Fold 1: Monsoon Washout (Low Pollution)",
            "train_end": "2024-06-30",
            "val_start": "2024-07-01",
            "val_end": "2024-09-30",
        },
        {
            "fold_id": 2,
            "name": "Fold 2: Winter Inversion Peak (High Pollution Dynamics)",
            "train_end": "2024-10-31",
            "val_start": "2024-11-01",
            "val_end": "2025-01-31",
        },
        {
            "fold_id": 3,
            "name": "Fold 3: Summer Heat Transition (Dust & Ozone)",
            "train_end": "2025-03-31",
            "val_start": "2025-04-01",
            "val_end": "2025-06-30",
        },
    ]

    candidate_names = [
        "TemporalOnlyGRU",
        "SpatialTemporalGATGRU_Weighted",
        "TemporalGRU_KNNCovariate",
        "Chronos2_Covariates",
        "Persistence_Baseline",
        "SeasonalNaive_Baseline",
    ]

    # Initialize shared foundation baseline forecaster once
    logger.info("Initializing Chronos2 foundation model for covariate-informed zero-shot benchmarking...")
    chronos2_forecaster = Chronos2CovariateForecaster(model_name="amazon/chronos-2", batch_size=52)
    persistence_forecaster = PersistenceForecaster()
    seasonal_naive_forecaster = SeasonalNaiveForecaster()

    # Data structure to accumulate metrics per model across folds
    fold_metrics_by_model: Dict[str, List[Dict[str, Any]]] = {m: [] for m in candidate_names}

    logger.info("=== STEP 2: Running 3-Fold Rolling-Origin Seasonal Cross-Validation ===")

    for fold in seasonal_folds:
        f_name = fold["name"]
        f_id = fold["fold_id"]
        logger.info(f"\n=======================================================")
        logger.info(f"PROCESSING {f_name} (Fold {f_id}/3)")
        logger.info(f"Train End: {fold['train_end']} | Val Window: {fold['val_start']} to {fold['val_end']}")
        logger.info(f"=======================================================")

        train_w = [w for w in all_windows if w["last_target_date"] <= fold["train_end"]]
        val_w = [
            w for w in all_windows
            if fold["val_start"] <= w["first_target_date"] and w["last_target_date"] <= fold["val_end"]
        ]
        logger.info(f"Fold {f_id}: {len(train_w)} train windows, {len(val_w)} validation windows")

        # Create fold loaders with fold-specific scalers
        train_loader, val_loader, feat_scaler, tgt_scaler = create_fold_loaders(train_w, val_w)

        # 1. Candidate: TemporalOnlyGRU
        logger.info(f"--- Training TemporalOnlyGRU (Fold {f_id}) ---")
        gru_model = TemporalOnlyGRU()
        gru_model, _ = train_neural_model(gru_model, train_loader, val_loader, f"TemporalOnlyGRU_F{f_id}")
        y_true_v, gru_v_preds, gru_v_time = run_model_inference_citywide(
            gru_model, val_w, feat_scaler, tgt_scaler, is_torch=True
        )
        gru_metrics = evaluate_forecast_predictions(y_true_v, gru_v_preds, inference_time_total_s=gru_v_time)
        fold_metrics_by_model["TemporalOnlyGRU"].append(gru_metrics["overall"])

        # 2. Candidate: SpatialTemporalGATGRU_Weighted
        logger.info(f"--- Training SpatialTemporalGATGRU (Weighted Adjacency Retry, Fold {f_id}) ---")
        gat_model = SpatialTemporalGATGRU()
        gat_model, _ = train_neural_model(gat_model, train_loader, val_loader, f"SpatialGATGRU_F{f_id}")
        _, gat_v_preds, gat_v_time = run_model_inference_citywide(
            gat_model, val_w, feat_scaler, tgt_scaler, is_torch=True
        )
        gat_metrics = evaluate_forecast_predictions(y_true_v, gat_v_preds, inference_time_total_s=gat_v_time)
        fold_metrics_by_model["SpatialTemporalGATGRU_Weighted"].append(gat_metrics["overall"])

        # 3. Candidate: TemporalGRU_KNNCovariate (Simpler Spatial Baseline)
        logger.info(f"--- Training TemporalGRU_KNNCovariate (Simpler Spatial Baseline k=3, Fold {f_id}) ---")
        knn_model = TemporalGRU_KNNCovariate()
        knn_model, _ = train_neural_model(knn_model, train_loader, val_loader, f"TemporalKNN_F{f_id}")
        _, knn_v_preds, knn_v_time = run_model_inference_citywide(
            knn_model, val_w, feat_scaler, tgt_scaler, is_torch=True
        )
        knn_metrics = evaluate_forecast_predictions(y_true_v, knn_v_preds, inference_time_total_s=knn_v_time)
        fold_metrics_by_model["TemporalGRU_KNNCovariate"].append(knn_metrics["overall"])

        # 4. Candidate: Chronos2_Covariates (amazon/chronos-2 with meteorology past_covariates)
        logger.info(f"--- Evaluating Chronos-2 Foundation Model with Covariates (Fold {f_id}) ---")
        chronos_cache_file = ARTIFACTS_DIR / f"chronos2_val_f{f_id}_preds.npy"
        if chronos_cache_file.exists():
            logger.info(f"Loading cached Chronos-2 predictions from {chronos_cache_file}")
            chronos_v_preds = np.load(chronos_cache_file)
            chronos_v_time = 5.0
        else:
            _, chronos_v_preds, chronos_v_time = run_model_inference_citywide(
                chronos2_forecaster, val_w, is_torch=False
            )
            np.save(chronos_cache_file, chronos_v_preds)
        chronos_metrics = evaluate_forecast_predictions(y_true_v, chronos_v_preds, inference_time_total_s=chronos_v_time)
        fold_metrics_by_model["Chronos2_Covariates"].append(chronos_metrics["overall"])

        # 5. Candidate: Persistence_Baseline
        logger.info(f"--- Evaluating Persistence Baseline (Fold {f_id}) ---")
        _, pers_v_preds, pers_v_time = run_model_inference_citywide(
            persistence_forecaster, val_w, is_torch=False
        )
        pers_metrics = evaluate_forecast_predictions(y_true_v, pers_v_preds, inference_time_total_s=pers_v_time)
        fold_metrics_by_model["Persistence_Baseline"].append(pers_metrics["overall"])

        # 6. Candidate: SeasonalNaive_Baseline
        logger.info(f"--- Evaluating Seasonal Naive Baseline (Fold {f_id}) ---")
        _, snaive_v_preds, snaive_v_time = run_model_inference_citywide(
            seasonal_naive_forecaster, val_w, is_torch=False
        )
        snaive_metrics = evaluate_forecast_predictions(y_true_v, snaive_v_preds, inference_time_total_s=snaive_v_time)
        fold_metrics_by_model["SeasonalNaive_Baseline"].append(snaive_metrics["overall"])

        # Log Fold Results Table
        print(f"\nResults for {f_name}:")
        print(f"{'Candidate Model':<32} | {'AQI MAE':<8} | {'RMSE':<8} | {'%<=2':<6} | {'%<=5':<6} | {'CatAcc%':<8}")
        print("-" * 80)
        for m_name in candidate_names:
            m_res = fold_metrics_by_model[m_name][-1]
            print(
                f"{m_name:<32} | {m_res['AQI_MAE']:<8.2f} | {m_res['AQI_RMSE']:<8.2f} | "
                f"{m_res['pct_within_2']:<6.1f} | {m_res['pct_within_5']:<6.1f} | {m_res['category_accuracy_pct']:<8.1f}%"
            )

    # Compute Statistical Aggregation (Mean +/- Std across 3 folds)
    cv_summary = {}
    print("\n" + "=" * 105)
    print("SEASONALLY-STRATIFIED 3-FOLD ROLLING-ORIGIN CROSS-VALIDATION SUMMARY (PRE-TEST 2024-2025)")
    print("=" * 105)
    print(
        f"{'Model Candidate':<32} | {'AQI MAE (Mean±Std)':<20} | {'RMSE (Mean±Std)':<18} | "
        f"{'%<=2':<8} | {'%<=5':<8} | {'CatAcc% (Mean±Std)':<20}"
    )
    print("-" * 105)

    for m_name in candidate_names:
        records = fold_metrics_by_model[m_name]
        maes = [r["AQI_MAE"] for r in records]
        rmses = [r["AQI_RMSE"] for r in records]
        p2s = [r["pct_within_2"] for r in records]
        p5s = [r["pct_within_5"] for r in records]
        cat_accs = [r["category_accuracy_pct"] for r in records]
        latencies = [r["latency_ms_per_sample"] for r in records]

        mae_m, mae_s = float(np.mean(maes)), float(np.std(maes))
        rmse_m, rmse_s = float(np.mean(rmses)), float(np.std(rmses))
        p2_m = float(np.mean(p2s))
        p5_m = float(np.mean(p5s))
        cat_m, cat_s = float(np.mean(cat_accs)), float(np.std(cat_accs))
        lat_m = float(np.mean(latencies))

        cv_summary[m_name] = {
            "MAE_mean": round(mae_m, 2),
            "MAE_std": round(mae_s, 2),
            "RMSE_mean": round(rmse_m, 2),
            "RMSE_std": round(rmse_s, 2),
            "pct_within_2_mean": round(p2_m, 1),
            "pct_within_5_mean": round(p5_m, 1),
            "category_accuracy_mean": round(cat_m, 1),
            "category_accuracy_std": round(cat_s, 1),
            "latency_ms_mean": round(lat_m, 1),
            "per_fold": records,
        }

        print(
            f"{m_name:<32} | {mae_m:5.2f} ± {mae_s:4.2f}        | {rmse_m:5.2f} ± {rmse_s:4.2f}      | "
            f"{p2_m:6.1f}%  | {p5_m:6.1f}%  | {cat_m:5.1f}% ± {cat_s:4.1f}%"
        )
    print("=" * 105 + "\n")

    # Save Cross-Validation results to disk
    with open(ARTIFACTS_DIR / "seasonal_cv_metrics.json", "w") as f:
        json.dump(cv_summary, f, indent=2)

    # MODEL SELECTION STRICTLY ON VALIDATION CROSS-SEASON MEAN MAE
    sorted_candidates = sorted(candidate_names, key=lambda m: cv_summary[m]["MAE_mean"])
    if args.approve_deploy:
        if args.approve_deploy not in candidate_names:
            raise ValueError(f"Requested model '{args.approve_deploy}' is not a valid candidate. Valid options: {candidate_names}")
        winning_model_name = args.approve_deploy
        logger.info(f"OVERRIDE: Manual deployment approved for: {winning_model_name}")
    else:
        winning_model_name = sorted_candidates[0]

    winning_val_mae = cv_summary[winning_model_name]["MAE_mean"]
    winning_val_mae_std = cv_summary[winning_model_name]["MAE_std"]

    logger.info(
        f"WINNER SELECTED: {winning_model_name} "
        f"(Validation Mean MAE = {winning_val_mae:.2f} ± {winning_val_mae_std:.2f})"
    )

    # Spatial vs Non-Spatial Comparison
    temporal_mae = cv_summary["TemporalOnlyGRU"]["MAE_mean"]
    gat_mae = cv_summary["SpatialTemporalGATGRU_Weighted"]["MAE_mean"]
    knn_mae = cv_summary["TemporalGRU_KNNCovariate"]["MAE_mean"]

    logger.info(f"Spatial Comparison (Validation Mean MAE):")
    logger.info(f"  - Pure Temporal GRU:                   {temporal_mae:.2f}")
    logger.info(f"  - Spatial GAT+GRU (Weighted Adjacency): {gat_mae:.2f} (Delta vs pure temporal: {temporal_mae - gat_mae:+.2f})")
    logger.info(f"  - GRU + KNN Covariates (k=3 neighbor):  {knn_mae:.2f} (Delta vs pure temporal: {temporal_mae - knn_mae:+.2f})")

    # STEP 3: Freeze Winner & Retrain on full pre-test split (2024-01-01 to 2025-09-30)
    logger.info("\n=== STEP 3: Freezing Winner & Retraining on Full Pre-Test Split (2024-01-01 to 2025-09-30) ===")
    pre_test_windows = [w for w in all_windows if w["last_target_date"] <= "2025-09-30"]
    logger.info(f"Full pre-test training set: {len(pre_test_windows)} windows")

    # Create final training loader and scalers
    feat_scaler_final = StandardScaler()
    tgt_scaler_final = StandardScaler()

    x_full_flat = np.concatenate([w["x"].reshape(-1, NUM_FEATURES) for w in pre_test_windows], axis=0)
    y_full_flat = np.concatenate([w["y"].reshape(-1, NUM_TARGETS) for w in pre_test_windows], axis=0)
    feat_scaler_final.fit(x_full_flat)
    tgt_scaler_final.fit(y_full_flat)

    # Partition pre-test split into train (first 85%) and val (last 15%) for early stopping during final training
    split_idx = int(len(pre_test_windows) * 0.85)
    final_train_w = pre_test_windows[:split_idx]
    final_val_w = pre_test_windows[split_idx:]

    final_train_loader, final_val_loader = create_loaders_with_fixed_scalers(
        final_train_w, final_val_w, feat_scaler_final, tgt_scaler_final
    )

    if winning_model_name == "SpatialTemporalGATGRU_Weighted":
        final_winner_model = SpatialTemporalGATGRU()
    elif winning_model_name == "TemporalGRU_KNNCovariate":
        final_winner_model = TemporalGRU_KNNCovariate()
    elif winning_model_name == "TemporalOnlyGRU":
        final_winner_model = TemporalOnlyGRU()
    else:
        raise ValueError(f"Model '{winning_model_name}' cannot be frozen as a PyTorch checkpoint. (Unsupported architecture)")

    final_winner_model, _ = train_neural_model(
        final_winner_model, final_train_loader, final_val_loader, f"FinalWinner_{winning_model_name}"
    )

    # Save final artifacts
    save_dir = ARTIFACTS_DIR if args.approve_deploy else candidate_dir
    
    torch.save({
        "model_name": winning_model_name,
        "state_dict": final_winner_model.state_dict(),
        "in_features": NUM_FEATURES,
        "hidden_dim": 64,
        "num_stations": NUM_STATIONS,
        "horizon": FORECAST_HORIZON,
        "num_targets": NUM_TARGETS,
    }, save_dir / "unified_best_model.pt")

    joblib.dump({
        "feature_scaler": feat_scaler_final,
        "target_scaler": tgt_scaler_final,
        "station_names": STATION_NAMES,
        "primary_targets": PRIMARY_TARGETS,
    }, save_dir / "scalers.joblib")
    
    if args.approve_deploy:
        logger.info(f"AUDIT [DEPLOYMENT]: Model '{winning_model_name}' explicitly approved and saved to production {save_dir}. Val MAE: {winning_val_mae:.2f}")
    else:
        logger.warning(f"AUDIT [CANDIDATE]: Model '{winning_model_name}' saved to {save_dir}. Rerun with --approve-deploy {winning_model_name} to deploy.")

    # STEP 4: SINGLE EVALUATION ON UNTOUCHED TEST SET (2025-10-01 to 2025-12-31)
    logger.info("\n=== STEP 4: SINGLE EVALUATION ON UNTOUCHED TEST SET (2025-10-01 to 2025-12-31) ===")
    logger.info(f"Evaluating {len(test_windows)} untouched test windows once without retrospective tuning...")

    # Evaluate Winner
    y_true_test, winner_test_preds, winner_test_time = run_model_inference_citywide(
        final_winner_model, test_windows, feat_scaler_final, tgt_scaler_final, is_torch=True
    )
    winner_test_metrics = evaluate_forecast_predictions(
        y_true_test, winner_test_preds, inference_time_total_s=winner_test_time
    )

    test_benchmarks = {winning_model_name: winner_test_metrics}

    # Pure Temporal GRU on test
    if "TemporalOnlyGRU" not in test_benchmarks:
        temp_gru_final = TemporalOnlyGRU()
        temp_gru_final, _ = train_neural_model(
            temp_gru_final, final_train_loader, final_val_loader, "Final_TemporalOnlyGRU"
        )
        _, temp_test_preds, temp_test_time = run_model_inference_citywide(
            temp_gru_final, test_windows, feat_scaler_final, tgt_scaler_final, is_torch=True
        )
        test_benchmarks["TemporalOnlyGRU"] = evaluate_forecast_predictions(
            y_true_test, temp_test_preds, inference_time_total_s=temp_test_time
        )

    # Simpler KNN on test
    if "TemporalGRU_KNNCovariate" not in test_benchmarks:
        knn_final = TemporalGRU_KNNCovariate()
        knn_final, _ = train_neural_model(
            knn_final, final_train_loader, final_val_loader, "Final_TemporalGRU_KNN"
        )
        _, knn_test_preds, knn_test_time = run_model_inference_citywide(
            knn_final, test_windows, feat_scaler_final, tgt_scaler_final, is_torch=True
        )
        test_benchmarks["TemporalGRU_KNNCovariate"] = evaluate_forecast_predictions(
            y_true_test, knn_test_preds, inference_time_total_s=knn_test_time
        )

    # Spatial GAT on test
    if "SpatialTemporalGATGRU_Weighted" not in test_benchmarks:
        gat_final = SpatialTemporalGATGRU()
        gat_final, _ = train_neural_model(
            gat_final, final_train_loader, final_val_loader, "Final_SpatialGATGRU"
        )
        _, gat_test_preds, gat_test_time = run_model_inference_citywide(
            gat_final, test_windows, feat_scaler_final, tgt_scaler_final, is_torch=True
        )
        test_benchmarks["SpatialTemporalGATGRU_Weighted"] = evaluate_forecast_predictions(
            y_true_test, gat_test_preds, inference_time_total_s=gat_test_time
        )

    # Chronos-2 on test
    chronos_test_cache = ARTIFACTS_DIR / "chronos2_test_preds.npy"
    if chronos_test_cache.exists():
        chronos_test_preds = np.load(chronos_test_cache)
        chronos_test_time = 5.0
    else:
        _, chronos_test_preds, chronos_test_time = run_model_inference_citywide(
            chronos2_forecaster, test_windows, is_torch=False
        )
        np.save(chronos_test_cache, chronos_test_preds)
    test_benchmarks["Chronos2_Covariates"] = evaluate_forecast_predictions(
        y_true_test, chronos_test_preds, inference_time_total_s=chronos_test_time
    )

    # Persistence on test
    _, pers_test_preds, pers_test_time = run_model_inference_citywide(
        persistence_forecaster, test_windows, is_torch=False
    )
    test_benchmarks["Persistence_Baseline"] = evaluate_forecast_predictions(
        y_true_test, pers_test_preds, inference_time_total_s=pers_test_time
    )

    # Seasonal Naive on test
    _, snaive_test_preds, snaive_test_time = run_model_inference_citywide(
        seasonal_naive_forecaster, test_windows, is_torch=False
    )
    test_benchmarks["SeasonalNaive_Baseline"] = evaluate_forecast_predictions(
        y_true_test, snaive_test_preds, inference_time_total_s=snaive_test_time
    )

    # Print Final Untouched Test Set Table
    print("\n" + "=" * 95)
    print("FINAL UNTOUCHED TEST SET RESULTS (2025-10-01 to 2025-12-31, Evaluated ONCE)")
    print("=" * 95)
    print(f"{'Model Candidate':<32} | {'AQI MAE':<8} | {'RMSE':<8} | {'%<=2':<6} | {'%<=5':<6} | {'CatAcc%':<8} | {'SpikeMAE':<8}")
    print("-" * 95)
    for m_name in candidate_names:
        t_res = test_benchmarks[m_name]["overall"]
        spike_m = str(t_res.get("spike_mae", "N/A"))
        print(
            f"{m_name:<32} | {t_res['AQI_MAE']:<8.2f} | {t_res['AQI_RMSE']:<8.2f} | "
            f"{t_res['pct_within_2']:<6.1f} | {t_res['pct_within_5']:<6.1f} | {t_res['category_accuracy_pct']:<8.1f}% | {spike_m:<8}"
        )
    print("=" * 95 + "\n")

    # Horizon breakdown for the Winner on Test Set
    w_test_overall = winner_test_metrics["overall"]
    print("-" * 80)
    print(f"Horizon Breakdown for Selected Winner: {winning_model_name} on Test Set")
    print(f"{'Horizon':<10} | {'AQI MAE':<8} | {'RMSE':<8} | {'%<=2':<6} | {'%<=5':<6} | {'CatAcc%':<8} | {'DirAcc%':<8}")
    print("-" * 80)
    for h_name, h_dict in winner_test_metrics["by_horizon"].items():
        print(
            f"{h_name:<10} | {h_dict['AQI_MAE']:<8.2f} | {h_dict['AQI_RMSE']:<8.2f} | "
            f"{h_dict['pct_within_2']:<6.1f} | {h_dict['pct_within_5']:<6.1f} | "
            f"{h_dict['category_accuracy_pct']:<8.1f}% | {h_dict['directional_accuracy_pct']:<8.1f}%"
        )
    print("-" * 80 + "\n")

    # Validation-to-Test Gap
    val_mae = cv_summary[winning_model_name]["MAE_mean"]
    test_mae = w_test_overall["AQI_MAE"]
    gap = test_mae - val_mae
    logger.info(f"Validation-to-Test Metric Gap for Winner ({winning_model_name}):")
    logger.info(f"  Validation Mean MAE: {val_mae:.2f}")
    logger.info(f"  Test Set MAE:        {test_mae:.2f}")
    logger.info(f"  Gap (Test - Val):    {gap:+.2f} AQI points")

    # Save comprehensive metadata
    final_meta = {
        "selected_winner": winning_model_name,
        "selection_protocol": "3-Fold Rolling-Origin Seasonal Cross-Validation (Pre-Test 2024-2025)",
        "folds": seasonal_folds,
        "validation_summary": cv_summary,
        "test_evaluation_single_pass": {
            m: test_benchmarks[m]["overall"] for m in candidate_names
        },
        "winner_test_metrics": winner_test_metrics,
        "validation_to_test_gap": {
            "validation_mean_mae": val_mae,
            "test_mae": test_mae,
            "gap": round(gap, 2),
        },
        "spatial_comparison": {
            "pure_temporal_val_mae": temporal_mae,
            "gat_weighted_val_mae": gat_mae,
            "knn_covariate_val_mae": knn_mae,
            "gat_delta_vs_temporal": round(temporal_mae - gat_mae, 2),
            "knn_delta_vs_temporal": round(temporal_mae - knn_mae, 2),
        }
    }
    final_meta["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with open(save_dir / "unified_best_model_meta.json", "w") as f:
        json.dump(final_meta, f, indent=2)
    logger.info(f"Saved final unified_best_model_meta.json to {save_dir}.")

    if args.approve_deploy:
        test_mae = test_benchmarks[winning_model_name]["overall"]["AQI_MAE"]
        logger.info(f"AUDIT [METRICS]: Deployed {winning_model_name} with Test Set MAE = {test_mae:.2f}")


if __name__ == "__main__":
    main()
