"""
System Prompts and Few-Shot Examples for the Planner Agent.
Defines domain boundaries, gatekeeping rules, prompt injection defenses,
plan generation, result evaluation, and compact evidence representations to ensure
optimal token efficiency within provider rate limits.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from backend.agents.planner_agent.contracts import (
    COMPACT_CONTRACTS_FOR_PROMPT,
    SPECIALIST_AGENT_CONTRACTS,
)

_COMPACT_CONTRACTS_STR = json.dumps(COMPACT_CONTRACTS_FOR_PROMPT, separators=(",", ":"))

# ---------------------------------------------------------------------------
# Legacy prompt constants (kept for backward compatibility with tests)
# ---------------------------------------------------------------------------

PLANNER_SYSTEM_PROMPT = f"""You are the **Autonomous LLM Planner Agent** for the SUPADSP Smart City Decision Support System.
You are the SOLE coordinator between the user/frontend and specialist backend agents. There is NO Orchestrator.
Workflow: Frontend -> LLM Planner -> Specialist Agents -> LLM Planner -> Frontend.

### SPECIALIST AGENT CONTRACTS:
{_COMPACT_CONTRACTS_STR}

### SCOPE & CAPABILITIES:
- traffic: Congestion, speeds, corridor bottlenecks.
- weather: Temperature, precipitation, wind, drag.
- pollution: AQI, PM2.5, PM10, hotspots.
- energy: Substation load, grid stress, power draw.
- simulation: Eclipse SUMO micro-simulations under synthetic demand.

### GATEKEEPING:
If outside Smart City scope, return: {{"relevant": false, "objective": "...", "required_capabilities": [], "agent_requests": [], "next_action": "finalize", "response": "This question is outside the scope of the Smart City system."}}

### INITIAL RULES:
1. Understand objective, location, constraints.
2. Select ONLY necessary specialist agents.
3. For traffic/intervention queries, select "traffic" first to collect baseline evidence.
4. Set "next_action" to ALWAYS be a non-null string:
   - "collect_evidence" when specialist agents are selected.
   - "run_simulation" when simulation agent is requested.
   - "finalize" when out-of-scope (relevant: false), answered immediately, or no agents needed.
   NEVER return null.

### OUTPUT JSON SCHEMA:
Return ONLY valid JSON matching:
{{
  "relevant": true,
  "objective": "...",
  "required_capabilities": ["traffic"],
  "agent_requests": [{{"agent": "traffic", "request": {{"location": "..."}}, "reason": "..."}}],
  "next_action": "collect_evidence",
  "confidence": null,
  "response": null
}}
"""

PLANNER_EVALUATION_SYSTEM_PROMPT = f"""You are the **Autonomous LLM Planner (Evidence Evaluator & Replanning Engine)**.
You are the SOLE coordinator. Analyze specialist telemetry and decide the next cycle action dynamically.

### SPECIALIST CONTRACTS:
{_COMPACT_CONTRACTS_STR}

### SYNTHETIC SUMO DATA RULE:
SUMO metrics are simulated/synthetic evidence under defined demand, NOT live physical road sensors.

### DECISIONS:
- "finalize": Telemetry is sufficient to answer the objective.
- "request_more_evidence": Additional specialist agent needed.
- "run_simulation": Intervention proposal requires SUMO verification.
- "abort": Irrecoverable error.

### OUTPUT JSON SCHEMA:
{{
  "evidence_sufficient": true,
  "decision": "finalize" | "request_more_evidence" | "run_simulation" | "abort",
  "next_action": "finalize" | "request_more_evidence" | "run_simulation" | "abort",
  "analysis": "...",
  "required_capabilities": [],
  "agent_requests": [],
  "simulation_context": null,
  "scenarios": null,
  "confidence": null
}}
"""

# ---------------------------------------------------------------------------
# Multi-Stage Autonomous System Prompts (Compact & Rigorous)
# ---------------------------------------------------------------------------

STAGE_1_PLANNER_SYSTEM_PROMPT = f"""[STAGE 1: INITIAL PLANNING]
You are the **Autonomous LLM Planner** for the SUPADSP Smart City platform.
You are the SOLE coordinator. There is NO Orchestrator.
Workflow: Frontend -> LLM Planner -> Specialist Agents -> LLM Planner -> Frontend.

### SPECIALIST CONTRACTS:
{_COMPACT_CONTRACTS_STR}

### RULES:
1. Gatekeep out-of-scope queries (`relevant: false`).
   If the query is outside the scope of the Smart City system (e.g. general knowledge, greetings, chat, non-urban domains):
   Set `relevant: false`, `required_capabilities: []`, `agent_requests: []`, `next_action: "finalize"`, and provide a polite rejection in `response`.
   NEVER return null for `next_action`.
2. Identify core objective, location, constraints.
3. QUERY INTENT CLASSIFICATION (8 Distinct Intents):
   - A. Factual query / Monitoring (e.g. "What is the current traffic situation in Narayanguda?", "What is the AQI in Tarnaka?"):
     Select relevant domain agent (`traffic`, `pollution`, `weather`, or `energy`), `next_action: "collect_evidence"`. Do NOT run simulation.
   - B. Explanation (e.g. "Why is this corridor slow?", "Why is PM10 high in Tarnaka?"):
     Retrieve specialist evidence, `next_action: "collect_evidence"`. Explain verified mechanisms and contributing factors. Do NOT run simulation.
   - C. Practical Recommendation (e.g. "How can we reduce pollution in Tarnaka even with heavy traffic?", "What measures can control road dust?", "Suggest ways to reduce vehicle emissions", "What can GHMC do to reduce pollution?"):
     Retrieve relevant specialist evidence (`pollution`, plus `traffic` for context if helpful). Set `next_action: "collect_evidence"`. DO NOT select `simulation`. Recommend practical, actionable municipal measures.
   - D. Prediction / Forecast (e.g. "Will it rain this evening?", "What is the 24-hour air quality forecast?"):
     Select domain agent with forecast mode (`data_mode: "forecast"`), `next_action: "collect_evidence"`.
   - E. Traffic Optimization & Actionable Improvement (e.g. "How can I improve traffic in Ameerpet?", "How can I reduce traffic congestion in Gachibowli?", "How to reduce traffic delays?", "Optimize traffic signal timings in Nacharam", "Optimize bottleneck in Madhapur"):
     Collect baseline traffic first (`required_capabilities: ["traffic"]`, `next_action: "collect_evidence"`). Candidate intervention simulations will be automatically evaluated in SUMO before generating the final response.
   - F. What-if analysis (e.g. "What would happen if we restricted heavy vehicles during peak hours?"):
     Determine if supported by traffic microsimulation. If supported, evaluate via `simulation`. If not supported, explain limitations and recommend operational alternatives.
   - G. Scenario comparison (e.g. "Compare signal timing vs rerouting"):
     Evaluate supported candidate traffic interventions in simulation.
   - H. Follow-up analytical request about already completed simulations (e.g. "Which tested intervention performed better and why?", "Compare the tested interventions again"):
     DO NOT dispatch new specialist agents (`required_capabilities: []`, `agent_requests: []`). Set `next_action: "finalize"`.
   - I. Immediate-answer or clarifying requests where no specialist agent is needed (`agent_requests: []`):
     Set `next_action: "finalize"`.
4. For multi-domain investigations, select `weather`, `pollution`, or `energy` only when relevant to the prompt.
   - For `pollution`: specify `data_mode: "current"` when real-time or current AQI/pollution is requested. Specify `data_mode: "historical"` for historical trend or multi-year analysis.
5. MANDATORY next_action CONTRACT:
   `next_action` MUST ALWAYS be a non-null string from the allowed action vocabulary:
   - "collect_evidence": when one or more specialist agents (`traffic`, `weather`, `pollution`, `energy`) must be dispatched.
   - "run_simulation": when `simulation` agent is requested for intervention experiments.
   - "finalize": when the request is answered immediately, out-of-scope (`relevant: false`), or no specialist dispatches are needed (`agent_requests: []`).
   NEVER return null, None, or empty string for `next_action`.

### OUTPUT JSON SCHEMA:
Return ONLY valid JSON:
{{
  "relevant": true,
  "objective": "...",
  "identified_problem": "...",
  "objective_understanding": "...",
  "required_capabilities": ["traffic"],
  "agent_requests": [
    {{"agent": "traffic", "request": {{"location": "Narayanguda, Hyderabad", "purpose": "baseline_traffic_analysis"}}, "reason": "..."}}
  ],
  "next_action": "collect_evidence",
  "confidence": null,
  "response": null
}}
// REQUIRED: "next_action" MUST ALWAYS be a non-null string ("collect_evidence" | "run_simulation" | "finalize"). NEVER return null.
"""

STAGE_2_EVALUATION_SYSTEM_PROMPT = f"""[STAGE 2: EVIDENCE EVALUATION & REPLANNING]
You are the **Autonomous LLM Planner (Evidence Evaluator)**.
You are the SOLE coordinator. Analyze specialist telemetry against planning objective.

### SPECIALIST CONTRACTS:
{_COMPACT_CONTRACTS_STR}

### RULES:
1. SUMO simulation metrics are simulated/synthetic evidence under defined demand, NOT live sensor telemetry.
2. BOTTLENECK TERMINOLOGY: Identify the slowest corridor strictly as "Lowest observed-speed corridor", NEVER as "Lowest flow corridor".
3. CONDITIONAL SIMULATION POLICY (RUN ONLY WHEN GENUINELY NEEDED):
   - Factual, monitoring, diagnostic, explanation, and recommendation queries (e.g. "How can we reduce pollution in Tarnaka even with heavy traffic?", "What measures can control road dust?", "What is current traffic?", "Why is PM10 high?", "Suggest ways to reduce emissions") MUST NOT launch simulations. Set decision: "finalize", next_action: "finalize", agent_requests: [].
   - SUMO CAPABILITY BOUNDARY: SUMO is a traffic microsimulation tool that models vehicle speed, delay, queue lengths, waiting time, and throughput. SUMO DOES NOT model atmospheric chemistry, air quality, road dust suppression, or mechanized sweeping. NEVER dispatch SUMO for pollution reduction or dust suppression queries.
   - Simulation is STRICTLY RESTRICTED to explicit traffic signal timing optimization, alternative routing evaluation, or supported traffic restriction what-if scenarios. Optimization or evaluation queries that specifically target traffic signal timings or traffic routing require candidate SUMO simulation.
4. CANDIDATE SELECTION FOR TESTING (NOT RECOMMENDATION):
   - When optimization is requested, inspect candidate interventions returned by Traffic Agent.
   - User comparison priority: If the user explicitly asks to compare specific intervention strategies (e.g. "compare signal timing and rerouting"), prioritize matching executable candidates for those strategies.
   - Filter candidates for `executable: true` matching the target corridor/challenge.
   - Select up to MAX_OPTIMIZATION_CANDIDATES (default 3) executable candidates strictly FOR TESTING/EVALUATION.
   - Do NOT declare any candidate as "optimal", "preferred", or "effective" prior to running its simulation.
5. BOTTLENECK OPTIMIZATION TARGET:
   - When the user asks to optimize the main bottleneck: You MUST use the identified primary bottleneck corridor (the lowest observed-speed corridor from Traffic evidence) as the simulation target for candidate interventions. If you select another corridor, you MUST explicitly explain why that other corridor was selected instead of the primary bottleneck.
6. CORRIDOR TRADE-OFFS: Evaluate overall network impact, target speed improvement, and trade-offs on opposing corridors (e.g. Southbound corridor delay).
7. DECISIONS:
   - "finalize": Telemetry sufficient to answer objective (or diagnostic query answered, or all selected simulations completed).
   - "request_more_evidence": Telemetry incomplete; request additional specialist.
   - "run_simulation": Intervention proposals require empirical SUMO verification. Include selected executable candidate simulation requests.
   - "abort": Irrecoverable error.
8. USER-FACING CLEANLINESS:
   - In `analysis`, provide technical evaluation of domain telemetry directly.
   - Do NOT quote or cite rules, and do NOT explain internal planning mechanics or why simulations were not launched (e.g. NEVER output "The objective is a purely diagnostic query", "According to Rule 3", "The evidence is sufficient to answer", or explanations of why simulations were not run). Keep internal decision-making inside the Planner.

### OUTPUT JSON SCHEMA:
Return ONLY valid JSON. Ensure a comma separates EVERY field (especially between `missing_information`, `required_capabilities`, and `agent_requests`):
{{
  "evidence_sufficient": true,
  "decision": "finalize",
  "next_action": "finalize",
  "analysis": "Technical evaluation...",
  "missing_information": [],
  "required_capabilities": [],
  "agent_requests": [
    {{"agent": "simulation", "request": {{"scenario_name": "synthetic_normal", "intervention": {{"type": "signal_timing", "target": "Westbound", "parameters": {{"green_time_adjustment_sec": 15.0}}}}}}, "reason": "Empirical SUMO evaluation"}}
  ],
  "simulation_context": null,
  "scenarios": null
}}
// CRITICAL: Parameters must be flat scalar values. NEVER nest an intervention dictionary inside its own parameters. Always separate fields with commas.
"""

STAGE_3_FINAL_REASONING_SYSTEM_PROMPT = """[STAGE 3: FINAL REASONING]
You are the **Autonomous LLM Planner (Cross-Domain Synthesizer)**.
Synthesize collected evidence into actionable municipal recommendations.

### CRITICAL THREE-TIER EVIDENCE DISTINCTION:
1. OBSERVED EFFECT:
   - An empirical metric change actually measured by Eclipse SUMO in a completed simulation run during this cycle.
   - Only tested interventions have observed effects.
2. EXPECTED / INTENDED MECHANISM:
   - A conceptual mechanism described by a candidate intervention (if explicitly supplied by the Traffic Agent), e.g. target diversion fraction or signal split change.
   - An intended mechanism is an unverified design hypothesis, NOT an observed outcome. The Planner must NEVER convert an intended mechanism into an observed result or predictive certainty.
3. UNTESTED CANDIDATES:
   - Candidate interventions identified from specialist intelligence that have NOT been executed in SUMO during this cycle.
   - No empirical effect is available yet.

### RULES FOR UNTESTED CANDIDATES:
- ALLOWED:
  * State that the candidate exists.
  * State its configured parameters.
  * State its intended mechanism IF that mechanism is explicitly supplied by the Traffic Agent.
  * State that it requires simulation and that its operational effectiveness has not yet been established.
  * State that it can be evaluated in a subsequent simulation run.
- STRICTLY FORBIDDEN:
  * NEVER state or imply that an untested candidate "will reduce traffic", "will reduce arrivals", "to reduce arrival rates", "will improve the bottleneck", "will reduce congestion", "will reduce delay", or "will improve network performance".
  * NEVER claim an untested candidate is "better", "more effective", "preferred", "optimal", "superior", or "should be deployed".
  * Only make causal or impact claims about an effect that has actually been observed in an actual simulation.

### RULES FOR BOTTLENECK RESOLUTION & TRADE-OFFS:
- Improvement in the target corridor alone does not establish that the bottleneck has been resolved. Report the measured corridor change and any observed trade-offs instead.
- Do NOT use "successfully addressed", "resolved", "fixed", "solved", or equivalent language merely because the target corridor speed increased.
- When the target corridor speed improves but another corridor becomes slower or network delay increases, report the empirical facts: the measured target corridor speed change alongside the observed opposing corridor and network delay trade-offs.

### RULES FOR FOLLOW-UP SIMULATION ANALYSIS & BOTTLENECK RESOLUTION:
1. DISTINGUISH HISTORICAL SIMULATIONS FROM CURRENT-TURN SIMULATIONS:
   - When historical simulation evidence exists, base reasoning strictly on that completed simulation history.
   - Note clearly whether a new simulation was run in the current turn (e.g., "No new simulation was executed in this conversational turn; evaluating completed empirical simulation results from previous cycle").
   - Evidence status remains simulation-backed (EVIDENCE: MULTI-SIMULATION EVALUATION or EVIDENCE: SINGLE SIMULATION RUN); do NOT demote it to OBSERVATIONAL simply because zero new simulations ran this turn.
2. BOTTLENECK RESOLUTION EVALUATION:
   - For "Did the optimization solve the bottleneck?", do NOT claim the bottleneck was solved merely because target corridor speed improved.
   - Systematically evaluate:
     * Target corridor: speed improvement %
     * Opposing / conflicting corridors: speed degradation %, queue/delay increases
     * Network: average speed delta, delay delta, waiting time, congestion index
   - If target corridor speed improves but opposing corridors degrade or network delay increases:
     State factually: "The target corridor improved by X%, but the simulation also showed Y degradation in [metric/corridor], so the evidence supports localized improvement rather than full bottleneck resolution."
3. NO HISTORY SCENARIO:
   - If the user asks which tested intervention performed better but NO simulation history exists:
     Do NOT invent results. Clearly state that no candidate interventions have been tested in simulation yet.

### RECOMMENDATION STRUCTURE FOR A SINGLE TESTED INTERVENTION:
When exactly one intervention was tested in simulation, produce concise evidence-grounded reasoning following this structure:
1. Identify the bottleneck corridor.
2. State what intervention was actually tested.
3. State the observed target-corridor effect (measured percentage change).
4. State important network and opposing-corridor trade-offs (e.g. network delay delta, opposing corridor speed delta).
5. State whether the tested intervention should be treated as a standalone solution based on the observed evidence.
6. If candidate alternatives exist, identify them as UNTESTED and state that they require simulation before their effectiveness can be assessed.

### RECOMMENDATION FOR MULTIPLE TESTED INTERVENTIONS:
- Compare ONLY the interventions that were actually simulated in SUMO using empirical metrics.
- At minimum compare: target corridor speed change, network average speed change, network delay, and corridor trade-offs.
- EMPIRICAL DOMINANCE RULE:
  * If one tested intervention achieves better performance across the key reported objective metrics (e.g. larger target-corridor speed gain, higher network speed gain, greater network delay reduction, greater waiting time reduction), you MUST select and prioritize that intervention for validation.
  * NEVER claim or recommend a lower-performing intervention as the "strongest" or "preferred" when another tested intervention outperforms it across the objective metrics, unless there is an explicit, evidence-based trade-off justification (e.g. catastrophic gridlock on a critical opposing artery that outweighs all other gains).
- TRADE-OFF AWARENESS & MONITORING:
  * Always report measured opposing corridor degradations (e.g. opposing phase speed drops) as operational monitoring requirements, not reasons to pick an inferior alternative.
- SUPPORT "NO CLEAR WINNER": Only if tested interventions have genuine conflicting trade-offs with no clear dominance (e.g. A improves target speed by +10% but worsens delay by +20%, while B improves delay by +15% but leaves target speed unchanged), state that neither clearly dominates and explain the operational trade-off.
- Untested candidates remain unsimulated and cannot be chosen over tested configurations.

### GENERAL USER-CENTRIC CONCISENESS & OPERATIONAL DESIGN:
Keep outputs clear, professional, readable, and easy to understand for municipal operators and everyday citizens:
1. Assessment Structure:
   - Provide a direct, plain-language assessment in 2 to 3 sentences maximum.
   - For Traffic: State whether conditions are Free Flow, Moderate, or Congested, along with current speed vs. free-flow baseline and observed delay.
   - For Weather: State the condition (e.g. Sunny, Rain), temperature, humidity, and immediate outlook in one clean sentence.
   - For Air Quality: State AQI score, health category, and primary pollutant driver clearly.
   - For Energy / Grid: State current substation load status (e.g. Normal, High), demand MW, and capacity headroom.
2. No Jargon & No Speculative Clutter:
   - Avoid long, repetitive technical essays that overwhelm the user.
   - Never speculate on secondary unverified causes (e.g. mechanical soil resuspension or industrial perimeter fires) unless specifically requested by an analytical query.
   - Do not quote internal engine mechanics or planning rules.
3. Actionable Recommendations:
   - Keep recommended operational actions concise and prioritized (top 2 to 3 items only).
   - Tell operators or citizens what immediate action is needed without duplicating the assessment text.

### HONEST EVIDENCE STATUS & PROVENANCE:
- For responses where simulations were actually executed:
  * If 2 or more simulations: `EVIDENCE: MULTI-SIMULATION EVALUATION`
  * If 1 simulation: `EVIDENCE: SINGLE SIMULATION RUN`
- For responses with ZERO simulations:
  * If primary evidence is from numerical air quality models (e.g. Open-Meteo): `EVIDENCE: MODELLED ESTIMATE`. (Do NOT mislabel numerical atmospheric models as physical ground sensor observations).
  * If primary evidence is from live API traffic telemetry (e.g. TomTom): `EVIDENCE: API-SOURCED TELEMETRY`.
  * If combining TomTom live traffic telemetry and Open-Meteo air quality model: `EVIDENCE: MULTI-SOURCE (API & MODELLED)`.
  * If providing municipal recommendations or domain advisories: `EVIDENCE: MUNICIPAL ADVISORY & RECOMMENDATION`.
  * NEVER assign a blanket 'EVIDENCE: OBSERVATIONAL' to modelled atmospheric estimates or simulation results.

### STRICT REAL-WORLD TRAFFIC EVIDENCE GROUNDING:
- Every real-world traffic metric MUST originate from the TomTom API response.
- If the traffic data source is TomTom (observed):
  * Only cite observed TomTom fields: `network_speed_kmh`, `free_flow_speed_kmh`, `congestion_index`, and `corridors` (speed, status).
  * Never invent or state metrics unsupported by TomTom, such as vehicle counts/volume, queue length, waiting time, or vehicle throughput.
  * If delay_sec is cited, cite it strictly as segment travel time delay compared to free flow (not average stopped delay per vehicle).
  * Distinguish direct API observations from inferences. If data is unavailable, omit it or state that it is not measured by the traffic API.

### PRACTICAL, ACTIONABLE MUNICIPAL RECOMMENDATIONS:
When users ask how to improve a situation (e.g. "How can we reduce pollution in Tarnaka even with heavy traffic?", "What measures can control road dust?", "Suggest ways to reduce vehicle emissions", "What can GHMC do?"):
1. Focus on practical, actionable municipal measures structured by horizon:
   - Immediate measures: Mechanized road sweeping, water-mist dust suppression, clearing roadside dust/silt, controlling open waste burning, covering construction material trucks with tarpaulins, reducing unnecessary vehicle idling at intersections.
   - Medium-term measures: Construction-site dust-control enforcement (windbreak sheets, water cannons), improved municipal waste collection, public transit augmentation (feeder buses), cleaner commercial vehicle fleets.
   - Long-term measures: Sustainable urban transport planning, green buffer strips with broad-leaved vegetation along corridors, road paving, non-motorized transport infrastructure.
2. Ground recommendations in the specific observed evidence:
   - Elevated PM10 justifies prioritizing road dust and construction dust controls.
   - Elevated PM2.5 and NO2 justifies transport, idling reduction, and fleet emission controls.
   - Open burning or localized peaks justify waste-management enforcement.
   - Do not automatically assume traffic is the cause of every pollution problem. Distinguish confirmed sources from possible contributing factors.
3. Relevant Stakeholders:
   - Identify relevant implementation bodies such as GHMC (sanitation, town planning), Hyderabad Traffic Police, TSPCB, and Transport Department.
4. User-Centric Conciseness:
   - Keep the Assessment brief, direct, and conversational (2-3 concise sentences maximum).
   - Answer directly: State the current AQI, health category (e.g., Moderate / Unhealthy for Sensitive Groups), and the primary pollutant.
   - Avoid overwhelming simple users with exhaustive paragraphs about mechanical resuspension or speculative causality unless explicitly asked.
5. Integrity:
   - Do NOT invent percentage improvements or guaranteed outcomes.
   - Do NOT run SUMO simulations for pollution reduction queries.
   - Explain what action is proposed, why it is relevant, how it helps, and the implementation horizon.

### RECOMMENDATION FOR ZERO SIMULATIONS:
- For traffic optimization or intervention requests where zero simulations were run:
  * State that candidate interventions remain untested in simulation and require empirical verification.
- For non-traffic requests (weather-only, pollution-only, energy-only, or environmental recommendations):
  * Provide only relevant evidence, domain analysis, and legitimate domain advisories.
  * Do NOT include traffic optimization, corridor baseline, or SUMO simulation disclaimers.
- For multi-agent requests:
  * Mention simulation limitations ONLY if simulation is relevant to the request or was explicitly requested.
- Set synthetic_data_note to null unless SUMO simulation evidence was actually evaluated.

### DELTA SIGN CONVENTION:
All delta fields follow signed raw-change semantics:
- speed_change_pct: POSITIVE = speed improved (higher speed = better)
- delay_change_pct: NEGATIVE = delay improved (lower delay = better); POSITIVE = delay worsened
- waiting_time_change_pct: NEGATIVE = waiting improved; POSITIVE = waiting worsened
- congestion_change_pct: NEGATIVE = congestion improved; POSITIVE = congestion worsened
- throughput_change: POSITIVE = more arrivals = improved

When reporting metric changes, always state the direction correctly:
  delay_change_pct = -23.69% → "delay improved by 23.69%"
  delay_change_pct = +4.80%  → "delay worsened by 4.80%"
  congestion_change_pct = -24.56% → "congestion improved by 24.56%"

### STRUCTURED RESPONSE SCOPE:
Determine the user's requested response scope and return it in `response_scope`:
- `fields`: A list of the specific fields or topics explicitly requested by the user.
  Examples:
  * "What is the bottleneck corridor?" → fields: ["bottleneck_corridor"], detail_level: "minimal"
  * "What is the average speed?" → fields: ["average_speed"], detail_level: "minimal"
  * "Give me the bottleneck corridor and average speed." → fields: ["bottleneck_corridor", "average_speed"], detail_level: "minimal"
  * "Why is Narayanguda congested?" → fields: ["causes"], detail_level: "minimal"
  * "What is the PM2.5 level in Narayanguda?" → fields: ["pm25"], detail_level: "minimal"
  * "What is the air quality index?" → fields: ["city_avg_aqi"], detail_level: "minimal"
  * "Analyze traffic congestion in Narayanguda." → fields: ["congestion", "relevant_metrics", "causes", "recommendations"], detail_level: "analysis"
  * "Analyze air pollution in Hyderabad." → fields: ["pollution", "aqi", "pm25", "pm10", "suggested_interventions"], detail_level: "analysis"
  * "How can we reduce congestion?" → fields: ["recommendations"], detail_level: "summary"
  * "Simulate the best intervention." → fields: ["simulation"], detail_level: "analysis"
- `detail_level`: "minimal" | "summary" | "analysis" | "full"

### RESPONSE RENDERING RULES BASED ON RESPONSE SCOPE:
- When `detail_level` is "minimal":
  * Answer the question directly using ONLY the information needed to satisfy the requested `fields`.
  * Do NOT automatically include unrequested metrics (average speed, congestion percentage, waiting time, throughput, vehicle counts, causes, recommendations, interventions, or simulation results) unless explicitly asked in `fields`.
  * Set `recommendation` to "" (empty string) unless recommendations or interventions were explicitly requested in `fields`.
- When `detail_level` is "analysis" or "summary" (or "recommendations" in `fields`):
  * Provide the requested broader synthesis and municipal recommendations.

### USER-FACING RESPONSE CONCISENESS & CLEANLINESS:
- For simple diagnostic queries, return the requested answer and relevant evidence directly.
- NEVER include internal Planner reasoning, rule explanations, or rule citations in user-facing fields (`summary`, `recommendation`).
- Do NOT include meta-explanations such as:
  * "The objective is a purely diagnostic query..."
  * "According to Rule [X]..."
  * "The evidence is sufficient to answer..."
  * Explanations about why simulations were not launched or not run (e.g. "No simulations were launched because...", "Simulations were not run because this is a diagnostic query").
- Keep internal decision-making inside the Planner. Preserve relevant metrics, source information, limitations, and actual simulation results when applicable.

### OUTPUT JSON SCHEMA:
Return ONLY valid JSON:
{
  "response_scope": {
    "fields": ["..."],
    "detail_level": "minimal" | "summary" | "analysis" | "full"
  },
  "summary": "...",
  "evidence_used": ["..."],
  "cross_domain_relationships": "...",
  "causation_likelihood": "STRONG" | "PLAUSIBLE" | "UNLIKELY" | "INDEPENDENT",
  "simulation_findings": "...",
  "synthetic_data_note": "SUMO simulation metrics represent simulated/synthetic evidence under a defined traffic-demand scenario, distinct from live physical road sensors.",
  "uncertainty_and_limitations": "...",
  "recommendation": "...",
  "evidence_status": "EVIDENCE: OBSERVATIONAL" | "EVIDENCE: SINGLE SIMULATION RUN" | "EVIDENCE: MULTI-SIMULATION EVALUATION",
  "recommendation_basis": "...",
  "next_action": "operational_implementation"
}
"""


# ---------------------------------------------------------------------------
# Specialist Evidence Compaction Helpers (Saves 80%+ Input Tokens)
# ---------------------------------------------------------------------------

def _compact_traffic_evidence(trf: Dict[str, Any]) -> Dict[str, Any]:
    """Extract strictly essential traffic telemetry for LLM reasoning."""
    if not isinstance(trf, dict):
        return trf

    is_observed = (trf.get("source_type") or (trf.get("source") or {}).get("type")) == "observed" or (trf.get("source_provider") or (trf.get("source") or {}).get("provider")) == "tomtom"

    metrics = trf.get("metrics") or {}
    compact: Dict[str, Any] = {
        "location": trf.get("location"),
        "source_provider": trf.get("source_provider") or (trf.get("source") or {}).get("provider") or "tomtom",
        "source_type": trf.get("source_type") or (trf.get("source") or {}).get("type") or "observed",
        "data_source": trf.get("data_source") or "tomtom_traffic_api",
        "network_speed_kmh": metrics.get("average_speed_kmh") if metrics.get("average_speed_kmh") is not None else trf.get("average_speed_kmh"),
        "free_flow_speed_kmh": trf.get("free_flow_speed_kmh"),
        "congestion_index": metrics.get("congestion_index") if metrics.get("congestion_index") is not None else trf.get("congestion_index"),
        "waiting_time_sec": None if is_observed else (metrics.get("average_waiting_time_sec") if metrics.get("average_waiting_time_sec") is not None else trf.get("average_waiting_time_sec")),
        "delay_sec": metrics.get("average_delay_sec") if metrics.get("average_delay_sec") is not None else trf.get("average_delay_sec"),
        "active_vehicles": None if is_observed else (metrics.get("active_vehicles") or trf.get("active_vehicles")),
        "total_vehicles": None if is_observed else (metrics.get("total_vehicles") or trf.get("total_vehicles")),
        "throughput": None if is_observed else (metrics.get("throughput") if metrics.get("throughput") is not None else trf.get("throughput")),
    }

    # Corridors
    corridors = trf.get("corridors") or []
    if corridors:
        compact["corridors"] = [
            {
                "name": c.get("name"),
                "avg_speed_kmh": c.get("avg_speed"),
                "status": c.get("status"),
            }
            for c in corridors
            if isinstance(c, dict)
        ]

    # Bottlenecks
    bottlenecks = trf.get("bottlenecks") or []
    if bottlenecks:
        compact["bottlenecks"] = [
            {
                "corridor": b.get("corridor"),
                "severity": b.get("severity"),
                "reason": b.get("reason"),
                "speed_kmh": (b.get("evidence") or {}).get("speed_kmh") if isinstance(b.get("evidence"), dict) else None,
                "speed_deficit_pct": (b.get("evidence") or {}).get("speed_deficit_pct") if isinstance(b.get("evidence"), dict) else None,
            }
            for b in bottlenecks
            if isinstance(b, dict)
        ]

    # Candidate interventions: keep executable candidates and essential impact fields
    candidates = trf.get("candidate_interventions") or []
    if candidates:
        executable_candidates = [c for c in candidates if isinstance(c, dict) and c.get("executable")]
        pool = executable_candidates[:3] if executable_candidates else candidates[:3]
        compact["candidate_interventions"] = [
            {
                "type": c.get("type"),
                "target": c.get("target"),
                "parameters": c.get("parameters"),
                "executable": c.get("executable"),
                "potential_benefit": c.get("potential_benefit"),
                "potential_tradeoff": c.get("potential_tradeoff"),
            }
            for c in pool
            if isinstance(c, dict)
        ]

    # Trade-offs: keep compact affected corridors and trade-off summaries
    trade_offs = trf.get("trade_offs") or []
    if trade_offs:
        compact["trade_offs"] = [
            {
                "target": t.get("target"),
                "affected_corridors": t.get("affected_corridors"),
                "potential_tradeoff": t.get("potential_tradeoff"),
            }
            for t in trade_offs[:3]
            if isinstance(t, dict)
        ]

    # Preserve dynamic baseline metadata from actual evidence (NO hardcoded environment-specific values)
    meta = trf.get("metadata") if isinstance(trf.get("metadata"), dict) else {}
    actual_seed = trf.get("seed") if trf.get("seed") is not None else meta.get("random_seed")
    actual_dur = trf.get("duration_seconds") if trf.get("duration_seconds") is not None else meta.get("duration_seconds")
    actual_scen = trf.get("scenario") or trf.get("scenario_name") or meta.get("demand_profile")
    actual_loc = trf.get("location")

    if actual_seed is not None:
        compact["seed"] = actual_seed
    if actual_dur is not None:
        compact["duration_seconds"] = actual_dur
    if actual_scen:
        compact["scenario"] = actual_scen
    if actual_loc:
        compact["location"] = actual_loc

    return compact


def _compact_simulation_evidence(sim: Any) -> Any:
    """Extract strictly essential simulation outcome and comparison telemetry while preserving full horizon metadata."""
    if isinstance(sim, list):
        return [_compact_simulation_evidence(s) for s in sim]
    if not isinstance(sim, dict):
        return sim

    comp = sim.get("comparison") or {}
    base_sum = comp.get("baseline_summary") or {}
    int_sum = comp.get("intervention_summary") or (sim.get("metrics") or {})
    int_applied = sim.get("intervention_applied") or sim.get("intervention") or {}
    meta = sim.get("metadata") if isinstance(sim.get("metadata"), dict) else {}

    scenario = sim.get("scenario") or comp.get("intervention_scenario") or comp.get("baseline_scenario") or meta.get("demand_profile")
    duration = sim.get("duration_seconds") or sim.get("duration") or comp.get("intervention_duration_seconds") or comp.get("baseline_duration_seconds") or meta.get("duration_seconds")
    seed = sim.get("seed") or comp.get("intervention_seed") or comp.get("baseline_seed") or meta.get("random_seed")
    network = sim.get("network_name") or comp.get("intervention_network") or comp.get("baseline_network") or meta.get("network_name") or "narayanguda_network.net.xml"
    evidence_status = sim.get("evidence_status") or comp.get("evidence_status") or ("EVIDENCE: MULTI-SIMULATION EVALUATION" if comp else "EVIDENCE: OBSERVATIONAL")

    return {
        "scenario_id": sim.get("scenario_id"),
        "scenario": scenario,
        "duration_seconds": duration,
        "seed": seed,
        "network": network,
        "evidence_status": evidence_status,
        "status": sim.get("status"),
        "intervention": {
            "type": int_applied.get("type"),
            "target": int_applied.get("target"),
            "parameters": int_applied.get("parameters"),
        },
        "baseline": {
            "scenario": comp.get("baseline_scenario") or scenario,
            "duration_seconds": comp.get("baseline_duration_seconds") or duration,
            "seed": comp.get("baseline_seed") or seed,
            "network": comp.get("baseline_network") or network,
            "speed_kmh": base_sum.get("average_speed_kmh"),
            "delay_sec": base_sum.get("average_delay_sec"),
            "waiting_sec": base_sum.get("average_waiting_time_sec"),
            "congestion_index": base_sum.get("congestion_index"),
            "throughput": base_sum.get("throughput"),
        },
        "intervention_metrics": {
            "scenario": comp.get("intervention_scenario") or scenario,
            "duration_seconds": comp.get("intervention_duration_seconds") or duration,
            "seed": comp.get("intervention_seed") or seed,
            "network": comp.get("intervention_network") or network,
            "speed_kmh": int_sum.get("average_speed_kmh"),
            "delay_sec": int_sum.get("average_delay_sec"),
            "waiting_sec": int_sum.get("average_waiting_time_sec"),
            "congestion_index": int_sum.get("congestion_index"),
            "throughput": int_sum.get("throughput"),
        },
        "deltas": {
            # NEW signed fields (use these for all reasoning):
            # speed_change_pct: positive = improved
            # delay_change_pct, waiting_time_change_pct, congestion_change_pct: negative = improved
            # throughput_change: positive = improved
            "speed_change_pct": comp.get("speed_change_pct"),
            "delay_change_pct": comp.get("delay_change_pct"),
            "waiting_time_change_pct": comp.get("waiting_time_change_pct"),
            "congestion_change_pct": comp.get("congestion_change_pct"),
            "throughput_change": comp.get("throughput_change"),
            "target_corridor_speed_change_pct": comp.get("target_corridor_speed_change_pct"),
        },
        "corridor_comparisons": comp.get("corridor_comparisons", []),
        "corridor_trade_offs": sim.get("corridor_trade_offs") or comp.get("corridor_trade_offs") or [],
        "trade_off_summary": sim.get("trade_off_summary") or comp.get("trade_off_summary"),
        "fair_comparison": comp.get("fair_comparison", False if comp.get("status") == "baseline_missing" else True),
        "comparison_status": comp.get("status", "SUCCESS"),
    }


def _compact_weather_evidence(wtr: Any) -> Any:
    """Extract strictly essential weather telemetry for token-bounded LLM reasoning."""
    if not isinstance(wtr, dict):
        return wtr

    forecast_summary = []
    for day in (wtr.get("forecast_7d") or [])[:3]:
        if isinstance(day, dict):
            forecast_summary.append({
                "day": day.get("day"),
                "high": day.get("high"),
                "low": day.get("low"),
                "condition": day.get("condition"),
                "rain": day.get("rain"),
            })

    return {
        "city": wtr.get("city") or wtr.get("location"),
        "temperature_c": wtr.get("temperature_c"),
        "feels_like_c": wtr.get("feels_like_c"),
        "condition": wtr.get("condition"),
        "humidity_pct": wtr.get("humidity_pct"),
        "wind_speed_kmh": wtr.get("wind_speed_kmh"),
        "wind_direction": wtr.get("wind_direction"),
        "precipitation_mm": wtr.get("precipitation_mm"),
        "pressure_hpa": wtr.get("pressure_hpa"),
        "uv_index": wtr.get("uv_index"),
        "visibility_km": wtr.get("visibility_km"),
        "provider": wtr.get("provider") or wtr.get("source"),
        "timestamp": wtr.get("timestamp"),
        "forecast_summary": forecast_summary,
    }


def _compact_pollution_evidence(pol: Any) -> Any:
    """Extract concise, essential air quality telemetry for clean municipal reasoning."""
    if not isinstance(pol, dict):
        return pol

    # Keep only the top 2-3 immediate actionable interventions to avoid drowning the LLM in boilerplates
    suggested = pol.get("suggested_interventions") or []
    compact_interventions = []
    if isinstance(suggested, list):
        for inv in suggested[:3]:
            if isinstance(inv, dict):
                compact_interventions.append({
                    "action_type": inv.get("action_type"),
                    "horizon": inv.get("horizon"),
                    "description": inv.get("description"),
                })
            else:
                compact_interventions.append(str(inv))

    return {
        "location": pol.get("location"),
        "city_avg_aqi": pol.get("city_avg_aqi") if "city_avg_aqi" in pol else pol.get("aqi"),
        "category": pol.get("category"),
        "primary_pollutant": pol.get("primary_pollutant"),
        "pm25": pol.get("pm25"),
        "pm10": pol.get("pm10"),
        "pollutants": pol.get("pollutants"),
        "suggested_interventions": compact_interventions,
        "data_source": pol.get("data_source"),
    }


def _compact_generic_evidence(data: Any) -> Any:
    """Strip massive arrays like station lists or hourly data from generic telemetry."""
    if isinstance(data, dict):
        exclude = {
            "stations", "substations", "forecast_7d", "hourly_temp", "hourly_data",
            "weekly_precipitation", "metadata", "source", "correlations", "provenance_summary"
        }
        return {k: _compact_generic_evidence(v) for k, v in data.items() if k not in exclude}
    elif isinstance(data, list):
        return [_compact_generic_evidence(v) for v in data]
    return data


def compact_specialist_results(results: Dict[str, Any]) -> Dict[str, Any]:
    """Compacts specialist telemetry payloads for token-bounded LLM reasoning."""
    if not isinstance(results, dict):
        return results

    compacted: Dict[str, Any] = {}
    for agent_cap, val in results.items():
        if agent_cap == "traffic":
            compacted["traffic"] = _compact_traffic_evidence(val)
        elif agent_cap == "weather":
            compacted["weather"] = _compact_weather_evidence(val)
        elif agent_cap == "pollution":
            compacted["pollution"] = _compact_pollution_evidence(val)
        elif agent_cap in ("simulation", "simulations"):
            if "simulation" not in compacted:
                compacted["simulation"] = _compact_simulation_evidence(val)
        else:
            compacted[agent_cap] = _compact_generic_evidence(val)
    return compacted


# ---------------------------------------------------------------------------
# Prompt Formatters
# ---------------------------------------------------------------------------

def build_planner_prompt(user_query: str) -> str:
    """Format legacy planner query."""
    return f"""User Query: \"\"\"{user_query}\"\"\"
Analyze according to system instructions, determine relevance, select required agents, and return structured JSON."""


def build_evaluation_prompt(
    objective: str,
    plan: List[str],
    collected_results: Dict[str, Any],
    failures: Dict[str, Any],
) -> str:
    """Format legacy evaluation prompt with compacted telemetry."""
    compact_results = compact_specialist_results(collected_results or {})
    return f"""Planning Objective: \"{objective}\"
Plan: {json.dumps(plan, separators=(',', ':'))}
Evidence: {json.dumps(compact_results, separators=(',', ':'), default=str)}
Failures: {json.dumps(failures or {}, separators=(',', ':'))}
Decide next_action and return structured JSON."""


def build_stage_1_prompt(
    objective: str,
    location: Optional[str] = None,
    constraints: Optional[List[Any]] = None,
    simulation_history: Optional[List[Dict[str, Any]]] = None,
    existing_results: Optional[Dict[str, Any]] = None,
) -> str:
    """Build prompt for initial planning and agent selection."""
    sim_count = len(simulation_history or [])
    sim_hint = f"\nCompleted Simulation History: {sim_count} simulation runs available in session." if sim_count > 0 else ""
    return f"""Objective: \"\"\"{objective}\"\"\"
Location: {location or 'Not specified'}
Constraints: {json.dumps(constraints or [], separators=(',', ':'), default=str)}{sim_hint}
Determine relevance, select agents, and generate contract-compliant requests. next_action must ALWAYS be a non-null string ("collect_evidence", "run_simulation", or "finalize")."""


def build_stage_2_prompt(
    objective: str,
    cycle_num: int = 1,
    history: Optional[List[Dict[str, Any]]] = None,
    collected_results: Optional[Dict[str, Any]] = None,
    failures: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> str:
    """Build prompt for multi-cycle evaluation and simulation determination."""
    compact_results = compact_specialist_results(collected_results or {})
    compact_hist = []
    if history:
        for h in history[-2:]:  # Keep only last 2 cycle records
            compact_hist.append({
                "cycle": h.get("cycle"),
                "decision": h.get("decision"),
                "next_action": h.get("next_action"),
            })

    return f"""Objective: \"{objective}\"
Cycle: {cycle_num}
History: {json.dumps(compact_hist, separators=(',', ':'), default=str)}
Evidence: {json.dumps(compact_results, separators=(',', ':'), default=str)}
Failures: {json.dumps(failures or {}, separators=(',', ':'))}
Evaluate evidence against objective and decide next_action."""


def build_stage_3_prompt(
    objective: str,
    location: Optional[str] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    collected_results: Optional[Dict[str, Any]] = None,
    simulation_results: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> str:
    """Build prompt for final cross-domain reasoning and municipal recommendations."""
    compact_results = compact_specialist_results(collected_results or {})

    # Derive tested vs untested interventions
    sim_raw = simulation_results or (collected_results.get("simulations") if collected_results else None) or (collected_results.get("simulation") if collected_results else None)
    sim_list = sim_raw if isinstance(sim_raw, list) else ([sim_raw] if isinstance(sim_raw, dict) else [])

    tested_interventions: List[Dict[str, Any]] = kwargs.get("tested_interventions")
    if tested_interventions is None:
        tested_interventions = []
        for s in sim_list:
            if isinstance(s, dict):
                int_info = s.get("intervention_applied") or s.get("intervention") or {}
                comp = s.get("comparison") or {}
                tested_interventions.append({
                    "scenario_id": s.get("scenario_id"),
                    "scenario": s.get("scenario") or comp.get("intervention_scenario") or comp.get("baseline_scenario"),
                    "duration_seconds": s.get("duration_seconds") or comp.get("intervention_duration_seconds") or comp.get("baseline_duration_seconds"),
                    "seed": s.get("seed") or comp.get("intervention_seed") or comp.get("baseline_seed"),
                    "type": int_info.get("type"),
                    "target": int_info.get("target"),
                    "parameters": int_info.get("parameters"),
                    "status": "SIMULATED",
                    "target_corridor_speed_change_pct": comp.get("target_corridor_speed_change_pct"),
                    # NEW signed change fields (negative = improved for delay/waiting/congestion):
                    "network_speed_change_pct": comp.get("speed_change_pct"),
                    "network_delay_change_pct": comp.get("delay_change_pct"),
                    "network_waiting_change_pct": comp.get("waiting_time_change_pct"),
                    "network_congestion_change_pct": comp.get("congestion_change_pct"),
                    "corridor_trade_offs": comp.get("corridor_trade_offs") or s.get("corridor_trade_offs") or [],
                })

    from backend.agents.planner_agent.scope import (
        classify_response_scope,
        request_involves_traffic_optimization_or_simulation,
    )
    involves_traffic_opt_or_sim = request_involves_traffic_optimization_or_simulation(
        objective=objective,
        collected_results=collected_results,
        tested_interventions=tested_interventions,
    )

    untested_candidates: List[Dict[str, Any]] = kwargs.get("untested_candidates")
    if untested_candidates is None:
        untested_candidates = []
        if involves_traffic_opt_or_sim:
            trf = collected_results.get("traffic") if isinstance(collected_results, dict) else {}
            all_cands = trf.get("candidate_interventions", []) if isinstance(trf, dict) else []
            for c in all_cands:
                if not isinstance(c, dict):
                    continue
                c_type = str(c.get("type") or c.get("intervention_type") or "").strip().lower()
                c_target = str(c.get("target") or "").strip().lower()
                is_tested = any(
                    str(t.get("type") or "").strip().lower() == c_type
                    and (not c_target or not t.get("target") or c_target in str(t.get("target")).strip().lower() or str(t.get("target")).strip().lower() in c_target)
                    for t in tested_interventions
                )
                if not is_tested:
                    untested_entry: Dict[str, Any] = {
                        "type": c.get("type"),
                        "target": c.get("target"),
                        "parameters": c.get("parameters"),
                        "status": "UNTESTED_IN_THIS_CYCLE",
                    }
                    intended_mech = c.get("potential_benefit") or c.get("intended_mechanism")
                    if intended_mech:
                        untested_entry["intended_mechanism"] = str(intended_mech)
                    untested_candidates.append(untested_entry)
            untested_candidates = untested_candidates[:5]

    # If simulation is already inside compact_results, do not duplicate it
    compact_sim = None
    if simulation_results and "simulation" not in compact_results:
        compact_sim = _compact_simulation_evidence(simulation_results)

    prompt_parts = [
        f"Objective: \"{objective}\"",
        f"Location: {location or 'Not specified'}",
        f"Evidence: {json.dumps(compact_results, separators=(',', ':'), default=str)}",
    ]
    if compact_sim:
        prompt_parts.append(f"Simulation: {json.dumps(compact_sim, separators=(',', ':'), default=str)}")

    if tested_interventions:
        prompt_parts.append(f"Tested Interventions (Simulated via SUMO with empirical results): {json.dumps(tested_interventions, separators=(',', ':'), default=str)}")
    if untested_candidates:
        prompt_parts.append(
            f"Untested Candidates (Candidate-only, NOT simulated in this cycle - NO empirical effect available; "
            f"intended mechanism is an unverified design hypothesis requiring simulation; "
            f"MUST NOT claim causal effects such as 'will reduce' or 'to reduce arrivals'): "
            f"{json.dumps(untested_candidates, separators=(',', ':'), default=str)}"
        )

    scopes = classify_response_scope(objective)
    prompt_parts.append(f"Target Output Scope: {json.dumps(scopes)}. If the scope is narrow (e.g. bottleneck_corridor, average_speed), answer ONLY what was asked directly and concisely without unrequested metrics or recommendations.")
    if involves_traffic_opt_or_sim:
        prompt_parts.append("Synthesize final reasoning, cite specific metrics, explain trade-offs, strictly distinguish tested from untested interventions, and recommend municipal action.")
    else:
        prompt_parts.append("Synthesize final reasoning strictly for the requested domain(s). Focus only on relevant evidence and analysis. Do NOT include traffic optimization or SUMO simulation disclaimers.")
    return "\n".join(prompt_parts)
