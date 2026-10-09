# Pollution Agent Grounding & Verification Subsystem

## Overview
The Grounding & Verification subsystem ensures that the Planning AI chat (`localhost:3000/planning` via supervisor port 8000) answers ANY Hyderabad air-quality question accurately, apt to the question, and exclusively from verified sources (CPCB NAQI engine, OpenAQ live telemetry, `TemporalGRU_KNNCovariate` 7-day forecast model, and `live_accumulation.py`).

## Core Invariants
1. **Zero Hallucination / Zero Fabrication**:
   - Every AQI value and pollutant concentration comes directly from `aqi_engine.py` or tool outputs.
   - The LLM performs zero arithmetic on AQI or breakpoints.
   - Missing data returns `unavailable` (never synthetic interpolation or speculative estimates).
2. **Deterministic Verifier**:
   - Compares all numeric values in generated responses against tool execution payloads and verified fact sheet.
   - Enforces staleness reporting when `is_stale=true` (e.g. data older than 3 hours).
   - Enforces that any forecast mention is labelled `PREDICTED`.
   - Rejects real-world causal assertions (e.g. "traffic caused this", "industrial emissions caused this") unless accompanied by an explicit disclaimer that the system lacks source-attribution sensors.
3. **Seamless Planning AI UI Integration**:
   - Output format strictly adheres to the schema required by `Planning.jsx`:
     - `text`: Single-paragraph introduction summarizing findings.
     - `insights`: 1 to 5 high-priority bullet insights.
     - `suggestions`: Exactly 3 follow-up action chips.
4. **Zero Non-Pollution Change**:
   - Traffic, energy, weather, and general queries pass through untouched, receiving the generic multi-domain adaptive intervention response.
   - When `POLLUTION_GROUNDING=false`, the hook is completely bypassed with byte-identical behavior.

---

## Tool Functions (`backend/agents/pollution_agent/grounding/tools.py`)
1. `get_current(station=None)`: Current observed AQI for Hyderabad city or a specific station. Returns concentrations, dominant pollutant, and staleness metadata.
2. `explain_station_aqi(station)`: Detailed breakdown of station AQI, rank among 15 stations, dominant pollutant margin, sub-indices, and averaging window.
3. `compare_stations(station_a=None, station_b=None)`: Compares two stations (or highest vs lowest) with difference in AQI points.
4. `get_station_history(station, days=7)`: Archive and live-store daily rolling values.
5. `get_forecast(horizon=7)`: 7-day predicted AQI trajectory, explicitly labelled `PREDICTED`, with per-horizon MAE and directional accuracy limits.
6. `get_data_status()`: Live accumulation tracking, consecutive live days, gap dates, and 14-day switchover status.
7. `compute_aqi(pollutants)`: Direct call to `aqi_engine.py` for deterministic sub-index interpolation and dominant pollutant derivation.
8. `resolve_station(query)`: Station resolver with exact, alias, and fuzzy matching (0.75 threshold). Unknown/unmonitored locations return `found: False`.

---

## Environment Flags
- `POLLUTION_GROUNDING=true|false`: Enables the grounding router in the supervisor's `POST /api/planning/chat`.
- `POLLUTION_VERIFY=true|false`: Enables the deterministic output verifier and retry loop.
- `POLLUTION_LIVE_MODE=true|false`: Uses live OpenAQ telemetry when available; falls back to historical archive.

---

## Running Evaluation and Tests

### 1. Run Grounding Unit Test Suite (24 tests)
```bash
python -m pytest backend/agents/pollution_agent/test_grounding.py -v
```

### 2. Run Existing Pollution Agent Regression Tests (137 tests)
```bash
python -m pytest backend/agents/pollution_agent/tests.py -v
python -m pytest backend/agents/pollution_agent/test_forecast_7d.py backend/agents/pollution_agent/test_unified_forecast.py backend/agents/pollution_agent/test_cpcb_crosscheck.py -v
```

### 3. Run Full 123-Question Golden Set Evaluation
```bash
python backend/agents/pollution_agent/eval/run_eval.py
```
This tests all 123 golden set questions across 8 categories plus 20 non-pollution regression questions against the live supervisor endpoint (`POST /api/planning/chat`).
Output is saved to `backend/agents/pollution_agent/eval/eval_scorecard.json`.
