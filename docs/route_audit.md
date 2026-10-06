# SUPADSP Route Audit & Contract Verification

**Date:** 2026-10-04  
**Audit Scope:** Supervisor (Port 8000), Specialist Agent Routers, Frontend Clients (`api.js`, `pollutionApi.js`, `Planning.jsx`)

---

## 1. Executive Summary & Critical Findings

1. **Route Shadowing / Duplicate Detection:**
   - `GET /health` is registered twice: first in `backend/supervisor/main.py:588` (System health) and shadowed by `backend/agents/pollution_agent/main.py:531` (Pollution agent health) when `pollution_router` is included.
2. **Broken Frontend Contracts (Missing Routes / 404s):**
   - `POST /agents/orchestrator/execute` (called by `frontend/src/services/api.js:163`): Returns 404 because the supervisor implements `/agents/planner/execute`. The frontend swallows the error and uses client-side mock data.
   - `GET /agents/orchestrator/tasks/{taskId}` (called by `frontend/src/services/api.js:247`): Returns 404 because the supervisor has no task tracking route for orchestrator.
   - `POST http://localhost:8000/api/planning/chat` (called by `frontend/src/pages/Planning.jsx:292`): Previously failed with 404 or uncaught HTTP errors, causing the frontend UI to display "Processing your request..." indefinitely without displaying error text or actionable feedback.
3. **Latency & Uncached Route Bottlenecks (>3s warm / Timeouts):**
   - `/api/pollution/forecast/daily`, `/api/pollution/forecast/7day`, `/api/pollution/alerts`, `/api/pollution/summary`, and `/api/v1/pollution/aqi-summary` had cold/warm latency exceeding 3 seconds (up to >10s) due to synchronous on-demand neural network inference (`UnifiedForecaster`) and repeated live OpenAQ network calls across 15 monitoring stations.
   - `/api/pollution/historical/latest` warm latency was 5088.88ms (>3s).
4. **Environment / Specialist Errors (500s):**
   - `GET /api/v1/traffic/kpis` and `POST /api/v1/traffic/analyze` return HTTP 500 `SumoExecutionError` because Eclipse SUMO 1.27.1 is not installed in the host environment.
5. **Planning Assistant Architecture & Baseline Routing:**
   - `/api/planning/chat` is defined in `backend/agents/pollution_agent/main.py:1057` and registered on supervisor via `pollution_router`.
   - Domain routing prior to changes only checked `is_pollution_question(question)`. Any non-pollution query fell back to canned text ("Based on current multi-domain telemetry...").
   - Baseline prompt evaluation was recorded to `eval/baseline_planning.jsonl`.

---

## 2. Complete Supervisor Route Inventory & Smoke Test Results

| Method | Path | Owning Router | Handler Location | Status Code | Cold (ms) | Warm (ms) | Body Status / Mode | Flagged Issues |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/openapi.json` | Supervisor | applications.py:1108 | 200 | 165.3 | 17.1 | None | None |
| `GET` | `/docs` | Supervisor | applications.py:1123 | 200 | 35.7 | 8.9 | None | None |
| `GET` | `/docs/oauth2-redirect` | Supervisor | applications.py:1141 | 200 | 7.4 | 6.1 | None | None |
| `GET` | `/redoc` | Supervisor | applications.py:1151 | 200 | 6.4 | 7.6 | None | None |
| `GET` | `/health` | System / Supervisor | supervisor/main.py:588 | 200 | 31.7 | 9.4 | ONLINE | Shadowed by pollution /health |
| `POST` | `/planning/requests` | Public API - Planning | supervisor/main.py:593 | *Skipped* | - | - | - | Mutating POST |
| `GET` | `/planning/requests/{request_id}` | Public API - Planning | supervisor/main.py:619 | 404 | 14.0 | 15.6 | None | ID not found (expected) |
| `POST` | `/agents/planner/plan` | Internal API - Planner | supervisor/main.py:651 | *Skipped* | - | - | - | Mutating POST |
| `POST` | `/agents/planner/feedback` | Internal API - Planner | supervisor/main.py:720 | *Skipped* | - | - | - | Mutating POST |
| `POST` | `/agents/planner/execute` | Internal API - Planner | supervisor/main.py:1022 | *Skipped* | - | - | - | Mutating POST |
| `POST` | `/agents/knowledge/search` | Internal API - Knowledge | supervisor/main.py:1611 | 422 | 5.4 | 3.2 | None | Requires query payload |
| `POST` | `/agents/data-discovery/discover` | Internal API - Data | supervisor/main.py:1632 | 422 | 6.7 | 3.4 | None | Requires query payload |
| `POST` | `/agents/data-retrieval/retrieve` | Internal API - Data | supervisor/main.py:1654 | 422 | 3.7 | 3.5 | None | Requires source payload |
| `POST` | `/models/traffic/analyze` | Internal API - Models | supervisor/main.py:1685 | 200 | 5.4 | 26.5 | COMPLETED | None |
| `POST` | `/models/flood/analyze` | Internal API - Models | supervisor/main.py:1695 | 200 | 15.7 | 3.4 | COMPLETED | None |
| `POST` | `/models/energy/analyze` | Internal API - Models | supervisor/main.py:1705 | 200 | 4.4 | 3.3 | COMPLETED | None |
| `POST` | `/models/weather/analyze` | Internal API - Models | supervisor/main.py:1715 | 200 | 3.9 | 4.0 | COMPLETED | None |
| `GET` | `/monitoring/status` | Public API - Monitoring | supervisor/main.py:1725 | 200 | 5.3 | 3.7 | None | None |
| `GET` | `/monitoring/events` | Public API - Monitoring | supervisor/main.py:1745 | 200 | 5.0 | 4.3 | None | None |
| `GET` | `/alerts` | Public API - Alerts | supervisor/main.py:1773 | 200 | 4.2 | 4.3 | None | None |
| `GET` | `/alerts/{alert_id}` | Public API - Alerts | supervisor/main.py:1786 | 200 | 3.8 | 3.5 | ACTIVE | None |
| `POST` | `/alerts/{alert_id}/acknowledge` | Public API - Alerts | supervisor/main.py:1800 | *Skipped* | - | - | - | Mutating POST |
| `POST` | `/alerts/{alert_id}/dismiss` | Public API - Alerts | supervisor/main.py:1817 | *Skipped* | - | - | - | Mutating POST |
| `POST` | `/simulations` | Public API - Simulations | supervisor/main.py:1834 | *Skipped* | - | - | - | Mutating POST |
| `GET` | `/simulations/{simulation_id}` | Public API - Simulations | supervisor/main.py:1853 | 404 | 20.3 | 3.6 | None | ID not found (expected) |
| `GET` | `/simulations/{simulation_id}/results`| Public API - Simulations | supervisor/main.py:1867 | 404 | 5.1 | 3.3 | None | ID not found (expected) |
| `POST` | `/agents/verification/verify` | Internal API - Verification| supervisor/main.py:1895 | *Skipped* | - | - | - | Mutating POST |
| `POST` | `/agents/fail-safe/check` | Internal API - Fail-Safe | supervisor/main.py:1911 | *Skipped* | - | - | - | Mutating POST |
| `GET` | `/recommendations/{recommendation_id}` | Public API - Recs | supervisor/main.py:1929 | 404 | 17.1 | 3.4 | None | ID not found (expected) |
| `POST` | `/recommendations/{id}/approve` | Public API - Recs | supervisor/main.py:1967 | *Skipped* | - | - | - | Mutating POST |
| `POST` | `/recommendations/{id}/reject` | Public API - Recs | supervisor/main.py:1985 | *Skipped* | - | - | - | Mutating POST |
| `POST` | `/recommendations/{id}/modify` | Public API - Recs | supervisor/main.py:2003 | *Skipped* | - | - | - | Mutating POST |
| `GET` | `/digital-twin/state` | Public API - Digital Twin| supervisor/main.py:2021 | 200 | 3.8 | 3.3 | None | None |
| `GET` | `/digital-twin/state/{location}` | Public API - Digital Twin| supervisor/main.py:2042 | 200 | 5.1 | 3.9 | None | None |
| `GET` | `/api/v1/traffic/kpis` | Specialist Agent - Traffic | traffic_agent/main.py:31 | 500 | 16.8 | 27.7 | None | 500: SUMO not installed |
| `POST` | `/api/v1/traffic/analyze` | Specialist Agent - Traffic | traffic_agent/main.py:73 | 500 | 29.2 | 20.3 | None | 500: SUMO not installed |
| `POST` | `/api/v1/traffic/optimize-signal` | Specialist Agent - Traffic | traffic_agent/main.py:94 | *Skipped* | - | - | - | Mutating POST |
| `GET` | `/api/v1/weather/current` | Specialist Agent - Weather | weather_agent/main.py:14 | 200 | 11.1 | 6.1 | None | None |
| `GET` | `/api/v1/pollution/aqi-summary` | Specialist Agent - Pollution | pollution_agent/main.py:383 | 200 (warm) | >10s | >10s | None | Slow warm (>3s) |
| `GET` | `/api/v1/pollution/current` | Specialist Agent - Pollution | pollution_agent/main.py:421 | 200 | 95.4 | 37.3 | None | None |
| `POST` | `/api/v1/pollution/analyze` | Specialist Agent - Pollution | pollution_agent/main.py:461 | 422 | 7.0 | 4.8 | None | Schema validation |
| `GET` | `/health` (Pollution) | Specialist Agent - Pollution | pollution_agent/main.py:531 | 200 | 6.7 | 5.5 | ONLINE | Duplicate route path |
| `GET` | `/api/pollution/current` | Specialist Agent - Pollution | pollution_agent/main.py:603 | 200 | 36.8 | 34.8 | success | None |
| `GET` | `/api/pollution/pollutants` | Specialist Agent - Pollution | pollution_agent/main.py:648 | 200 | 42.6 | 23.5 | success | None |
| `GET` | `/api/pollution/trend` | Specialist Agent - Pollution | pollution_agent/main.py:702 | 200 | 18.0 | 3.4 | unavailable | Unavailable status on live window |
| `GET` | `/api/pollution/hotspots` | Specialist Agent - Pollution | pollution_agent/main.py:724 | 200 | 61.2 | 17.4 | success | None |
| `GET` | `/api/pollution/distribution` | Specialist Agent - Pollution | pollution_agent/main.py:738 | 200 | 39.3 | 16.7 | success | None |
| `GET` | `/api/pollution/areas/trend` | Specialist Agent - Pollution | pollution_agent/main.py:757 | 200 | 45.9 | 6.3 | unavailable | Unavailable status |
| `GET` | `/api/pollution/forecast/daily` | Specialist Agent - Pollution | pollution_agent/main.py:774 | 200 (warm) | >10s | >10s | None | Slow warm (>3s) - needs cache |
| `GET` | `/api/pollution/forecast/7day` | Specialist Agent - Pollution | pollution_agent/main.py:787 | 200 (warm) | >10s | >10s | None | Slow warm (>3s) - needs cache |
| `GET` | `/api/pollution/forecast/hourly` | Specialist Agent - Pollution | pollution_agent/main.py:797 | 200 | 123.4 | 8.4 | unavailable | Unsupported standard |
| `GET` | `/api/pollution/alerts` | Specialist Agent - Pollution | pollution_agent/main.py:805 | 200 (warm) | >10s | >10s | None | Slow warm (>3s) - needs cache |
| `GET` | `/api/pollution/summary` | Specialist Agent - Pollution | pollution_agent/main.py:821 | 200 (warm) | >10s | >10s | None | Slow warm (>3s) - needs cache |
| `GET` | `/api/pollution/historical/latest` | Specialist Agent - Pollution| pollution_agent/main.py:998 | 200 | 3283.0 | 5088.9 | success | Slow warm (>3s) |
| `GET` | `/api/pollution/reconciliation` | Specialist Agent - Pollution | pollution_agent/main.py:1008| 200 | 154.6 | 614.0 | success | None |
| `POST` | `/api/pollution/predict` | Specialist Agent - Pollution | pollution_agent/main.py:1016| *Skipped* | - | - | - | Mutating POST |
| `GET` | `/api/pollution/info` | Specialist Agent - Pollution | pollution_agent/main.py:1025| 200 | 263.7 | 89.6 | ready | None |
| `GET` | `/api/pollution/metrics` | Specialist Agent - Pollution | pollution_agent/main.py:1034| 200 | 44.2 | 71.5 | None | None |
| `GET` | `/api/pollution/live-data-status` | Specialist Agent - Pollution| pollution_agent/main.py:1044| 200 | 21.0 | 28.2 | None | None |
| `POST` | `/api/planning/chat` | Specialist Agent - Pollution | pollution_agent/main.py:1057| 200 | 6222.4 | 1741.2 | None | Planning chat assistant |
| `POST` | `/api/pollution/chat` | Specialist Agent - Pollution | pollution_agent/main.py:1058| 200 | 6222.4 | 1741.2 | None | Duplicate path alias |
| `GET` | `/api/v1/energy/grid-status` | Specialist Agent - Energy | energy_agent/main.py:34 | 200 | 6399.4 | 36.0 | None | None |
| `POST` | `/api/v1/energy/peak-shave` | Specialist Agent - Energy | energy_agent/main.py:44 | *Skipped* | - | - | - | Mutating POST |
| `POST` | `/api/v1/energy/analyze` | Specialist Agent - Energy | energy_agent/main.py:54 | *Skipped* | - | - | - | Mutating POST |
| `GET` | `/api/v1/energy/substations` | Specialist Agent - Energy | energy_agent/main.py:64 | 200 | 49.3 | 110.7 | None | Uncalled by frontend |
| `GET` | `/api/v1/energy/zones` | Specialist Agent - Energy | energy_agent/main.py:74 | 200 | 542.4 | 42.6 | None | Uncalled by frontend |
| `POST` | `/api/v1/simulation/run` | Specialist Agent - Simulation | simulation_agent/main.py:24 | *Skipped* | - | - | - | Mutating POST |
| `GET` | `/api/v1/simulation/status` | Specialist Agent - Simulation | simulation_agent/main.py:48 | 200 | 47.5 | 20.8 | COMPLETED | None |
| `GET` | `/api/v1/simulation/results`| Specialist Agent - Simulation | simulation_agent/main.py:60 | 200 | 24.9 | 44.4 | COMPLETED | None |

---

## 3. Frontend vs Backend Cross-Match

### 3.1 Calls with No Route (404)
1. `POST /agents/orchestrator/execute` (`frontend/src/services/api.js:163`)  
   *Target on backend is `/agents/planner/execute`.* Currently triggers mock fallback in `api.js`.
2. `GET /agents/orchestrator/tasks/{taskId}` (`frontend/src/services/api.js:247`)  
   *No matching backend route exists.* Currently triggers mock fallback in `api.js`.

### 3.2 Routes Nobody Calls
- `/agents/knowledge/search`
- `/agents/data-discovery/discover`
- `/agents/data-retrieval/retrieve`
- `/models/flood/analyze`
- `/models/weather/analyze`
- `/api/v1/energy/substations`
- `/api/v1/energy/zones`
- `/api/pollution/metrics`
- `/api/pollution/reconciliation`

### 3.3 Method / Shape Mismatches
- `/api/v1/traffic/kpis` (GET): Backend fails with 500 (`SumoExecutionError`).
- `/api/v1/traffic/analyze` (POST): Backend fails with 500 (`SumoExecutionError`).
- `/api/pollution/forecast/hourly` (GET): Returns status `unavailable` because CPCB NAQI standard uses daily exposure.

---

## 4. Remediation Plan (Aligned with Rules R1-R6)

1. **Step 2 Contract Fixes:**
   - Resolve `/health` route shadowing: Rename `pollution_agent`'s health check to `/api/pollution/health` or ensure supervisor `/health` remains the system authority.
   - Patch `frontend/src/pages/Planning.jsx` (≤15 lines) to verify `res.ok`, parse error text, and set messages cleanly so "Processing your request..." is never shown on errors.
   - Add in-memory response caching with `data_age_seconds` for `/api/pollution/forecast/7day`, `/forecast/daily`, `/summary`, `/alerts`, and `/historical/latest` to guarantee ≤3s warm responses.
2. **Step 3 WeatherAPI Provider:**
   - Integrate `WeatherAPIProvider` into `backend/agents/weather_agent/` supporting `WEATHERAPI_KEY` and `WEATHER_PROVIDER=auto|weatherapi|existing`.
   - Never request `aqi=yes`.
   - Provide caching (5m current, 30m forecast), fallback to existing provider in auto mode, and IST/UTC observation timestamps.
3. **Step 4 Unified Planning Assistant:**
   - Single `/api/planning/chat` endpoint with intent-based domain routing (pollution, weather, traffic, energy).
   - Pollution uses existing grounding handler + verifier.
   - Weather uses new tools `get_weather_current` and `get_weather_forecast`.
   - Traffic and energy strictly preserve the baseline behavior.
