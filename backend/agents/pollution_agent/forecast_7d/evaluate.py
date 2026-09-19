"""
Evaluation framework for Hyderabad 7-day forecasting.
Calculates pollutant-level metrics, horizon-level metrics, and CPCB AQI-level metrics.
Benchmarks against the frozen Ganesh BiLSTM Day-1 baseline.
"""
from typing import Dict, List, Tuple, Any, Optional
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, confusion_matrix

from ..aqi_engine import calculate_aqi, get_aqi_category
from ..model import get_model
from .config import PRIMARY_TARGETS, FORECAST_HORIZON


CPCB_CATEGORIES = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]


def compute_smape(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1e-6) -> float:
    """Symmetric Mean Absolute Percentage Error (handles near-zero values gracefully)."""
    denominator = (np.abs(y_true) + np.abs(y_pred)) / 2.0 + eps
    diff = np.abs(y_pred - y_true) / denominator
    return float(np.mean(diff) * 100.0)


def compute_directional_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Directional accuracy of changes (percentage of identical change signs)."""
    if len(y_true) < 2:
        return 100.0
    true_diff = np.diff(y_true, axis=0)
    pred_diff = np.diff(y_pred, axis=0)
    matching = np.sign(true_diff) == np.sign(pred_diff)
    return float(np.mean(matching) * 100.0)


def evaluate_pollutant_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    pollutant_names: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Compute comprehensive metrics for pollutant concentrations.
    y_true, y_pred shape: (N, horizon, num_targets)
    """
    pollutant_names = pollutant_names or PRIMARY_TARGETS
    N, H, T = y_true.shape

    metrics = {
        "overall": {},
        "by_horizon": {},
        "by_pollutant": {},
        "matrix": {}  # pollutant x horizon
    }

    # Overall metrics across all horizons and pollutants
    overall_mae = mean_absolute_error(y_true.reshape(-1), y_pred.reshape(-1))
    overall_rmse = np.sqrt(mean_squared_error(y_true.reshape(-1), y_pred.reshape(-1)))
    overall_r2 = r2_score(y_true.reshape(-1), y_pred.reshape(-1))
    overall_smape = compute_smape(y_true.reshape(-1), y_pred.reshape(-1))

    # Calculate per-pollutant metrics first to derive true macro metrics
    pollutant_maes = []
    pollutant_rmses = []
    pollutant_r2s = []
    pollutant_smapes = []
    for t, p_name in enumerate(pollutant_names):
        p_true = y_true[:, :, t]
        p_pred = y_pred[:, :, t]
        p_mae = mean_absolute_error(p_true, p_pred)
        p_rmse = np.sqrt(mean_squared_error(p_true, p_pred))
        p_r2 = r2_score(p_true, p_pred)
        p_smape = compute_smape(p_true, p_pred)
        p_dir = compute_directional_accuracy(p_true, p_pred)
        pollutant_maes.append(p_mae)
        pollutant_rmses.append(p_rmse)
        pollutant_r2s.append(p_r2)
        pollutant_smapes.append(p_smape)

        metrics["by_pollutant"][p_name] = {
            "MAE": round(float(p_mae), 2),
            "RMSE": round(float(p_rmse), 2),
            "R2": round(float(p_r2), 4),
            "sMAPE": round(float(p_smape), 2),
            "DirAcc": round(float(p_dir), 2),
        }

        # Pollutant x Horizon Matrix
        metrics["matrix"][p_name] = {}
        for h in range(H):
            h_name = f"D{h + 1}"
            ph_true = y_true[:, h, t]
            ph_pred = y_pred[:, h, t]
            metrics["matrix"][p_name][h_name] = {
                "MAE": round(float(mean_absolute_error(ph_true, ph_pred)), 2),
                "RMSE": round(float(np.sqrt(mean_squared_error(ph_true, ph_pred))), 2),
                "R2": round(float(r2_score(ph_true, ph_pred)), 4),
            }

    metrics["overall"] = {
        "macro_MAE": round(float(np.mean(pollutant_maes)), 2),
        "macro_RMSE": round(float(np.mean(pollutant_rmses)), 2),
        "macro_R2": round(float(np.mean(pollutant_r2s)), 4),
        "pooled_MAE": round(float(overall_mae), 2),
        "pooled_RMSE": round(float(overall_rmse), 2),
        "pooled_R2": round(float(overall_r2), 4),
        "MAE": round(float(np.mean(pollutant_maes)), 2),  # Primary unweighted macro MAE
        "RMSE": round(float(np.mean(pollutant_rmses)), 2),
        "R2": round(float(np.mean(pollutant_r2s)), 4),
        "sMAPE": round(float(overall_smape), 2),
    }

    # By Horizon (D1 to D7)
    for h in range(H):
        h_name = f"D{h + 1}"
        h_true = y_true[:, h, :]
        h_pred = y_pred[:, h, :]

        h_mae = mean_absolute_error(h_true, h_pred)
        h_rmse = np.sqrt(mean_squared_error(h_true, h_pred))
        h_r2 = r2_score(h_true, h_pred)
        h_smape = compute_smape(h_true, h_pred)

        metrics["by_horizon"][h_name] = {
            "MAE": round(float(h_mae), 2),
            "RMSE": round(float(h_rmse), 2),
            "R2": round(float(h_r2), 4),
            "sMAPE": round(float(h_smape), 2),
        }

    # By Pollutant
    for t, p_name in enumerate(pollutant_names):
        p_true = y_true[:, :, t]
        p_pred = y_pred[:, :, t]

        p_mae = mean_absolute_error(p_true, p_pred)
        p_rmse = np.sqrt(mean_squared_error(p_true, p_pred))
        p_r2 = r2_score(p_true, p_pred)
        p_smape = compute_smape(p_true, p_pred)
        p_dir = compute_directional_accuracy(p_true, p_pred)

        metrics["by_pollutant"][p_name] = {
            "MAE": round(float(p_mae), 2),
            "RMSE": round(float(p_rmse), 2),
            "R2": round(float(p_r2), 4),
            "sMAPE": round(float(p_smape), 2),
            "DirAcc": round(float(p_dir), 2),
        }

        # Pollutant x Horizon Matrix
        metrics["matrix"][p_name] = {}
        for h in range(H):
            h_name = f"D{h + 1}"
            ph_true = y_true[:, h, t]
            ph_pred = y_pred[:, h, t]
            metrics["matrix"][p_name][h_name] = {
                "MAE": round(float(mean_absolute_error(ph_true, ph_pred)), 2),
                "RMSE": round(float(np.sqrt(mean_squared_error(ph_true, ph_pred))), 2),
                "R2": round(float(r2_score(ph_true, ph_pred)), 4),
            }

    return metrics


def evaluate_cpcb_aqi_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    pollutant_names: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Convert pollutant concentrations to CPCB AQI using the existing CPCB AQI engine.
    Calculates AQI MAE, RMSE, Category Accuracy, and Confusion Matrix.
    """
    pollutant_names = pollutant_names or PRIMARY_TARGETS
    N, H, T = y_true.shape

    true_aqis = np.zeros((N, H), dtype=np.float32)
    pred_aqis = np.zeros((N, H), dtype=np.float32)
    true_cats = []
    pred_cats = []

    for i in range(N):
        row_true_cats = []
        row_pred_cats = []
        for h in range(H):
            # True AQI
            conc_true = {pollutant_names[t]: float(y_true[i, h, t]) for t in range(T)}
            res_true = calculate_aqi(conc_true)
            true_aqi = res_true.get("aqi") if res_true.get("aqi") is not None else 0.0
            true_aqis[i, h] = true_aqi
            row_true_cats.append(res_true.get("category", "Unknown"))

            # Predicted AQI
            conc_pred = {pollutant_names[t]: float(y_pred[i, h, t]) for t in range(T)}
            res_pred = calculate_aqi(conc_pred)
            pred_aqi = res_pred.get("aqi") if res_pred.get("aqi") is not None else 0.0
            pred_aqis[i, h] = pred_aqi
            row_pred_cats.append(res_pred.get("category", "Unknown"))

        true_cats.append(row_true_cats)
        pred_cats.append(row_pred_cats)

    # Calculate metrics
    aqi_metrics = {
        "overall": {},
        "by_horizon": {},
        "confusion_matrix": {}
    }

    flat_true_aqi = true_aqis.reshape(-1)
    flat_pred_aqi = pred_aqis.reshape(-1)

    overall_mae = mean_absolute_error(flat_true_aqi, flat_pred_aqi)
    overall_rmse = np.sqrt(mean_squared_error(flat_true_aqi, flat_pred_aqi))
    flat_true_cats = [cat for sub in true_cats for cat in sub]
    flat_pred_cats = [cat for sub in pred_cats for cat in sub]

    cat_matches = sum(1 for t, p in zip(flat_true_cats, flat_pred_cats) if t == p)
    cat_accuracy = (cat_matches / len(flat_true_cats) * 100.0) if len(flat_true_cats) > 0 else 0.0

    aqi_metrics["overall"] = {
        "AQI_MAE": round(float(overall_mae), 2),
        "AQI_RMSE": round(float(overall_rmse), 2),
        "Category_Accuracy_Pct": round(float(cat_accuracy), 2),
    }

    # Confusion matrix
    present_cats = sorted(list(set(flat_true_cats + flat_pred_cats)))
    cm = confusion_matrix(flat_true_cats, flat_pred_cats, labels=present_cats)
    aqi_metrics["confusion_matrix"] = {
        "labels": present_cats,
        "matrix": cm.tolist()
    }

    # Horizon breakdown (D1 to D7)
    for h in range(H):
        h_name = f"D{h + 1}"
        h_true_aqi = true_aqis[:, h]
        h_pred_aqi = pred_aqis[:, h]
        h_true_cat = [true_cats[i][h] for i in range(N)]
        h_pred_cat = [pred_cats[i][h] for i in range(N)]

        h_matches = sum(1 for t, p in zip(h_true_cat, h_pred_cat) if t == p)
        h_cat_acc = (h_matches / len(h_true_cat) * 100.0) if len(h_true_cat) > 0 else 0.0

        aqi_metrics["by_horizon"][h_name] = {
            "AQI_MAE": round(float(mean_absolute_error(h_true_aqi, h_pred_aqi)), 2),
            "AQI_RMSE": round(float(np.sqrt(mean_squared_error(h_true_aqi, h_pred_aqi))), 2),
            "Category_Accuracy_Pct": round(float(h_cat_acc), 2),
            "Directional_Accuracy_Pct": round(compute_directional_accuracy(h_true_aqi, h_pred_aqi), 2)
        }

    return aqi_metrics


def evaluate_ganesh_day1_baseline(test_samples: List[dict]) -> Optional[Dict[str, Any]]:
    """
    Evaluate the frozen, verified Ganesh BiLSTM baseline specifically on Day 1 AQI.
    Uses the 7-day historical context leading up to each forecast origin.
    """
    try:
        from datetime import datetime, timedelta, date
        ganesh = get_model()
        if ganesh.status != "ready":
            ganesh.load(city_name="Hyderabad")

        if ganesh.status != "ready":
            return {"status": "unavailable", "reason": f"Ganesh model not ready: {ganesh.status}"}

        ganesh_preds = []
        true_day1_aqis = []
        true_day1_cats = []
        pred_day1_cats = []

        for s in test_samples:
            # Origin date of forecast
            orig_dt = datetime.strptime(s["origin_date"], "%Y-%m-%d").date()
            # Last 7 days of context
            x_seq = s["x"][-7:]  # Shape (7, num_features)
            seq_dicts = []
            for d_idx in range(7):
                cur_dt = orig_dt - timedelta(days=(6 - d_idx))
                d_dict = {
                    "date": cur_dt,
                    "reading_count": 96,
                    "completeness": {}
                }
                for p_idx, p_name in enumerate(PRIMARY_TARGETS):
                    d_dict[p_name] = max(0.01, float(x_seq[d_idx, p_idx]))
                # Secondary features for BiLSTM feature vector compatibility
                # NO, NOx, NH3, Benzene, Toluene, Xylene (approximate city baselines)
                d_dict["NO"] = 8.0
                d_dict["NOx"] = 15.0
                d_dict["NH3"] = 14.0
                d_dict["Benzene"] = 1.0
                d_dict["Toluene"] = 2.5
                d_dict["Xylene"] = 1.2
                seq_dicts.append(d_dict)

            pred_res = ganesh.predict(seq_dicts)
            if pred_res.get("forecast_status") == "success" and pred_res.get("forecast_aqi") is not None:
                g_aqi = float(pred_res["forecast_aqi"])
                ganesh_preds.append(g_aqi)
                cat_tuple = get_aqi_category(g_aqi)
                pred_day1_cats.append(cat_tuple[0] if isinstance(cat_tuple, tuple) else cat_tuple)

                # True Day 1 AQI
                day1_conc = {p: float(s["y"][0, idx]) for idx, p in enumerate(PRIMARY_TARGETS)}
                res_true = calculate_aqi(day1_conc)
                t_aqi = float(res_true.get("aqi", 0.0))
                true_day1_aqis.append(t_aqi)
                true_day1_cats.append(res_true.get("category", "Unknown"))

        if len(ganesh_preds) == 0:
            return {"status": "unavailable", "reason": "No valid predictions produced by Ganesh BiLSTM"}

        true_arr = np.array(true_day1_aqis)
        pred_arr = np.array(ganesh_preds)

        g_mae = mean_absolute_error(true_arr, pred_arr)
        g_rmse = np.sqrt(mean_squared_error(true_arr, pred_arr))
        cat_acc = sum(1 for t, p in zip(true_day1_cats, pred_day1_cats) if t == p) / len(true_day1_cats) * 100.0

        return {
            "model": "Ganesh_BiLSTM_Pretrained",
            "horizon": "Day 1 (Next-Day)",
            "evaluated_samples": len(ganesh_preds),
            "AQI_MAE": round(float(g_mae), 2),
            "AQI_RMSE": round(float(g_rmse), 2),
            "Category_Accuracy_Pct": round(float(cat_acc), 2),
            "Directional_Accuracy_Pct": round(compute_directional_accuracy(true_arr, pred_arr), 2),
            "provenance": "Pretrained on Indian CPCB dataset (Nadkarni et al.)"
        }
    except Exception as e:
        return {"error": str(e)}
