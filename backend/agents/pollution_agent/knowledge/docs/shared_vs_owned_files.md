# Shared vs Owned Files

## Owned (Pollution Domain - Editable)
All files under `backend/agents/pollution_agent/` except shared integration contracts. This includes:
- `main.py` (pollution API/router)
- `data_provider.py`
- `aqi_engine.py`
- `alerts.py`, `analytics.py`
- `forecast_7d/` and `unified_forecast/`
- All tests specific to pollution.

## Teammate Domains (Do Not Edit)
- Traffic Domain: `backend/agents/traffic_agent/*`
- Energy Domain: `backend/agents/energy_agent/*`
- Weather Domain: `backend/agents/weather_agent/*`

## Shared Code (Minimal Diffs Only)
- The Frontend Chat Page: `frontend/src/pages/Planning.jsx` (will need integration with `assistant/api.py`).
- The Planner Agent: `backend/agents/planner_agent/planner.py`, `prompts.py` (will need scope guard and domain prompt injection).
- The Supervisor API: `backend/supervisor/main.py` (will need the assistant chat endpoint mounted).
