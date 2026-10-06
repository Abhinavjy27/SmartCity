# Traffic Agent Specification & Architecture Guide

## 1. Role & Responsibilities

In the SmartCity / SUPADSP multi-agent architecture:
```
Frontend ──► LLM Planner ──► Specialist Agents ──► LLM Planner ──► Frontend
```

### Architectural Responsibilities:
- **Traffic Agent**: **Analyzes and Proposes.** Extracts empirical observations from Eclipse SUMO microsimulations, diagnoses corridor bottlenecks from telemetry, proposes structured candidate interventions across categories, and computes potential pre-simulation trade-offs.
- **LLM Planner**: **Decides.** Serves as the sole coordinator and intelligent decision authority. Evaluates candidate interventions, selects experiments to run, compares multi-scenario results, and synthesizes policy recommendations.
- **Simulation Agent**: **Executes.** Runs candidate intervention experiments in Eclipse SUMO via TraCI in-memory program modifications and returns comparative evidence to the Planner.

> [!IMPORTANT]
> **ABSOLUTE INVARIANT: NO ORCHESTRATOR.**
> The Traffic Agent does NOT make executive policy choices, select final interventions, or route tasks to other agents.

---

## 2. API Endpoints & Contracts

### A. `GET /api/v1/traffic/kpis`
Returns baseline traffic telemetry and analysis for a given location, scenario, duration, and random seed.

**Query Parameters:**
- `location` (str): Target locality (default: `"Narayanguda, Hyderabad"`).
- `scenario` (str): Synthetic demand scenario (`synthetic_normal`, `synthetic_peak_northbound`, `synthetic_peak_southbound`, etc.).
- `duration_seconds` (int): Simulation window in seconds (default: `120`).
- `seed` (int): Deterministic random seed (default: `42`).
- `purpose` (str): Contextual objective (default: `"baseline_traffic_analysis"`).
- `force_fresh` (bool): Bypass cache if true.

### B. `POST /api/v1/traffic/analyze`
Accepts a `TrafficAnalyzeRequest` JSON payload and returns the structured `TrafficEvidenceResponse`.

**Request Body (`TrafficAnalyzeRequest`):**
```json
{
  "location": "Narayanguda, Hyderabad",
  "scenario": "synthetic_normal",
  "duration_seconds": 120,
  "seed": 42,
  "purpose": "baseline_traffic_analysis",
  "force_fresh": false
}
```

### C. `POST /api/v1/traffic/optimize-signal`
Accepts candidate signal optimization parameters, validates defensive safety bounds, and returns parameterized candidate configurations.

**Request Body (`SignalOptimizationRequest`):**
```json
{
  "intersection_id": "cluster_308783170_3158879059_3217073805_4433969588",
  "target_corridor": "Westbound",
  "green_time_adjustment_sec": 15.0,
  "current_cycle_sec": 120
}
```

**Response (`SignalOptimizationResponse`):**
```json
{
  "status": "CANDIDATES_GENERATED",
  "intersection_id": "cluster_308783170_3158879059_3217073805_4433969588",
  "target_corridor": "Westbound",
  "candidates": [
    {
      "intersection_id": "cluster_308783170_3158879059_3217073805_4433969588",
      "target_corridor": "Westbound",
      "green_time_adjustment_sec": 5.0,
      "min_green_sec": 10.0,
      "max_green_sec": 60.0,
      "cycle_sec": 120,
      "executable": true,
      "rationale": "Conservative green extension (+5s) for slight queue clearance with minimal cross-street impact."
    },
    {
      "intersection_id": "cluster_308783170_3158879059_3217073805_4433969588",
      "target_corridor": "Westbound",
      "green_time_adjustment_sec": 10.0,
      "min_green_sec": 10.0,
      "max_green_sec": 60.0,
      "cycle_sec": 120,
      "executable": true,
      "rationale": "Balanced green extension (+10s) clearing peak queues while maintaining opposing corridor stability."
    },
    {
      "intersection_id": "cluster_308783170_3158879059_3217073805_4433969588",
      "target_corridor": "Westbound",
      "green_time_adjustment_sec": 15.0,
      "min_green_sec": 10.0,
      "max_green_sec": 60.0,
      "cycle_sec": 120,
      "executable": true,
      "rationale": "Moderate-high green extension (+15s) for significant bottleneck relief."
    }
  ],
  "validation_status": "VALID",
  "timestamp": "2026-09-18T03:15:00+00:00",
  "message": "Generated 3 bounded signal timing candidates for Westbound."
}
```

---

## 3. Evidence-Based Telemetry & Observations

The `TrafficEvidenceResponse` provides structured, unmanipulated telemetry directly from the TraCI per-vehicle lifecycle ledger:

- `network_average_speed_kmh`: Mean observed vehicle speed in km/h across active vehicle-seconds (`None` if 0 vehicles).
- `average_delay_sec`: Mean terminal time loss per simulated vehicle compared to ideal free-flow (`None` if 0 vehicles).
- `average_waiting_time_sec`: Mean accumulated time spent with speed $< 0.1\text{ m/s}$ (`None` if 0 vehicles).
- `congestion_index`: Dimensionless metric $\max(0.0, \min(1.0, 1.0 - \frac{\text{speed}}{\text{free\_flow}}))$.
- `throughput`: Count of unique vehicles arriving at destination (completed trips).
- `max_halting_vehicles`: Peak simultaneous halting vehicles ($\text{speed} < 0.1\text{ m/s}$).
- `teleported_vehicles`: Count of vehicles teleported due to gridlock timeout.
- `corridors`: Per-corridor empirical speed and status (`SMOOTH`, `MODERATE`, `HEAVY`, `CRITICAL`, or `NO_DATA`).

---

## 4. Dynamic Bottleneck Detection

Bottleneck detection is strictly evidence-driven:
1. **Critical/Heavy Corridors**: If any corridor is classified `CRITICAL` ($< 14\text{ km/h}$) or `HEAVY` ($< 22\text{ km/h}$), it is flagged as an active bottleneck.
2. **Lowest Observed-Speed Corridor**: When all corridors are `SMOOTH` or `MODERATE`, the corridor with the lowest observed speed is identified (e.g. Westbound at 35.0 km/h in normal demand, or Southbound in peak southbound demand).
3. **No Hardcoding**: Corridors are never hardcoded. Under different demand distributions (e.g. `synthetic_peak_southbound`), Southbound is dynamically diagnosed.
4. **Gridlock Teleports**: If `teleported_vehicles > 0`, network-level junction starvation is diagnosed.

---

## 5. Candidate Interventions: Executable vs. Candidate-Only

The Traffic Agent generates structured candidates across 4 core categories:

| Category | Target | Executable in Current Milestone | Execution Mechanics / Rationale |
| :--- | :--- | :--- | :--- |
| **`signal_timing`** | Diagnosed corridor phase | **YES (`executable: true`)** | Dynamically modifies green phase allocation in-memory via TraCI `setCompleteRedYellowGreenDefinition`. Bounded (+5s, +10s, +15s, +19s). |
| **`rerouting`** | Arterial diversion | **NO (`executable: false`)** | Candidate specification. Current SUMO Narayanguda network and synthetic static demand do not expose dynamic route reassignment without risk of simulation deadlocks. |
| **`lane_use`** | Approach lanes | **NO (`executable: false`)** | Candidate specification. Fixed OSM multi-lane geometry does not support dynamic reversible lanes without modifying the base `.net.xml` file. |
| **`incident_response`** | Corridor clearance / speed harmonization | **NO (`executable: false`)** | Candidate specification. Requires dynamic obstruction injection or lane closure via TraCI. |

---

## 6. Pre-Simulation Potential Trade-Offs

The Traffic Agent identifies potential corridor interactions before simulation:
- **`signal_timing`**: Extending green duration on the target corridor (e.g. Westbound) will reduce green split for conflicting/opposing phases (e.g. Southbound), potentially increasing opposing queue delays.
- **`rerouting`**: Diverting traffic reduces volume on the target arterial but may shift volume onto secondary perimeter streets.
- **`lane_use`**: Adding an inbound lane reduces opposing lane capacity, potentially creating a reverse bottleneck.

The Traffic Agent clearly labels these as **potential trade-offs**. Only the Simulation Agent measures empirical trade-offs.
