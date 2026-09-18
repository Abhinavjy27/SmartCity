# SUPADSP SmartCity — Complete Architecture Audit
### Derived from actual codebase inspection · No assumptions · No modifications

---

## 1. SYSTEM OVERVIEW

**SUPADSP** (Smart Urban Planning and Decision Support Platform) is a multi-agent AI system for Smart City governance in Hyderabad, India. It allows municipal planners to pose natural-language urban problems (traffic, energy, pollution, weather), and the system autonomously reasons, queries specialist domain agents, optionally runs Eclipse SUMO microsimulations, and returns actionable municipal recommendations.

**Key design invariants (as coded):**
- There is **NO Orchestrator** in the codebase.
- The **Planner Agent is the sole coordinator** of all specialist agents.
- All coordination decisions (which agents to call, whether to replan, whether to simulate) are **100% LLM-driven**.
- Deterministic Python code exists only as **validation safeguards**, never as coordinators.

---

## 2. HIGH-LEVEL ARCHITECTURE DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────┐
│                          FRONTEND (React / Vite)                    │
│                                                                     │
│  Pages: Dashboard, Planning, Traffic, Weather, Pollution, Energy,   │
│         Simulation                                                  │
│                                                                     │
│  Services: frontend/src/services/api.js                             │
│    - planningApi.executePlanner()  → POST /agents/planner/execute   │
│    - planningApi.generatePlan()    → POST /agents/planner/plan      │
│    - alertsApi, simulationsApi, recommendationsApi, etc.            │
└────────────────────────┬────────────────────────────────────────────┘
                         │ HTTP (JSON)
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│              SUPERVISOR API  (FastAPI, backend/supervisor/main.py)  │
│                                                                     │
│  PORT: 8000   Title: "SUPADSP Unified API Contract v1.0.0"         │
│  CORS: allow_origins=["*"]                                          │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  POST /agents/planner/execute   ← PRIMARY ENTRY POINT        │  │
│  │  POST /agents/planner/plan      ← Plan-only (no dispatch)    │  │
│  │  POST /agents/planner/feedback  ← Feedback evaluation only   │  │
│  └──────────────────┬───────────────────────────────────────────┘  │
│                     │ calls PlannerAgent                            │
│  ┌──────────────────▼───────────────────────────────────────────┐  │
│  │              LLM PLANNER AGENT                               │  │
│  │  backend/agents/planner_agent/planner.py                     │  │
│  │                                                              │  │
│  │  Stage 1: plan_autonomous()   ← LLM call (Stage-1 prompt)   │  │
│  │    - Understand objective                                    │  │
│  │    - Select required specialist capabilities                 │  │
│  │    - Generate contract-compliant agent requests              │  │
│  │    - Determine next_action                                   │  │
│  │                                                              │  │
│  │  Dispatch Loop (while cycle ≤ max_cycles):                   │  │
│  │    ├─ dispatch_agent("traffic", payload)                     │  │
│  │    ├─ dispatch_agent("weather", payload)                     │  │
│  │    ├─ dispatch_agent("pollution", payload)                   │  │
│  │    ├─ dispatch_agent("energy", payload)                      │  │
│  │    └─ dispatch_agent("simulation", payload)                  │  │
│  │                                                              │  │
│  │  Stage 2: evaluate_and_replan()  ← LLM call (Stage-2 prompt)│  │
│  │    - Extract structured evidence from all agent results      │  │
│  │    - Evaluate evidence sufficiency                           │  │
│  │    - Decide: finalize | request_more_evidence | run_sim      │  │
│  │    - Prepare next cycle if needed                            │  │
│  │                                                              │  │
│  │  (optional) Stage 3: final_reasoning  ← LLM cross-domain    │  │
│  │    - Cross-domain synthesis of all findings                  │  │
│  │    - Produce final municipal recommendation                  │  │
│  └──────────────────┬───────────────────────────────────────────┘  │
│                     │ via dispatch_agent()                          │
│  ┌──────────────────▼───────────────────────────────────────────┐  │
│  │              AGENT TRANSPORT LAYER                            │  │
│  │  backend/supervisor/agent_client.py                          │  │
│  │                                                              │  │
│  │  If env URL set  → HTTP requests to remote agent microservice│  │
│  │  If no URL set   → In-process ASGI TestClient invocation     │  │
│  └──────────────────┬───────────────────────────────────────────┘  │
│                     │                                               │
│  ┌──────────────────▼───────────────────────────────────────────┐  │
│  │                SPECIALIST AGENTS (FastAPI Routers)           │  │
│  │  All mounted on the same supervisor app via include_router() │  │
│  │                                                              │  │
│  │  Traffic Agent    GET  /api/v1/traffic/kpis        (SUMO)    │  │
│  │  Traffic Agent    POST /api/v1/traffic/analyze               │  │
│  │  Traffic Agent    POST /api/v1/traffic/optimize-signal       │  │
│  │  Weather Agent    GET  /api/v1/weather/current      (static) │  │
│  │  Pollution Agent  GET  /api/v1/pollution/aqi-summary(static) │  │
│  │  Pollution Agent  GET  /api/v1/pollution/current    (static) │  │
│  │  Energy Agent     GET  /api/v1/energy/grid-status   (static) │  │
│  │  Simulation Agent POST /api/v1/simulation/run       (SUMO)   │  │
│  │  Simulation Agent GET  /api/v1/simulation/status             │  │
│  │  Simulation Agent GET  /api/v1/simulation/results            │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. COMPONENT DESCRIPTIONS

### 3.1 Frontend (`frontend/`)

| Item | Detail |
|------|--------|
| Framework | React + Vite |
| Entry point | `frontend/src/main.jsx` → `App.jsx` |
| Routing | React Router (inferred from page structure) |
| API client | `frontend/src/services/api.js` (715 lines) |
| Base URL | `import.meta.env.VITE_API_URL` or `''` (same-origin) |
| Timeout | 10 seconds (AbortController) |
| Fallback | Every API call has a static mock fallback in the `catch` block |

**Pages:**

| Page | File | Primary API Calls |
|------|------|-------------------|
| Dashboard | `pages/Dashboard.jsx` | `systemApi.getHealth()`, `alertsApi.getAlerts()`, `digitalTwinApi.getDigitalTwinState()`, `systemApi.getMonitoringEvents()` |
| Planning | `pages/Planning.jsx` | `planningApi.executePlanner()` → `/agents/planner/execute` |
| Traffic | `pages/Traffic.jsx` | `trafficApi.getKPIs()` → `/api/v1/traffic/kpis` |
| Weather | `pages/Weather.jsx` | `weatherApi.getCurrent()` → `/api/v1/weather/current` |
| Pollution | `pages/Pollution.jsx` | `pollutionApi.getCurrent()`, `pollutionApi.getAqiSummary()` |
| Energy | `pages/Energy.jsx` | `energyApi.getGridStatus()` → `/api/v1/energy/grid-status` |
| Simulation | `pages/Simulation.jsx` | `simulationApi.run()`, `simulationApi.getResults()` |

**Notable components:**
- `ProblemSolverSection.jsx` (23 KB) — The main Planning UI, submits objective to `/agents/planner/execute`
- `AQIGauge.jsx` — Renders AQI as a gauge chart
- `MetricCard.jsx` — KPI display card

---

### 3.2 Supervisor / API Gateway (`backend/supervisor/main.py`)

The supervisor is a **monolithic FastAPI application** that:
1. Defines all public and internal API contracts.
2. Contains the Planner execution loop directly.
3. Mounts all 5 specialist agent routers.
4. Maintains in-memory stores for alerts, simulations, and recommendations.

**Application metadata:**
```
Title:   "SUPADSP Unified API Contract"
Version: "1.0.0-contract"
CORS:    allow_origins=["*"]
```

---

## 4. COMPLETE API ENDPOINT MAP

### Public API — System

| Method | Endpoint | Handler | Notes |
|--------|----------|---------|-------|
| GET | `/health` | `health()` | Returns `{"service": "supervisor-contract", "status": "ONLINE"}` |
| GET | `/monitoring/status` | `monitoring_status()` | Returns domain status map + active alerts count |
| GET | `/monitoring/events` | `monitoring_events(limit)` | Returns hardcoded 2 events; limit query param |

### Public API — Planning (request lifecycle)

| Method | Endpoint | Handler | Notes |
|--------|----------|---------|-------|
| POST | `/planning/requests` | `create_planning_request()` | Creates a request record; does NOT invoke Planner |
| GET | `/planning/requests/{request_id}` | `get_planning_request()` | Returns stored planning request status |

### Internal API — Planner (core intelligence)

| Method | Endpoint | Handler | What happens |
|--------|----------|---------|--------------|
| **POST** | **`/agents/planner/execute`** | `planner_execute()` | **FULL AUTONOMOUS PIPELINE** — plan → dispatch → evaluate → (replan) → final response |
| POST | `/agents/planner/plan` | `planner_plan()` | Stage 1 only — generates agent selection plan, does NOT dispatch |
| POST | `/agents/planner/feedback` | `planner_feedback()` | Stage 2 only — evaluates pre-collected results, does NOT dispatch |

### Public API — Alerts

| Method | Endpoint | Handler | Notes |
|--------|----------|---------|-------|
| GET | `/alerts` | `list_alerts()` | Supports `?status_filter=ACTIVE\|ACKNOWLEDGED\|DISMISSED\|RESOLVED` |
| GET | `/alerts/{alert_id}` | `get_alert()` | 404 if not found |
| POST | `/alerts/{alert_id}/acknowledge` | `acknowledge_alert()` | Updates in-memory store |
| POST | `/alerts/{alert_id}/dismiss` | `dismiss_alert()` | Updates in-memory store |

### Public API — Simulations (management plane)

| Method | Endpoint | Handler | Notes |
|--------|----------|---------|-------|
| POST | `/simulations` | `create_simulation()` | Queues a named simulation, returns `simulation_id` |
| GET | `/simulations/{simulation_id}` | `get_simulation()` | Returns status (QUEUED/RUNNING/COMPLETED) |
| GET | `/simulations/{simulation_id}/results` | `get_simulation_results()` | Returns hardcoded comparison summary |

### Public API — Recommendations

| Method | Endpoint | Handler | Notes |
|--------|----------|---------|-------|
| GET | `/recommendations/{recommendation_id}` | `get_recommendation()` | 404 if not found in store |
| POST | `/recommendations/{recommendation_id}/approve` | `approve_recommendation()` | Auto-creates if missing |
| POST | `/recommendations/{recommendation_id}/reject` | `reject_recommendation()` | Auto-creates if missing |
| POST | `/recommendations/{recommendation_id}/modify` | `modify_recommendation()` | Auto-creates if missing |

### Public API — Digital Twin

| Method | Endpoint | Handler | Notes |
|--------|----------|---------|-------|
| GET | `/digital-twin/state` | `digital_twin_state()` | Returns hardcoded Narayanguda + HITECH City + Nacharam state |
| GET | `/digital-twin/state/{location}` | `digital_twin_location_state()` | Returns per-location state dict |

### Internal API — Knowledge / Data

| Method | Endpoint | Handler | Notes |
|--------|----------|---------|-------|
| POST | `/agents/knowledge/search` | `knowledge_search()` | Returns hardcoded Hyderabad policy document |
| POST | `/agents/data-discovery/discover` | `data_discovery()` | Returns synthetic dataset descriptors per domain |
| POST | `/agents/data-retrieval/retrieve` | `data_retrieval()` | Returns S3 URI stub |

### Internal API — Domain Models (evaluation stubs)

| Method | Endpoint | Handler | Notes |
|--------|----------|---------|-------|
| POST | `/models/traffic/analyze` | `traffic_model()` | Stub — returns hardcoded outputs |
| POST | `/models/flood/analyze` | `flood_model()` | Stub — returns hardcoded outputs |
| POST | `/models/energy/analyze` | `energy_model()` | Stub — returns hardcoded outputs |
| POST | `/models/weather/analyze` | `weather_model()` | Stub — returns hardcoded outputs |

### Internal API — Verification / Fail-Safe

| Method | Endpoint | Handler | Notes |
|--------|----------|---------|-------|
| POST | `/agents/verification/verify` | `verify_recommendation()` | Always returns PASSED for all checks |
| POST | `/agents/fail-safe/check` | `fail_safe_check()` | Always returns `safe_to_proceed=true` |

### Specialist Agent APIs (mounted via `include_router`)

| Method | Endpoint | Agent | Real or Simulated |
|--------|----------|-------|-------------------|
| GET | `/api/v1/traffic/kpis` | Traffic Agent | **REAL — runs Eclipse SUMO** |
| POST | `/api/v1/traffic/analyze` | Traffic Agent | REAL — SUMO |
| POST | `/api/v1/traffic/optimize-signal` | Traffic Agent | REAL — SUMO |
| GET | `/api/v1/weather/current` | Weather Agent | **Static mock data** |
| GET | `/api/v1/pollution/aqi-summary` | Pollution Agent | **Static mock data** |
| GET | `/api/v1/pollution/current` | Pollution Agent | **Static mock data** |
| GET | `/api/v1/energy/grid-status` | Energy Agent | **Static mock data** |
| POST | `/api/v1/simulation/run` | Simulation Agent | **REAL — runs Eclipse SUMO** |
| GET | `/api/v1/simulation/status` | Simulation Agent | Static stub |
| GET | `/api/v1/simulation/results` | Simulation Agent | Static stub |

---

## 5. PLANNER AGENT — DETAILED INTERNALS

### File: `backend/agents/planner_agent/planner.py`
**Class:** `PlannerAgent`

### Stage 1 — `plan_autonomous(objective, location, constraints)`
1. Calls `build_stage_1_prompt()` → constructs structured prompt with agent contracts injected.
2. Invokes `provider.generate_json(STAGE_1_PLANNER_SYSTEM_PROMPT, user_prompt, temperature=0.1)`.
3. Validates result against `LLMPlanDecision` Pydantic model.
4. **Deterministic safeguard**: Filters `agent_requests` against `ALLOWED_CAPABILITIES = {"traffic", "weather", "pollution", "energy", "simulation"}`. Any hallucinated agent name is rejected.
5. Returns `LLMPlanDecision` with: `required_capabilities`, `agent_requests`, `next_action`, `confidence`, `relevant`.

### Stage 2 — `evaluate_and_replan(objective, plan, collected_results, failures, cycle_num, max_cycles, location)`
1. Calls `validate_agent_output(cap, data)` for each capability — checks required fields exist.
2. Calls `extract_evidence(cap, data, location)` — converts raw agent data into structured `EvidenceItem` list (severity-tagged atomic metrics).
3. Calls `evaluate_and_replan_autonomous()` → LLM call with Stage-2 prompt containing all evidence.
4. LLM returns `LLMEvaluationDecision` with: `decision` (finalize|abort|replan|request_more_evidence|run_simulation), `next_action`, `next_cycle_caps`, `analysis`, `final_recommendation`, `confidence`.
5. Builds `CrossDomainAnalysis` with `key_findings`, `diagnosed_bottlenecks`, `candidate_interventions`, `tested_scenarios`, `simulation_comparison`.
6. Returns `PlannerEvaluationResponse`.

### Stage 3 (optional) — Final Reasoning
- If `eval_result.final_reasoning` is populated, it becomes the `final_response` in the API response.
- If not, the `planner_execute` loop synthesizes a fallback dict from `analysis + recommendation + confidence`.

### `planner_execute` Loop (in `supervisor/main.py`):
```
max_cycles = min(payload.max_cycles or 3, 3)  # Hard cap at 3 cycles

while current_cycle ≤ max_cycles:
    # Step A: Dispatch agents (for actions: collect_evidence | run_simulation | request_more_evidence)
    for each call in current_agent_requests:
        if capability == "simulation":
            → Inherit baseline seed/duration from traffic results
            → Generate scenario_id via SimulationService.generate_scenario_id()
            → Duplicate scenario detection (cache-hit avoidance)
            → dispatch_agent("simulation", req_payload)
        else:
            → dispatch_agent(capability, req_payload)

    # Step B: Evaluate with LLM
    eval_result = planner_agent.evaluate_and_replan(...)

    # Step C: Check termination
    if eval_result.decision in ("finalize", "abort"):
        break
    if current_cycle < max_cycles:
        current_cycle += 1
        current_agent_requests = eval_result.next_cycle_calls
    else:
        break
```

---

## 6. AGENT TRANSPORT LAYER

### File: `backend/supervisor/agent_client.py`
**Function:** `dispatch_agent(capability, context)`

**Registry (AGENT_REGISTRY):**

| Capability | Env Var | Endpoint | Method |
|------------|---------|----------|--------|
| `traffic` | `TRAFFIC_AGENT_URL` | `/api/v1/traffic/kpis` | GET |
| `weather` | `WEATHER_AGENT_URL` | `/api/v1/weather/current` | GET |
| `energy` | `ENERGY_AGENT_URL` | `/api/v1/energy/grid-status` | GET |
| `pollution` | `POLLUTION_AGENT_URL` | `/api/v1/pollution/aqi-summary` | GET |
| `simulation` | `SIMULATION_AGENT_URL` | `/api/v1/simulation/run` | POST |

**Dispatch logic:**
1. Look up `AGENT_REGISTRY[capability]`.
2. Check environment for `{CAPABILITY}_AGENT_URL`.
   - If URL set → send real HTTP request (`requests.get/post`, timeout=5s).
   - If no URL → **in-process ASGI invocation** using `fastapi.testclient.TestClient` against the agent's own `app` object (imported via `importlib`).
3. Context payload supports `_endpoint` and `_method` overrides.

> **Architecture Note**: Since all agent routers are included in the main supervisor app, the in-process TestClient path IS the default execution path when no separate microservice URLs are configured.

---

## 7. SPECIALIST AGENT FILE-LEVEL ARCHITECTURE

### Traffic Agent (`backend/agents/traffic_agent/`)

| File | Role |
|------|------|
| `main.py` | FastAPI app + router; exposes `/api/v1/traffic/kpis`, `/analyze`, `/optimize-signal` |
| `service.py` | `TrafficService` — orchestrates demand generation + SUMO execution + metrics extraction |
| `sumo_runner.py` | `SumoRunner` — manages TraCI connection, SUMO subprocess lifecycle |
| `demand_generator.py` | Generates synthetic vehicle demand (trips/routes XML) for SUMO scenarios |
| `metrics.py` | `MetricsExtractor` — reads SUMO output files, computes `congestion_index`, `average_speed_kmh`, `corridors`, `bottlenecks`, `candidate_interventions` |
| `schemas.py` | Pydantic models: `TrafficEvidenceResponse`, `SignalOptimizationRequest/Response`, `TrafficAnalyzeRequest` |

**SUMO files used:**
```
simulations/configs/narayanguda_network.net.xml   ← Road network
simulations/routes/narayanguda_routes.rou.xml     ← Vehicle routes
```

**Traffic KPI response key fields:**
```json
{
  "congestion_index": 0.62,
  "average_speed_kmh": 21.4,
  "average_delay_sec": 45.0,
  "average_waiting_time_sec": 22.1,
  "throughput": 182,
  "total_vehicles": 216,
  "corridors": [{"name": "...", "avg_speed": 18.2, "status": "HEAVY"}],
  "sensors": [{"name": "...", "speed": 14.2, "occ": 91.4, "congestion": "HEAVY"}],
  "bottlenecks": [{"corridor": "...", "reason": "...", "severity": "HEAVY"}],
  "candidate_interventions": [{"type": "signal_timing", "target": "...", "executable": true}]
}
```

---

### Simulation Agent (`backend/agents/simulation_agent/`)

| File | Role |
|------|------|
| `main.py` | FastAPI app + router; exposes `/api/v1/simulation/run` (POST) |
| `service.py` | `SimulationService` — runs intervention simulation via SUMO, compares against baseline |
| `schemas.py` | `SimulationScenarioRequest`, `SimulationEvidenceResponse` |

**Key method:** `service.run_intervention_simulation(req)` → runs SUMO with intervention applied, returns metrics + comparison dict.

**Simulation request key fields:**
```json
{
  "scenario_name": "narayanguda_signal_optimization",
  "target_location": "Narayanguda, Hyderabad",
  "seed": 42,
  "duration_seconds": 120,
  "intervention": "adaptive_signal_control",
  "baseline_metrics": { ... }
}
```

**Simulation response key fields:**
```json
{
  "scenario_id": "...",
  "scenario": "intervention_experiment",
  "intervention_applied": "adaptive_signal_control",
  "metrics": {"average_speed_kmh": 28.5, "average_delay_sec": 18.2, "congestion_index": 0.42},
  "comparison": {"speed_change_pct": +33.2, "delay_reduction_pct": 59.6, "congestion_reduction_pct": 32.3},
  "corridor_trade_offs": [...],
  "status": "SUCCESS"
}
```

---

### Weather Agent (`backend/agents/weather_agent/main.py`)

- Single file, 86 lines.
- Returns **static hardcoded data**: temperature, humidity, wind, 7-day forecast, hourly temps.
- No external API integration in the current implementation.

---

### Pollution Agent (`backend/agents/pollution_agent/main.py`)

- Single file, 102 lines.
- Returns **static hardcoded data**: city AQI=136, 4 monitoring stations, 24h forecast.
- References TSPCB sensor streams and Gaussian Plume modeling in the docstring — these are **not yet implemented**.

---

### Energy Agent (`backend/agents/energy_agent/main.py`)

- Single file, 77 lines.
- Returns **static hardcoded data**: load=78.4%, 3 substations, hourly load, 6 zone breakdown.
- No live SCADA/power grid integration in current implementation.

---

## 8. LLM INFRASTRUCTURE

### File: `backend/agents/planner_agent/llm_client.py`

**Provider abstraction:** `BaseLLMProvider` (ABC)
- Method: `generate_json(system_prompt, user_prompt, temperature, max_tokens) → Dict`

**Supported providers:**

| Provider Key | Class | Default Model |
|-------------|-------|---------------|
| `groq` | `GroqLLMProvider` | `llama-3.3-70b-versatile` |
| `openai` | `OpenAILLMProvider` | `gpt-4o` |
| `anthropic` | `AnthropicLLMProvider` | `claude-3-5-sonnet-20241022` |
| `gemini` | `GeminiLLMProvider` | `gemini-1.5-pro` |
| `mock` | `MockLLMProvider` | (for unit tests only) |

**Environment variables:**
```bash
LLM_PROVIDER=groq          # Which provider to use
LLM_MODEL=llama-3.3-70b-versatile  # Model override
LLM_API_KEY=<api-key>      # Unified API key
```

**Key properties:**
- **No automatic fallback** if the selected provider fails.
- **No automatic model fallback**.
- All providers use `generate_json()` → JSON-mode outputs only.
- `get_llm_provider()` factory reads env and instantiates the right class.

---

### File: `backend/agents/planner_agent/prompts.py`

Three prompt builders:
| Function | Stage | Purpose |
|----------|-------|---------|
| `build_stage_1_prompt()` | Stage 1 | Encodes objective + location + constraints + agent contract specs |
| `build_stage_2_prompt()` | Stage 2 | Encodes cycle history + all collected evidence + failures |
| `build_stage_3_prompt()` | Stage 3 | Encodes all cross-domain evidence for final synthesis |

---

## 9. SPECIALIST AGENT CONTRACTS (Machine-Readable)

### File: `backend/agents/planner_agent/contracts.py`

The Planner is contract-aware. Each capability has a formal contract that the LLM is given during Stage 1 planning.

| Capability | Endpoint | Method | Required Inputs | Key Outputs |
|------------|----------|--------|-----------------|-------------|
| `traffic` | `/api/v1/traffic/kpis` | GET | `location` | `congestion_index`, `average_speed_kmh`, `corridors`, `sensors` |
| `weather` | `/api/v1/weather/current` | GET | `location` | `temperature_c`, `condition`, `precipitation_mm`, `forecast_7d` |
| `pollution` | `/api/v1/pollution/aqi-summary` | GET | `location` | `city_avg_aqi`, `pm25`, `pm10`, `stations` |
| `energy` | `/api/v1/energy/grid-status` | GET | `location` | `load_pct`, `current_load_mw`, `substations` |
| `simulation` | `/api/v1/simulation/run` | POST | `scenario_name`, `target_location` | `metrics`, `sim_results`, `comparison`, `status` |

**Cross-agent context dependencies (as defined in contracts):**
- `traffic` reads context from: `weather`, `simulation`
- `weather` reads context from: (none)
- `pollution` reads context from: `traffic`, `weather`
- `energy` reads context from: `weather`, `traffic`
- `simulation` reads context from: `traffic`, `weather`

---

## 10. EVIDENCE EXTRACTION SYSTEM

### Thresholds used by `planner.py::extract_evidence()`

**Traffic:**
| Metric | CRITICAL | HIGH | MODERATE | LOW |
|--------|----------|------|----------|-----|
| `congestion_index` (%) | ≥ 75% | ≥ 60% | ≥ 40% | < 40% |
| `average_speed_kmh` | < 15 | < 22 | — | ≥ 22 |
| `average_delay_sec` | ≥ 60s | ≥ 30s | ≥ 10s | < 10s |

**Weather:**
| Metric | HIGH | MODERATE | LOW |
|--------|------|----------|-----|
| `precipitation_mm` | > 10 mm | > 0 mm | 0 mm |
| `rain_probability` (%) | ≥ 75% (CRITICAL), ≥ 50% | < 50% | — |

**Pollution:**
| Metric | CRITICAL | HIGH | MODERATE |
|--------|----------|------|----------|
| `city_avg_aqi` | ≥ 200 | ≥ 150 | < 150 |

**Energy:**
| Metric | CRITICAL | HIGH | MODERATE |
|--------|----------|------|----------|
| `load_pct` | ≥ 85% | ≥ 75% | < 75% |

---

## 11. PYDANTIC SCHEMA MAP

### Planner Agent Schemas (`backend/agents/planner_agent/schema.py`)

| Schema | Purpose |
|--------|---------|
| `LLMPlanDecision` | Output of Stage 1 LLM call |
| `LLMEvaluationDecision` | Output of Stage 2 LLM call |
| `LLMFinalReasoning` | Output of Stage 3 LLM call |
| `AgentRequest` | Structured request the LLM generates for a specialist agent |
| `AgentContextRequest` | Full context-enriched request built by `build_agent_request_context()` |
| `EvidenceItem` | Atomic evidence unit with source, metric, value, unit, severity, location, timestamp |
| `CrossDomainAnalysis` | Synthesized multi-domain findings with bottlenecks, interventions, sim comparison |
| `PlannerResponse` | Simplified response from `plan()` method (backward-compat) |
| `PlannerEvaluationResponse` | Full evaluation result from `evaluate_and_replan()` |
| `ScenarioDefinition` | Simulation scenario metadata (id, label, assumptions) |
| `SeverityLevel` | Enum: CRITICAL, HIGH, MODERATE, LOW |
| `SelectedAgentCall` | Internal tracking of which agents were called |

### Supervisor Schemas (`backend/supervisor/main.py` — inlined)

| Schema | Purpose |
|--------|---------|
| `PlannerExecuteRequest` | Input to `POST /agents/planner/execute` |
| `PlannerExecuteResponse` | Output from the same |
| `PlannerPlanRequest/Response` | Input/output for `POST /agents/planner/plan` |
| `PlannerFeedbackRequest/Response` | Input/output for `POST /agents/planner/feedback` |
| `Alert`, `AlertActionRequest/Response` | Alert lifecycle models |
| `Recommendation`, `RecommendationDecisionRequest/Response` | Recommendation lifecycle |
| `SimulationCreateRequest/Response`, `SimulationStatusResponse`, `SimulationResultResponse` | Simulation management |
| `MonitoringStatusResponse`, `MonitoringEventsResponse`, `MonitoringEvent` | Monitoring |
| `DigitalTwinStateResponse`, `DigitalTwinLocationStateResponse` | City state |

---

## 12. END-TO-END EXECUTION TRACE

### Example: "Find the risk of heavy traffic due to rainfall in Narayanguda"

```
1. USER types in Planning page (ProblemSolverSection.jsx)

2. Frontend calls:
   planningApi.executePlanner({
     objective: "Find the risk of heavy traffic due to rainfall in Narayanguda",
     location: "Narayanguda, Hyderabad",
     max_cycles: 2
   })
   → POST /agents/planner/execute

3. supervisor/main.py::planner_execute(payload) is invoked
   req_id = make_id("planreq")   # e.g. "planreq_a1b2c3d4e5f6"

4. Stage 1 — plan_autonomous():
   LLM reads agent contracts and objective.
   LLM returns:
   {
     "relevant": true,
     "required_capabilities": ["weather", "traffic"],
     "agent_requests": [
       {"agent": "weather", "request": {"location": "Narayanguda, Hyderabad"}, "reason": "Get rainfall data"},
       {"agent": "traffic", "request": {"location": "Narayanguda, Hyderabad"}, "reason": "Get traffic KPIs"}
     ],
     "next_action": "collect_evidence"
   }
   Safeguard validates both capabilities are in ALLOWED_CAPABILITIES ✓

5. Dispatch loop (cycle 1):
   dispatch_agent("weather", {"location": "Narayanguda, Hyderabad"})
   → agent_client.py checks WEATHER_AGENT_URL (not set in dev)
   → In-process TestClient call to weather_agent.app
   → GET /api/v1/weather/current
   → Returns weather JSON {temperature_c: 31.5, precipitation_mm: 0.0, condition: "Partly Cloudy", forecast_7d: [...]}

   dispatch_agent("traffic", {"location": "Narayanguda, Hyderabad"})
   → agent_client.py checks TRAFFIC_AGENT_URL (not set in dev)
   → In-process TestClient call to traffic_agent.app
   → GET /api/v1/traffic/kpis?location=Narayanguda%2C+Hyderabad
   → TrafficService.run_baseline_simulation() is called
   → SumoRunner launches Eclipse SUMO with Narayanguda network
   → TraCI executes 120 simulation steps
   → MetricsExtractor reads outputs
   → Returns TrafficEvidenceResponse {congestion_index: 0.62, average_speed_kmh: 21.4, ...}

6. Stage 2 — evaluate_and_replan():
   validate_agent_output("weather", weather_result)  → ✓ (has "condition")
   validate_agent_output("traffic", traffic_result)  → ✓ (has "congestion_index")
   extract_evidence("weather", ...)  → EvidenceItems for precipitation, condition, rain_probability
   extract_evidence("traffic", ...)  → EvidenceItems for congestion (62%), speed (21.4 km/h), corridors

   LLM receives structured evidence + objective.
   LLM evaluates: "Rainfall currently low (0mm) but forecast shows 65-80% chance Thu-Fri.
                    Traffic congestion is HIGH (62%). Combined risk is SIGNIFICANT."
   LLM returns:
   {
     "decision": "finalize",
     "next_action": "finalize",
     "goal_achieved": true,
     "analysis": "Current rainfall is minimal but Thursday-Friday forecast indicates 65-80%...",
     "final_recommendation": "Pre-position adaptive signal timing for Narayanguda corridor...",
     "confidence": 0.88
   }

7. final_reasoning_dict is assembled from eval_result.
   CrossDomainAnalysis includes key_findings, diagnosed_bottlenecks.

8. PlannerExecuteResponse is returned:
   {
     "request_id": "planreq_a1b2c3d4e5f6",
     "status": "COMPLETED",
     "cycle": 1,
     "selected_capabilities": ["weather", "traffic"],
     "dispatched_agents": ["weather_agent", "traffic_agent"],
     "agent_results": {weather: {...}, traffic: {...}},
     "planner_feedback": {
       "decision": "finalize",
       "confidence": 0.88,
       "insights": {
         "recommendation": "Pre-position adaptive signal timing...",
         "analysis": "..."
       }
     },
     "final_response": {
       "summary": "...",
       "recommendation": "...",
       "confidence": 0.88
     }
   }

9. Frontend planningApi.executePlanner() receives the response.
   Normalizes: task_id, collected_results, planner_feedback.
   ProblemSolverSection.jsx renders the recommendation, agent results, and confidence scores.
```

---

## 13. TRAFFIC INTERVENTIONS TABLE

Interventions the system can reason about, defined in `contracts.py`:

| Intervention Type | Description | Executable via SUMO? |
|-------------------|-------------|---------------------|
| `signal_timing` | Adjust green/red phase durations | ✓ Yes |
| `adaptive_signal_control` | Dynamic signal control based on density | ✓ Yes |
| `rerouting` | Redirect vehicles to alternate routes | ✓ Yes |
| `traffic_diversion` | Divert traffic away from congested corridors | ✓ Yes |
| `lane_use_changes` | Change lane assignments | ✓ Yes |
| `turn_restrictions` | Block or allow specific turn movements | ✓ Yes |
| `road_closure` | Close a road segment entirely | ✓ Yes |
| `traffic_demand_management` | Restrict demand by time-of-day | ✓ Yes |
| `incident_response` | Traffic response to incidents or hazards | ✓ Yes |
| `combined_strategy` | Compound of multiple interventions | ✓ Yes |

---

## 14. REAL vs. MOCK/STUB COMPONENT TABLE

| Component | Status | Details |
|-----------|--------|---------|
| Traffic Agent — SUMO simulation | **REAL** | Runs Eclipse SUMO 1.27.1 via TraCI on Narayanguda network |
| Simulation Agent — SUMO simulation | **REAL** | Runs SUMO for intervention experiments |
| LLM Planner — Groq/OpenAI/Anthropic/Gemini | **REAL** | Actual LLM API calls with JSON mode |
| Weather Agent data | **Static Mock** | Hardcoded Hyderabad data in `weather/main.py` |
| Pollution Agent data | **Static Mock** | Hardcoded AQI=136, 4 stations |
| Energy Agent data | **Static Mock** | Hardcoded load=78.4%, 3 substations |
| Alerts store | **In-memory Mock** | 4 hardcoded alerts; no database persistence |
| Simulations store (management) | **In-memory stub** | `/simulations` endpoints do not invoke SUMO |
| Recommendations store | **In-memory Mock** | No persistence; auto-created on approve/reject |
| Knowledge Search | **Stub** | Returns 1 hardcoded Hyderabad policy document |
| Data Discovery / Retrieval | **Stub** | Returns synthetic dataset descriptors |
| Domain Model Evaluation (`/models/*`) | **Stub** | Returns hardcoded KPI deltas |
| Verification (`/agents/verification`) | **Stub** | Always returns PASSED |
| Fail-Safe (`/agents/fail-safe`) | **Stub** | Always returns safe_to_proceed=true |
| Digital Twin State | **Static Mock** | Hardcoded Narayanguda/HITECH/Nacharam values |
| Database (Postgres/TimescaleDB) | **Configured, not used** | Defined in docker-compose; not connected in current code |
| Redis | **Configured, not used** | Defined in docker-compose; not connected |
| MinIO | **Configured, not used** | Defined in docker-compose; S3 URIs are stubs |
| Kafka | **Configured, not used** | Defined in docker-compose; no consumers/producers in code |

---

## 15. INFRASTRUCTURE & DEPLOYMENT

### Docker Compose Services (`docker-compose.yml`)

| Service | Image / Port | Role |
|---------|-------------|------|
| `supervisor` | `backend/Dockerfile` / 8000 | Main API server |
| `postgres` | `postgres:15` / 5432 | TimescaleDB — configured but not used in current code |
| `redis` | `redis:7` / 6379 | Cache — configured but not used |
| `minio` | `minio/minio` / 9000 | Object store — configured but not used |
| `kafka` | Confluent / 9092 | Event streaming — configured but not used |

### Environment Variables (`.env.example`)

| Variable | Purpose |
|----------|---------|
| `LLM_PROVIDER` | LLM backend: `groq`, `openai`, `anthropic`, `gemini` |
| `LLM_MODEL` | Model name override |
| `LLM_API_KEY` | API key for the selected provider |
| `TRAFFIC_AGENT_URL` | Remote URL for Traffic Agent (optional; in-process if unset) |
| `WEATHER_AGENT_URL` | Remote URL for Weather Agent |
| `ENERGY_AGENT_URL` | Remote URL for Energy Agent |
| `POLLUTION_AGENT_URL` | Remote URL for Pollution Agent |
| `SIMULATION_AGENT_URL` | Remote URL for Simulation Agent |
| `DATABASE_URL` | Postgres connection string |
| `REDIS_URL` | Redis connection string |

---

## 16. FILE-LEVEL RESPONSIBILITY TABLE

| File | Layer | Responsibility |
|------|-------|---------------|
| `frontend/src/services/api.js` | Frontend | Unified API client; all HTTP calls; mock fallbacks |
| `frontend/src/pages/Planning.jsx` | Frontend | Main planner UI with problem solver |
| `frontend/src/pages/Dashboard.jsx` | Frontend | City-wide overview dashboard |
| `frontend/src/pages/Traffic.jsx` | Frontend | Traffic KPI visualizations |
| `frontend/src/pages/Weather.jsx` | Frontend | Weather telemetry display |
| `frontend/src/pages/Pollution.jsx` | Frontend | AQI and pollution metrics |
| `frontend/src/pages/Energy.jsx` | Frontend | Grid load and substation status |
| `frontend/src/pages/Simulation.jsx` | Frontend | SUMO simulation results viewer |
| `frontend/src/components/ProblemSolverSection.jsx` | Frontend | Problem statement input + planner result rendering |
| `backend/supervisor/main.py` | API Gateway | FastAPI app; all routes; planner execution loop; in-memory stores |
| `backend/supervisor/agent_client.py` | Transport | Dispatch agents via HTTP or in-process ASGI |
| `backend/agents/planner_agent/planner.py` | Intelligence | PlannerAgent class; 3-stage LLM reasoning; evidence extraction |
| `backend/agents/planner_agent/contracts.py` | Intelligence | Specialist agent machine-readable contracts |
| `backend/agents/planner_agent/schema.py` | Intelligence | Pydantic models for all planner I/O |
| `backend/agents/planner_agent/prompts.py` | Intelligence | Stage 1/2/3 prompt builders |
| `backend/agents/planner_agent/llm_client.py` | Intelligence | LLM provider abstraction + 4 provider implementations |
| `backend/agents/traffic_agent/main.py` | Specialist | Traffic FastAPI app + router |
| `backend/agents/traffic_agent/service.py` | Specialist | `TrafficService` — SUMO orchestration logic |
| `backend/agents/traffic_agent/sumo_runner.py` | Specialist | `SumoRunner` — TraCI interface |
| `backend/agents/traffic_agent/demand_generator.py` | Specialist | Synthetic trip demand XML generation |
| `backend/agents/traffic_agent/metrics.py` | Specialist | SUMO output parsing + KPI computation |
| `backend/agents/traffic_agent/schemas.py` | Specialist | Traffic Pydantic models |
| `backend/agents/simulation_agent/main.py` | Specialist | Simulation FastAPI app + router |
| `backend/agents/simulation_agent/service.py` | Specialist | `SimulationService` — intervention SUMO run + comparison |
| `backend/agents/simulation_agent/schemas.py` | Specialist | Simulation Pydantic models |
| `backend/agents/weather_agent/main.py` | Specialist | Weather FastAPI app + static data |
| `backend/agents/pollution_agent/main.py` | Specialist | Pollution FastAPI app + static data |
| `backend/agents/energy_agent/main.py` | Specialist | Energy FastAPI app + static data |
| `simulations/configs/narayanguda_network.net.xml` | Simulation Data | Eclipse SUMO road network for Narayanguda |
| `simulations/routes/narayanguda_routes.rou.xml` | Simulation Data | Vehicle demand routes for SUMO |

---

## 17. DISCREPANCIES: DOCUMENTATION vs. ACTUAL CODE

| Item | Documentation / Plan | Actual Implementation |
|------|---------------------|----------------------|
| Orchestrator | Mentioned in earlier plans; to be removed | **Not present in code** — correctly absent |
| TSPCB sensor integration | Mentioned in Pollution Agent docstring | **Not implemented** — static hardcoded data |
| Gaussian Plume modeling | Mentioned in Pollution Agent docstring | **Not implemented** |
| TimescaleDB persistence | Defined in docker-compose | **Not connected** in any agent or supervisor code |
| Redis cache | Defined in docker-compose | **Not used** |
| MinIO / S3 storage | S3 URI returned as stub | **Not connected** |
| Kafka event streaming | Defined in docker-compose | **No producers/consumers** in code |
| `/simulations` management plane | Creates simulation_id | **Does NOT invoke SUMO** — only manages an in-memory status record |
| `/models/*/analyze` endpoints | Listed as domain model evaluation | **Stubs** returning hardcoded KPI deltas |
| `/agents/verification/verify` | Verification guardrail | **Always PASSED** — no real checks |
| `/agents/fail-safe/check` | Safety guardrail | **Always safe** — no real checks |
| `flood` domain | Listed in `Domain` enum; alert ALERT_04 exists | **No flood specialist agent** exists |

---

## 18. KNOWN LIMITATIONS

1. **No live sensor integration** — Weather, Pollution, and Energy agents return static hardcoded data, not real city telemetry.
2. **No database persistence** — All state (alerts, recommendations, simulations) is in-memory and lost on restart.
3. **Flood domain** — Listed in `Domain` enum, ALERT_04 is a flood alert, but there is no `flood_agent` implemented.
4. **No LLM fallback** — If the configured LLM provider fails, the entire `/agents/planner/execute` call returns HTTP 503. No retries.
5. **Single-server architecture** — All routers (supervisor + 5 specialists) are mounted on one FastAPI app; microservice deployment requires setting the `*_AGENT_URL` environment variables.
6. **Verification/Fail-Safe are stubs** — Both endpoints always pass; no real policy enforcement.
7. **Knowledge Base is a stub** — Returns 1 hardcoded policy document; no vector store or document retrieval system.
8. **simulation_id management plane** does not connect to actual SUMO simulations — it is a separate administrative interface.

---

*Audit performed by code inspection. No files were modified. All findings derived from actual implementation.*
