import json
import os
import backend.agents.pollution_agent.aqi_engine as ae
import backend.agents.pollution_agent.alerts as al
import backend.agents.pollution_agent.data_provider as dp
import backend.agents.pollution_agent.data_quality as dq
from fastapi import FastAPI
from backend.agents.pollution_agent.main import app as pollution_app

def generate():
    d = 'backend/agents/pollution_agent/knowledge'
    os.makedirs(d, exist_ok=True)
    
    # aqi breakpoints
    json.dump(ae.BREAKPOINTS, open(os.path.join(d, 'cpcb_breakpoints.json'), 'w'), indent=2)
    
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
    json.dump(alert_rules, open(os.path.join(d, 'alert_rules.json'), 'w'), indent=2)
    
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
            
    json.dump(endpoints, open(os.path.join(d, 'endpoints.json'), 'w'), indent=2)
    
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
    json.dump(stations_list, open(os.path.join(d, 'stations.json'), 'w'), indent=2)
    
    # data_quality_ranges
    json.dump(dq.VALID_RANGES, open(os.path.join(d, 'data_quality_ranges.json'), 'w'), indent=2)

    # forecast_metrics
    forecast_metrics = {
        "deployed_model": "TemporalGRU_KNNCovariate",
        "test_window": "2024-01-01 to 2025-12-31",
        "mae_per_horizon": {
            "Day 1": 9.48,
            "Day 2": 10.77,
            "Day 3": 11.77,
            "Day 4": 12.42,
            "Day 5": 12.59,
            "Day 6": 12.69,
            "Day 7": 13.42
        },
        "directional_accuracy": {
            "Day 1": 38.8,
            "Day 2": 38.8,
            "Day 3": 21.2,
            "Day 4": 36.5,
            "Day 5": 37.6,
            "Day 6": 45.9,
            "Day 7": 49.4
        },
        "source": "backend/agents/pollution_agent/unified_forecast/artifacts/unified_best_model_meta.json"
    }
    json.dump(forecast_metrics, open(os.path.join(d, 'forecast_metrics.json'), 'w'), indent=2)

if __name__ == "__main__":
    generate()
