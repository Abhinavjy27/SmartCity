"""
Structured Response Scope Determination, Validation, and Scoped Output Enforcement
for the LLM Planner Agent.

Ensures the Planner answers the user's actual question directly and exposes only
the information needed to satisfy that question, while preserving full internal
specialist evidence (telemetry, bottlenecks, trade-offs, candidate interventions).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from backend.agents.planner_agent.schema import ResponseScope

logger = logging.getLogger("planner_agent.scope")


def strip_unrelated_traffic_disclaimers(text: str) -> str:
    """
    Remove traffic optimization, baseline, or SUMO simulation disclaimers
    from non-traffic or non-simulation responses.
    Preserves legitimate domain evidence, findings, and advisories.
    """
    if not text:
        return text

    patterns = [
        r"No traffic optimization interventions were simulated in this cycle\s*(?:\([^)]*\))?\.?\s*",
        r"Available candidate interventions\s*(?:\([^)]*\))?\s*remain untested in SUMO microsimulation;?\s*(?:their operational effectiveness has not been established and they require simulation execution[^.]*\.?)?\s*",
        r"Available candidate interventions\s*(?:\([^)]*\))?\s*remain untested in simulation;?\s*(?:their operational effectiveness has not been established and they require simulation execution[^.]*\.?)?\s*",
        r"Candidate interventions remain untested in SUMO microsimulation\.?\s*",
        r"Candidate interventions remain untested in simulation\.?\s*",
        r"No simulation history is available\.?\s*",
        r"No simulation evidence exists\s*(?:\([^)]*\))?\.?\s*(?:No traffic optimization interventions have been executed in SUMO microsimulation yet[^.]*\.?)?\s*",
        r"\(untested candidate requiring simulation\)",
        r"\(Note:\s*Other candidate interventions[^)]*remain untested in this cycle[^)]*\)",
        r"SUMO simulation metrics represent simulated/synthetic evidence under a defined traffic-demand scenario, distinct from live physical road sensors\.?\s*",
    ]
    cleaned = text
    for pat in patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)

    # Clean up whitespace and punctuation
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"^\s*[,;.-]\s*", "", cleaned).strip()
    return cleaned


def strip_internal_planner_reasoning(text: str) -> str:
    """
    Remove internal Planner reasoning, rule explanations, rule citations, and
    procedural non-launch explanations from user-facing responses.

    Preserves factual metrics, source citations, legitimate domain limitations,
    and actual simulation results when applicable.
    """
    if not text:
        return text

    # 1. Sentence-level filtering
    sentences = re.split(r'(?<=[.!?])\s+', text)
    cleaned_sentences = []

    removal_patterns = [
        # Rule citations or rules
        r"\b(?:according to|under|per|following|as per)?\s*rule\s+\d+\b",
        # Purely diagnostic query explanations
        r"\bpurely\s+diagnostic\b",
        r"\bdiagnostic\s+intent\b",
        r"\bdiagnostic\s+query\b",
        # Evidence sufficiency assertions
        r"\b(?:evidence|telemetry)\s+is\s+sufficient\b",
        r"\bsufficient\s+to\s+answer\b",
        # Explanations about why simulations were not launched / run / needed
        r"\b(?:no|zero)\s+simulations?\s+(?:were|was)\s+(?:launched|run|required|needed|conducted|executed)\b",
        r"\bsimulations?\s+(?:were|was)\s+not\s+(?:launched|run|required|needed|conducted|executed)\b",
        r"\b(?:must\s+not|do\s+not|not\s+to)\s+launch\s+simulations?\b",
        r"\bno\s+new\s+simulations?\s+(?:were|was|required)\b",
    ]

    for sent in sentences:
        sent_str = sent.strip()
        if not sent_str:
            continue
        # Drop sentence if it contains internal Planner reasoning or rule explanations
        if any(re.search(pat, sent_str, flags=re.IGNORECASE) for pat in removal_patterns):
            continue
        cleaned_sentences.append(sent_str)

    cleaned = " ".join(cleaned_sentences).strip()

    # 2. In-clause fragment cleanup for cases without punctuation boundaries
    clause_patterns = [
        r"(?:According to|Under|Per|Following|As per)\s+Rule\s+\d+[^,.:;]*[,.:;]?",
        r"(?:The|This)\s+objective\s+is\s+(?:a\s+)?purely\s+diagnostic\s+query[^.]*\.?",
        r"(?:The|This)\s+query\s+is\s+(?:a\s+)?purely\s+diagnostic\s*(?:query|request)?[^.]*\.?",
        r"(?:As|Since|Because)\s+this\s+is\s+a\s+(?:purely\s+)?diagnostic\s+(?:query|request)[^,.]*,?\s*",
        r"\b(?:purely\s+diagnostic\s+query|purely\s+diagnostic\s+request)\b[^.]*\.?",
        r"(?:The\s+collected\s+evidence|The\s+evidence|Evidence)\s+is\s+sufficient\s+to\s+answer[^.]*\.?",
        r"(?:(?:No|Zero)\s+simulations?\s+were\s+(?:launched|run|required|needed|conducted|executed)\s*(?:because|since|as|for)?[^.]*\.?)",
        r"(?:(?:Simulations?|Simulation\s+runs?)\s+were\s+not\s+(?:launched|run|required|needed|conducted|executed)\s*(?:because|since|as|for)?[^.]*\.?)",
    ]
    for cpat in clause_patterns:
        cleaned = re.sub(cpat, "", cleaned, flags=re.IGNORECASE)

    # Clean up whitespace and punctuation
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"^\s*[,;.-]\s*", "", cleaned).strip()
    return cleaned


def request_involves_traffic_optimization_or_simulation(
    objective: str,
    collected_results: Optional[Dict[str, Any]] = None,
    tested_interventions: Optional[List[Any]] = None,
    untested_candidates: Optional[List[Any]] = None,
) -> bool:
    """
    Determine whether the current user request actually involves traffic optimization,
    traffic interventions, or simulation.

    Returns True ONLY when:
    1. Simulation was explicitly requested or executed (tested interventions or simulation results exist).
    2. The objective asks about simulation execution, simulation comparison, or tested interventions.
    3. The objective explicitly involves traffic optimization (signal timing, rerouting, bottleneck resolution, congestion reduction).
    4. For single-domain traffic requests, candidate interventions exist from the Traffic Agent.

    Returns False for:
    - Weather-only queries
    - Pollution-only queries
    - Energy-only queries
    - Multi-agent queries that do not explicitly request traffic optimization or simulation
    - Pure observational or diagnostic queries where no candidates or simulations exist
    """
    if tested_interventions and len(tested_interventions) > 0:
        return True

    if collected_results and bool(collected_results.get("simulation")):
        return True

    obj = (objective or "").lower().strip()

    # 1. Explicit simulation keywords / comparison inquiries
    sim_keywords = [
        "which tested intervention", "which tested", "performed better", "perform better",
        "compare the tested", "compare tested", "compare the simulated", "compare simulated",
        "was the intervention effective", "why did the tested", "why did tested",
        "did the optimization solve", "did it solve the bottleneck", "was the bottleneck solved",
        "simulate", "simulation", "sumo", "run simulation", "test in simulation",
        "test the intervention", "synthetic demand"
    ]
    if any(k in obj for k in sim_keywords):
        return True

    # 2. Specific traffic optimization / intervention phrases
    traffic_opt_phrases = [
        "optimize traffic", "traffic optimization", "optimize the traffic", "optimize signals",
        "optimize signal", "signal timing", "rerouting", "green time", "traffic intervention",
        "candidate intervention", "candidate interventions", "bottleneck resolution",
        "solve the bottleneck", "solve bottleneck", "alleviate the bottleneck",
        "reduce traffic congestion", "alleviate traffic", "mitigate traffic",
        "traffic mitigation", "improve traffic flow"
    ]
    if any(p in obj for p in traffic_opt_phrases):
        return True

    # 3. Combination of optimization action verb + explicit traffic concept
    opt_verbs = [
        "optimize", "optimization", "how can we reduce", "how to reduce",
        "how can we improve", "how to improve", "how can we alleviate", "how to alleviate",
        "how can we fix", "how to fix", "how to mitigate", "how can we mitigate",
        "recommend an intervention", "suggest an intervention", "propose an intervention",
        "mitigation strategy", "how to solve", "how can we solve"
    ]
    traffic_nouns = [
        "traffic", "congestion", "bottleneck", "corridor", "delay",
        "signal", "intersection", "junction", "vehicle queue", "queuing"
    ]
    if any(v in obj for v in opt_verbs) and any(n in obj for n in traffic_nouns):
        return True

    # 4. Check if candidates exist in traffic data for single-domain traffic requests
    has_traffic_cands = False
    if untested_candidates and len(untested_candidates) > 0:
        has_traffic_cands = True
    elif collected_results and isinstance(collected_results.get("traffic"), dict):
        raw_cands = collected_results["traffic"].get("candidate_interventions", [])
        if raw_cands and len(raw_cands) > 0:
            has_traffic_cands = True

    if has_traffic_cands:
        domains = [k for k in (collected_results or {}).keys() if k in {"traffic", "weather", "pollution", "energy"}]
        is_multi_agent = len(domains) > 1
        if not is_multi_agent:
            # Diagnostic-only questions asking only for bottleneck or metric should not trigger optimization disclaimers
            is_diagnostic_only = any(
                p in obj for p in [
                    "what is the bottleneck", "which corridor is the bottleneck", "what are the bottleneck",
                    "what is the average speed", "what is the speed", "give me the bottleneck",
                    "what is the traffic congestion", "why is", "congestion level"
                ]
            ) and not any(
                w in obj for w in [
                    "candidate", "candidates", "intervention", "interventions", "recommend",
                    "recommendation", "optimize", "reduce", "improve", "solve", "mitigate"
                ]
            )
            if not is_diagnostic_only:
                return True

    return False


def determine_response_scope(objective: str) -> ResponseScope:
    """
    Determine the structured ResponseScope (fields and detail_level) based on
    the user's natural language request.

    Used by MockLLMProvider and as an application-level validator to ensure
    the LLM Planner produces a properly bounded response scope.
    """
    obj = (objective or "").lower().strip()

    # 1. Analytical simulation follow-up / comparison queries
    analytical_followup_phrases = [
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
    if any(phrase in obj for phrase in analytical_followup_phrases):
        return ResponseScope(fields=["simulation_evaluation"], detail_level="analysis")

    # 2. Simulation execution request
    is_sim_req = any(w in obj for w in ["simulate", "run simulation", "test in simulation", "run a simulation", "test the intervention", "run a test"])
    if is_sim_req and any(w in obj for w in ["best", "intervention", "timing", "rerouting", "strategy", "candidate"]):
        return ResponseScope(fields=["simulation"], detail_level="analysis")

    # 3. Explicit optimization / recommendation inquiry
    is_opt_or_rec_req = any(p in obj for p in [
        "optimize", "optimization", "how can we reduce", "how to reduce", "how can we improve", "how to improve",
        "how can we alleviate", "how to alleviate", "how can we fix", "how to fix",
        "how to mitigate", "how can we mitigate", "how do we reduce",
        "what recommendations", "what are the recommendations", "recommend an intervention",
        "what interventions", "what can be done", "what should we do", "suggest solutions",
        "suggest an intervention", "propose an intervention", "mitigation strategy",
        "how to solve", "how can we solve", "remedy"
    ])

    # 4. Broad analysis / diagnosis request
    is_broad = any(p in obj for p in [
        "analyze", "analysis", "traffic situation", "traffic conditions",
        "overview", "traffic report", "comprehensive", "diagnose current traffic",
        "diagnose traffic", "assess traffic", "full assessment", "evaluate traffic"
    ])

    # Narrow questions asking specifically for an isolated field
    has_narrow_question = any(p in obj for p in [
        "what is the bottleneck corridor", "what are the bottleneck corridors",
        "which corridor is the bottleneck", "where is the bottleneck",
        "what is the bottleneck", "identify the bottleneck corridor",
        "what is the average speed", "give me the bottleneck corridor and",
        "average speed on the bottleneck", "why is", "why are",
        "what is the congestion", "congestion level", "congestion percentage", "congestion index"
    ])

    if is_opt_or_rec_req and not has_narrow_question:
        return ResponseScope(fields=["recommendations"], detail_level="summary")

    if is_broad and not has_narrow_question:
        return ResponseScope(
            fields=["congestion", "relevant_metrics", "causes", "recommendations"],
            detail_level="analysis",
        )

    # 5. Targeted informational inquiries
    has_bottleneck_plural = any(p in obj for p in [
        "what are the bottleneck corridors", "what are the bottlenecks",
        "list the bottleneck corridors", "list the bottlenecks",
        "which corridors are bottlenecks", "bottleneck corridors",
        "what are bottleneck corridors", "show bottleneck corridors"
    ])

    has_bottleneck_singular = any(p in obj for p in [
        "what is the bottleneck corridor", "which corridor is the bottleneck",
        "where is the bottleneck", "identify the bottleneck corridor",
        "identify the bottleneck", "what is the bottleneck",
        "which corridor is congested", "slowest corridor", "lowest observed-speed corridor",
        "what is our bottleneck", "name the bottleneck corridor", "tell me the bottleneck corridor"
    ]) or (
        ("bottleneck corridor" in obj or "the bottleneck" in obj or "bottleneck" in obj)
        and any(w in obj for w in ["what", "which", "where", "identify", "show", "tell", "name", "give me"])
        and not is_opt_or_rec_req
    )

    has_speed_on_bottleneck = any(p in obj for p in [
        "average speed on the bottleneck", "speed on the bottleneck",
        "speed of the bottleneck", "speed on bottleneck", "speed of bottleneck",
        "average speed on bottleneck corridor", "speed on the bottleneck corridor"
    ])

    has_general_speed = any(p in obj for p in [
        "average speed", "network speed", "what is the speed", "how fast", "traffic speed",
        "current speed", "mean speed"
    ])

    # Combined query: bottleneck corridor + average speed
    has_combined_bottleneck_and_speed = (
        ("bottleneck" in obj)
        and has_general_speed
        and not has_speed_on_bottleneck
        and not is_broad
    )
    if has_combined_bottleneck_and_speed:
        return ResponseScope(fields=["bottleneck_corridor", "average_speed"], detail_level="minimal")

    if has_speed_on_bottleneck:
        return ResponseScope(fields=["bottleneck_speed"], detail_level="minimal")

    if has_bottleneck_plural:
        return ResponseScope(fields=["bottleneck_corridors_list"], detail_level="minimal")

    if has_bottleneck_singular:
        return ResponseScope(fields=["bottleneck_corridor"], detail_level="minimal")

    if has_general_speed and not is_broad:
        return ResponseScope(fields=["average_speed"], detail_level="minimal")

    # Cause inquiry ("Why is Narayanguda congested?")
    if any(p in obj for p in ["why is", "why are", "cause of", "causes of", "reason for", "what causes"]):
        return ResponseScope(fields=["causes"], detail_level="minimal")

    # Congestion level / index inquiry
    if any(p in obj for p in ["what is the congestion", "congestion level", "congestion percentage", "congestion index", "how congested"]):
        return ResponseScope(fields=["congestion"], detail_level="minimal")

    # Pollution domain targeted inquiries
    has_pm25 = bool(re.search(r"\bpm2\.?5\b", obj)) or "particulate matter 2.5" in obj
    has_pm10 = bool(re.search(r"\bpm10\b", obj)) or "particulate matter 10" in obj
    has_aqi = bool(re.search(r"\baqi\b", obj)) or "air quality index" in obj or "air quality" in obj

    if has_pm25 and has_pm10 and not is_broad:
        return ResponseScope(fields=["pm25", "pm10"], detail_level="minimal")

    if has_pm25 and not has_pm10 and not is_broad:
        return ResponseScope(fields=["pm25"], detail_level="minimal")

    if has_pm10 and not has_pm25 and not is_broad:
        return ResponseScope(fields=["pm10"], detail_level="minimal")

    if has_aqi and not (has_pm25 or has_pm10) and not is_broad and any(w in obj for w in ["what", "how", "current", "level", "index", "value"]):
        return ResponseScope(fields=["city_avg_aqi"], detail_level="minimal")

    if ("pollution" in obj or "air quality" in obj) and not any(w in obj for w in ["traffic", "congestion", "speed"]):
        is_concise_pollution = any(w in obj for w in ["what", "whats", "current", "currect", "level", "index", "show", "tell", "give"])
        if is_concise_pollution and not is_broad:
            return ResponseScope(fields=["pollution", "city_avg_aqi", "pm25", "pm10"], detail_level="summary")
        return ResponseScope(fields=["pollution", "aqi", "pm25", "pm10", "suggested_interventions"], detail_level="analysis")

    # Weather domain targeted inquiries
    has_temp = bool(re.search(r"\btemp(erature)?\b", obj))
    has_rain = any(w in obj for w in ["rain", "raining", "rainfall", "precipitation"])
    has_forecast = "forecast" in obj
    has_weather = any(w in obj for w in ["weather", "climate", "humidity", "wind", "sunny", "cloudy"]) or has_temp or has_rain or has_forecast
    has_traffic_terms = any(w in obj for w in ["traffic", "congestion", "speed", "bottleneck", "corridor", "delay", "rerout", "signal", "junction", "vehicles"])

    if has_weather and not has_traffic_terms:
        if has_temp and not (has_rain or has_forecast) and not is_broad:
            return ResponseScope(fields=["temperature"], detail_level="minimal")
        if has_rain and not has_forecast and not is_broad:
            return ResponseScope(fields=["precipitation", "condition"], detail_level="minimal")
        if has_forecast:
            return ResponseScope(fields=["weather_forecast"], detail_level="summary")
        if not is_broad:
            return ResponseScope(fields=["weather", "temperature", "condition", "humidity", "precipitation"], detail_level="summary")
        return ResponseScope(fields=["weather", "temperature", "condition", "precipitation", "forecast"], detail_level="analysis")

    # Energy domain targeted inquiries
    has_grid = any(w in obj for w in ["grid status", "power grid", "substation", "substations"])
    has_load = any(w in obj for w in ["power load", "grid load", "load pct", "current load", "electricity load"])
    has_energy = any(w in obj for w in ["energy", "electricity", "power"]) or has_grid or has_load

    if has_energy and not has_traffic_terms and not has_weather:
        if has_grid and not is_broad:
            return ResponseScope(fields=["grid_status", "load_pct"], detail_level="minimal")
        if has_load and not is_broad:
            return ResponseScope(fields=["load_pct", "current_load_mw"], detail_level="minimal")
        if not is_broad:
            return ResponseScope(fields=["energy", "grid_status", "load_pct"], detail_level="summary")
        return ResponseScope(fields=["energy", "grid_status", "load_pct", "substations"], detail_level="analysis")

    # Domain-aware default fallback
    if has_weather and not has_traffic_terms:
        return ResponseScope(fields=["weather", "temperature", "condition"], detail_level="summary")
    if has_energy and not has_traffic_terms:
        return ResponseScope(fields=["energy", "grid_status", "load_pct"], detail_level="summary")
    if ("pollution" in obj or "air quality" in obj) and not has_traffic_terms:
        return ResponseScope(fields=["pollution", "city_avg_aqi", "pm25", "pm10"], detail_level="summary")

    # Default fallback: broad analysis
    return ResponseScope(fields=["congestion", "relevant_metrics", "causes", "recommendations"], detail_level="analysis")


def classify_response_scope(objective: str) -> List[str]:
    """Compatibility helper returning the fields list from determine_response_scope."""
    return determine_response_scope(objective).fields


def extract_specialist_traffic_metrics(collected_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safely extract specialist traffic metrics and bottlenecks from collected_results.
    Handles flat telemetry dicts, nested SUMO KPI objects, corridors, and bottlenecks.
    Never hardcodes or fabricates values.
    """
    trf = collected_results.get("traffic") or {}
    metrics = trf.get("metrics") if isinstance(trf.get("metrics"), dict) else {}

    bottleneck_name: Optional[str] = (
        trf.get("bottleneck_corridor")
        or trf.get("bottleneck")
        or metrics.get("bottleneck_corridor")
    )
    bottleneck_reason: Optional[str] = None
    bottleneck_speed: Optional[float] = None
    all_bottlenecks: List[str] = []
    if bottleneck_name:
        all_bottlenecks.append(str(bottleneck_name))

    # 1. Structured bottlenecks list
    trf_bottlenecks = trf.get("bottlenecks") or []
    for b in trf_bottlenecks:
        b_corr = b.get("corridor") if isinstance(b, dict) else getattr(b, "corridor", "")
        b_reason = b.get("reason") if isinstance(b, dict) else getattr(b, "reason", "")
        b_ev = b.get("evidence") if isinstance(b, dict) else getattr(b, "evidence", {})
        b_spd = b_ev.get("speed_kmh") if isinstance(b_ev, dict) else None
        if b_corr:
            if b_corr not in all_bottlenecks:
                all_bottlenecks.append(b_corr)
            if not bottleneck_name:
                bottleneck_name = b_corr
                bottleneck_reason = b_reason
                if b_spd is not None:
                    try:
                        bottleneck_speed = float(b_spd)
                    except (ValueError, TypeError):
                        pass

    # 2. Corridors list
    corridors = trf.get("corridors") or []
    if corridors:
        critical_corrs = [
            c for c in corridors
            if (c.get("status") if isinstance(c, dict) else getattr(c, "status", "")) in ("CRITICAL", "HEAVY")
        ]
        for cc in critical_corrs:
            c_name = cc.get("name") if isinstance(cc, dict) else getattr(cc, "name", "")
            if c_name and c_name not in all_bottlenecks:
                all_bottlenecks.append(c_name)

        if not bottleneck_name:
            valid_corrs = [
                c for c in corridors
                if (c.get("avg_speed") if isinstance(c, dict) else getattr(c, "avg_speed", None)) is not None
            ]
            if valid_corrs:
                slowest = min(
                    valid_corrs,
                    key=lambda c: (c.get("avg_speed") if isinstance(c, dict) else getattr(c, "avg_speed", 999.0))
                )
                bottleneck_name = slowest.get("name") if isinstance(slowest, dict) else getattr(slowest, "name", "")
                spd_val = slowest.get("avg_speed") if isinstance(slowest, dict) else getattr(slowest, "avg_speed", None)
                if spd_val is not None:
                    try:
                        bottleneck_speed = float(spd_val)
                    except (ValueError, TypeError):
                        pass
                if bottleneck_name and bottleneck_name not in all_bottlenecks:
                    all_bottlenecks.append(bottleneck_name)

    # Match corridor speed if bottleneck name is resolved
    if bottleneck_name and bottleneck_speed is None and corridors:
        for c in corridors:
            c_name = c.get("name") if isinstance(c, dict) else getattr(c, "name", "")
            if c_name and str(c_name).strip().lower() == str(bottleneck_name).strip().lower():
                spd_val = c.get("avg_speed") if isinstance(c, dict) else getattr(c, "avg_speed", None)
                if spd_val is not None:
                    try:
                        bottleneck_speed = float(spd_val)
                    except (ValueError, TypeError):
                        pass
                break

    # Average speed
    avg_speed = trf.get("average_speed") if "average_speed" in trf else (
        trf.get("average_speed_kmh") if "average_speed_kmh" in trf else metrics.get("average_speed_kmh")
    )
    if avg_speed is not None:
        try:
            avg_speed = float(avg_speed)
        except (ValueError, TypeError):
            pass

    # Congestion index / percentage
    cong = trf.get("congestion") if "congestion" in trf else (
        trf.get("congestion_index") if "congestion_index" in trf else metrics.get("congestion_index")
    )
    if cong is not None:
        try:
            cong = float(cong)
        except (ValueError, TypeError):
            pass

    # Waiting time, delay, throughput, vehicle count
    waiting = trf.get("waiting_time") if "waiting_time" in trf else (
        trf.get("average_waiting_time_sec") if "average_waiting_time_sec" in trf else metrics.get("average_waiting_time_sec")
    )
    delay = trf.get("delay") if "delay" in trf else (
        trf.get("average_delay_sec") if "average_delay_sec" in trf else metrics.get("average_delay_sec")
    )
    throughput = trf.get("throughput") if "throughput" in trf else metrics.get("throughput")
    total_veh = trf.get("total_vehicles") if "total_vehicles" in trf else metrics.get("total_vehicles")

    return {
        "bottleneck_name": bottleneck_name,
        "all_bottlenecks": all_bottlenecks,
        "bottleneck_reason": bottleneck_reason,
        "bottleneck_speed": bottleneck_speed,
        "average_speed_kmh": avg_speed,
        "congestion_index": cong,
        "waiting_sec": waiting,
        "delay_sec": delay,
        "throughput": throughput,
        "total_vehicles": total_veh,
    }


def extract_traffic_metrics_and_bottlenecks(collected_results: Dict[str, Any]) -> Dict[str, Any]:
    """Alias for extract_specialist_traffic_metrics."""
    return extract_specialist_traffic_metrics(collected_results)


def extract_specialist_pollution_metrics(collected_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safely extract specialist pollution metrics from collected_results.
    Extracts city_avg_aqi, pm25, pm10, stations, and suggested_interventions.
    Never fabricates values.
    """
    pol = collected_results.get("pollution") or {}
    aqi = pol.get("city_avg_aqi") if "city_avg_aqi" in pol else pol.get("aqi")
    pm25 = pol.get("pm25")
    pm10 = pol.get("pm10")
    stations = pol.get("stations", [])
    interventions = pol.get("suggested_interventions", [])
    data_mode = pol.get("data_mode") or "historical"
    data_source = pol.get("data_source") or "open-meteo-air-quality-historical"
    data_timestamp = pol.get("data_timestamp")
    retrieved_at = pol.get("retrieved_at")

    return {
        "city_avg_aqi": aqi,
        "pm25": pm25,
        "pm10": pm10,
        "stations": stations,
        "suggested_interventions": interventions,
        "data_mode": data_mode,
        "data_source": data_source,
        "data_timestamp": data_timestamp,
        "retrieved_at": retrieved_at,
    }


def extract_specialist_weather_metrics(collected_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safely extract specialist weather metrics from collected_results.
    Extracts temperature_c, condition, humidity_pct, precipitation_mm, wind_speed_kmh, forecast_7d.
    Never fabricates values.
    """
    wth = collected_results.get("weather") or {}
    return {
        "temperature_c": wth.get("temperature_c"),
        "condition": wth.get("condition"),
        "humidity_pct": wth.get("humidity_pct") if "humidity_pct" in wth else wth.get("humidity"),
        "precipitation_mm": wth.get("precipitation_mm") if "precipitation_mm" in wth else wth.get("precipitation"),
        "wind_speed_kmh": wth.get("wind_speed_kmh") if "wind_speed_kmh" in wth else wth.get("wind_speed"),
        "forecast_7d": wth.get("forecast_7d", []),
        "city": wth.get("city") or wth.get("location"),
    }


def extract_specialist_energy_metrics(collected_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safely extract specialist energy metrics from collected_results.
    Extracts grid_status, load_pct, current_load_mw, capacity_mw, substations.
    Never fabricates values.
    """
    nrg = collected_results.get("energy") or {}
    return {
        "grid_status": nrg.get("grid_status") or nrg.get("status"),
        "load_pct": nrg.get("load_pct"),
        "current_load_mw": nrg.get("current_load_mw"),
        "capacity_mw": nrg.get("capacity_mw"),
        "substations": nrg.get("substations", []),
    }


def validate_and_enforce_response_scope(
    final_reasoning: Any,
    objective: str,
    collected_results: Dict[str, Any],
    cross_analysis: Optional[Any] = None,
) -> None:
    """
    Validate the structured ResponseScope on final_reasoning and enforce that
    only requested information is exposed to the user, while preserving full
    internal specialist evidence.
    """
    # 1. Ensure structured ResponseScope exists
    scope: Optional[ResponseScope] = getattr(final_reasoning, "response_scope", None)
    if not isinstance(scope, ResponseScope):
        if isinstance(scope, dict):
            try:
                scope = ResponseScope.model_validate(scope)
            except Exception:
                scope = determine_response_scope(objective)
        else:
            scope = determine_response_scope(objective)
        setattr(final_reasoning, "response_scope", scope)
    setattr(final_reasoning, "requested_scope", scope.fields)

    involves_traffic_opt_or_sim = request_involves_traffic_optimization_or_simulation(
        objective=objective,
        collected_results=collected_results,
        tested_interventions=getattr(final_reasoning, "tested_interventions", None),
        untested_candidates=getattr(final_reasoning, "untested_candidates", None),
    )

    # Strip internal reasoning, rule citations, and simulation non-launch explanations from all user-facing fields
    for attr in ("summary", "recommendation", "uncertainty_and_limitations"):
        val = getattr(final_reasoning, attr, None)
        if val and isinstance(val, str):
            setattr(final_reasoning, attr, strip_internal_planner_reasoning(val))

    # When request does not involve traffic optimization or simulation, strip any stray traffic/SUMO disclaimers
    if not involves_traffic_opt_or_sim:
        if hasattr(final_reasoning, "summary") and final_reasoning.summary:
            final_reasoning.summary = strip_unrelated_traffic_disclaimers(final_reasoning.summary)
        if hasattr(final_reasoning, "recommendation") and final_reasoning.recommendation:
            final_reasoning.recommendation = strip_unrelated_traffic_disclaimers(final_reasoning.recommendation)
        if hasattr(final_reasoning, "uncertainty_and_limitations") and final_reasoning.uncertainty_and_limitations:
            final_reasoning.uncertainty_and_limitations = strip_unrelated_traffic_disclaimers(final_reasoning.uncertainty_and_limitations)
        if hasattr(final_reasoning, "synthetic_data_note"):
            setattr(final_reasoning, "synthetic_data_note", None)
        if hasattr(final_reasoning, "simulation_findings"):
            setattr(final_reasoning, "simulation_findings", None)

    # 2. If broad analysis or simulation evaluation is requested, preserve comprehensive reasoning (after stripping disclaimers & internal reasoning)
    if scope.detail_level in ("analysis", "full") or "broad_analysis" in scope.fields or "simulation_evaluation" in scope.fields:
        for attr in ("summary", "recommendation", "uncertainty_and_limitations"):
            val = getattr(final_reasoning, attr, None)
            if val and isinstance(val, str):
                setattr(final_reasoning, attr, strip_internal_planner_reasoning(val))
        return

    # 3. For narrow/minimal scopes, enforce that unrequested information is not exposed
    fields = set(scope.fields)
    wants_recommendations = bool({"recommendations", "interventions", "suggested_interventions"}.intersection(fields))
    wants_bottleneck = bool({"bottleneck_corridor", "bottleneck_corridors_list"}.intersection(fields))
    wants_speed = bool({"average_speed", "bottleneck_speed"}.intersection(fields))
    wants_causes = "causes" in fields
    wants_congestion = "congestion" in fields

    wants_simulation = bool({"simulation", "simulation_evaluation"}.intersection(fields))

    obj_l = (objective or "").lower()
    wants_explicit_candidates = any(w in obj_l for w in [
        "candidate", "candidates", "intervention", "interventions", "recommendation", "recommendations",
        "what can be done", "solutions", "how to fix", "how to reduce", "how can we", "suggest", "propose"
    ])

    # If recommendations or candidates were not requested (e.g. diagnostic query only asking for bottleneck or metric):
    if not wants_recommendations and not wants_explicit_candidates:
        setattr(final_reasoning, "recommendation", "")
        if hasattr(final_reasoning, "untested_candidates"):
            setattr(final_reasoning, "untested_candidates", [])

    # If simulation was not requested, clear simulation fields
    if not wants_simulation:
        if hasattr(final_reasoning, "synthetic_data_note"):
            setattr(final_reasoning, "synthetic_data_note", None)
        if hasattr(final_reasoning, "simulation_findings"):
            setattr(final_reasoning, "simulation_findings", None)

    metrics_info = extract_specialist_traffic_metrics(collected_results)
    bottleneck_name = metrics_info["bottleneck_name"]
    bottleneck_speed = metrics_info["bottleneck_speed"]
    all_bottlenecks = metrics_info["all_bottlenecks"]
    bottleneck_reason = metrics_info["bottleneck_reason"]
    avg_speed = metrics_info["average_speed_kmh"]
    cong = metrics_info["congestion_index"]

    pol_metrics = extract_specialist_pollution_metrics(collected_results)
    pm25_val = pol_metrics.get("pm25")
    pm10_val = pol_metrics.get("pm10")
    aqi_val = pol_metrics.get("city_avg_aqi")
    pol_mode = pol_metrics.get("data_mode") or "historical"
    pol_ts = pol_metrics.get("data_timestamp")

    # Scope 1: Bottleneck corridor only
    if fields == {"bottleneck_corridor"}:
        corridor_display = bottleneck_name or "Not identified"
        final_reasoning.summary = f"Bottleneck corridor: {corridor_display}."

    # Scope 2: Bottleneck corridors list
    elif fields == {"bottleneck_corridors_list"}:
        if len(all_bottlenecks) > 1:
            final_reasoning.summary = f"Bottleneck corridors: {', '.join(all_bottlenecks)}."
        elif all_bottlenecks:
            final_reasoning.summary = f"Bottleneck corridor: {all_bottlenecks[0]}."
        else:
            corridor_display = bottleneck_name or "None identified"
            final_reasoning.summary = f"Bottleneck corridor: {corridor_display}."

    # Scope 3: Average speed only
    elif fields == {"average_speed"}:
        if avg_speed is not None:
            spd_disp = f"{avg_speed:.1f}" if isinstance(avg_speed, float) else str(avg_speed)
            final_reasoning.summary = f"Average speed: {spd_disp} km/h."
        else:
            final_reasoning.summary = "Average speed: Telemetry unavailable."

    # Scope 4: Bottleneck corridor speed
    elif fields == {"bottleneck_speed"}:
        corridor_display = bottleneck_name or "bottleneck corridor"
        spd_val = bottleneck_speed if bottleneck_speed is not None else avg_speed
        if spd_val is not None:
            spd_disp = f"{spd_val:.1f}" if isinstance(spd_val, float) else str(spd_val)
            final_reasoning.summary = f"Average speed on bottleneck corridor ({corridor_display}): {spd_disp} km/h."
        else:
            final_reasoning.summary = f"Average speed on bottleneck corridor ({corridor_display}): Telemetry unavailable."

    # Scope 5: Bottleneck corridor + Average speed
    elif "bottleneck_corridor" in fields and "average_speed" in fields and len(fields) == 2:
        corridor_display = bottleneck_name or "Not identified"
        spd_val = bottleneck_speed if bottleneck_speed is not None else avg_speed
        if spd_val is not None:
            spd_disp = f"{spd_val:.1f}" if isinstance(spd_val, float) else str(spd_val)
            final_reasoning.summary = f"Bottleneck corridor: {corridor_display}. Average speed: {spd_disp} km/h."
        else:
            final_reasoning.summary = f"Bottleneck corridor: {corridor_display}."

    # Scope 6: Causes only
    elif fields == {"causes"}:
        reason_display = bottleneck_reason or "Elevated vehicle density and roadway junction bottlenecks"
        final_reasoning.summary = f"Congestion cause: {reason_display}."

    # Scope 7: Congestion only
    elif fields == {"congestion"}:
        if cong is not None:
            c_val = float(cong)
            c_disp = f"{c_val * 100:.1f}%" if 0.0 <= c_val <= 1.0 else f"{c_val:.1f}%"
            final_reasoning.summary = f"Traffic congestion level: {c_disp}."
        else:
            final_reasoning.summary = "Traffic congestion level: Telemetry unavailable."

    # Scope 8: PM2.5 only
    elif fields == {"pm25"}:
        if pm25_val is not None:
            p_disp = f"{pm25_val:.1f}" if isinstance(pm25_val, float) else str(pm25_val)
            prefix = "Current PM2.5" if pol_mode == "current" else "PM2.5"
            final_reasoning.summary = f"{prefix}: {p_disp} µg/m³."
        else:
            final_reasoning.summary = "PM2.5: Telemetry unavailable."

    # Scope 9: PM10 only
    elif fields == {"pm10"}:
        if pm10_val is not None:
            p_disp = f"{pm10_val:.1f}" if isinstance(pm10_val, float) else str(pm10_val)
            prefix = "Current PM10" if pol_mode == "current" else "PM10"
            final_reasoning.summary = f"{prefix}: {p_disp} µg/m³."
        else:
            final_reasoning.summary = "PM10: Telemetry unavailable."

    # Scope 10: AQI only
    elif fields in ({"city_avg_aqi"}, {"aqi"}):
        if aqi_val is not None:
            if pol_mode == "current":
                meta_suffix = f" (Updated: {pol_ts})" if pol_ts else ""
                final_reasoning.summary = f"Current Air Quality Index (AQI): {aqi_val}{meta_suffix}."
            else:
                final_reasoning.summary = f"Air Quality Index (AQI): {aqi_val}."
        else:
            final_reasoning.summary = "Air Quality Index (AQI): Telemetry unavailable."

    # Scope 11: PM2.5 and PM10
    elif fields == {"pm25", "pm10"}:
        p25_str = f"{pm25_val:.1f}" if isinstance(pm25_val, float) else str(pm25_val)
        p10_str = f"{pm10_val:.1f}" if isinstance(pm10_val, float) else str(pm10_val)
        if pol_mode == "current":
            final_reasoning.summary = f"Current PM2.5: {p25_str} µg/m³. Current PM10: {p10_str} µg/m³."
        else:
            final_reasoning.summary = f"PM2.5: {p25_str} µg/m³. PM10: {p10_str} µg/m³."

    # Scope 12: General Pollution status / summary
    elif "pollution" in fields or ({"city_avg_aqi", "pm25", "pm10"}.issubset(fields)):
        parts = []
        if aqi_val is not None:
            parts.append(f"AQI: {aqi_val}")
        if pm25_val is not None:
            p25_str = f"{pm25_val:.1f}" if isinstance(pm25_val, float) else str(pm25_val)
            parts.append(f"PM2.5: {p25_str} µg/m³")
        if pm10_val is not None:
            p10_str = f"{pm10_val:.1f}" if isinstance(pm10_val, float) else str(pm10_val)
            parts.append(f"PM10: {p10_str} µg/m³")
        if parts:
            if pol_mode == "current":
                meta_suffix = f" (Updated: {pol_ts})" if pol_ts else ""
                final_reasoning.summary = f"Current Air Quality: {', '.join(parts)}{meta_suffix}."
            else:
                final_reasoning.summary = f"Air Quality: {', '.join(parts)}."
        else:
            final_reasoning.summary = "Air Quality: Telemetry unavailable."

    # Scope 13: Temperature only
    elif fields == {"temperature"}:
        w_info = extract_specialist_weather_metrics(collected_results)
        t_val = w_info.get("temperature_c")
        if t_val is not None:
            t_disp = f"{t_val:.1f}" if isinstance(t_val, float) else str(t_val)
            final_reasoning.summary = f"Current temperature: {t_disp}°C."
        else:
            final_reasoning.summary = "Temperature: Telemetry unavailable."

    # Scope 14: Precipitation and Condition
    elif fields in ({"precipitation", "condition"}, {"precipitation"}):
        w_info = extract_specialist_weather_metrics(collected_results)
        c_val = w_info.get("condition") or "Clear"
        p_val = w_info.get("precipitation_mm")
        p_str = f"{p_val} mm" if p_val is not None else "None reported"
        final_reasoning.summary = f"Weather condition: {c_val}. Precipitation: {p_str}."

    # Scope 15: Weather status / summary
    elif "weather" in fields or "weather_forecast" in fields:
        w_info = extract_specialist_weather_metrics(collected_results)
        c_val = w_info.get("condition")
        t_val = w_info.get("temperature_c")
        p_val = w_info.get("precipitation_mm")
        h_val = w_info.get("humidity_pct")
        parts = []
        if c_val:
            parts.append(f"{c_val}")
        if t_val is not None:
            t_disp = f"{t_val:.1f}" if isinstance(t_val, float) else str(t_val)
            parts.append(f"{t_disp}°C")
        if p_val is not None:
            parts.append(f"Precipitation: {p_val} mm")
        if h_val is not None:
            parts.append(f"Humidity: {h_val}%")
        if parts:
            final_reasoning.summary = f"Current weather: {', '.join(parts)}."
        else:
            final_reasoning.summary = "Weather: Telemetry unavailable."

    # Scope 16: Grid status only
    elif fields in ({"grid_status", "load_pct"}, {"grid_status"}):
        e_info = extract_specialist_energy_metrics(collected_results)
        st_val = e_info.get("grid_status") or "ONLINE"
        lp_val = e_info.get("load_pct")
        lp_str = f" (Load: {lp_val}%)" if lp_val is not None else ""
        final_reasoning.summary = f"Power grid status: {st_val}{lp_str}."

    # Scope 17: Energy load / status
    elif "energy" in fields or "load_pct" in fields:
        e_info = extract_specialist_energy_metrics(collected_results)
        st_val = e_info.get("grid_status") or "ONLINE"
        lp_val = e_info.get("load_pct")
        mw_val = e_info.get("current_load_mw")
        parts = [f"Status: {st_val}"]
        if lp_val is not None:
            parts.append(f"Load: {lp_val}%")
        if mw_val is not None:
            parts.append(f"{mw_val} MW")
        final_reasoning.summary = f"Energy grid: {', '.join(parts)}."

    # Final pass to ensure all user-facing fields are stripped of internal reasoning
    for attr in ("summary", "recommendation", "uncertainty_and_limitations"):
        val = getattr(final_reasoning, attr, None)
        if val and isinstance(val, str):
            setattr(final_reasoning, attr, strip_internal_planner_reasoning(val))


def apply_response_scope(
    final_reasoning: Any,
    objective: str,
    collected_results: Dict[str, Any],
    cross_analysis: Optional[Any] = None,
) -> None:
    """Convenience alias for validate_and_enforce_response_scope."""
    validate_and_enforce_response_scope(
        final_reasoning=final_reasoning,
        objective=objective,
        collected_results=collected_results,
        cross_analysis=cross_analysis,
    )
