"""
Comprehensive Evaluation Metrics Framework for Unified Pollution Forecasting.
Computes:
- AQI MAE, RMSE
- % predictions within ±2, ±5, ±10 AQI
- CPCB Category Accuracy & Calibration (Precision, Recall, F1)
- Directional Accuracy
- Pollutant MAE, RMSE, sMAPE
- Error during pollution spikes (AQI >= 100)
- Per-horizon D1–D7 metrics breakdown
- Inference latency (ms)
"""
import time
from typing import Dict, List, Tuple, Any, Optional
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, confusion_matrix, precision_recall_fscore_support

from ..aqi_engine import calculate_aqi, get_aqi_category
from .config import PRIMARY_TARGETS, FORECAST_HORIZON

CPCB_CATEGORIES = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]


def compute_smape(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1e-6) -> float:
    denominator = (np.abs(y_true) + np.abs(y_pred)) / 2.0 + eps
    diff = np.abs(y_pred - y_true) / denominator
    return float(np.mean(diff) * 100.0)


def compute_directional_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) < 2:
        return 100.0
    true_diff = np.diff(y_true, axis=0)
    pred_diff = np.diff(y_pred, axis=0)
    matching = np.sign(true_diff) == np.sign(pred_diff)
    return float(np.mean(matching) * 100.0)


def evaluate_forecast_predictions(
    y_true_city: np.ndarray,  # (N_windows, 7, 6) physical concentrations
    y_pred_city: np.ndarray,  # (N_windows, 7, 6) physical concentrations
    pollutant_names: Optional[List[str]] = None,
    inference_time_total_s: float = 0.0,
) -> Dict[str, Any]:
    """
    Evaluates multi-horizon citywide forecasts against true citywide observations.
    Calculates exact AQI using the existing CPCB engine.
    """
    pollutant_names = pollutant_names or PRIMARY_TARGETS
    N, H, T = y_true_city.shape
    y_pred_city = np.clip(y_pred_city, 0.0, None)  # Physical bounds >= 0

    # 1. Compute Pollutant-level metrics
    pollutant_metrics = {}
    macro_maes = []
    macro_rmses = []
    macro_r2s = []

    for t_idx, p_name in enumerate(pollutant_names):
        p_true = y_true_city[:, :, t_idx].reshape(-1)
        p_pred = y_pred_city[:, :, t_idx].reshape(-1)

        mae = mean_absolute_error(p_true, p_pred)
        rmse = np.sqrt(mean_squared_error(p_true, p_pred))
        r2 = r2_score(p_true, p_pred)
        smape = compute_smape(p_true, p_pred)

        macro_maes.append(mae)
        macro_rmses.append(rmse)
        macro_r2s.append(r2)

        pollutant_metrics[p_name] = {
            "MAE": round(float(mae), 2),
            "RMSE": round(float(rmse), 2),
            "R2": round(float(r2), 4),
            "sMAPE": round(float(smape), 2),
        }

    # 2. Evaluate CPCB AQI for True and Predicted concentrations
    true_aqis = np.zeros((N, H), dtype=np.float32)
    pred_aqis = np.zeros((N, H), dtype=np.float32)
    true_cats = []
    pred_cats = []

    for i in range(N):
        row_true_cats = []
        row_pred_cats = []
        for h in range(H):
            conc_true = {pollutant_names[t]: float(y_true_city[i, h, t]) for t in range(T)}
            conc_pred = {pollutant_names[t]: float(y_pred_city[i, h, t]) for t in range(T)}

            res_true = calculate_aqi(conc_true)
            res_pred = calculate_aqi(conc_pred)

            true_aqi = res_true.get("aqi") if res_true.get("aqi") is not None else 0.0
            pred_aqi = res_pred.get("aqi") if res_pred.get("aqi") is not None else 0.0

            true_aqis[i, h] = true_aqi
            pred_aqis[i, h] = pred_aqi

            row_true_cats.append(res_true.get("category", "Unknown"))
            row_pred_cats.append(res_pred.get("category", "Unknown"))

        true_cats.append(row_true_cats)
        pred_cats.append(row_pred_cats)

    flat_true_aqi = true_aqis.reshape(-1)
    flat_pred_aqi = pred_aqis.reshape(-1)
    abs_errors = np.abs(flat_true_aqi - flat_pred_aqi)

    # Error distribution & tolerance bounds
    pct_within_2 = float(np.mean(abs_errors <= 2.0) * 100.0)
    pct_within_5 = float(np.mean(abs_errors <= 5.0) * 100.0)
    pct_within_10 = float(np.mean(abs_errors <= 10.0) * 100.0)

    overall_aqi_mae = float(mean_absolute_error(flat_true_aqi, flat_pred_aqi))
    overall_aqi_rmse = float(np.sqrt(mean_squared_error(flat_true_aqi, flat_pred_aqi)))

    # Category classification accuracy
    flat_true_cats = [cat for sub in true_cats for cat in sub]
    flat_pred_cats = [cat for sub in pred_cats for cat in sub]
    cat_matches = sum(1 for t, p in zip(flat_true_cats, flat_pred_cats) if t == p)
    overall_cat_acc = float(cat_matches / len(flat_true_cats) * 100.0) if flat_true_cats else 0.0

    # Pollution spike performance (AQI >= 100)
    spike_mask = flat_true_aqi >= 100.0
    if np.any(spike_mask):
        spike_mae = float(mean_absolute_error(flat_true_aqi[spike_mask], flat_pred_aqi[spike_mask]))
        spike_count = int(np.sum(spike_mask))
    else:
        spike_mae = None
        spike_count = 0

    # Category Calibration (Precision, Recall, F1 per category)
    present_cats = sorted(list(set(flat_true_cats + flat_pred_cats)))
    p, r, f1, support = precision_recall_fscore_support(
        flat_true_cats, flat_pred_cats, labels=present_cats, zero_division=0
    )
    calibration = {}
    for idx, c_name in enumerate(present_cats):
        calibration[c_name] = {
            "precision": round(float(p[idx]), 3),
            "recall": round(float(r[idx]), 3),
            "f1": round(float(f1[idx]), 3),
            "support": int(support[idx]),
        }

    # Per-Horizon breakdown (D1 to D7)
    by_horizon = {}
    for h in range(H):
        h_name = f"D{h + 1}"
        h_true = true_aqis[:, h]
        h_pred = pred_aqis[:, h]
        h_errors = np.abs(h_true - h_pred)

        h_true_c = [true_cats[i][h] for i in range(N)]
        h_pred_c = [pred_cats[i][h] for i in range(N)]
        h_matches = sum(1 for tc, pc in zip(h_true_c, h_pred_c) if tc == pc)
        h_cat_acc = float(h_matches / len(h_true_c) * 100.0) if h_true_c else 0.0

        by_horizon[h_name] = {
            "AQI_MAE": round(float(mean_absolute_error(h_true, h_pred)), 2),
            "AQI_RMSE": round(float(np.sqrt(mean_squared_error(h_true, h_pred))), 2),
            "pct_within_2": round(float(np.mean(h_errors <= 2.0) * 100.0), 2),
            "pct_within_5": round(float(np.mean(h_errors <= 5.0) * 100.0), 2),
            "pct_within_10": round(float(np.mean(h_errors <= 10.0) * 100.0), 2),
            "category_accuracy_pct": round(h_cat_acc, 2),
            "directional_accuracy_pct": round(compute_directional_accuracy(h_true, h_pred), 2),
        }

    latency_ms_per_sample = round((inference_time_total_s / max(1, N)) * 1000.0, 3)

    return {
        "overall": {
            "AQI_MAE": round(overall_aqi_mae, 2),
            "AQI_RMSE": round(overall_aqi_rmse, 2),
            "pct_within_2": round(pct_within_2, 2),
            "pct_within_5": round(pct_within_5, 2),
            "pct_within_10": round(pct_within_10, 2),
            "category_accuracy_pct": round(overall_cat_acc, 2),
            "spike_mae": round(spike_mae, 2) if spike_mae is not None else None,
            "spike_count": spike_count,
            "macro_pollutant_MAE": round(float(np.mean(macro_maes)), 2),
            "macro_pollutant_RMSE": round(float(np.mean(macro_rmses)), 2),
            "latency_ms_per_sample": latency_ms_per_sample,
        },
        "by_horizon": by_horizon,
        "pollutants": pollutant_metrics,
        "calibration": calibration,
    }
