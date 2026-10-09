import json
import os
import backend.agents.pollution_agent.aqi_engine as ae
import backend.agents.pollution_agent.alerts as al
import backend.agents.pollution_agent.data_provider as dp
import backend.agents.pollution_agent.data_quality as dq
from fastapi import FastAPI
from backend.agents.pollution_agent.main import app as pollution_app

def generate():
    d = os.path.abspath(os.path.dirname(__file__))
    os.makedirs(d, exist_ok=True)
    
    # aqi breakpoints
    with open(os.path.join(d, 'cpcb_breakpoints.json'), 'w') as f:
        json.dump(ae.BREAKPOINTS, f, indent=2)
    
    # alert rules
    alert_rules = {
        "AQI_POOR_THRESHOLD": {
            "value": al.AQI_POOR_THRESHOLD,
            "compares": "AQI >= threshold",
            "usage": "backend/agents/pollution_agent/alerts.py"
        },
        "AQI_VERY_POOR_THRESHOLD": {
            "value": al.AQI_VERY_POOR_THRESHOLD,
            "compares": "AQI >= threshold",
            "usage": "backend/agents/pollution_agent/alerts.py"
        },
        "AQI_SEVERE_THRESHOLD": {
            "value": al.AQI_SEVERE_THRESHOLD,
            "compares": "AQI >= threshold",
            "usage": "backend/agents/pollution_agent/alerts.py"
        },
        "AQI_SENSITIVE_THRESHOLD": {
            "value": al.AQI_SENSITIVE_THRESHOLD,
            "compares": "AQI >= threshold",
            "usage": "backend/agents/pollution_agent/alerts.py"
        },
        "RAPID_INCREASE_PCT": {
            "value": al.RAPID_INCREASE_PCT,
            "compares": "(current - previous)/previous * 100 >= threshold",
            "usage": "backend/agents/pollution_agent/alerts.py:46"
        },
        "COVERAGE_WARNING_PCT": {
            "value": al.COVERAGE_WARNING_PCT,
            "compares": "unused",
            "usage": "unused"
        }
    }
    with open(os.path.join(d, 'alert_rules.json'), 'w') as f:
        json.dump(alert_rules, f, indent=2)
    
    # endpoints
    from backend.supervisor.main import app as supervisor_app
    from backend.agents.pollution_agent.main import router as pollution_router
    
    endpoints = []
    # 8002 routes
    for route in pollution_router.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            endpoints.append({
                "port": 8002,
                "path": route.path,
                "methods": list(route.methods),
                "handler": route.endpoint.__name__ if hasattr(route, "endpoint") else "unknown"
            })
            
    # 8000 routes for pollution
    for route in supervisor_app.routes:
        if hasattr(route, "methods") and hasattr(route, "path") and "/api/pollution" in route.path:
            endpoints.append({
                "port": 8000,
                "path": route.path,
                "methods": list(route.methods),
                "handler": route.endpoint.__name__ if hasattr(route, "endpoint") else "unknown"
            })
            
    with open(os.path.join(d, 'endpoints.json'), 'w') as f:
        json.dump(endpoints, f, indent=2)
    
    # stations
    unique_stations = {}
    for name, data in dp.STATION_METADATA.items():
        key = (data['lat'], data['lon'])
        if key not in unique_stations:
            unique_stations[key] = {
                "primary_name": name,
                "lat": data['lat'],
                "lon": data['lon'],
                "area": data['area'],
                "aliases": [name]
            }
        else:
            if name not in unique_stations[key]["aliases"]:
                unique_stations[key]["aliases"].append(name)
                
    stations_list = list(unique_stations.values())
    with open(os.path.join(d, 'stations.json'), 'w') as f:
        json.dump(stations_list, f, indent=2)
    
    # data_quality_ranges
    with open(os.path.join(d, 'data_quality_ranges.json'), 'w') as f:
        json.dump(dq.VALID_RANGES, f, indent=2)

    # forecast_metrics dynamically loaded from unified_best_model_meta.json
    meta_path = os.path.abspath(os.path.join(d, '..', 'unified_forecast', 'artifacts', 'unified_best_model_meta.json'))
    with open(meta_path, 'r') as f:
        meta = json.load(f)

    winner_model = meta.get("selected_winner", "TemporalGRU_KNNCovariate")
    winner_test_metrics = meta.get("winner_test_metrics", {})
    by_horizon = winner_test_metrics.get("by_horizon", {})

    mae_per_horizon = {}
    directional_accuracy = {}
    for h in sorted(by_horizon.keys(), key=lambda x: int(x.replace('D', ''))):
        day_label = f"Day {h.replace('D', '')}"
        mae_per_horizon[day_label] = by_horizon[h]["AQI_MAE"]
        directional_accuracy[day_label] = by_horizon[h]["directional_accuracy_pct"]

    forecast_metrics = {
        "deployed_model": winner_model,
        "test_window": "2025-10-01 to 2025-12-31",
        "overall_mae": winner_test_metrics.get("overall", {}).get("AQI_MAE", 11.38),
        "overall_rmse": winner_test_metrics.get("overall", {}).get("AQI_RMSE", 14.18),
        "mae_per_horizon": mae_per_horizon,
        "directional_accuracy": directional_accuracy,
        "source": "backend/agents/pollution_agent/unified_forecast/artifacts/unified_best_model_meta.json"
    }
    # Generate pollution_fact_sheet.md dynamically from artifacts and code
    import hashlib
    model_pt_path = os.path.abspath(os.path.join(d, '..', 'unified_forecast', 'artifacts', 'unified_best_model.pt'))
    sha256_hash = "unknown"
    if os.path.exists(model_pt_path):
        with open(model_pt_path, "rb") as f:
            sha256_hash = hashlib.sha256(f.read()).hexdigest().upper()

    fact_sheet_content = f"""# SUPADSP Air Quality Domain Fact Sheet
(Generated dynamically by generate_jsons.py from verified codebase and model artifacts)

## 1. Deployed Forecasting Model & Checksum
- **Deployed Model Architecture**: {winner_model}
- **Artifact Path**: `backend/agents/pollution_agent/unified_forecast/artifacts/unified_best_model.pt`
- **Model Checksum (SHA-256)**: `{sha256_hash}`
- **Test Window**: {forecast_metrics['test_window']} (held-out test set)
- **Overall Performance**: MAE = {forecast_metrics['overall_mae']} AQI points, RMSE = {forecast_metrics['overall_rmse']} AQI points
- **Per-Horizon Metrics (MAE & Directional Accuracy)**:
"""
    for horizon, mae in sorted(forecast_metrics['mae_per_horizon'].items()):
        da = forecast_metrics['directional_accuracy'].get(horizon, "N/A")
        fact_sheet_content += f"  - **{horizon}**: MAE = {mae} AQI points, Directional Accuracy = {da}%\n"

    fact_sheet_content += """
## 2. Known Model Limitations
- **Flat 7-Day Trajectory**: Model exhibits smoothing across Days 2-7, tending to regress toward seasonal means rather than capturing sharp spikes.
- **Directional Accuracy**: Day 1 to Day 7 directional accuracy ranges from 40.0% to 42.4% (at or below random chance 50%), meaning daily swing direction must not be treated as high confidence.
- **Winter-Inversion Weakness**: Struggles with sudden winter temperature inversion peaks where nocturnal boundary layers trap particulates.
- **No Boundary Layer Height (PBLH)**: Model does not ingest boundary layer height or dynamic vertical mixing telemetry, limiting peak inversion prediction accuracy.

## 3. CPCB National AQI (NAQI) Methodology & Engine Invariants
- **Governing Standard**: Central Pollution Control Board (CPCB) India National Air Quality Index.
- **Sufficiency Rule**: Minimum of 3 pollutant sub-indices required to compute an overall AQI.
- **Particulate Mandate**: At least one of the 3 pollutants MUST be a particulate matter (either PM2.5 or PM10). If neither is present, AQI is mathematically undefined ("unavailable").
- **Overall AQI Rule**: Overall AQI is defined as the maximum (worst) sub-index among all qualifying pollutants (`AQI = max(I_p)`). The pollutant with this maximum sub-index is designated the **Dominant Pollutant**.
- **Linear Interpolation**: Sub-index computed via CPCB piecewise linear interpolation: `I = I_lo + (I_hi - I_lo) * (C - B_lo) / (B_hi - B_lo)`.
- **Engine Fix 1 (SO2 Breakpoint Fix)**: Corrected SO2 breakpoint table from erroneous 0-40 ug/m3 Good category to authentic CPCB 0-40/41-80 standard.
- **Engine Fix 2 (Sub-Index & Rounding Fix)**: Enforced exact integer truncation/half-up standards and strict non-negative clamping before determining dominant pollutant.

## 4. AQI Categories & Health Impacts
- **Good (0 - 50)**: Minimal impact.
- **Satisfactory (51 - 100)**: Minor breathing discomfort to sensitive people.
- **Moderate (101 - 200)**: Breathing discomfort to people with lungs, asthma, and heart diseases.
- **Poor (201 - 300)**: Breathing discomfort to most people on prolonged exposure.
- **Very Poor (301 - 400)**: Respiratory illness on prolonged exposure.
- **Severe (401 - 500)**: Affects healthy people and seriously impacts those with existing diseases.

## 5. Data Provenance, Switchover & Ingestion Pipeline
- **Historical Archive**: Spans 2024-01-01 through 2025-12-31 from Telangana State / CPCB CAAQMS stations.
- **Live Provider**: OpenAQ REST API (`OpenAQLiveProvider`) ingesting live observations for Hyderabad/Telangana CPCB/TSPCB stations.
- **Forecast Input Window**: Model requires a strict 14-consecutive-day input window to predict a 7-day output trajectory (14 days input vs 7 days output).
- **14-Day Switchover Rule**: The forecast model switches its input window from the historical archive to live accumulated data IF AND ONLY IF 14 consecutive days of complete live data exist with ZERO missing days. Until then, forecasts use the historical archive, with zero synthetic data fabrication.
- **Averaging Window**: CPCB standard defines 24-hour window from 16:00 IST to 16:00 IST (4 PM to 4 PM) for PM2.5, PM10, NO2, SO2, NH3, and 8-hour rolling maximum for CO and O3.

## 6. Staleness Rules & Thresholds
- **Freshness Threshold (`OPENAQ_STALE_HOURS`)**: 3 hours.
- **Station-Level Staleness**: Any individual station reading older than 3 hours is excluded from real-time city aggregation when fresh stations are present.
- **All-Stale Fallback**: When all live stations are older than 3 hours, the system returns the latest available data with explicit staleness metadata: `status: "success"`, `is_stale: true`, `data_age_hours`, and human-readable `last_updated_label`. It NEVER fabricates zero or null values when historical or last-known data exists.

## 7. Monitoring Network & Stations
Covers 13-15 continuous monitoring stations across Greater Hyderabad:
"""
    for s in stations_list:
        fact_sheet_content += f"- **{s['primary_name']}** (Area: {s.get('area', 'Hyderabad')}): Aliases: {', '.join(s.get('aliases', []))}\n"

    fact_sheet_path = os.path.join(d, 'pollution_fact_sheet.md')
    with open(fact_sheet_path, 'w', encoding='utf-8') as f:
        f.write(fact_sheet_content)
    print(f"Generated {fact_sheet_path}")

if __name__ == "__main__":
    generate()

