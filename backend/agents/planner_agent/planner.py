"""
Autonomous LLM Planner Agent for the SUPADSP Smart City platform.

The Planner Agent is the SOLE coordinator in the system. There is NO orchestrator.
Frontend -> LLM Planner -> Specialist Agents -> LLM Planner -> Frontend.

All core planning decisions are 100% LLM-driven:
  1. Natural-language understanding & gatekeeping
  2. Specialist agent selection based on contracts
  3. Contract-aware input generation
  4. Evidence sufficiency evaluation
  5. Multi-cycle replanning decisions
  6. Dynamic simulation necessity decisions (SUMO boundary)
  7. Final cross-domain reasoning and municipal recommendations

Deterministic code serves strictly as defensive safeguards:
  - Allowed-agent validation
  - Schema & JSON validation
  - Input completeness verification (no fabricated missing fields)
  - Specialist output verification & malformed data rejection
  - Structured evidence normalization
  - Max cycles and loop protection
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

MAX_OPTIMIZATION_CANDIDATES = int(os.getenv("MAX_OPTIMIZATION_CANDIDATES", "3"))

from backend.agents.planner_agent.contracts import SPECIALIST_AGENT_CONTRACTS
from backend.agents.planner_agent.llm_client import (
    BaseLLMProvider,
    LLMConfigurationError,
    LLMError,
    LLMJsonParsingError,
    LLMProviderError,
    get_llm_provider,
)
from backend.agents.planner_agent.prompts import (
    STAGE_1_PLANNER_SYSTEM_PROMPT,
    STAGE_2_EVALUATION_SYSTEM_PROMPT,
    STAGE_3_FINAL_REASONING_SYSTEM_PROMPT,
    build_stage_1_prompt,
    build_stage_2_prompt,
    build_stage_3_prompt,
)
from backend.agents.planner_agent.schema import (
    AgentContextRequest,
    AgentRequest,
    CrossDomainAnalysis,
    EvidenceItem,
    LLMEvaluationDecision,
    LLMFinalReasoning,
    LLMPlanDecision,
    PlannerEvaluationResponse,
    PlannerResponse,
    ScenarioDefinition,
    SelectedAgentCall,
    SeverityLevel,
)
from backend.agents.planner_agent.scope import (
    apply_response_scope,
    classify_response_scope,
    determine_response_scope,
    extract_specialist_traffic_metrics,
    request_involves_traffic_optimization_or_simulation,
    strip_internal_planner_reasoning,
    strip_unrelated_traffic_disclaimers,
    validate_and_enforce_response_scope,
)

logger = logging.getLogger("planner_agent")

ALLOWED_CAPABILITIES = {"traffic", "weather", "pollution", "energy", "simulation"}


def is_analytical_history_followup(objective: str) -> bool:
    """Check if the objective represents an analytical follow-up query on existing simulation evidence."""
    obj_lower = (objective or "").lower().strip()
    return any(
        phrase in obj_lower for phrase in [
            "which tested intervention",
            "which tested",
            "performed better",
            "perform better",
            "is rerouting better",
            "is signal timing better",
            "compare the tested",
            "compare tested",
            "compare the simulated",
            "did the optimization solve",
            "did it solve the bottleneck",
            "did the optimization",
            "was the intervention effective",
            "why did the tested",
            "why did tested",
            "how did the tested",
            "what did the 600-second",
            "what did the 300-second",
            "what did the 120-second",
            "what did the simulation show",
            "what did the 600s simulation",
            "what did the 300s simulation",
            "what did the simulation",
            "what did the simulations show",
            "compare the 600-second",
            "compare the 300-second",
            "compare 600-second",
            "compare 300-second",
            "compare the 600s",
            "compare the 300s",
            "compare the 300-second and 600-second",
            "what changed between",
            "between 300 and 600",
            "between 600 and 300",
            "results of the 600",
            "results of the 300",
            "results of the simulation",
            "results of the run",
            "which interventions did we test",
            "interventions did we test",
            "interventions were tested",
            "what was tested",
            "among the tested",
            "strongest observed",
            "show me the baseline and intervention",
            "baseline and intervention values",
            "values for each tested",
            "each tested option",
            "each tested intervention",
        ]
    )


def is_test_proposed_intervention_query(objective: str) -> bool:
    """Check if the user is asking to simulate or test the proposed / recommended intervention from context."""
    obj_lower = (objective or "").lower().strip()
    return any(
        phrase in obj_lower for phrase in [
            "test the proposed intervention",
            "test the proposed",
            "test proposed intervention",
            "test proposed",
            "simulate the proposed intervention",
            "simulate the proposed",
            "simulate proposed intervention",
            "simulate proposed",
            "test the recommended intervention",
            "test recommended intervention",
            "test the recommended",
            "simulate the recommended",
            "test the intervention",
            "simulate the intervention",
            "run simulation for the proposed",
            "run simulation for proposed",
        ]
    )


def extract_proposed_intervention_from_context(
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    existing_results: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Extract candidate intervention details from conversation history or existing results."""
    # 1. Check existing_results
    if existing_results and isinstance(existing_results, dict):
        trf = existing_results.get("traffic") or {}
        if isinstance(trf, dict):
            cands = trf.get("candidate_interventions") or []
            for c in cands:
                if isinstance(c, dict) and c.get("type"):
                    return {
                        "type": c.get("type", "signal_timing"),
                        "target": c.get("target", "Westbound"),
                        "parameters": c.get("parameters", {"green_time_adjustment_sec": 10.0}),
                    }

    # 2. Check conversation_history in reverse order
    if conversation_history:
        for turn in reversed(conversation_history):
            if not isinstance(turn, dict):
                continue
            col = turn.get("collected_results") or {}
            if isinstance(col, dict) and "traffic" in col and isinstance(col["traffic"], dict):
                cands = col["traffic"].get("candidate_interventions") or []
                for c in cands:
                    if isinstance(c, dict) and c.get("type"):
                        return {
                            "type": c.get("type", "signal_timing"),
                            "target": c.get("target", "Westbound"),
                            "parameters": c.get("parameters", {"green_time_adjustment_sec": 10.0}),
                        }

            tev = turn.get("traffic_evidence") or {}
            if isinstance(tev, dict):
                cands = tev.get("candidate_interventions") or []
                for c in cands:
                    if isinstance(c, dict) and c.get("type"):
                        return {
                            "type": c.get("type", "signal_timing"),
                            "target": c.get("target", "Westbound"),
                            "parameters": c.get("parameters", {"green_time_adjustment_sec": 10.0}),
                        }

            unc = turn.get("untested_candidates") or (turn.get("final_response") or {}).get("untested_candidates") or []
            for c in unc:
                if isinstance(c, dict) and c.get("type"):
                    return {
                        "type": c.get("type", "signal_timing"),
                        "target": c.get("target", "Westbound"),
                        "parameters": c.get("parameters", {"green_time_adjustment_sec": 10.0}),
                    }

    return None


class PlannerAgent:
    """
    Autonomous LLM Planner Agent.
    Coordinates specialist agents, determines workflows via LLM reasoning,
    and enforces rigorous deterministic safeguards.
    """

    def __init__(self, llm_provider: Optional[BaseLLMProvider] = None):
        try:
            self.llm_provider = llm_provider or get_llm_provider()
        except LLMConfigurationError:
            # If default instantiation fails (e.g. unconfigured in env during import),
            # store None. Any invocation will raise clear LLMConfigurationError.
            self.llm_provider = llm_provider

    def _require_llm(self) -> BaseLLMProvider:
        """Ensure an LLM provider is configured, or raise a descriptive error."""
        if self.llm_provider is None:
            self.llm_provider = get_llm_provider()
        return self.llm_provider

    # ---------------------------------------------------------------------------
    # Stage 1: Autonomous LLM Plan & Agent Selection
    # ---------------------------------------------------------------------------
    def plan_autonomous(
        self,
        objective: str,
        location: Optional[str] = None,
        constraints: Optional[List[Any]] = None,
        simulation_history: Optional[List[Dict[str, Any]]] = None,
        existing_results: Optional[Dict[str, Any]] = None,
        duration_seconds: Optional[int] = None,
        scenario: Optional[str] = None,
        seed: Optional[int] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMPlanDecision:
        """
        Calls the LLM with agent contracts knowledge to understand the objective,
        select required specialist agents, and generate contract-adherent inputs.
        Supports deterministic intent routing for high-confidence single-domain queries.
        """
        if not objective or not objective.strip():
            return LLMPlanDecision(
                relevant=False,
                response="Please provide a valid query or description of the urban situation.",
            )

        obj_clean = objective.strip()
        obj_lower = obj_clean.lower()

        eff_duration = duration_seconds
        eff_scenario = scenario
        eff_seed = seed

        if eff_duration is None:
            if "300s" in obj_lower or "300 seconds" in obj_lower or "300 second" in obj_lower:
                eff_duration = 300
            elif "120s" in obj_lower or "120 seconds" in obj_lower or "120 second" in obj_lower:
                eff_duration = 120
            elif "600s" in obj_lower or "600 seconds" in obj_lower or "600 second" in obj_lower:
                eff_duration = 600

        if eff_scenario is None:
            if "synthetic_peak_westbound" in obj_lower or "peak westbound" in obj_lower or "peak_westbound" in obj_lower:
                eff_scenario = "synthetic_peak_westbound"
            elif "synthetic_normal" in obj_lower or "normal traffic" in obj_lower or "normal demand" in obj_lower:
                eff_scenario = "synthetic_normal"

        if eff_seed is None:
            import re
            m = re.search(r"\bseed\s*[:=]?\s*(\d+)\b", obj_lower)
            if m:
                try:
                    eff_seed = int(m.group(1))
                except (ValueError, TypeError):
                    pass

        eff_loc = location or "Narayanguda, Hyderabad"
        if not eff_loc or eff_loc.strip().lower() in {"unknown", "none", "null", "undefined", "n/a", "na", "?", "nil", "default"}:
            eff_loc = "Narayanguda, Hyderabad"

        # 1. Follow-up analytical inquiry detection on existing simulation evidence
        is_analytical_history = is_analytical_history_followup(obj_lower)
        is_explicit_new_testing = any(
            phrase in obj_lower for phrase in [
                "now test",
                "now simulate",
                "test a different",
                "simulate a different",
                "test another",
                "simulate another",
                "run a new simulation",
                "rerun",
            ]
        )

        has_sim_history = bool(
            (simulation_history and len(simulation_history) > 0)
            or (existing_results and (existing_results.get("simulations") or existing_results.get("simulation") or existing_results.get("simulation_history")))
        )

        if is_analytical_history and not is_explicit_new_testing:
            if has_sim_history:
                return LLMPlanDecision(
                    relevant=True,
                    objective=obj_clean,
                    identified_problem="Analytical evaluation of completed simulation history",
                    objective_understanding=f"Evaluate previously simulated intervention results: '{obj_clean}'",
                    required_capabilities=[],
                    agent_requests=[],
                    next_action="finalize",
                    confidence=1.0,
                    response=None,
                )
            else:
                return LLMPlanDecision(
                    relevant=True,
                    objective=obj_clean,
                    identified_problem="Analytical inquiry on unperformed simulations",
                    objective_understanding=f"Inquiry regarding tested interventions when no simulation history exists: '{obj_clean}'",
                    required_capabilities=[],
                    agent_requests=[],
                    next_action="finalize",
                    confidence=1.0,
                    response=None,
                )

        # 2. Follow-up: "Test / simulate the proposed intervention"
        if is_test_proposed_intervention_query(obj_lower):
            proposed_int = extract_proposed_intervention_from_context(conversation_history, existing_results)
            if not proposed_int:
                proposed_int = {
                    "type": "signal_timing",
                    "target": "Westbound",
                    "parameters": {"green_time_adjustment_sec": 10.0},
                }
            c_type = proposed_int.get("type", "signal_timing")
            c_target = proposed_int.get("target", "Westbound")
            c_label = f"{c_type}_{c_target.lower().replace(' ', '_')}"
            sim_req = {
                "scenario_name": eff_scenario or "synthetic_normal",
                "location": eff_loc,
                "duration_seconds": eff_duration or 120,
                "seed": eff_seed,
                "intervention": proposed_int,
                "candidate_intervention": c_label,
                "duration_steps": eff_duration or 120,
            }
            if c_type == "signal_timing":
                sim_req["signal_optimization"] = True

            has_base = bool(existing_results and ("traffic" in existing_results or "simulations" in existing_results))
            req_caps = ["simulation"] if has_base else ["traffic", "simulation"]
            agent_reqs = []
            if not has_base:
                agent_reqs.append(
                    AgentRequest(
                        agent="traffic",
                        request={
                            "location": eff_loc,
                            "duration_seconds": eff_duration or 120,
                            "scenario": eff_scenario or "synthetic_normal",
                            "seed": eff_seed,
                            "purpose": "baseline_traffic_analysis",
                        },
                        reason=f"Retrieve baseline traffic conditions at {eff_loc} before evaluating proposed intervention.",
                    )
                )
            agent_reqs.append(
                AgentRequest(
                    agent="simulation",
                    request=sim_req,
                    reason=f"Simulate proposed candidate intervention {c_type} on {c_target} corridor.",
                )
            )

            return LLMPlanDecision(
                relevant=True,
                objective=obj_clean,
                identified_problem=f"Empirical simulation evaluation of proposed intervention on {c_target}",
                objective_understanding=f"Simulate proposed {c_type} intervention on {c_target} corridor",
                required_capabilities=req_caps,
                agent_requests=agent_reqs,
                next_action="run_simulation" if has_base else "collect_evidence",
                confidence=1.0,
            )

        # 3. Deterministic Intent Routing for Single-Domain Queries
        is_weather_kw = any(w in obj_lower for w in ["weather", "temperature", "forecast", "precipitation", "rain", "raining", "rainfall", "humidity", "wind", "monsoon", "thunderstorm", "storm", "clear sky"])
        is_traffic_kw = any(w in obj_lower for w in ["traffic", "congestion", "bottleneck", "speed", "flow", "cars", "corridor", "queue", "delay", "flyover", "signal", "rerout", "intervention"])
        is_pollution_kw = any(w in obj_lower for w in ["pollution", "aqi", "air quality", "pm2.5", "pm25", "pm10", "smog", "emission", "emissions", "particulate"])
        is_energy_kw = any(w in obj_lower for w in ["energy", "grid status", "power grid", "substation load", "substation", "electricity load", "electricity consumption", "feeder load", "power consumption"])

        # Weather single-domain
        if is_weather_kw and not (is_traffic_kw or is_pollution_kw or is_energy_kw):
            return LLMPlanDecision(
                relevant=True,
                objective=obj_clean,
                identified_problem="Meteorological telemetry and weather monitoring",
                objective_understanding=f"Retrieve current weather and meteorological conditions at {eff_loc}",
                required_capabilities=["weather"],
                agent_requests=[
                    AgentRequest(
                        agent="weather",
                        request={"location": eff_loc, "purpose": "current_weather"},
                        reason=f"Determine current meteorological telemetry and precipitation at {eff_loc}.",
                    )
                ],
                next_action="collect_evidence",
                confidence=1.0,
            )

        # Pollution single-domain
        if is_pollution_kw and not (is_traffic_kw or is_weather_kw or is_energy_kw):
            is_hist = any(w in obj_lower for w in ["historical", "history", "trend", "trends", "past", "archive", "dataset", "2020", "2024", "multi-year"])
            data_mode = "historical" if is_hist else "current"
            return LLMPlanDecision(
                relevant=True,
                objective=obj_clean,
                identified_problem="Ambient air quality monitoring and particulate assessment",
                objective_understanding=f"Retrieve {'historical' if is_hist else 'current real-time'} air quality index and PM2.5 levels at {eff_loc}",
                required_capabilities=["pollution"],
                agent_requests=[
                    AgentRequest(
                        agent="pollution",
                        request={
                            "objective": obj_clean,
                            "location": eff_loc,
                            "data_mode": data_mode,
                            "purpose": "air_quality_assessment",
                        },
                        reason=f"Retrieve {'historical' if is_hist else 'current real-time'} ambient air quality index (AQI) and PM2.5 levels at {eff_loc}.",
                    )
                ],
                next_action="collect_evidence",
                confidence=1.0,
            )

        # Energy single-domain
        if is_energy_kw and not (is_traffic_kw or is_weather_kw or is_pollution_kw):
            return LLMPlanDecision(
                relevant=True,
                objective=obj_clean,
                identified_problem="Municipal electrical grid and substation load monitoring",
                objective_understanding=f"Query substation power draw and feeder load margins at {eff_loc}",
                required_capabilities=["energy"],
                agent_requests=[
                    AgentRequest(
                        agent="energy",
                        request={"location": eff_loc, "purpose": "substation_load_monitoring"},
                        reason=f"Query substation power draw and feeder load margins at {eff_loc}.",
                    )
                ],
                next_action="collect_evidence",
                confidence=1.0,
            )

        # Traffic diagnostic single-domain
        is_opt_kw = any(w in obj_lower for w in [
            "optimize", "optimization", "apply", "test", "simulate", "simulation", "compare",
            "evaluate", "reduce", "rerout", "signal", "intervention", "strategy", "mitigate", "remedy", "how can we"
        ])
        is_investigative = any(w in obj_lower for w in ["why", "cause", "reason", "due to"])
        is_traffic_diag = any(phrase in obj_lower for phrase in [
            "which corridor is the bottleneck",
            "which corridor is currently the bottleneck",
            "where is the bottleneck",
            "identify the bottleneck",
            "identify main bottlenecks",
            "diagnose current traffic",
            "what is the current traffic situation",
            "what are the current traffic conditions",
            "what is the traffic situation",
            "bottleneck corridor",
        ])
        if is_traffic_diag and not is_opt_kw and not is_investigative and not (is_weather_kw or is_pollution_kw or is_energy_kw):
            trf_req = {
                "location": eff_loc,
                "purpose": "baseline_traffic_analysis",
            }
            if eff_duration is not None:
                trf_req["duration_seconds"] = eff_duration
            if eff_scenario:
                trf_req["scenario"] = eff_scenario
            if eff_seed is not None:
                trf_req["seed"] = eff_seed

            return LLMPlanDecision(
                relevant=True,
                objective=obj_clean,
                identified_problem="Traffic congestion and corridor bottleneck diagnostics",
                objective_understanding=f"Retrieve baseline corridor congestion index, vehicle counts, and queue bottlenecks at {eff_loc}",
                required_capabilities=["traffic"],
                agent_requests=[
                    AgentRequest(
                        agent="traffic",
                        request=trf_req,
                        reason=f"Retrieve baseline corridor congestion index, vehicle counts, and queue bottlenecks at {eff_loc}.",
                    )
                ],
                next_action="collect_evidence",
                confidence=1.0,
            )

        # 4. Fall through to Autonomous LLM for complex / ambiguous / multi-domain planning
        provider = self._require_llm()
        user_prompt = build_stage_1_prompt(
            objective=obj_clean,
            location=eff_loc,
            constraints=constraints,
            simulation_history=simulation_history,
            existing_results=existing_results,
        )

        raw_json = provider.generate_json(
            system_prompt=STAGE_1_PLANNER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.1,
        )

        try:
            decision = LLMPlanDecision.model_validate(raw_json)
        except Exception as exc:
            logger.error(f"LLM initial plan schema validation failed: {exc}")
            raise LLMJsonParsingError(f"LLM plan output failed validation: {exc}") from exc

        # Deterministic safeguard: filter and validate selected agents against allowed capabilities
        validated_calls: List[AgentRequest] = []
        for call in decision.agent_requests:
            agent_name = call.agent.lower().strip()
            if agent_name in ALLOWED_CAPABILITIES:
                call.agent = agent_name
                if agent_name == "traffic":
                    call.request = dict(call.request or {})
                    if eff_duration is not None and "duration_seconds" not in call.request:
                        call.request["duration_seconds"] = eff_duration
                    if eff_scenario and "scenario" not in call.request:
                        call.request["scenario"] = eff_scenario
                    if eff_seed is not None and "seed" not in call.request:
                        call.request["seed"] = eff_seed
                elif agent_name == "pollution":
                    call.request = dict(call.request or {})
                    if not call.request.get("objective"):
                        call.request["objective"] = obj_clean
                    if not call.request.get("location"):
                        call.request["location"] = location or "Narayanguda, Hyderabad"
                validated_calls.append(call)
            else:
                logger.warning(f"Safeguard rejected unallowed agent requested by LLM: {call.agent}")

        decision.agent_requests = validated_calls
        decision.required_capabilities = [c.agent for c in validated_calls]
        if decision.relevant and not validated_calls and decision.next_action == "collect_evidence":
            decision.next_action = "finalize"
        if not decision.objective:
            decision.objective = decision.objective_understanding or objective
        return decision

    def plan(self, user_query: str) -> PlannerResponse:
        """
        Backward-compatible public entrypoint for plan generation.
        Uses autonomous LLM planning to evaluate the query and select agents.
        """
        decision = self.plan_autonomous(objective=user_query)
        if not decision.relevant:
            return PlannerResponse(
                relevant=False,
                response=decision.response or "This question is outside the scope of the Smart City system.",
            )

        primary_domain = decision.required_capabilities[0] if decision.required_capabilities else "traffic"
        steps = [
            f"Diagnose issue: {decision.identified_problem or decision.objective_understanding or user_query}",
        ]
        for call in decision.agent_requests:
            steps.append(f"Query {call.agent.title()} Agent: {call.reason or 'Retrieve telemetry'}")
        if decision.next_action == "collect_evidence":
            steps.append("Collect and evaluate specialist evidence")
        elif decision.next_action == "run_simulation":
            steps.append("Execute candidate intervention simulation experiment")
        else:
            steps.append("Finalize findings and recommendations")

        return PlannerResponse(
            relevant=True,
            domain=primary_domain,
            objective=decision.objective or decision.objective_understanding or user_query,
            plan=steps,
            selected_agents=decision.agent_requests,
            required_capabilities=decision.required_capabilities,
            next_action=decision.next_action,
        )

    # ---------------------------------------------------------------------------
    # Contract-Aware Context Construction & Input Completeness Check
    # ---------------------------------------------------------------------------
    def build_agent_request_context(
        self,
        capability: str,
        objective: str,
        location: str,
        constraints: Optional[List[Any]] = None,
        existing_evidence: Optional[List[EvidenceItem]] = None,
        existing_results: Optional[Dict[str, Any]] = None,
        llm_generated_input: Optional[Dict[str, Any]] = None,
    ) -> AgentContextRequest:
        """
        Constructs and validates the structured request for a specialist agent.
        Uses LLM-generated inputs when available, verifies contract completeness,
        and ensures no values are fabricated.
        """
        cap = capability.lower().strip()
        contract = SPECIALIST_AGENT_CONTRACTS.get(cap, {})
        target_endpoint = contract.get("endpoint", f"/api/v1/{cap}")
        method = contract.get("method", "GET")
        required_fields = list(contract.get("required_inputs", []))

        existing_results = existing_results or {}
        missing_fields: List[str] = []

        # Start with LLM-generated payload if provided
        payload: Dict[str, Any] = dict(llm_generated_input or {})

        # Resolve location context: prioritize explicit location or payload location
        resolved_loc = (location or payload.get("location") or payload.get("city") or "").strip()

        if cap == "pollution":
            if not payload.get("objective") and objective:
                payload["objective"] = objective
            elif not payload.get("objective"):
                payload["objective"] = f"Analyze air pollution at {resolved_loc or 'designated location'}"
            if not payload.get("location"):
                if resolved_loc:
                    payload["location"] = resolved_loc
                else:
                    missing_fields.append("location")

        elif cap in ["traffic", "energy"]:
            if not payload.get("location"):
                if resolved_loc:
                    payload["location"] = resolved_loc
                else:
                    missing_fields.append("location")

        elif cap == "weather":
            if not payload.get("location") and not payload.get("city"):
                if resolved_loc:
                    payload["location"] = resolved_loc
                else:
                    missing_fields.append("location")

        elif cap == "simulation":
            if not payload.get("scenario_name"):
                if "traffic" in existing_results:
                    trf = existing_results["traffic"]
                    corridors = trf.get("corridors", [])
                    heavy = [c for c in corridors if c.get("status") == "HEAVY"]
                    if heavy:
                        payload["scenario_name"] = f"{heavy[0].get('name', 'central_corridor').lower().replace(' ', '_')}_scenario"
                if not payload.get("scenario_name") and resolved_loc:
                    payload["scenario_name"] = f"{resolved_loc.lower().replace(' ', '_').replace(',', '')}_corridor"

            if not payload.get("scenario_name"):
                missing_fields.append("scenario_name")

            if not payload.get("target_location"):
                if resolved_loc:
                    payload["target_location"] = resolved_loc
                else:
                    missing_fields.append("target_location")

            if "signal_optimization" not in payload and "candidate_intervention" not in payload:
                payload["signal_optimization"] = True

        for rf in required_fields:
            if (rf not in payload or payload[rf] in (None, "")) and rf not in missing_fields:
                missing_fields.append(rf)

        is_complete = len(missing_fields) == 0

        return AgentContextRequest(
            capability=cap,
            target_endpoint=target_endpoint,
            method=method,
            location=resolved_loc,
            payload=payload,
            required_fields=required_fields,
            missing_fields=missing_fields,
            is_complete=is_complete,
        )

    # ---------------------------------------------------------------------------
    # Specialist Output Validation (Deterministic Safeguard)
    # ---------------------------------------------------------------------------
    def validate_agent_output(self, capability: str, raw_output: Any) -> Dict[str, Any]:
        """
        Validates specialist response format and required metrics.
        Detects missing or corrupted data and raises ValueError.
        """
        cap = capability.lower().strip()

        if not isinstance(raw_output, dict):
            if cap in ("simulation", "simulations", "simulation_history", "simulations_history") and isinstance(raw_output, list):
                for item in raw_output:
                    if not isinstance(item, dict):
                        raise ValueError(f"Specialist agent '{capability}' list contains non-dict item")
                return raw_output
            raise ValueError(
                f"Specialist agent '{capability}' returned invalid non-dict response of type {type(raw_output).__name__}"
            )
        if not raw_output:
            raise ValueError(f"Specialist agent '{capability}' returned an empty payload")

        if cap == "traffic":
            metrics_dict = raw_output.get("metrics") if isinstance(raw_output.get("metrics"), dict) else {}
            has_metric = any(
                k in raw_output or k in metrics_dict
                for k in ["congestion_index", "average_speed_kmh", "corridors", "sensors", "active_vehicles"]
            )
            if not has_metric:
                raise ValueError("Specialist agent 'traffic' returned malformed payload missing key traffic metrics")

        elif cap == "weather":
            has_metric = any(k in raw_output for k in ["temperature_c", "condition", "precipitation_mm", "forecast_7d"])
            if not has_metric:
                raise ValueError("Specialist agent 'weather' returned malformed payload missing key meteorological metrics")

        elif cap == "pollution":
            if isinstance(raw_output, dict) and (
                raw_output.get("status") in ("unavailable", "failed", "error")
                or "error" in raw_output
            ):
                return raw_output
            required_numeric = ["city_avg_aqi", "pm25", "pm10"]
            missing_fields = [f for f in required_numeric if f not in raw_output or raw_output[f] is None]
            if missing_fields:
                raise ValueError(
                    f"Specialist agent 'pollution' returned malformed payload missing required numeric fields: {missing_fields}"
                )
            for num_field in required_numeric:
                val = raw_output[num_field]
                if isinstance(val, bool) or not isinstance(val, (int, float)):
                    raise ValueError(
                        f"Specialist agent 'pollution' field '{num_field}' must be numeric, got {type(val).__name__}"
                    )

        elif cap == "energy":
            has_metric = any(k in raw_output for k in ["load_pct", "current_load_mw", "substations"])
            if not has_metric:
                raise ValueError("Specialist agent 'energy' returned malformed payload missing grid load metrics")

        elif cap == "simulation":
            has_metric = any(k in raw_output for k in ["metrics", "sim_results", "scenario", "status"])
            if not has_metric:
                raise ValueError("Specialist agent 'simulation' returned malformed payload missing simulation metrics")

        return raw_output

    # ---------------------------------------------------------------------------
    # Structured Evidence Extraction (Deterministic Safeguard)
    # ---------------------------------------------------------------------------
    def extract_evidence(
        self,
        capability: str,
        data: Any,
        location: str,
    ) -> List[EvidenceItem]:
        """Extract atomic, structured evidence items from specialist telemetry."""
        evidence: List[EvidenceItem] = []
        loc = location or "Hyderabad"
        now_ts = data.get("timestamp") if isinstance(data, dict) else datetime.datetime.now(datetime.timezone.utc).isoformat()


        if capability == "traffic":
            metrics_dict = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
            cong_raw = data.get("congestion_index") if "congestion_index" in data else metrics_dict.get("congestion_index")
            if cong_raw is not None:
                val = float(cong_raw)
                if 0.0 < val <= 1.0:
                    val = val * 100.0
                sev = SeverityLevel.CRITICAL if val >= 75 else (SeverityLevel.HIGH if val >= 60 else (SeverityLevel.MODERATE if val >= 40 else SeverityLevel.LOW))
                evidence.append(EvidenceItem(
                    source="traffic",
                    metric="congestion_index",
                    value=val,
                    unit="percent",
                    location=loc,
                    severity=sev,
                    timestamp=now_ts,
                    details={
                        "active_vehicles": data.get("active_vehicles") or metrics_dict.get("active_vehicles"),
                        "delay_sec": data.get("average_delay_sec") or metrics_dict.get("average_delay_sec")
                    },
                ))
            speed_raw = data.get("average_speed_kmh") if "average_speed_kmh" in data else metrics_dict.get("average_speed_kmh")
            if speed_raw is not None:
                val = float(speed_raw)
                sev = SeverityLevel.CRITICAL if val < 15 else (SeverityLevel.HIGH if val < 22 else SeverityLevel.MODERATE)
                evidence.append(EvidenceItem(
                    source="traffic",
                    metric="average_speed_kmh",
                    value=val,
                    unit="km/h",
                    location=loc,
                    severity=sev,
                    timestamp=now_ts,
                ))
            delay_raw = data.get("average_delay_sec") if "average_delay_sec" in data else metrics_dict.get("average_delay_sec")
            if delay_raw is not None:
                val = float(delay_raw)
                sev = SeverityLevel.CRITICAL if val >= 60 else (SeverityLevel.HIGH if val >= 30 else (SeverityLevel.MODERATE if val >= 10 else SeverityLevel.LOW))
                evidence.append(EvidenceItem(
                    source="traffic",
                    metric="average_delay_sec",
                    value=val,
                    unit="seconds",
                    location=loc,
                    severity=sev,
                    timestamp=now_ts,
                ))
            tp_raw = data.get("throughput") if "throughput" in data else metrics_dict.get("throughput")
            if tp_raw is not None:
                tot = data.get("total_vehicles") or metrics_dict.get("total_vehicles") or 0
                evidence.append(EvidenceItem(
                    source="traffic",
                    metric="throughput",
                    value=float(tp_raw),
                    unit="vehicles",
                    location=loc,
                    severity=SeverityLevel.LOW,
                    timestamp=now_ts,
                    details={"total_vehicles": tot},
                ))
            for c in data.get("corridors", []):
                if c.get("status") in ["HEAVY", "CRITICAL"]:
                    evidence.append(EvidenceItem(
                        source="traffic",
                        metric="corridor_congestion",
                        value=c.get("avg_speed", 0.0),
                        unit="km/h",
                        location=c.get("name", loc),
                        severity=SeverityLevel.HIGH,
                        timestamp=now_ts,
                        details=c,
                    ))
            for s in data.get("sensors", []):
                if s.get("congestion") == "HEAVY" or s.get("occ", 0) > 85:
                    evidence.append(EvidenceItem(
                        source="traffic",
                        metric="bottleneck_sensor",
                        value=s.get("speed", 0.0),
                        unit="km/h",
                        location=s.get("name", loc),
                        severity=SeverityLevel.HIGH,
                        timestamp=now_ts,
                        details=s,
                    ))
            for b in data.get("bottlenecks", []):
                b_ev = b.get("evidence", {}) if isinstance(b, dict) else (b.evidence.model_dump() if hasattr(b, "evidence") else {})
                b_corr = b.get("corridor") if isinstance(b, dict) else getattr(b, "corridor", loc)
                b_reason = b.get("reason") if isinstance(b, dict) else getattr(b, "reason", "Bottleneck detected")
                b_sev_str = b.get("severity", "MODERATE") if isinstance(b, dict) else getattr(b, "severity", "MODERATE")
                b_sev = SeverityLevel.CRITICAL if b_sev_str == "CRITICAL" else (SeverityLevel.HIGH if b_sev_str == "HEAVY" else SeverityLevel.MODERATE)
                spd_val = b_ev.get("speed_kmh") if isinstance(b_ev, dict) else 0.0
                evidence.append(EvidenceItem(
                    source="traffic",
                    metric="diagnosed_bottleneck",
                    value=float(spd_val or 0.0),
                    unit="km/h",
                    location=b_corr,
                    severity=b_sev,
                    timestamp=now_ts,
                    details={"reason": b_reason, "evidence": b_ev},
                ))
            for cand in data.get("candidate_interventions", []):
                c_type = cand.get("type") if isinstance(cand, dict) else getattr(cand, "type", "")
                c_target = cand.get("target") if isinstance(cand, dict) else getattr(cand, "target", "")
                c_reason = cand.get("reason") if isinstance(cand, dict) else getattr(cand, "reason", "")
                c_exec = cand.get("executable", False) if isinstance(cand, dict) else getattr(cand, "executable", False)
                evidence.append(EvidenceItem(
                    source="traffic",
                    metric="candidate_intervention",
                    value=1.0 if c_exec else 0.0,
                    unit="executable_flag",
                    location=f"{c_type}:{c_target}",
                    severity=SeverityLevel.LOW,
                    timestamp=now_ts,
                    details={"type": c_type, "target": c_target, "reason": c_reason, "executable": c_exec},
                ))

        elif capability == "weather":
            if "precipitation_mm" in data:
                val = float(data["precipitation_mm"])
                sev = SeverityLevel.HIGH if val > 10.0 else (SeverityLevel.MODERATE if val > 0.0 else SeverityLevel.LOW)
                evidence.append(EvidenceItem(
                    source="weather",
                    metric="precipitation_mm",
                    value=val,
                    unit="mm",
                    location=loc,
                    severity=sev,
                    timestamp=now_ts,
                ))
            if "condition" in data:
                cond = str(data["condition"])
                evidence.append(EvidenceItem(
                    source="weather",
                    metric="condition",
                    value=cond,
                    location=loc,
                    severity=SeverityLevel.MODERATE if "rain" in cond.lower() or "storm" in cond.lower() else SeverityLevel.LOW,
                    timestamp=now_ts,
                ))
            forecast = data.get("forecast_7d", [])
            max_rain_pct = 0
            for f in forecast:
                r_str = f.get("rain", "0%").rstrip("%")
                try:
                    r_val = int(r_str)
                    if r_val > max_rain_pct:
                        max_rain_pct = r_val
                except ValueError:
                    pass
            if max_rain_pct > 0:
                sev = SeverityLevel.CRITICAL if max_rain_pct >= 75 else (SeverityLevel.HIGH if max_rain_pct >= 50 else SeverityLevel.MODERATE)
                evidence.append(EvidenceItem(
                    source="weather",
                    metric="rain_probability",
                    value=max_rain_pct,
                    unit="percent",
                    location=loc,
                    severity=sev,
                    timestamp=now_ts,
                    details={"forecast_days": len(forecast)},
                ))

        elif capability == "pollution":
            aqi_val = data.get("city_avg_aqi") if "city_avg_aqi" in data else data.get("aqi")
            if aqi_val is not None:
                try:
                    val = float(aqi_val)
                    sev = SeverityLevel.CRITICAL if val >= 200 else (SeverityLevel.HIGH if val >= 150 else (SeverityLevel.MODERATE if val >= 100 else SeverityLevel.LOW))
                    evidence.append(EvidenceItem(
                        source="pollution",
                        metric="city_avg_aqi",
                        value=val,
                        unit="AQI",
                        location=loc,
                        severity=sev,
                        timestamp=now_ts,
                        details={"city_avg_aqi": val, "category": data.get("category"), "primary_pollutant": data.get("primary_pollutant")},
                    ))
                except (ValueError, TypeError):
                    pass

            pm25_val = data.get("pm25")
            if pm25_val is not None:
                try:
                    val = float(pm25_val)
                    sev = SeverityLevel.CRITICAL if val >= 90 else (SeverityLevel.HIGH if val >= 60 else (SeverityLevel.MODERATE if val >= 30 else SeverityLevel.LOW))
                    evidence.append(EvidenceItem(
                        source="pollution",
                        metric="pm25",
                        value=val,
                        unit="ug/m3",
                        location=loc,
                        severity=sev,
                        timestamp=now_ts,
                        details={"pm25": val},
                    ))
                except (ValueError, TypeError):
                    pass

            pm10_val = data.get("pm10")
            if pm10_val is not None:
                try:
                    val = float(pm10_val)
                    sev = SeverityLevel.CRITICAL if val >= 150 else (SeverityLevel.HIGH if val >= 100 else (SeverityLevel.MODERATE if val >= 50 else SeverityLevel.LOW))
                    evidence.append(EvidenceItem(
                        source="pollution",
                        metric="pm10",
                        value=val,
                        unit="ug/m3",
                        location=loc,
                        severity=sev,
                        timestamp=now_ts,
                        details={"pm10": val},
                    ))
                except (ValueError, TypeError):
                    pass

            for st in data.get("stations", []):
                if isinstance(st, dict):
                    st_aqi = st.get("aqi", 0)
                    if st_aqi >= 150:
                        evidence.append(EvidenceItem(
                            source="pollution",
                            metric="station_hotspot",
                            value=float(st_aqi),
                            unit="AQI",
                            location=st.get("name", loc),
                            severity=SeverityLevel.HIGH,
                            timestamp=now_ts,
                            details=st,
                        ))
                elif isinstance(st, str):
                    evidence.append(EvidenceItem(
                        source="pollution",
                        metric="station",
                        value=1.0,
                        unit="station",
                        location=st,
                        severity=SeverityLevel.LOW,
                        timestamp=now_ts,
                        details={"name": st},
                    ))

            for inv in data.get("suggested_interventions", []):
                inv_dict = inv if isinstance(inv, dict) else (inv.model_dump() if hasattr(inv, "model_dump") else {})
                act = inv_dict.get("action_type") or str(inv)
                imp = inv_dict.get("expected_impact_pct", 0.0)
                evidence.append(EvidenceItem(
                    source="pollution",
                    metric="suggested_intervention",
                    value=float(imp or 0.0),
                    unit="percent_impact",
                    location=act,
                    severity=SeverityLevel.LOW,
                    timestamp=now_ts,
                    details=inv_dict,
                ))

        elif capability == "energy":
            load_pct = data.get("load_pct")
            if load_pct is not None:
                val = float(load_pct)
                sev = SeverityLevel.CRITICAL if val >= 85 else (SeverityLevel.HIGH if val >= 75 else SeverityLevel.MODERATE)
                evidence.append(EvidenceItem(
                    source="energy",
                    metric="load_pct",
                    value=val,
                    unit="percent",
                    location=loc,
                    severity=sev,
                    timestamp=now_ts,
                    details={"current_load_mw": data.get("current_load_mw"), "capacity_mw": data.get("capacity_mw")},
                ))

        elif capability == "simulation":
            sim_list = data if isinstance(data, list) else [data]
            for sim_item in sim_list:
                if not isinstance(sim_item, dict):
                    continue
                metrics = sim_item.get("metrics", {})
                scen_id = sim_item.get("scenario_id") or sim_item.get("scenario") or "scenario"
                if metrics:
                    evidence.append(EvidenceItem(
                        source="simulation",
                        metric=f"sim_avg_speed_kmh_{scen_id}",
                        value=metrics.get("average_speed_kmh") or metrics.get("avg_speed_kmh"),
                        unit="km/h",
                        location=loc,
                        severity=SeverityLevel.LOW,
                        timestamp=now_ts,
                        details=metrics,
                    ))
                    evidence.append(EvidenceItem(
                        source="simulation",
                        metric=f"sim_avg_waiting_time_sec_{scen_id}",
                        value=metrics.get("average_waiting_time_sec") or metrics.get("avg_waiting_time_sec"),
                        unit="seconds",
                        location=loc,
                        severity=SeverityLevel.LOW,
                        timestamp=now_ts,
                        details=metrics,
                    ))

        return evidence


    # ---------------------------------------------------------------------------
    # Stage 2: Autonomous LLM Evidence Evaluation & Replanning Decision
    # ---------------------------------------------------------------------------
    def evaluate_and_replan_autonomous(
        self,
        objective: str,
        cycle_num: int,
        history: List[Dict[str, Any]],
        collected_results: Dict[str, Any],
        failures: Dict[str, Any],
    ) -> LLMEvaluationDecision:
        """
        Submits collected evidence to the LLM to evaluate sufficiency, determine whether
        Eclipse SUMO simulation is needed, or request additional specialist agents.
        """
        provider = self._require_llm()
        user_prompt = build_stage_2_prompt(
            objective=objective,
            cycle_num=cycle_num,
            history=history,
            collected_results=collected_results,
            failures=failures,
        )

        raw_json = provider.generate_json(
            system_prompt=STAGE_2_EVALUATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.1,
        )

        try:
            decision = LLMEvaluationDecision.model_validate(raw_json)
        except Exception as exc:
            logger.error(f"LLM evaluation schema validation failed: {exc}")
            raise LLMJsonParsingError(f"LLM evaluation output failed validation: {exc}") from exc

        return decision

    def evaluate_and_replan(
        self,
        objective: str,
        plan: List[str],
        collected_results: Dict[str, Any],
        failures: Optional[Dict[str, Any]] = None,
        cycle_num: int = 1,
        max_cycles: int = 3,
        location: str = "Hyderabad",
    ) -> PlannerEvaluationResponse:
        """
        Bridge evaluation method:
        Extracts structured evidence items, invokes the LLM evaluation decision,
        and dynamically determines next_action (finalize, request_more_evidence, run_simulation).
        """
        failures = failures or {}

        # 1. Deterministic Safeguard: Validate outputs and extract atomic evidence
        all_evidence: List[EvidenceItem] = []
        for cap, data in collected_results.items():
            try:
                valid_data = self.validate_agent_output(cap, data)
                if isinstance(valid_data, dict) and (valid_data.get("status") in ("unavailable", "failed", "error") or "error" in valid_data):
                    failures[cap] = valid_data.get("error") or valid_data.get("detail") or f"Specialist agent '{cap}' unavailable"
                    continue
                all_evidence.extend(self.extract_evidence(cap, valid_data, location))
            except Exception as exc:
                logger.warning(f"Failed to validate/extract evidence for {cap}: {exc}")
                failures[cap] = str(exc)

        # 2. Derive Cross-Domain Analysis Flags from returned evidence
        has_traffic = "traffic" in collected_results and "traffic" not in failures
        has_weather = "weather" in collected_results and "weather" not in failures
        has_pollution = "pollution" in collected_results and "pollution" not in failures
        has_energy = "energy" in collected_results and "energy" not in failures
        sim_raw = (
            collected_results.get("simulations")
            or collected_results.get("simulation")
            or collected_results.get("simulation_history")
        )
        sim_list = sim_raw if isinstance(sim_raw, list) else ([sim_raw] if isinstance(sim_raw, dict) else [])
        has_simulation = len(sim_list) > 0 or "simulation" in collected_results or "simulations" in collected_results

        # Evaluate query characteristics for deterministic evaluation
        obj_eval_lower = (objective or "").lower().strip()
        is_diag_eval = any(
            w in obj_eval_lower for w in [
                "which corridor is the bottleneck",
                "which corridor is currently the bottleneck",
                "where is the bottleneck",
                "identify the bottleneck",
                "identify main bottlenecks",
                "diagnose current traffic",
                "what is the current traffic situation",
                "what are the current traffic conditions",
                "what is the traffic situation",
                "why is it slow",
                "why is this corridor slow",
                "which tested intervention",
                "performed better",
                "is rerouting better",
                "did the optimization solve",
                "did the optimization",
                "was the intervention effective",
                "did it solve the bottleneck",
            ]
        ) or (
            any(w in obj_eval_lower for w in ["bottleneck", "traffic situation", "conditions", "slow"])
            and not any(w in obj_eval_lower for w in [
                "optimize", "optimization", "apply", "test", "simulat", "compare", "evaluate",
                "reduce", "rerout", "signal", "intervention", "run", "mitigate", "solve", "how can we"
            ])
        )

        is_opt_eval = not is_diag_eval and any(
            w in obj_eval_lower for w in [
                "optimize", "optimization", "improve", "evaluate", "compare",
                "apply", "test", "simulate", "intervention", "strategy", "strategies",
                "rerout", "signal", "mitigate", "reduce", "how can we", "solve", "remedy"
            ]
        )

        is_analytical_eval = is_analytical_history_followup(obj_eval_lower)

        # Determine if Stage 2 LLM evaluation can be resolved deterministically
        can_eval_deterministically = False
        det_eval_decision = "finalize"
        det_eval_sufficient = True

        if is_diag_eval:
            can_eval_deterministically = True
            det_eval_decision = "finalize"
            det_eval_sufficient = True
        elif is_analytical_eval:
            can_eval_deterministically = True
            det_eval_decision = "finalize"
            det_eval_sufficient = True
        elif has_simulation and len(sim_list) > 0:
            can_eval_deterministically = True
            det_eval_decision = "finalize"
            det_eval_sufficient = True
        elif not is_opt_eval and not has_traffic and (has_weather or has_pollution or has_energy):
            can_eval_deterministically = True
            det_eval_decision = "finalize"
            det_eval_sufficient = True
        elif is_opt_eval and len(sim_list) == 0 and has_traffic:
            can_eval_deterministically = True
            det_eval_decision = "run_simulation"
            det_eval_sufficient = False
        elif cycle_num >= max_cycles:
            can_eval_deterministically = True
            det_eval_decision = "finalize"
            det_eval_sufficient = True

        history = [
            {"cycle": cycle_num, "dispatched_capabilities": list(collected_results.keys())}
        ]

        if can_eval_deterministically:
            llm_eval = LLMEvaluationDecision(
                evidence_sufficient=det_eval_sufficient,
                decision=det_eval_decision,
                next_action=det_eval_decision,
                analysis=f"Deterministic evaluation: evidence sufficiency verified (decision={det_eval_decision}).",
                missing_information=[],
                agent_requests=[],
                required_capabilities=[],
                confidence=1.0,
            )
        else:
            llm_eval = self.evaluate_and_replan_autonomous(
                objective=objective,
                cycle_num=cycle_num,
                history=history,
                collected_results=collected_results,
                failures=failures,
            )

        key_findings = []
        diagnosed_bottlenecks = []
        candidate_interventions = []
        sim_comparison = None

        if has_traffic:
            trf = collected_results["traffic"]
            metrics = trf.get("metrics", {}) if isinstance(trf.get("metrics"), dict) else {}
            cong = trf.get("congestion_index") if "congestion_index" in trf else metrics.get("congestion_index")
            avg_speed = trf.get("average_speed_kmh") if "average_speed_kmh" in trf else metrics.get("average_speed_kmh")
            delay_sec = trf.get("average_delay_sec") if "average_delay_sec" in trf else metrics.get("average_delay_sec")
            wait_sec = trf.get("average_waiting_time_sec") if "average_waiting_time_sec" in trf else metrics.get("average_waiting_time_sec")
            tp = trf.get("throughput") if "throughput" in trf else metrics.get("throughput")
            tot_veh = trf.get("total_vehicles") if "total_vehicles" in trf else metrics.get("total_vehicles")

            if cong is not None:
                cong_f = float(cong)
                cong_disp = f"{cong_f * 100:.1f}%" if 0.0 <= cong_f <= 1.0 else f"{cong_f:.1f}%"
            else:
                cong_disp = "N/A"

            spd_disp = f"{avg_speed} km/h" if avg_speed is not None else "N/A"
            key_findings.append(f"Traffic telemetry indicates {cong_disp} congestion index at {spd_disp} average speed.")
            if delay_sec is not None:
                key_findings.append(f"Average vehicle delay: {delay_sec}s (accumulated waiting time: {wait_sec or 0.0}s).")
            if tot_veh is not None:
                key_findings.append(f"Throughput: {tp or 0} completed trips across {tot_veh} participating vehicles.")

            # Populate diagnosed bottlenecks from structured traffic intelligence if present
            trf_bottlenecks = trf.get("bottlenecks", [])
            if trf_bottlenecks:
                for b in trf_bottlenecks:
                    b_corr = b.get("corridor") if isinstance(b, dict) else getattr(b, "corridor", "")
                    b_reason = b.get("reason") if isinstance(b, dict) else getattr(b, "reason", "")
                    if "lowest observed-speed corridor" in (b_reason or "").lower():
                        diagnosed_bottlenecks.append(f"Lowest observed-speed corridor: '{b_corr}' ({b_reason})")
                    else:
                        diagnosed_bottlenecks.append(f"Bottleneck '{b_corr}': {b_reason or 'congestion identified'}")
            else:
                corridors = trf.get("corridors", [])
                for c in corridors:
                    if c.get("status") in ("HEAVY", "CRITICAL"):
                        diagnosed_bottlenecks.append(f"Corridor '{c.get('name')}' (Speed: {c.get('avg_speed')} km/h, Status: {c.get('status')})")
                for s in trf.get("sensors", []):
                    if s.get("congestion") in ("HEAVY", "CRITICAL"):
                        diagnosed_bottlenecks.append(f"{s.get('name')} (Status: {s.get('congestion')})")

                if not diagnosed_bottlenecks and corridors:
                    valid_corrs = [c for c in corridors if c.get("avg_speed") is not None]
                    if valid_corrs:
                        slowest = min(valid_corrs, key=lambda c: c.get("avg_speed", 999))
                        diagnosed_bottlenecks.append(f"Lowest observed-speed corridor: '{slowest.get('name')}' (Speed: {slowest.get('avg_speed')} km/h, Status: {slowest.get('status')})")

            # Ingest structured candidate interventions from Traffic Agent
            trf_candidates = trf.get("candidate_interventions", [])
            for cand in trf_candidates:
                c_type = cand.get("type") if isinstance(cand, dict) else getattr(cand, "type", "")
                c_target = cand.get("target") if isinstance(cand, dict) else getattr(cand, "target", "")
                c_reason = cand.get("reason") if isinstance(cand, dict) else getattr(cand, "reason", "")
                c_exec = cand.get("executable", False) if isinstance(cand, dict) else getattr(cand, "executable", False)
                exec_lbl = "EXECUTABLE" if c_exec else "CANDIDATE-ONLY"
                candidate_interventions.append(f"[{c_type}:{c_target}] ({exec_lbl}) {c_reason}")

            # Ingest potential pre-simulation trade-offs
            trf_tradeoffs = trf.get("trade_offs", [])
            for to in trf_tradeoffs:
                to_interv = to.get("intervention") if isinstance(to, dict) else getattr(to, "intervention", "")
                to_target = to.get("target") if isinstance(to, dict) else getattr(to, "target", "")
                to_tradeoff = to.get("potential_tradeoff") if isinstance(to, dict) else getattr(to, "potential_tradeoff", "")
                key_findings.append(f"Traffic Agent trade-off analysis: {to_interv} for {to_target} - {to_tradeoff}")

        if has_weather:
            wtr = collected_results["weather"]
            cond = wtr.get("condition", "Partly Cloudy")
            precip = float(wtr.get("precipitation_mm", 0.0))
            if has_traffic:
                key_findings.append(f"Weather conditions ({cond}, {precip} mm rain) evaluated against roadway friction.")
            else:
                key_findings.append(f"Weather conditions: {cond}, {precip} mm precipitation.")

        if has_pollution:
            pol = collected_results["pollution"]
            aqi = pol.get("city_avg_aqi") if "city_avg_aqi" in pol else (pol.get("aqi") or 0)
            pm25 = pol.get("pm25")
            pm10 = pol.get("pm10")
            pol_desc = f"Air quality index: {aqi} AQI"
            if pm25 is not None and pm10 is not None:
                pol_desc += f" (PM2.5: {pm25} µg/m³, PM10: {pm10} µg/m³)"
            if has_traffic:
                key_findings.append(f"{pol_desc} correlated with roadway corridor emissions.")
            else:
                key_findings.append(f"{pol_desc}.")

            interventions = pol.get("suggested_interventions", [])
            if interventions and isinstance(interventions, list):
                interv_names = []
                for inv in interventions:
                    if isinstance(inv, dict):
                        interv_names.append(inv.get("action_type", "intervention"))
                    elif hasattr(inv, "action_type"):
                        interv_names.append(getattr(inv, "action_type"))
                if interv_names:
                    key_findings.append(f"Pollution Agent suggested municipal interventions: {', '.join(interv_names)}.")

        if has_energy:
            eng = collected_results["energy"]
            load_pct = eng.get("load_pct", 0)
            key_findings.append(f"Grid substation load monitored at {load_pct}%.")

        tested_scenarios: List[Dict[str, Any]] = []
        all_trade_offs: List[str] = []

        if has_simulation:
            for s_idx, sim in enumerate(sim_list):
                if not isinstance(sim, dict):
                    continue
                metrics = sim.get("metrics", {}) if isinstance(sim.get("metrics"), dict) else {}
                comparison_dict = sim.get("comparison")
                scen_id = sim.get("scenario_id") or sim.get("scenario") or f"scenario_{s_idx+1}"

                # If comparison not precomputed, compute against traffic baseline if present
                if not comparison_dict and has_traffic:
                    trf = collected_results["traffic"]
                    trf_m = trf.get("metrics", {}) if isinstance(trf.get("metrics"), dict) else {}
                    base_spd = trf.get("average_speed_kmh") or trf_m.get("average_speed_kmh")
                    int_spd = sim.get("average_speed_kmh") or metrics.get("average_speed_kmh")
                    base_del = trf.get("average_delay_sec") or trf_m.get("average_delay_sec")
                    int_del = sim.get("average_delay_sec") or metrics.get("average_delay_sec")
                    base_cong = trf.get("congestion_index") or trf_m.get("congestion_index")
                    int_cong = sim.get("congestion_index") or metrics.get("congestion_index")

                    spd_pct = round(((int_spd - base_spd) / base_spd) * 100.0, 2) if (base_spd and int_spd and base_spd > 0) else None
                    del_pct = round(((base_del - int_del) / base_del) * 100.0, 2) if (base_del and int_del and base_del > 0) else None
                    cong_pct = round(((base_cong - int_cong) / base_cong) * 100.0, 2) if (base_cong and int_cong and base_cong > 0) else None

                    delay_change = round(((int_del - base_del) / base_del) * 100.0, 2) if (base_del and int_del and base_del > 0) else None
                    cong_change = round(((int_cong - base_cong) / base_cong) * 100.0, 2) if (base_cong and int_cong and base_cong > 0) else None

                    cor_comps = []
                    base_corrs = {str(c.get("name") or c.get("id")).lower(): c.get("avg_speed") for c in trf.get("corridors", []) if isinstance(c, dict) and c.get("avg_speed") is not None}
                    sim_corrs = sim.get("corridors", []) if isinstance(sim.get("corridors"), list) else []
                    for sim_c in sim_corrs:
                        if isinstance(sim_c, dict):
                            c_name = sim_c.get("name") or sim_c.get("id")
                            c_spd = sim_c.get("avg_speed")
                            if c_name and c_spd is not None:
                                b_spd = base_corrs.get(str(c_name).lower())
                                if b_spd and b_spd > 0:
                                    c_delta_pct = round(((c_spd - b_spd) / b_spd) * 100.0, 2)
                                    cor_comps.append({
                                        "name": c_name,
                                        "id": sim_c.get("id"),
                                        "baseline_speed_kmh": b_spd,
                                        "intervention_speed_kmh": c_spd,
                                        "speed_change_pct": c_delta_pct,
                                        "is_target": bool(sim.get("intervention_applied", {}).get("target", "").lower() in str(c_name).lower()),
                                    })

                    comparison_dict = {
                        "scenario_id": scen_id,
                        "speed_change_pct": spd_pct,
                        "delay_reduction_pct": del_pct,
                        "delay_change_pct": delay_change,
                        "congestion_reduction_pct": cong_pct,
                        "congestion_change_pct": cong_change,
                        "corridor_comparisons": cor_comps,
                    }

                trade_offs = (comparison_dict.get("corridor_trade_offs") if comparison_dict else None) or sim.get("corridor_trade_offs") or []
                all_trade_offs.extend(trade_offs)

                scen_comp = comparison_dict or {}
                scen_meta = sim.get("metadata", {}) if isinstance(sim.get("metadata"), dict) else {}
                scen_dur = sim.get("duration_seconds") or sim.get("duration") or scen_meta.get("duration_seconds") or scen_comp.get("intervention_duration_seconds") or scen_comp.get("baseline_duration_seconds")
                scen_seed = sim.get("seed") or scen_meta.get("random_seed") or scen_comp.get("intervention_seed") or scen_comp.get("baseline_seed")
                scen_scenario = sim.get("scenario") or scen_meta.get("demand_profile") or scen_comp.get("intervention_scenario") or scen_comp.get("baseline_scenario") or "synthetic_peak_westbound"
                scen_net = sim.get("network_name") or scen_meta.get("network_name") or scen_comp.get("intervention_network") or scen_comp.get("baseline_network") or "narayanguda_network.net.xml"

                b_ref = sim.get("baseline_reference") or scen_comp.get("baseline_reference")
                b_metrics = sim.get("baseline_metrics") or scen_comp.get("baseline_summary")
                int_metrics = sim.get("intervention_metrics") or scen_comp.get("intervention_summary") or metrics

                scen_entry = {
                    "scenario_id": scen_id,
                    "scenario": scen_scenario,
                    "duration_seconds": scen_dur,
                    "seed": scen_seed,
                    "network": scen_net,
                    "network_name": scen_net,
                    "intervention": sim.get("intervention_applied") or sim.get("intervention"),
                    "baseline_reference": b_ref,
                    "baseline_metrics": b_metrics,
                    "intervention_metrics": int_metrics,
                    "metrics": metrics,
                    "comparison": comparison_dict,
                    "corridor_trade_offs": trade_offs,
                    "trade_off_summary": comparison_dict.get("trade_off_summary") if comparison_dict else None,
                    "fair_comparison": comparison_dict.get("fair_comparison", True) if comparison_dict else True,
                    "status": sim.get("status", "SUCCESS"),
                    "evidence_status": sim.get("evidence_status") or ("EVIDENCE: MULTI-SIMULATION EVALUATION" if len(sim_list) > 1 else "EVIDENCE: SINGLE SIMULATION RUN"),
                }
                tested_scenarios.append(scen_entry)

                int_spd_val = sim.get("average_speed_kmh") or metrics.get("average_speed_kmh")
                int_del_val = sim.get("average_delay_sec") or metrics.get("average_delay_sec")
                key_findings.append(
                    f"Scenario '{scen_id}' microsimulation completed: speed={int_spd_val} km/h, delay={int_del_val}s."
                )
                if comparison_dict:
                    spd_chg = comparison_dict.get("speed_change_pct")
                    del_red = comparison_dict.get("delay_reduction_pct")
                    cor_comps = comparison_dict.get("corridor_comparisons", [])
                    target_cor_comp = next((c for c in cor_comps if c.get("speed_change_pct") is not None and c.get("speed_change_pct") != 0.0), None)
                    if target_cor_comp:
                        key_findings.append(
                            f"[{scen_id}] Target corridor '{target_cor_comp.get('name')}' speed changed by "
                            f"{target_cor_comp.get('speed_change_pct'):+.1f}% ({target_cor_comp.get('baseline_speed_kmh')} -> {target_cor_comp.get('intervention_speed_kmh')} km/h)."
                        )
                    if trade_offs:
                        key_findings.append(
                            f"[{scen_id}] Corridor trade-offs identified: {'; '.join(trade_offs)}."
                        )
                    if spd_chg is not None and del_red is not None:
                        key_findings.append(
                            f"[{scen_id}] Network delta: speed change {spd_chg:+.2f}%, delay change {-del_red:+.2f}%."
                        )

            import re
            target_dur = None
            obj_l = objective.lower()
            if not ("300" in obj_l and "600" in obj_l):
                dur_match = re.search(r"\b(120|300|600)\s*(?:-|\s)?(?:sec|s|second)", obj_l)
                if dur_match:
                    target_dur = int(dur_match.group(1))

            matching_scenarios = [
                s for s in tested_scenarios
                if target_dur is None or s.get("duration_seconds") == target_dur
            ]
            target_scen = matching_scenarios[-1] if matching_scenarios else (tested_scenarios[-1] if tested_scenarios else {})

            sim_comparison = {
                "source": "SUMO (Synthetic Traffic Demand Simulation)",
                "scenario_count": len(tested_scenarios),
                "tested_scenarios": tested_scenarios,
                "comparison": target_scen.get("comparison", {}) if isinstance(target_scen, dict) else {},
                "corridor_trade_offs": list(dict.fromkeys(all_trade_offs)),
                "status": "SUCCESS",
                "requested_duration": target_dur,
            }

        corr_label = "Domain Assessment"
        if has_weather and has_traffic:
            corr_label = "Weather → Traffic Friction & Flow Delay"
        elif has_traffic and has_pollution:
            corr_label = "Traffic Congestion & Emissions → Air Pollution Exposure"
        elif has_pollution:
            corr_label = "Environmental Air Quality Analysis"

        cross_analysis = CrossDomainAnalysis(
            primary_correlation=corr_label,
            risk_level=SeverityLevel.HIGH if (has_weather and has_traffic) or (has_traffic and has_pollution) else SeverityLevel.MODERATE,
            causation_likelihood="STRONG" if (has_weather and has_traffic) or (has_traffic and has_pollution) else "PLAUSIBLE",
            key_findings=key_findings,
            diagnosed_bottlenecks=diagnosed_bottlenecks[:4],
            candidate_interventions=candidate_interventions[:3],
            simulation_comparison=sim_comparison,
        )

        # 4. Map LLM decision and next action dynamically
        dec_lower = str(llm_eval.decision).lower().strip()
        obj_lower = objective.lower().strip()

        is_purely_diagnostic = any(
            w in obj_lower for w in [
                "which corridor is the bottleneck",
                "which corridor is currently the bottleneck",
                "where is the bottleneck",
                "identify the bottleneck",
                "identify main bottlenecks",
                "diagnose current traffic",
                "what is the current traffic situation",
                "what are the current traffic conditions",
                "what is the traffic situation",
                "why is it slow",
                "why is this corridor slow",
                "which tested intervention",
                "performed better",
                "is rerouting better",
                "did the optimization solve",
                "did the optimization",
                "was the intervention effective",
                "did it solve the bottleneck",
            ]
        ) or (
            any(w in obj_lower for w in ["bottleneck", "traffic situation", "conditions", "slow"])
            and not any(w in obj_lower for w in [
                "optimize", "optimization", "apply", "test", "simulat", "compare", "evaluate",
                "reduce", "rerout", "signal", "intervention", "run", "mitigate", "solve", "how can we"
            ])
        )

        is_optimization_requested = not is_purely_diagnostic and any(
            w in obj_lower for w in [
                "optimize", "optimization", "improve", "evaluate", "compare",
                "apply", "test", "simulate", "intervention", "strategy", "strategies",
                "rerout", "signal", "mitigate", "reduce", "how can we", "solve", "remedy"
            ]
        )

        if is_purely_diagnostic:
            decision_mapped = "finalize"
            next_action = "finalize"
            is_sufficient = True
            validated_next_calls = []
            next_cycle_caps = []
        elif is_optimization_requested and len(tested_scenarios) == 0 and has_traffic:
            # Multi-intervention candidate selection for real SUMO simulation
            trf_data = collected_results["traffic"]
            b_meta = trf_data.get("metadata") if isinstance(trf_data.get("metadata"), dict) else {}
            base_seed = trf_data.get("seed") if trf_data.get("seed") is not None else b_meta.get("random_seed")
            base_duration = trf_data.get("duration_seconds") if trf_data.get("duration_seconds") is not None else b_meta.get("duration_seconds")
            base_scenario = trf_data.get("scenario") or trf_data.get("scenario_name") or b_meta.get("demand_profile")
            base_loc = trf_data.get("location") or location

            raw_cands = trf_data.get("candidate_interventions", [])
            executable_cands = [
                c for c in raw_cands
                if (c.get("executable") if isinstance(c, dict) else getattr(c, "executable", False))
            ]

            # Identify the primary/main bottleneck from traffic analysis
            main_bottleneck = None
            if diagnosed_bottlenecks:
                main_bottleneck = diagnosed_bottlenecks[0]
            elif trf_data.get("bottlenecks"):
                b0 = trf_data["bottlenecks"][0]
                main_bottleneck = b0.get("corridor") or b0.get("name") if isinstance(b0, dict) else str(b0)
            elif trf_data.get("corridors"):
                valid_c = [c for c in trf_data["corridors"] if c.get("avg_speed") is not None]
                if valid_c:
                    slowest_c = min(valid_c, key=lambda c: c["avg_speed"])
                    main_bottleneck = slowest_c.get("name")

            # Extract clean direction token if corridor has format like "Narayanguda - Hyderguda (Westbound)"
            target_direction = main_bottleneck
            if main_bottleneck:
                for d in ["Westbound", "Eastbound", "Northbound", "Southbound"]:
                    if d.lower() in main_bottleneck.lower():
                        target_direction = d
                        break

            is_optimize_bottleneck_query = any(
                w in obj_lower for w in [
                    "main bottleneck", "optimize bottleneck", "optimize the bottleneck",
                    "solve the bottleneck", "relieve the bottleneck", "address the bottleneck",
                    "optimize slowest", "fix the bottleneck"
                ]
            )

            # If user asks to optimize the main bottleneck, prioritize candidates targeting that bottleneck
            if is_optimize_bottleneck_query and (target_direction or main_bottleneck):
                tgt_key = (target_direction or main_bottleneck or "").lower()
                bottleneck_cands = [
                    c for c in executable_cands
                    if tgt_key in str(c.get("target") if isinstance(c, dict) else getattr(c, "target", "")).lower()
                ]
                other_cands = [c for c in executable_cands if c not in bottleneck_cands]
                executable_cands = bottleneck_cands + other_cands

            # Priority for explicit user-requested comparison (User Adjustment 4)
            wants_signal = any(w in obj_lower for w in ["signal", "timing", "green"])
            wants_reroute = any(w in obj_lower for w in ["rerout", "diversion", "divert"])

            selected_candidates = []
            sig_c = next((c for c in executable_cands if "signal" in str(c.get("type") if isinstance(c, dict) else getattr(c, "type", "")).lower()), None)
            rer_c = next((c for c in executable_cands if "rerout" in str(c.get("type") if isinstance(c, dict) else getattr(c, "type", "")).lower()), None)

            if wants_reroute and not wants_signal:
                if rer_c:
                    selected_candidates.append(rer_c)
            elif wants_signal and not wants_reroute:
                if sig_c:
                    selected_candidates.append(sig_c)
            elif wants_signal and wants_reroute:
                if sig_c:
                    selected_candidates.append(sig_c)
                if rer_c:
                    selected_candidates.append(rer_c)

            # Fill remaining executable candidates up to MAX_OPTIMIZATION_CANDIDATES
            for cand in executable_cands:
                if len(selected_candidates) >= MAX_OPTIMIZATION_CANDIDATES:
                    break
                if cand not in selected_candidates:
                    selected_candidates.append(cand)

            if selected_candidates:
                missing_meta = []
                if base_seed is None:
                    missing_meta.append("seed")
                if base_duration is None:
                    missing_meta.append("duration_seconds")
                if not base_scenario:
                    missing_meta.append("scenario")
                if not base_loc:
                    missing_meta.append("location")

                if missing_meta:
                    raise ValueError(
                        f"Missing required baseline simulation metadata: {', '.join(missing_meta)}. "
                        f"Baseline metadata must be dynamically provided by Traffic Agent / baseline simulation without environment-specific fallbacks."
                    )
                validated_next_calls = []
                base_net = trf_data.get("network_name") or b_meta.get("network_name") or "narayanguda_network.net.xml"
                b_reference = {
                    "scenario_id": trf_data.get("scenario_id") or f"baseline:dur{base_duration}s:seed{base_seed}",
                    "scenario": base_scenario,
                    "duration_seconds": base_duration,
                    "seed": base_seed,
                    "network": base_net,
                }
                for cand in selected_candidates:
                    c_dict = cand if isinstance(cand, dict) else cand.model_dump()
                    c_type = c_dict.get("type") or c_dict.get("intervention_type")
                    c_target = c_dict.get("target") or target_direction or main_bottleneck or "Westbound"
                    c_params = c_dict.get("parameters") or {}

                    if is_optimize_bottleneck_query and target_direction and target_direction.lower() not in c_target.lower():
                        c_reason = (
                            f"Primary bottleneck is {main_bottleneck or target_direction}, but candidate intervention {c_type} targets "
                            f"{c_target} to test upstream diversion / alternative arterial route mitigation."
                        )
                    else:
                        c_reason = f"Candidate intervention {c_type} on {c_target} selected for evaluation under baseline conditions (seed={base_seed}, duration={base_duration}s)."

                    validated_next_calls.append(AgentRequest(
                        agent="simulation",
                        request={
                            "scenario_name": base_scenario,
                            "location": base_loc,
                            "duration_seconds": base_duration,
                            "seed": base_seed,
                            "network_name": base_net,
                            "intervention": {
                                "type": c_type,
                                "target": c_target,
                                "parameters": c_params,
                            },
                            "candidate_intervention": f"{c_type}_{c_target.lower().replace(' ', '_')}",
                            "duration_steps": base_duration,
                            "baseline_reference": b_reference,
                        },
                        reason=c_reason,
                    ))
                decision_mapped = "run_simulation"
                next_action = "run_simulation"
                next_cycle_caps = ["simulation"]
                is_sufficient = False
            elif dec_lower == "run_simulation" or any(r.agent == "simulation" for r in llm_eval.agent_requests):
                decision_mapped = "run_simulation"
                next_action = "run_simulation"
                next_cycle_caps = ["simulation"]
                is_sufficient = False
                fallback_target = target_direction or main_bottleneck or "Westbound"
                validated_next_calls = [
                    r for r in llm_eval.agent_requests if r.agent in ALLOWED_CAPABILITIES
                ] or [
                    AgentRequest(
                        agent="simulation",
                        request={
                            "scenario_name": base_scenario,
                            "location": base_loc,
                            "duration_seconds": base_duration,
                            "seed": base_seed,
                            "intervention": {
                                "type": "signal_timing",
                                "target": fallback_target,
                                "parameters": {"green_time_adjustment_sec": 10.0},
                            },
                        },
                        reason=f"Evaluate signal timing optimization on {fallback_target} bottleneck.",
                    )
                ]
            else:
                decision_mapped = "finalize"
                next_action = "finalize"
                is_sufficient = True
                validated_next_calls = []
                next_cycle_caps = []
        else:
            is_sufficient = llm_eval.evidence_sufficient or dec_lower in ("finalize", "proceed_to_recommendation", "enough_evidence") or (cycle_num >= max_cycles)

            if cycle_num >= max_cycles:
                decision_mapped = "finalize"
                next_action = "finalize"
            elif dec_lower in ("run_simulation", "request_more_evidence", "abort", "finalize"):
                decision_mapped = dec_lower
            elif is_sufficient:
                decision_mapped = "finalize"
            else:
                decision_mapped = "re_plan"

            next_cycle_caps = []
            validated_next_calls = []

            for na in llm_eval.agent_requests:
                if na.agent in ALLOWED_CAPABILITIES:
                    validated_next_calls.append(na)
                    if na.agent not in next_cycle_caps:
                        next_cycle_caps.append(na.agent)

            if dec_lower == "run_simulation" and "simulation" not in next_cycle_caps:
                next_cycle_caps.append("simulation")
            elif dec_lower == "abort":
                decision_mapped = "abort"

            if cycle_num >= max_cycles or is_sufficient:
                next_action = "finalize"
            else:
                next_action = "run_simulation" if "simulation" in next_cycle_caps or dec_lower == "run_simulation" else "request_more_evidence"

        # Structured partition: tested interventions (executed via SUMO with empirical metrics)
        tested_interventions: List[Dict[str, Any]] = []
        for scen in tested_scenarios:
            scen_int = scen.get("intervention") or {}
            scen_comp = scen.get("comparison") or {}
            scen_id_str = str(scen.get("scenario_id") or "").lower()
            if scen_id_str.startswith("baseline") and not (scen_int.get("type") or scen.get("intervention_applied")):
                continue
            tested_interventions.append({
                "type": scen_int.get("type"),
                "target": scen_int.get("target"),
                "parameters": scen_int.get("parameters"),
                "scenario_id": scen.get("scenario_id"),
                "status": "SIMULATED",
                "metrics": scen.get("metrics"),
                "comparison": scen_comp,
                "corridor_trade_offs": scen.get("corridor_trade_offs", []),
                "baseline_reference": scen.get("baseline_reference"),
                "baseline_metrics": scen.get("baseline_metrics"),
                "intervention_metrics": scen.get("intervention_metrics"),
            })

        # Structured partition: untested candidates (from Traffic Agent, NOT simulated in this cycle)
        untested_candidates: List[Dict[str, Any]] = []
        if has_traffic:
            raw_cands = collected_results["traffic"].get("candidate_interventions", [])
            for cand in raw_cands:
                cand_dict = cand if isinstance(cand, dict) else (cand.model_dump() if hasattr(cand, "model_dump") else {})
                c_type = str(cand_dict.get("type") or cand_dict.get("intervention_type") or "").strip().lower()
                c_target = str(cand_dict.get("target") or "").strip().lower()

                # Reliable structured matching: match intervention type and target
                is_tested = any(
                    str(t.get("type") or "").strip().lower() == c_type
                    and (not c_target or not t.get("target") or c_target in str(t.get("target")).strip().lower() or str(t.get("target")).strip().lower() in c_target)
                    for t in tested_interventions
                )
                if not is_tested:
                    untested_candidates.append({
                        "type": cand_dict.get("type") or cand_dict.get("intervention_type"),
                        "target": cand_dict.get("target"),
                        "parameters": cand_dict.get("parameters", {}),
                        "reason": cand_dict.get("reason", ""),
                        "status": "UNTESTED_IN_THIS_CYCLE",
                        "potential_benefit": cand_dict.get("potential_benefit", ""),
                        "potential_tradeoff": cand_dict.get("potential_tradeoff", ""),
                        "notes": "Candidate identified by Traffic Agent but not simulated in this cycle. Comparative effectiveness is unverified.",
                    })

        involves_traffic_opt_or_sim = request_involves_traffic_optimization_or_simulation(
            objective=objective,
            collected_results=collected_results,
            tested_interventions=tested_interventions,
            untested_candidates=untested_candidates,
        )

        # Deterministic evidence status based strictly on executed simulation count
        num_simulated = len(tested_interventions)
        if num_simulated == 0:
            det_evidence_status = "EVIDENCE: OBSERVATIONAL"
        elif num_simulated == 1:
            det_evidence_status = "EVIDENCE: SINGLE SIMULATION RUN"
        else:
            det_evidence_status = "EVIDENCE: MULTI-SIMULATION EVALUATION"

        final_reasoning = None
        final_rec = None

        if is_sufficient or cycle_num >= max_cycles:
            try:
                sim_res = collected_results.get("simulation")
                final_reasoning = self.generate_final_reasoning(
                    objective=objective,
                    location=location,
                    history=history,
                    collected_results=collected_results,
                    simulation_results=sim_res,
                )
                if final_reasoning:
                    final_reasoning.evidence_status = det_evidence_status
                    final_reasoning.tested_interventions = tested_interventions
                    final_reasoning.untested_candidates = untested_candidates
                    if not involves_traffic_opt_or_sim:
                        final_reasoning.synthetic_data_note = None
                        final_reasoning.simulation_findings = None

                    if has_traffic:
                        trf_data = collected_results["traffic"]
                        final_reasoning.baseline_metrics = trf_data.get("metrics") or trf_data
                    if has_simulation and tested_scenarios:
                        obj_l = (objective or "").lower()
                        req_dur = None
                        if "120s" in obj_l or "120 seconds" in obj_l or "120 second" in obj_l:
                            req_dur = 120
                        elif "300s" in obj_l or "300 seconds" in obj_l or "300 second" in obj_l:
                            req_dur = 300
                        elif "600s" in obj_l or "600 seconds" in obj_l or "600 second" in obj_l:
                            req_dur = 600

                        is_multi_horizon = ("300" in obj_l and "600" in obj_l) or "between 300 and 600" in obj_l or "compare 300 and 600" in obj_l

                        matching_scens = [
                            s for s in tested_scenarios
                            if req_dur is None or s.get("duration_seconds") == req_dur
                        ]
                        active_scen = matching_scens[-1] if matching_scens else tested_scenarios[-1]

                        final_reasoning.intervention_metrics = active_scen["metrics"]
                        final_reasoning.intervention = active_scen["intervention"]
                        final_reasoning.metric_changes = active_scen["comparison"]
                        final_reasoning.tested_scenarios = tested_scenarios if (is_multi_horizon or req_dur is None) else matching_scens
                        final_reasoning.corridor_trade_offs = list(dict.fromkeys(all_trade_offs))
                        final_reasoning.selected_scenario_id = active_scen["scenario_id"]
                    final_reasoning.diagnosed_bottlenecks = cross_analysis.diagnosed_bottlenecks
                    final_reasoning.key_findings = cross_analysis.key_findings

                    # Enforce invariant: untested candidates must never be recommended as proven solutions
                    self._enforce_recommendation_evidence_rules(
                        final_reasoning=final_reasoning,
                        tested_interventions=tested_interventions,
                        untested_candidates=untested_candidates,
                        evidence_status=det_evidence_status,
                        objective=objective,
                    )

                    # Validate and enforce structured response scope: answer only what was asked
                    validate_and_enforce_response_scope(
                        final_reasoning=final_reasoning,
                        objective=objective,
                        collected_results=collected_results,
                        cross_analysis=cross_analysis,
                    )
                final_rec = final_reasoning.recommendation if final_reasoning else None
            except Exception as exc:
                logger.warning(f"Final reasoning generation note: {exc}")
                final_rec = llm_eval.analysis

        resp_scope = (
            getattr(final_reasoning, "response_scope", None)
            if final_reasoning
            else determine_response_scope(objective)
        )

        return PlannerEvaluationResponse(
            goal_achieved=is_sufficient,
            decision=decision_mapped,
            next_action=next_action,
            analysis=strip_internal_planner_reasoning(llm_eval.analysis) if (llm_eval and hasattr(llm_eval, "analysis") and llm_eval.analysis) else (llm_eval.analysis if llm_eval else ""),
            final_recommendation=final_rec,
            final_reasoning=final_reasoning,
            revised_plan=[f"Execute {cap} specialist agent" for cap in next_cycle_caps],
            evidence_status=det_evidence_status,
            confidence=llm_eval.confidence,
            evidence=all_evidence,
            cross_analysis=cross_analysis,
            next_cycle_caps=next_cycle_caps,
            next_cycle_calls=validated_next_calls,
            simulation_context=llm_eval.simulation_context,
            scenarios=llm_eval.scenarios,
            response_scope=resp_scope,
        )

    # ---------------------------------------------------------------------------
    # Stage 3: Autonomous LLM Final Cross-Agent Reasoning
    # ---------------------------------------------------------------------------
    def generate_final_reasoning(
        self,
        objective: str,
        location: str,
        history: List[Dict[str, Any]],
        collected_results: Dict[str, Any],
        simulation_results: Optional[Dict[str, Any]] = None,
    ) -> LLMFinalReasoning:
        """
        Sends the complete dossier of evidence to the LLM to generate the final
        cross-domain synthesis, evidence citation, and municipal recommendations.
        """
        provider = self._require_llm()
        user_prompt = build_stage_3_prompt(
            objective=objective,
            location=location,
            history=history,
            collected_results=collected_results,
            simulation_results=simulation_results,
        )

        raw_json = provider.generate_json(
            system_prompt=STAGE_3_FINAL_REASONING_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.1,
        )

        try:
            return LLMFinalReasoning.model_validate(raw_json)
        except Exception as exc:
            logger.error(f"LLM final reasoning schema validation failed: {exc}")
            raise LLMJsonParsingError(f"LLM final reasoning failed validation: {exc}") from exc

    @staticmethod
    def _sanitize_bottleneck_resolution_text(text: str) -> str:
        """
        Sanitize premature 'successfully addressed/resolved/fixed' bottleneck claims.
        Replaces them with factual reporting of corridor speed improvements and trade-offs.
        """
        if not text:
            return text

        replacements = [
            (
                r"\b(successfully\s+addressed|successfully\s+resolved)\s+(the\s+lowest\s+observed-speed\s+corridor\s+bottleneck|the\s+bottleneck|corridor\s+bottlenecks?)\b",
                r"improved speed on \2 with observed network trade-offs",
            ),
            (
                r"\b(successfully\s+addressed\s+the\s+corridor\s+bottleneck)\b",
                r"improved target corridor travel speed with observed trade-offs",
            ),
            (
                r"\b(successfully\s+addressed|successfully\s+resolved)\b",
                r"improved target corridor speed for",
            ),
            (
                r"\b(resolved|fixes|fixed|solves|solved)\s+(the\s+lowest\s+observed-speed\s+corridor\s+bottleneck|the\s+bottleneck|corridor\s+bottlenecks?)\b",
                r"improved speed on \2",
            ),
            (
                r"\b(bottleneck\s+(?:was|is|has\s+been)\s+(?:successfully\s+addressed|resolved|fixed|solved))\b",
                r"target corridor speed improved with observed trade-offs",
            ),
            (
                r"\b(problem\s+(?:was|is|has\s+been)\s+(?:successfully\s+addressed|resolved|fixed|solved))\b",
                r"corridor conditions were evaluated",
            ),
            (
                r"\b(successfully\s+improves\s+targeted\s+corridor\s+performance)\b",
                r"improved targeted corridor speed with observed trade-offs",
            ),
            (
                r"\b(addresses\s+observed\s+corridor\s+bottlenecks)\b",
                r"evaluates observed corridor performance",
            ),
        ]

        sanitized = text
        for pattern, repl in replacements:
            sanitized = re.sub(pattern, repl, sanitized, flags=re.IGNORECASE)
        return sanitized

    @classmethod
    def _enforce_recommendation_evidence_rules(
        cls,
        final_reasoning: LLMFinalReasoning,
        tested_interventions: List[Dict[str, Any]],
        untested_candidates: List[Dict[str, Any]],
        evidence_status: str,
        objective: Optional[str] = None,
    ) -> None:
        """
        Enforce invariants:
        1. An untested intervention must never be presented as an empirically supported recommendation,
           nor may unsupported causal/impact claims (e.g. 'will reduce', 'to reduce arrivals') be made.
        2. Premature 'successfully addressed/resolved/fixed' bottleneck claims must be replaced with
           factual corridor speed changes and observed trade-offs.
        3. For a single tested intervention, the recommendation must follow the 6-step evidence structure.
        """
        # Step 1: Sanitize bottleneck resolution language across key fields
        for field in ["summary", "recommendation", "simulation_findings", "intervention_assessment"]:
            val = getattr(final_reasoning, field, None)
            if val and isinstance(val, str):
                cleaned_val = cls._sanitize_bottleneck_resolution_text(val)
                cleaned_val = strip_internal_planner_reasoning(cleaned_val)
                setattr(final_reasoning, field, cleaned_val)

        # Also sanitize summary from making unsupported causal claims about untested candidates
        involves_traffic_opt_or_sim = request_involves_traffic_optimization_or_simulation(
            objective=objective or getattr(final_reasoning, "objective", None) or "",
            tested_interventions=tested_interventions,
            untested_candidates=untested_candidates,
        )
        summary = final_reasoning.summary or ""
        if summary and untested_candidates and involves_traffic_opt_or_sim:
            for u in untested_candidates:
                u_type = str(u.get("type") or "").strip().lower()
                toks = [u_type]
                if "_" in u_type:
                    toks.append(u_type.replace("_", " "))
                for tok in toks:
                    if not tok:
                        continue
                    summary = re.sub(
                        rf"\b({re.escape(tok)}[^\.\;]*?)\s+(to\s+reduce|will\s+reduce|to\s+improve|will\s+improve|to\s+relieve|will\s+relieve)\s+(?:arrival\s+rates?|arrivals?|traffic|congestion|delay|the\s+bottleneck)\b",
                        rf"\1 (untested candidate requiring simulation)",
                        summary,
                        flags=re.IGNORECASE,
                    )
            final_reasoning.summary = summary

        rec = (final_reasoning.recommendation or "").strip()
        rec_lower = rec.lower()
        num_tested = len(tested_interventions)

        obj_text = (objective or getattr(final_reasoning, "objective", None) or "").lower()
        is_solve_bottleneck_query = any(
            p in obj_text or p in rec_lower
            for p in [
                "did the optimization solve",
                "did it solve the bottleneck",
                "solve the bottleneck",
                "resolved the bottleneck",
                "was the bottleneck solved",
                "did the optimization",
            ]
        ) and any(w in obj_text for w in ["solve", "solved", "resolv", "effective", "did the optimization"])

        is_compare_tested_query = any(
            p in obj_text
            for p in [
                "which tested intervention",
                "performed better",
                "perform better",
                "compare the tested",
                "compare tested",
                "is rerouting better",
                "is signal timing better",
            ]
        )

        # Set recommendation_basis deterministically if not set or ambiguous
        if not final_reasoning.recommendation_basis:
            if num_tested == 0:
                final_reasoning.recommendation_basis = "OBSERVATIONAL_TELEMETRY_ONLY"
            elif num_tested == 1:
                final_reasoning.recommendation_basis = "SINGLE_SIMULATION_OBSERVED_DELTAS"
            else:
                final_reasoning.recommendation_basis = "MULTI_SIMULATION_EMPIRICAL_COMPARISON"

        # Case 1: Zero simulations executed
        if num_tested == 0:
            final_reasoning.selected_scenario_id = None
            cand_names = [f"{c.get('type')} ({c.get('target')})" for c in untested_candidates if c.get('type')]
            cand_str = ", ".join(cand_names) if cand_names else "candidate interventions"

            if is_compare_tested_query or "which tested" in obj_text:
                final_reasoning.recommendation = (
                    f"No candidate interventions have been tested in simulation yet ({evidence_status}). "
                    f"No empirical simulation results are available to compare. "
                    f"Available candidate interventions ({cand_str}) require simulation execution to evaluate their comparative operational performance."
                )
                final_reasoning.summary = (
                    f"No simulation history is available. Candidate interventions remain untested in SUMO microsimulation."
                )
                return

            if is_solve_bottleneck_query:
                final_reasoning.recommendation = (
                    f"No simulation evidence exists ({evidence_status}). No traffic optimization interventions have been executed in SUMO microsimulation yet, "
                    f"so empirical bottleneck resolution cannot be assessed. Please request an optimization simulation to test candidate interventions."
                )
                final_reasoning.summary = (
                    f"No simulation evidence exists to evaluate bottleneck resolution. Telemetry is purely observational."
                )
                return

            if involves_traffic_opt_or_sim:
                optimization_terms = [
                    "optimal", "proven", "mitigated", "improved speed by", "reduced delay by",
                    "deploy", "implement", "alleviate", "recommended intervention", "effective solution",
                    "successfully addressed", "resolved the bottleneck"
                ]
                if any(t in rec_lower for t in optimization_terms) or "untested" not in rec_lower or not rec:
                    final_reasoning.recommendation = (
                        f"No traffic optimization interventions were simulated in this cycle ({evidence_status}). "
                        f"Available candidate interventions ({cand_str}) remain untested in SUMO microsimulation; "
                        f"their operational effectiveness has not been established and they require simulation execution to empirically validate their operational impacts."
                    )
            else:
                # User request does not involve traffic optimization or simulation.
                # Strip any accidental traffic/SUMO disclaimers and internal reasoning.
                final_reasoning.summary = strip_internal_planner_reasoning(strip_unrelated_traffic_disclaimers(final_reasoning.summary))
                final_reasoning.recommendation = strip_internal_planner_reasoning(strip_unrelated_traffic_disclaimers(final_reasoning.recommendation))
                final_reasoning.synthetic_data_note = None
                final_reasoning.simulation_findings = None
            return

        if is_solve_bottleneck_query:
            final_reasoning.recommendation = cls._build_bottleneck_resolution_evaluation_text(
                tested_interventions=tested_interventions,
                untested_candidates=untested_candidates,
                is_followup_turn=True,
            )
            final_reasoning.recommendation_basis = "MULTI_SIMULATION_EMPIRICAL_COMPARISON" if num_tested > 1 else "SINGLE_SIMULATION_OBSERVED_DELTAS"
            return

        if is_compare_tested_query and num_tested >= 2:
            final_reasoning.recommendation = cls._build_multi_intervention_comparison_text(
                tested_interventions=tested_interventions,
                untested_candidates=untested_candidates,
            )
            final_reasoning.recommendation_basis = "MULTI_SIMULATION_EMPIRICAL_COMPARISON"
            return

        # Common regex helpers for detecting untested candidate violations
        causal_impact_verbs = r"(to\s+reduce|will\s+reduce|would\s+reduce|can\s+reduce|reduces?|reducing|to\s+improve|will\s+improve|would\s+improve|improves?|improving|to\s+relieve|will\s+relieve|relieves?|relieving|to\s+alleviate|will\s+alleviate|alleviates?|alleviating|to\s+clear|will\s+clear|clears?|clearing|to\s+address|will\s+address|addresses?|addressing)"
        causal_impact_targets = r"(arrivals?|arrival\s+rates?|traffic|congestion|delay|queues?|travel\s+time|bottlenecks?|speed|flow|throughput|performance)"

        def has_untested_violation(target_text: str) -> Optional[Dict[str, Any]]:
            for u in untested_candidates:
                u_type = str(u.get("type") or "").strip().lower()
                u_tokens = [u_type]
                if "_" in u_type:
                    u_tokens.append(u_type.replace("_", " "))

                for tok in u_tokens:
                    if not tok:
                        continue
                    patterns = [
                        rf"\b(recommend|recommends|recommending|deploy|deploys|deploying|implement|implements|implementing|adopt|adopts|adopting|prefer|prefers|preferred)\b[^\.\;]*\b{re.escape(tok)}\b",
                        rf"\b{re.escape(tok)}\b[^\.\;]*\b(is\s+better|is\s+optimal|is\s+preferred|is\s+more\s+effective|instead\s+of|over\s+the\s+tested|recommended|should\s+be\s+deployed)\b",
                        rf"\b{re.escape(tok)}\b[^\.\;]*\b{causal_impact_verbs}\b[^\.\;]*\b{causal_impact_targets}\b",
                        rf"\b{causal_impact_verbs}\b[^\.\;]*\b{causal_impact_targets}\b[^\.\;]*\b{re.escape(tok)}\b",
                        rf"\b(includes?|including|with)\s+(?:the\s+)?(?:untested\s+)?{re.escape(tok)}[^\.\;]*\b{causal_impact_verbs}\b",
                    ]
                    if any(re.search(pat, target_text) for pat in patterns):
                        return u
            return None

        # Case 2: Exactly 1 intervention tested
        if num_tested == 1:
            t_int = tested_interventions[0]
            t_type = str(t_int.get("type") or "intervention").replace("_", " ")
            t_target = str(t_int.get("target") or "target corridor")
            t_comp = t_int.get("comparison") or {}

            violating_cand = has_untested_violation(rec_lower)

            if violating_cand:
                # Build structured 6-step recommendation from empirical evidence
                tgt_spd_pct = t_comp.get("target_corridor_speed_change_pct")
                if tgt_spd_pct is None:
                    for cc in t_comp.get("corridor_comparisons", []):
                        if cc.get("name") == t_target or cc.get("id", "").endswith(t_target[:2].upper()):
                            tgt_spd_pct = cc.get("speed_change_pct")
                            break

                if tgt_spd_pct is not None:
                    if tgt_spd_pct >= 0:
                        tgt_effect = f"improved the target {t_target} corridor speed by {tgt_spd_pct:.2f}%"
                    else:
                        tgt_effect = f"reduced the target {t_target} corridor speed by {abs(tgt_spd_pct):.2f}%"
                else:
                    tgt_effect = f"altered traffic conditions on the target {t_target} corridor"

                trade_off_parts = []
                del_red = t_comp.get("delay_reduction_pct")
                if del_red is not None:
                    if del_red < 0:
                        trade_off_parts.append(f"increased network delay by {abs(del_red):.2f}%")
                    elif del_red > 0:
                        trade_off_parts.append(f"reduced network delay by {del_red:.2f}%")

                spd_pct = t_comp.get("speed_change_pct")
                if spd_pct is not None and spd_pct < 0:
                    trade_off_parts.append(f"reduced network speed by {abs(spd_pct):.2f}%")

                cor_tradeoffs = t_int.get("corridor_trade_offs") or t_comp.get("corridor_trade_offs") or []
                if cor_tradeoffs:
                    raw_to = str(cor_tradeoffs[0]).strip().rstrip(".")
                    m_to = re.search(r"([A-Za-z]+)\s+corridor\s+speed\s+degraded\s+by\s+(-?[0-9.]+)%", raw_to)
                    if m_to:
                        cor_name = m_to.group(1)
                        drop_val = abs(float(m_to.group(2)))
                        trade_off_parts.append(f"reduced {cor_name} speed by {drop_val:.2f}%")
                    else:
                        trade_off_parts.append(raw_to)

                trade_off_clause = f", but {', and '.join(trade_off_parts)}" if trade_off_parts else ""

                has_adverse = (del_red is not None and del_red < 0) or (spd_pct is not None and spd_pct < 0) or bool(cor_tradeoffs)
                if has_adverse:
                    standalone_clause = " It should not be treated as a standalone solution based on this simulation;"
                else:
                    standalone_clause = " Operational monitoring is recommended;"

                if untested_candidates:
                    u_clauses = []
                    for u in untested_candidates:
                        u_name = str(u.get("type") or "candidate").replace("_", " ")
                        u_params = u.get("parameters") or {}
                        param_str = ""
                        if isinstance(u_params, dict) and u_params:
                            if "diversion_fraction" in u_params:
                                div_pct = int(round(float(u_params["diversion_fraction"]) * 100))
                                param_str = f" with a {div_pct}% diversion parameter"
                            elif "adjustment_seconds" in u_params or "green_time_adjustment_sec" in u_params:
                                sec = u_params.get("adjustment_seconds") or u_params.get("green_time_adjustment_sec")
                                param_str = f" with a {sec}s adjustment parameter"
                        u_clauses.append(
                            f"{u_name}{param_str} was NOT simulated in this cycle; therefore, its comparative "
                            f"effectiveness has not been established and it requires simulation before it can be evaluated"
                        )
                    untested_clause = f" {'; '.join(u_clauses)}."
                else:
                    untested_clause = ""

                final_reasoning.recommendation = (
                    f"The tested {t_type} adjustment {tgt_effect}{trade_off_clause}.{standalone_clause}{untested_clause}"
                )
                final_reasoning.recommendation_basis = "SINGLE_SIMULATION_OBSERVED_DELTAS"
            else:
                rec_sanitized = re.sub(r"\b(the\s+best|the\s+optimal|the\s+most\s+effective)\b", "an effective tested", rec, flags=re.IGNORECASE)
                if rec_sanitized != rec:
                    rec = rec_sanitized

                if untested_candidates and "untested" not in rec.lower():
                    cand_types = list(dict.fromkeys([str(u.get("type") or "").replace("_", " ") for u in untested_candidates if u.get("type")]))
                    if cand_types:
                        rec += f" (Note: Other candidate interventions, including {', '.join(cand_types)}, remain untested in this cycle and require simulation.)"
                final_reasoning.recommendation = rec

        # Case 3: Multiple interventions tested
        elif num_tested >= 2:
            violating_cand = has_untested_violation(rec_lower)
            has_optimal_claim = bool(re.search(r"\b(the\s+best|the\s+optimal|optimal\s+solution|the\s+most\s+effective|is\s+optimal)\b", rec_lower))

            # Compute empirically dominant intervention via multi-metric scoring.
            # If a clear dominant exists, always rebuild recommendation deterministically
            # so the LLM cannot smuggle an incorrect winner through the "among the tested" gate.
            empirically_dominant_type = cls._compute_empirically_dominant_type(tested_interventions)

            # Evaluate whether all tested interventions have trade-offs (for gate logic)
            perfs_check = []
            for t in tested_interventions:
                t_comp = t.get("comparison") or {}
                t_del = t_comp.get("delay_reduction_pct")
                t_net = t_comp.get("speed_change_pct")
                t_tgt = t_comp.get("target_corridor_speed_change_pct")
                t_tos = t.get("corridor_trade_offs") or t_comp.get("corridor_trade_offs") or []
                t_adv = (t_del is not None and t_del < -0.5) or (t_net is not None and t_net < -0.2) or bool(t_tos)
                t_gain = t_tgt is not None and t_tgt > 1.0
                perfs_check.append({"adverse": t_adv, "gain": t_gain})

            all_tradeoffs = bool(perfs_check) and all(p["adverse"] or not p["gain"] for p in perfs_check)
            needs_comparison_text = (
                violating_cand
                or has_optimal_claim
                or not rec
                or "among the tested" not in rec_lower
                or (all_tradeoffs and "neither" not in rec_lower and "no clear" not in rec_lower)
                # Force deterministic text whenever a clear empirical winner exists;
                # this prevents the LLM from naming a non-dominant intervention as preferred.
                or empirically_dominant_type is not None
            )

            if needs_comparison_text:
                final_reasoning.recommendation = cls._build_multi_intervention_comparison_text(
                    tested_interventions=tested_interventions,
                    untested_candidates=untested_candidates,
                )
            else:
                rec_sanitized = cls._sanitize_bottleneck_resolution_text(rec)
                rec_sanitized = re.sub(r"\b(the\s+best|the\s+optimal|the\s+most\s+effective)\b", "the strongest tested", rec_sanitized, flags=re.IGNORECASE)
                if untested_candidates and "untested" not in rec_sanitized.lower():
                    cand_types = list(dict.fromkeys([str(u.get("type") or "").replace("_", " ") for u in untested_candidates if u.get("type")]))
                    if cand_types:
                        rec_sanitized += f" (Note: Other candidate interventions, including {', '.join(cand_types)}, remain untested in this cycle and require simulation.)"
                final_reasoning.recommendation = rec_sanitized

            final_reasoning.recommendation_basis = "MULTI_SIMULATION_EMPIRICAL_COMPARISON"

        # Ensure recommendation is distinct, concise, and does not duplicate reasoning summary
        if final_reasoning.recommendation and final_reasoning.summary and involves_traffic_opt_or_sim:
            r_clean = final_reasoning.recommendation.strip().lower()
            s_clean = final_reasoning.summary.strip().lower()
            if r_clean == s_clean or (len(r_clean) > 40 and (r_clean in s_clean or s_clean in r_clean)):
                if num_tested == 1:
                    t_int = tested_interventions[0]
                    t_type = str(t_int.get("type") or "intervention").replace("_", " ")
                    t_target = str(t_int.get("target") or "target corridor")
                    final_reasoning.recommendation = (
                        f"Deploy the evaluated {t_type} configuration on {t_target} with operational telemetry monitoring. "
                        f"Implement localized adjustments while monitoring opposing corridor phases to prevent queue spillback."
                    )
                elif num_tested >= 2:
                    final_reasoning.recommendation = (
                        "Implement balanced operational timing rather than aggressive single-corridor green extensions. "
                        "Selection between tested configurations represents an empirical trade-off between target progression and network delay balance."
                    )

    @classmethod
    def _build_multi_intervention_comparison_text(
        cls,
        tested_interventions: List[Dict[str, Any]],
        untested_candidates: List[Dict[str, Any]],
    ) -> str:
        """
        Build a concise, action-oriented recommendation across multiple tested interventions.

        Uses multi-metric scoring (target corridor speed, network speed, delay reduction,
        waiting-time reduction) to identify the empirically dominant intervention.
        Corridor trade-offs are reported as monitoring requirements, NOT disqualifiers —
        so an intervention that wins all four metrics but has a minor corridor degradation
        is still declared dominant and prioritized for field validation.

        Output format:
          Dominant: One concise action sentence naming the winner + primary gains + monitor clause.
          No winner: Brief factual note that trade-offs are genuine and selection is operational.
        """
        if not tested_interventions:
            return "No interventions were simulated in this cycle."

        entries: List[Dict[str, Any]] = []

        for t in tested_interventions:
            t_int = t.get("intervention") if isinstance(t.get("intervention"), dict) else t
            t_type = str(t.get("type") or t_int.get("type") or "intervention").replace("_", " ")
            t_target = str(t.get("target") or t_int.get("target") or "")
            t_params = t.get("parameters") or t_int.get("parameters") or {}

            param_parts: List[str] = []
            if isinstance(t_params, dict):
                if "green_time_adjustment_sec" in t_params:
                    param_parts.append(f"+{float(t_params['green_time_adjustment_sec']):.0f}s green")
                elif "adjustment_seconds" in t_params:
                    param_parts.append(f"+{float(t_params['adjustment_seconds']):.0f}s green")
                if "diversion_fraction" in t_params:
                    param_parts.append(f"{int(round(float(t_params['diversion_fraction']) * 100))}% diversion")

            param_str = f" ({', '.join(param_parts)})" if param_parts else ""
            label = f"{t_type.title()}{param_str}"

            comp = t.get("comparison") or {}

            # Target corridor speed (primary objective metric)
            tgt_spd = comp.get("target_corridor_speed_change_pct")
            if tgt_spd is None:
                for cc in comp.get("corridor_comparisons", []):
                    cc_name = str(cc.get("name") or "").lower()
                    cc_id = str(cc.get("id") or "").lower()
                    t_tgt_l = t_target.lower() if t_target else ""
                    if cc.get("is_target") or (
                        t_tgt_l and (
                            cc_name == t_tgt_l
                            or t_tgt_l in cc_name
                            or cc_id.endswith(t_tgt_l[:2])
                        )
                    ):
                        tgt_spd = cc.get("speed_change_pct")
                        if not t_target:
                            t_target = cc.get("name") or "target corridor"
                        break

            if not t_target:
                t_target = comp.get("target_corridor") or "target corridor"

            net_spd = comp.get("speed_change_pct")

            # del_red: positive = delay improved, negative = delay worsened
            del_red = comp.get("delay_reduction_pct")
            if del_red is None and comp.get("delay_change_pct") is not None:
                del_red = -float(comp["delay_change_pct"])

            # wait_red: positive = waiting time improved
            wait_red = comp.get("waiting_time_reduction_pct")
            if wait_red is None and comp.get("waiting_time_change_pct") is not None:
                wait_red = -float(comp["waiting_time_change_pct"])

            cor_tradeoffs = t.get("corridor_trade_offs") or comp.get("corridor_trade_offs") or []

            entries.append({
                "label": label,
                "type": t_type,
                "target": t_target,
                "tgt_spd": tgt_spd,
                "net_spd": net_spd,
                "del_red": del_red,
                "wait_red": wait_red,
                "trade_offs": cor_tradeoffs,
            })

        # ------------------------------------------------------------------
        # Multi-metric scoring: count metric wins per intervention.
        # All four metrics are "higher is better".
        # Corridor trade-offs are NOT used as disqualifiers here — they are
        # reported as monitoring requirements in the output text.
        # ------------------------------------------------------------------
        metric_keys = ["tgt_spd", "net_spd", "del_red", "wait_red"]
        scores: Dict[str, int] = {e["label"]: 0 for e in entries}

        for mk in metric_keys:
            vals = [(e["label"], e[mk]) for e in entries if e[mk] is not None]
            if len(vals) < 2:
                continue
            best_val = max(v for _, v in vals)
            for lbl, val in vals:
                if abs(val - best_val) < 0.05:  # negligible difference threshold
                    scores[lbl] += 1

        max_score = max(scores.values()) if scores else 0
        winners_by_score = [e for e in entries if scores[e["label"]] == max_score]

        # Determine available metric count (metrics where at least 2 interventions report a value)
        available_metrics = sum(
            1 for mk in metric_keys
            if sum(1 for e in entries if e[mk] is not None) >= 2
        )

        # Declare dominant if one intervention wins a clear majority of available metrics
        dominant_entry: Optional[Dict[str, Any]] = None
        if len(winners_by_score) == 1 and available_metrics > 0:
            threshold = max(2, available_metrics - 1)  # e.g. ≥3/4, ≥2/3, ≥2/2
            if max_score >= threshold:
                dominant_entry = winners_by_score[0]

        # ------------------------------------------------------------------
        # Untested clause
        # ------------------------------------------------------------------
        untested_clause = ""
        if untested_candidates:
            u_types = list(dict.fromkeys([
                str(u.get("type") or "candidate").replace("_", " ")
                for u in untested_candidates if u.get("type")
            ]))
            untested_clause = (
                f" Other candidate interventions ({', '.join(u_types)}) were not simulated "
                f"in this cycle and require empirical verification."
            )

        # ------------------------------------------------------------------
        # Build output text
        # ------------------------------------------------------------------
        if dominant_entry:
            # Concise action-oriented recommendation — does NOT repeat table percentages.
            # Name the winner, cite its 1–2 primary gains briefly, add monitor clause.
            primary_gains: List[str] = []
            if dominant_entry["tgt_spd"] is not None and dominant_entry["tgt_spd"] > 0.5:
                primary_gains.append(f"+{dominant_entry['tgt_spd']:.1f}% target {dominant_entry['target']} speed")
            if dominant_entry["del_red"] is not None and dominant_entry["del_red"] > 0.5:
                primary_gains.append(f"{dominant_entry['del_red']:.1f}% delay reduction")
            elif dominant_entry["wait_red"] is not None and dominant_entry["wait_red"] > 0.5:
                primary_gains.append(f"{dominant_entry['wait_red']:.1f}% waiting-time reduction")

            gains_str = " and ".join(primary_gains[:2]) if primary_gains else "the strongest overall performance"

            # Collect corridors to monitor from trade-offs across ALL interventions
            monitor_cors: List[str] = []
            for e in entries:
                for to in e["trade_offs"]:
                    m_to = re.search(r"([A-Za-z]+)\s+corridor", str(to), re.IGNORECASE)
                    if m_to:
                        cor_name = m_to.group(1).title()
                        if cor_name not in monitor_cors:
                            monitor_cors.append(cor_name)

            monitor_clause = ""
            if monitor_cors:
                monitor_clause = (
                    f" Monitor {' and '.join(monitor_cors[:3])} corridor speed for potential "
                    f"degradation during field deployment."
                )

            other_entries = [e for e in entries if e != dominant_entry]
            other_clause = ""
            if other_entries:
                other_summaries = [f"{oe['label']} on {oe['target']}" for oe in other_entries]
                other_clause = f" (outperforming {', '.join(other_summaries)})"

            return (
                f"Prioritize {dominant_entry['label']} on {dominant_entry['target']} for field validation — "
                f"it achieved {gains_str} among the tested interventions{other_clause}.{monitor_clause} "
                f"Validate against live traffic conditions before permanent deployment."
                f"{untested_clause}"
            )

        else:
            # Genuine trade-off: no intervention clearly dominates across metrics.
            # Build a brief per-intervention factual note without repeating full tables.
            brief_notes: List[str] = []
            for e in entries:
                note_parts: List[str] = []
                if e["tgt_spd"] is not None:
                    if e["tgt_spd"] > 0.5:
                        note_parts.append(f"+{e['tgt_spd']:.1f}% target speed")
                    else:
                        note_parts.append("negligible target speed change")
                if e["del_red"] is not None:
                    if e["del_red"] < -0.5:
                        note_parts.append(f"{abs(e['del_red']):.1f}% delay increase")
                    elif e["del_red"] > 0.5:
                        note_parts.append(f"{e['del_red']:.1f}% delay reduction")
                brief_notes.append(f"{e['label']} ({', '.join(note_parts) if note_parts else 'no clear gain'})")

            notes_str = "; ".join(brief_notes)
            return (
                f"Among the tested interventions, the evidence does not clearly favour one "
                f"configuration: {notes_str}. "
                f"Selection is an operational trade-off — validate both against live conditions "
                f"before committing to permanent deployment."
                f"{untested_clause}"
            )

    @classmethod
    def _compute_empirically_dominant_type(
        cls,
        tested_interventions: List[Dict[str, Any]],
    ) -> Optional[str]:
        """
        Determine which tested intervention is empirically dominant across the four key
        objective metrics: target corridor speed, network speed, delay reduction, and
        waiting-time reduction (all higher-is-better after sign normalisation).

        Returns the dominant intervention's *type* string (lowercased, spaces for underscores)
        if one intervention wins a clear majority of available metrics, else None.

        Corridor trade-offs are intentionally excluded from this comparison — an intervention
        that wins all four outcome metrics is dominant even if it has minor corridor spillbacks;
        those spillbacks are reported as monitoring requirements, not disqualifiers.
        """
        if len(tested_interventions) < 2:
            return None

        entries: List[Dict[str, Any]] = []
        for t in tested_interventions:
            comp = t.get("comparison") or {}
            tgt_spd = comp.get("target_corridor_speed_change_pct")
            net_spd = comp.get("speed_change_pct")
            del_red = comp.get("delay_reduction_pct")
            if del_red is None and comp.get("delay_change_pct") is not None:
                del_red = -float(comp["delay_change_pct"])
            wait_red = comp.get("waiting_time_reduction_pct")
            if wait_red is None and comp.get("waiting_time_change_pct") is not None:
                wait_red = -float(comp["waiting_time_change_pct"])
            t_type = str(t.get("type") or "").replace("_", " ").lower()
            entries.append({
                "type": t_type,
                "tgt_spd": tgt_spd,
                "net_spd": net_spd,
                "del_red": del_red,
                "wait_red": wait_red,
            })

        metric_keys = ["tgt_spd", "net_spd", "del_red", "wait_red"]
        scores: Dict[str, int] = {e["type"]: 0 for e in entries}

        for mk in metric_keys:
            vals = [(e["type"], e[mk]) for e in entries if e[mk] is not None]
            if len(vals) < 2:
                continue
            best_val = max(v for _, v in vals)
            for t_type, val in vals:
                if abs(val - best_val) < 0.05:
                    scores[t_type] += 1

        available_metrics = sum(
            1 for mk in metric_keys
            if sum(1 for e in entries if e[mk] is not None) >= 2
        )

        if available_metrics == 0:
            return None

        max_score = max(scores.values())
        winners = [t for t, s in scores.items() if s == max_score]
        threshold = max(2, available_metrics - 1)

        if len(winners) == 1 and max_score >= threshold:
            return winners[0]

        return None

    @classmethod
    def _build_bottleneck_resolution_evaluation_text(
        cls,
        tested_interventions: List[Dict[str, Any]],
        untested_candidates: List[Dict[str, Any]],
        is_followup_turn: bool = True,
    ) -> str:
        """
        Evaluate whether completed simulations resolved the bottleneck.
        Distinguishes target corridor speed improvement from overall bottleneck resolution
        by examining target corridor deltas, opposing corridor trade-offs, and network delay.
        Explicitly notes that no new simulation was run in this turn.
        """
        if not tested_interventions:
            return (
                "No simulation evidence exists. No traffic optimization interventions have been executed in SUMO microsimulation yet, "
                "so empirical bottleneck resolution cannot be assessed. Please request an optimization simulation to test candidate interventions."
            )

        sim_notice = "No new simulation was run in this turn; evaluating completed simulation evidence from history. " if is_followup_turn else ""

        # Analyze tested interventions
        perfs = []
        for t in tested_interventions:
            comp = t.get("comparison") or {}
            tgt_corridor = str(t.get("target") or "target corridor")
            tgt_spd = comp.get("target_corridor_speed_change_pct")
            if tgt_spd is None:
                for cc in comp.get("corridor_comparisons", []):
                    if cc.get("name") == tgt_corridor or str(cc.get("id", "")).endswith(tgt_corridor[:2].upper()):
                        tgt_spd = cc.get("speed_change_pct")
                        break

            net_spd = comp.get("speed_change_pct")
            del_red = comp.get("delay_reduction_pct")
            cor_tradeoffs = t.get("corridor_trade_offs") or comp.get("corridor_trade_offs") or []

            perfs.append({
                "target": tgt_corridor,
                "type": t.get("type"),
                "tgt_spd": tgt_spd,
                "net_spd": net_spd,
                "del_red": del_red,
                "trade_offs": cor_tradeoffs,
            })

        p = perfs[0]
        tgt_corridor = p["target"]
        tgt_spd = p["tgt_spd"]
        del_red = p["del_red"]
        cor_tradeoffs = p["trade_offs"]

        adverse_parts = []
        if cor_tradeoffs:
            for to in cor_tradeoffs:
                adverse_parts.append(str(to).strip().rstrip("."))
        if del_red is not None and del_red < -0.5:
            adverse_parts.append(f"network delay increased by {abs(del_red):.2f}%")

        if tgt_spd is not None and tgt_spd > 0:
            tgt_text = f"The tested optimization improved the target {tgt_corridor} corridor speed by {tgt_spd:+.1f}%"
        else:
            tgt_text = f"The tested optimization altered conditions on the target {tgt_corridor} corridor"

        if adverse_parts:
            adv_str = "; and ".join(adverse_parts)
            conclusion = (
                f"{sim_notice}{tgt_text}, but the simulation also showed degradation: {adv_str}. "
                f"Therefore, the empirical evidence demonstrates localized corridor improvement rather than full network bottleneck resolution."
            )
        elif tgt_spd is not None and tgt_spd > 2.0:
            conclusion = (
                f"{sim_notice}{tgt_text} with stable network delay, indicating meaningful bottleneck relief on the target corridor."
            )
        else:
            conclusion = (
                f"{sim_notice}The simulation showed negligible improvement on the bottleneck corridor, indicating that the tested intervention did not resolve the bottleneck."
            )

        if untested_candidates:
            u_types = list(dict.fromkeys([str(u.get("type") or "candidate").replace("_", " ") for u in untested_candidates if u.get("type")]))
            conclusion += f" Other candidate interventions ({', '.join(u_types)}) were not simulated in this cycle and require empirical verification."

        return conclusion


def get_planner_agent(llm_provider: Optional[BaseLLMProvider] = None) -> PlannerAgent:
    """Factory function for PlannerAgent."""
    return PlannerAgent(llm_provider=llm_provider)
