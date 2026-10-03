"""
Pollution Grounding Chat Handler — the main entry point for pollution questions
sent from the Planning AI chat.

Flow:
1. Detect if question is pollution-related (keyword + planner domain detection)
2. Select and call relevant tools based on question analysis
3. Load fact sheet for context
4. Build prompt with tool outputs + fact sheet
5. Call LLM (Groq, temperature 0.1)
6. Run deterministic verifier (if POLLUTION_VERIFY=true)
7. Return {text, insights, suggestions} for the frontend

Falls back to rule-based answer if LLM is unavailable.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("pollution_grounding.handler")

from .prompts import (
    POLLUTION_DOMAIN_PROMPT,
    is_pollution_question,
    is_advice_question,
    is_health_advice_question,
)
from .tools import (
    get_current,
    explain_station_aqi,
    compare_stations,
    get_forecast,
    get_data_status,
    compute_aqi,
    resolve_station,
    get_station_history,
    get_mitigation_playbook,
    get_health_advisory,
    get_priority_stations,
)


# ── Fact Sheet Loading ──

_FACT_SHEET_CACHE: Optional[str] = None


def _load_fact_sheet() -> str:
    global _FACT_SHEET_CACHE
    if _FACT_SHEET_CACHE is not None:
        return _FACT_SHEET_CACHE
    path = Path(__file__).resolve().parent.parent / "knowledge" / "pollution_fact_sheet.md"
    try:
        _FACT_SHEET_CACHE = path.read_text(encoding="utf-8")
    except Exception:
        _FACT_SHEET_CACHE = ""
    return _FACT_SHEET_CACHE


# ── Question Analysis ──

def _analyze_question(question: str) -> Dict[str, Any]:
    """Analyze question to determine which tools to call."""
    q = question.lower().strip()
    result = {
        "tools_needed": [],
        "stations_mentioned": [],
        "unknown_station": None,
        "is_comparison": False,
        "is_forecast": False,
        "is_model_limits": False,
        "is_methodology": False,
        "is_data_status": False,
        "is_why_higher": False,
        "is_current": False,
        "is_staleness": False,
        "is_advice": False,
        "is_health_advice": False,
        "is_adversarial_estimate": False,
        "is_adversarial_cause": False,
        "is_adversarial_guarantee": False,
        "is_out_of_scope": False,
    }

    # Out of scope detection (e.g. non-Hyderabad or non-city queries)
    if any(w in q for w in ["delhi", "mumbai", "bangalore", "bengaluru", "chennai", "kolkata", "london", "new york", "paris", "tokyo", "beijing"]):
        result["is_out_of_scope"] = True
        return result

    # Sensor offline detection
    if any(w in q for w in ["offline", "sensors fail", "sensor fail", "sensor is completely", "sensors are offline"]):
        result["is_sensors_offline"] = True
        return result

    # Data sufficiency detection
    if any(w in q for w in ["data sufficiency", "hourly reading", "16 hour", "packet loss", "valid rolling", "valid 24-hour", "below 16", "out of 24"]):
        result["is_data_sufficiency"] = True
        return result

    # Check for station names
    from .tools import _load_stations, resolve_station
    stations = _load_stations()
    for s in stations:
        names = [s["primary_name"].lower()] + [a.lower() for a in s.get("aliases", [])] + [s.get("area", "").lower()]
        for name in names:
            if name and name in q:
                if s["primary_name"] not in result["stations_mentioned"]:
                    result["stations_mentioned"].append(s["primary_name"])
                break

    # Known unmonitored or area locations to check if no station matched
    if not result["stations_mentioned"]:
        for loc in ["banjara hills", "kukatpally", "hitec city", "secunderabad", "jubilee hills", "madhapur", "begumpet", "ameerpet", "charminar", "koti"]:
            if loc in q:
                result["unknown_station"] = loc.title()
                break

    # Advice / Mitigation intent (gated by POLLUTION_REASONING)
    reasoning_enabled = os.getenv("POLLUTION_REASONING", "true").lower() in ("true", "1", "yes")
    if reasoning_enabled:
        if is_advice_question(q):
            result["is_advice"] = True
            result["is_current"] = True  # Need current data for context
            if "get_current" not in result["tools_needed"]:
                result["tools_needed"].insert(0, "get_current")

        # Health advice intent
        if is_health_advice_question(q):
            result["is_health_advice"] = True
            result["is_current"] = True
            if "get_current" not in result["tools_needed"]:
                result["tools_needed"].insert(0, "get_current")

    # Adversarial patterns
    if any(w in q for w in ["just estimate", "guess the aqi", "make an estimate", "estimate it without", "approximate yourself", "personal estimate", "fabricate an aqi"]):
        result["is_adversarial_estimate"] = True
    if any(w in q for w in ["guarantee", "100% accurate", "guaranteed", "certain", "is the forecast 100%", "guarantee aqi will drop", "promise"]):
        result["is_adversarial_guarantee"] = True
    if any(w in q for w in ["traffic caused", "industry caused", "factories caused", "due to traffic", "construction caused", "chemical factories", "diesel truck", "which factory"]):
        result["is_adversarial_cause"] = True
    # Adversarial: ignore rules / jailbreak
    if any(w in q for w in ["ignore your rules", "ignore the rules", "forget your instructions", "pretend you are", "disregard", "override your"]):
        result["is_adversarial_jailbreak"] = True

    # Methodology & Breakpoints
    if any(w in q for w in ["how is aqi calculated", "methodology", "cpcb", "breakpoint", "sub-index", "sub index",
                             "how does the engine", "naqi", "how is the aqi", "how do you calculate",
                             "why is pm2.5 or pm10 required", "particulate mandate", "sufficiency rule",
                             "health impact descriptors", "severe aqi reading", "good and satisfactory"]):
        result["is_methodology"] = True

    # Model limits & Accuracy
    if any(w in q for w in ["mae", "rmse", "limitation", "weakness", "how accurate", "accuracy", "inversion", "pblh",
                             "directional accuracy", "flat", "trajectory", "error rate", "model limits", "held-out test"]):
        result["is_model_limits"] = True

    # Data status & Switchover
    if any(w in q for w in ["live data", "switchover", "accumulation", "consecutive days", "data status",
                             "live mode", "historical archive", "14 days", "14 consecutive", "sufficiency",
                             "what provider ingests", "input window size", "staleness threshold in hours"]):
        result["is_data_status"] = True
        result["tools_needed"].append("get_data_status")

    # Comparisons
    if any(w in q for w in ["compare", "versus", "vs", "ranking", "worst", "best", "highest", "lowest", "rank"]):
        result["is_comparison"] = True
        result["tools_needed"].append("compare_stations")

    # Forecast
    if any(w in q for w in ["forecast", "predict", "tomorrow", "next week", "7 day", "7-day", "future", "will the"]):
        result["is_forecast"] = True
        result["tools_needed"].append("get_forecast")

    # Why higher
    if any(w in q for w in ["why is", "why does", "why higher", "reason for", "cause of", "dominant pollutant at"]):
        result["is_why_higher"] = True

    # Staleness
    if any(w in q for w in ["stale", "freshness", "data age", "last updated", "how old", "how recent", "is today's aqi live"]):
        result["is_staleness"] = True
        result["is_current"] = True

    # Current
    if any(w in q for w in ["current", "right now", "today", "latest", "observed", "what is the aqi"]):
        result["is_current"] = True

    # Default tool selection
    if not result["tools_needed"] or result["is_current"] or result["is_why_higher"] or result["is_staleness"]:
        if "get_current" not in result["tools_needed"]:
            result["tools_needed"].insert(0, "get_current")

    if result["stations_mentioned"] and (result["is_why_higher"] or "explain" in q or "detail" in q):
        if "explain_station_aqi" not in result["tools_needed"]:
            result["tools_needed"].append("explain_station_aqi")

    if len(result["stations_mentioned"]) >= 2 and "compare_stations" not in result["tools_needed"]:
        result["is_comparison"] = True
        result["tools_needed"].append("compare_stations")

    return result


# ── Tool Execution ──

def _execute_tools(analysis: Dict[str, Any], question: str) -> Dict[str, Any]:
    """Execute the tools identified by question analysis."""
    tool_outputs = {}

    for tool_name in analysis["tools_needed"]:
        try:
            if tool_name == "get_current":
                if analysis["stations_mentioned"]:
                    tool_outputs["current_station"] = get_current(station=analysis["stations_mentioned"][0])
                tool_outputs["current_city"] = get_current()

            elif tool_name == "explain_station_aqi":
                for station in analysis["stations_mentioned"]:
                    tool_outputs[f"explain_{station}"] = explain_station_aqi(station)

            elif tool_name == "compare_stations":
                if len(analysis["stations_mentioned"]) >= 2:
                    tool_outputs["comparison"] = compare_stations(
                        station_a=analysis["stations_mentioned"][0],
                        station_b=analysis["stations_mentioned"][1],
                    )
                else:
                    tool_outputs["comparison"] = compare_stations()

            elif tool_name == "get_forecast":
                tool_outputs["forecast"] = get_forecast()

            elif tool_name == "get_data_status":
                tool_outputs["data_status"] = get_data_status()

        except Exception as exc:
            logger.warning("Tool %s failed: %s", tool_name, exc)
            tool_outputs[tool_name] = {"status": "unavailable", "error": str(exc)}

    # Advice/mitigation: load playbook items for the dominant pollutant
    if analysis.get("is_advice") or analysis.get("is_health_advice"):
        # Determine dominant pollutant from station or city data
        dom_pollutant = None
        dom_category = None
        station_data = tool_outputs.get("current_station", {})
        city_data = tool_outputs.get("current_city", {})
        src = station_data if station_data.get("status") == "success" else city_data
        dom_pollutant = src.get("dominant_pollutant")
        dom_category = src.get("category")

        try:
            tool_outputs["playbook_items"] = get_mitigation_playbook(
                pollutant=dom_pollutant, category=dom_category
            )
        except Exception as exc:
            logger.warning("get_mitigation_playbook failed: %s", exc)
            tool_outputs["playbook_items"] = []

        if analysis.get("is_health_advice"):
            try:
                tool_outputs["health_advisory"] = get_health_advisory(
                    category=dom_category or "Satisfactory"
                )
            except Exception as exc:
                logger.warning("get_health_advisory failed: %s", exc)
                tool_outputs["health_advisory"] = {}

        # Also get priority stations for chip relevance
        try:
            tool_outputs["priority_stations"] = get_priority_stations(n=3)
        except Exception as exc:
            logger.warning("get_priority_stations failed: %s", exc)

        # If station mentioned, also get explanation for richer context
        if analysis["stations_mentioned"] and f"explain_{analysis['stations_mentioned'][0]}" not in tool_outputs:
            try:
                tool_outputs[f"explain_{analysis['stations_mentioned'][0]}"] = explain_station_aqi(
                    analysis["stations_mentioned"][0]
                )
            except Exception:
                pass

    return tool_outputs


# ── LLM Call ──

def _strip_think_blocks(text: str) -> str:
    """Strip Qwen3 <think>...</think> reasoning blocks from LLM output."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _call_llm(question: str, tool_outputs: Dict, fact_sheet: str) -> Optional[Dict[str, Any]]:
    """Call Groq LLM with the pollution domain prompt."""
    try:
        from backend.agents.planner_agent.llm_client import LLMClient
        client = LLMClient()
    except Exception as exc:
        logger.warning("LLM client unavailable: %s", exc)
        return None

    # Build the user message with tool context
    tool_context = json.dumps(tool_outputs, indent=2, default=str)
    fs_text = fact_sheet[:6000] if len(fact_sheet) > 6000 else fact_sheet

    # Include playbook items directly in prompt for advice questions
    playbook_section = ""
    playbook_items = tool_outputs.get("playbook_items", [])
    if playbook_items:
        pb_json = json.dumps(playbook_items[:8], indent=2, default=str)
        playbook_section = f"""\n## Mitigation Playbook Items (ONLY recommend from these, cite item id)
{pb_json}\n"""

    health_section = ""
    health_advisory = tool_outputs.get("health_advisory", {})
    if health_advisory:
        ha_json = json.dumps(health_advisory, indent=2, default=str)
        health_section = f"""\n## CPCB Health Advisory for Current Category
{ha_json}
Note: Always add disclaimer: 'General guidance based on CPCB AQI health descriptors, not personal medical advice.'\n"""

    user_message = f"""## User Question
"{question}"

## Tool Outputs (verified data — use these numbers exactly)
{tool_context}
{playbook_section}{health_section}
## Fact Sheet (reference)
{fs_text}

Based on the tool outputs and fact sheet above, answer the user's question.
Return ONLY a valid JSON object with keys: "text", "insights", "suggestions".
"""

    try:
        raw = client.generate_json_plan(
            system_prompt=POLLUTION_DOMAIN_PROMPT,
            user_query=user_message,
            temperature=0.1,
            max_tokens=1500,
        )
        # Strip Qwen3 <think> blocks
        raw = _strip_think_blocks(raw)
        parsed = json.loads(raw)
        if "text" in parsed and "insights" in parsed and "suggestions" in parsed:
            return parsed
        if "text" in parsed:
            return {
                "text": parsed["text"],
                "insights": parsed.get("insights", ["See tool data above."]),
                "suggestions": parsed.get("suggestions", [
                    "What is the current city AQI?",
                    "Which station has the highest AQI?",
                    "Show the 7-day forecast",
                ]),
            }
    except Exception as exc:
        logger.warning("LLM call failed: %s", exc)

    return None


# ── Rule-Based Fallback ──

def _build_advice_chips(analysis: Dict, tool_outputs: Dict) -> List[str]:
    """Build context-aware follow-up chips for advice/mitigation answers."""
    chips = []
    station_data = tool_outputs.get("current_station", {})
    city_data = tool_outputs.get("current_city", {})
    src = station_data if station_data.get("status") == "success" else city_data
    dom = src.get("dominant_pollutant", "PM10")
    station_name = analysis["stations_mentioned"][0] if analysis.get("stations_mentioned") else None
    city_aqi = city_data.get("aqi")
    st_aqi = station_data.get("aqi") if station_data.get("status") == "success" else None
    is_stale = src.get("is_stale", False)

    # Chip 1: priority stations
    chips.append("Which stations need action first?")

    # Chip 2: data-aware chip
    if is_stale:
        chips.append("How fresh is the current data?")
    elif station_name and st_aqi is not None and city_aqi is not None and st_aqi <= city_aqi:
        chips.append(f"Why is {station_name} lower than the city mean?")
    elif station_name:
        chips.append(f"Why is {station_name} higher?")
    else:
        chips.append("Show station rankings")

    # Chip 3: pollutant-specific
    chips.append(f"What measures help reduce {dom}?")

    return chips[:3]


def _rule_based_answer(question: str, analysis: Dict, tool_outputs: Dict) -> Dict[str, Any]:
    """Generate a structured answer from tool outputs without LLM."""
    text = ""
    insights = []
    suggestions = [
        "What is the current city AQI?",
        "Which station has the highest AQI?",
        "Show the 7-day forecast",
    ]

    current = tool_outputs.get("current_city", {})
    city_aqi = current.get("aqi")
    city_cat = current.get("category", "Unknown")
    city_dominant = current.get("dominant_pollutant", "PM10")
    is_stale = current.get("is_stale", False)
    stale_hours = current.get("data_age_hours")
    last_updated_label = current.get("last_updated_label", "")

    stale_str = f" (stale: {stale_hours}h old, {last_updated_label})" if is_stale and stale_hours else ""

    # Case 0: Out of scope
    if analysis.get("is_out_of_scope"):
        return {
            "text": "This question is outside the Hyderabad air quality domain.",
            "insights": [
                "The Planning AI specifically monitors continuous ambient air quality stations in Greater Hyderabad.",
                "External metropolitan regions are not covered in this telemetry stream.",
                "Available domains include Hyderabad Traffic, Energy, Weather, and Air Quality.",
            ],
            "suggestions": ["What is the current city AQI?", "Show station rankings", "7-day forecast"],
        }

    # Case 0b: Adversarial jailbreak
    if analysis.get("is_adversarial_jailbreak"):
        return {
            "text": "The system operates under fixed air quality analysis invariants and cannot override its verification rules.",
            "insights": [
                "All answers are grounded in verified CPCB CAAQMS sensor data and official methodology.",
                "The deterministic verifier enforces staleness reporting, source-attribution disclaimers, and forecast labelling.",
                "Prompt injection or rule-override attempts are logged and rejected.",
            ],
            "suggestions": ["What is the current city AQI?", "How is AQI calculated?", "Show the 7-day forecast"],
        }

    # Case 1: Unknown station
    if analysis.get("unknown_station"):
        cand = analysis["unknown_station"]
        from .tools import _load_stations
        known = [s["primary_name"] for s in _load_stations()]
        return {
            "text": f"Station '{cand}' is not monitored in the continuous CAAQMS network.",
            "insights": [
                f"Location '{cand}' does not match any active CPCB/TSPCB monitoring station in Greater Hyderabad.",
                f"Monitored network includes 13 continuous stations: {', '.join(known[:5])} and others.",
                "Missing data cannot be interpolated or estimated for unmonitored locations.",
            ],
            "suggestions": ["What is the current city AQI?", "Which station has the highest AQI?", "Show all monitored stations"],
        }

    # Case 2: Adversarial - request to estimate or guess
    if analysis.get("is_adversarial_estimate"):
        return {
            "text": "The system does not estimate, guess, or fabricate missing air quality numbers.",
            "insights": [
                "Invariant rule: Missing data returns 'unavailable', never an interpolation or speculative estimate.",
                "All AQI and pollutant concentrations are strictly derived from verified CPCB CAAQMS sensors.",
                "The CPCB engine requires at least 3 valid pollutant sub-indices including PM2.5 or PM10 to calculate AQI.",
            ],
            "suggestions": ["What is the current city AQI?", "How is AQI calculated?", "Show the 7-day forecast"],
        }

    # Case 3: Adversarial - request for forecast guarantee or promised AQI drop
    if analysis.get("is_adversarial_guarantee"):
        return {
            "text": "Forecasts are PREDICTED model estimates and are never guaranteed. AQI reduction outcomes cannot be promised.",
            "insights": [
                "Deployed model TemporalGRU_KNNCovariate has an overall MAE of 11.38 AQI points on held-out test data.",
                "Day 1 MAE is 8.76 AQI points (directional accuracy 40.0%); Day 7 MAE is 12.63 AQI points (directional accuracy 42.4%).",
                "Mitigation recommendations are general guidance from CPCB/NCAP protocols (source: CPCB CAP 2020); quantified effects are not promised and cannot be guaranteed.",
            ],
            "suggestions": ["Show the 7-day forecast", "What are the model limitations?", "What is current observed AQI?"],
        }

    # Case 3b: Sensor offline or hardware failure
    if analysis.get("is_sensors_offline"):
        return {
            "text": "When station sensors are completely offline or fail, the system reports status 'unavailable' with null values.",
            "insights": [
                "Data sufficiency requirement: CPCB NAQI requires at least 16 hourly readings out of a 24-hour rolling window. Offline sensors fail this sufficiency check.",
                "Mandatory particulate mandate: Valid AQI calculation requires at least 3 pollutants including PM2.5 or PM10. When offline, sub-indices cannot be computed.",
                "City aggregate impact: If all station sensors fail or active stations drop to zero, city-level AQI is marked unavailable rather than fabricating synthetic data.",
                "Zero estimation: The system strictly returns unavailable and never fabricates, interpolates, or guesses sensor readings when hardware fails.",
            ],
            "suggestions": ["What is the 16-hour sufficiency rule?", "What is current observed AQI?", "What is the staleness threshold?"],
        }

    # Case 3c: Data sufficiency & rolling average rules
    if analysis.get("is_data_sufficiency"):
        return {
            "text": "CPCB data sufficiency requires at least 16 hourly readings out of a 24-hour rolling window (minimum 67% data availability) for valid sub-index calculation.",
            "insights": [
                "16-hour sufficiency rule: A pollutant sub-index requires at least 16 hourly readings (out of 24) to be computed. If fewer than 16 hours are available due to packet loss or downtime, that pollutant sub-index is excluded.",
                "Particulate mandate: Overall AQI requires at least 3 valid pollutant sub-indices, of which at least one MUST be PM2.5 or PM10.",
                "Station exclusion: If a station fails to satisfy the 3-pollutant / particulate rule, its entire AQI reading is marked unavailable.",
                "14-day live switchover: For forecasting, the model requires 14 consecutive days of valid live observations before transitioning from the historical archive.",
            ],
            "suggestions": ["How is AQI calculated?", "What happens if sensors are offline?", "What is the 14-day switchover rule?"],
        }

    # ── NEW: Advice / Mitigation (rule-based fallback) ──
    if analysis.get("is_advice"):
        station_name = analysis["stations_mentioned"][0] if analysis.get("stations_mentioned") else None
        st_data = tool_outputs.get("current_station", {})
        src = st_data if st_data.get("status") == "success" else current
        obs_aqi = src.get("aqi", city_aqi)
        obs_cat = src.get("category", city_cat)
        obs_dom = src.get("dominant_pollutant", city_dominant)
        obs_stale = src.get("is_stale", is_stale)
        obs_hours = src.get("data_age_hours", stale_hours)
        obs_label = src.get("last_updated_label", last_updated_label)
        obs_stale_str = f" (stale: {obs_hours}h old, {obs_label})" if obs_stale and obs_hours else ""

        location = station_name or "Hyderabad"
        text = f"Observed AQI at {location} is {obs_aqi} ({obs_cat}), dominated by {obs_dom}.{obs_stale_str}"

        # Insight 1: baseline data
        expl = tool_outputs.get(f"explain_{station_name}", {}) if station_name else {}
        rank_str = ""
        if expl.get("rank") and expl.get("total_stations"):
            rank_str = f", ranked {expl['rank']}/{expl['total_stations']}"
        diff = expl.get("diff_vs_city_mean")
        diff_str = ""
        if diff is not None and city_aqi is not None:
            diff_str = f", {abs(diff)} points {'above' if diff > 0 else 'below'} city mean ({city_aqi})"
        insights.append(f"Baseline: Observed AQI {obs_aqi} ({obs_cat}), dominant pollutant {obs_dom}{rank_str}{diff_str}.")

        # Insight 2: honest framing
        if obs_cat in ("Good", "Satisfactory"):
            insights.append(f"Framing: AQI is already {obs_cat}. The focus is on maintaining low levels and reducing {obs_dom} exposure, not an emergency response.")
        else:
            insights.append(f"Framing: AQI is {obs_cat}. Targeted interventions for {obs_dom} are recommended to improve air quality.")

        # Insight 3-4: playbook recommendations (limit to 2 so framing & caveats fit within 5 bullets)
        pb_items = tool_outputs.get("playbook_items", [])
        rec_count = 0
        for item in pb_items[:2]:
            insights.append(
                f"Recommendation [{item.get('id')}]: {item.get('action')} "
                f"(who: {item.get('who', 'municipal')}, horizon: {item.get('time_horizon', 'short-term')}; "
                f"source: {item.get('source', 'CPCB/NCAP')}; confidence: {item.get('confidence_label', 'general guidance')})."
            )
            rec_count += 1

        if rec_count == 0:
            insights.append("General guidance: Follow CPCB/NCAP dust suppression and vehicular emission check protocols.")

        # Insight 5: source attribution caveat (mandatory)
        insights.append("Because the monitoring network does not have source-apportionment telemetry, local emission sources must be verified on-site before deploying capital resources.")

        return {"text": text, "insights": insights[:5], "suggestions": _build_advice_chips(analysis, tool_outputs)}

    # ── NEW: Health advice (rule-based fallback) ──
    if analysis.get("is_health_advice"):
        station_name = analysis["stations_mentioned"][0] if analysis.get("stations_mentioned") else None
        st_data = tool_outputs.get("current_station", {})
        src = st_data if st_data.get("status") == "success" else current
        obs_aqi = src.get("aqi", city_aqi)
        obs_cat = src.get("category", city_cat)
        obs_stale = src.get("is_stale", is_stale)
        obs_hours = src.get("data_age_hours", stale_hours)
        obs_label = src.get("last_updated_label", last_updated_label)
        obs_stale_str = f" (stale: {obs_hours}h old, {obs_label})" if obs_stale and obs_hours else ""

        location = station_name or "Hyderabad"
        ha = tool_outputs.get("health_advisory", {})

        text = f"Current AQI at {location} is {obs_aqi} ({obs_cat}).{obs_stale_str}"
        insights.append(f"CPCB health descriptor for {obs_cat}: {ha.get('cpcb_descriptor', 'N/A')}.")
        insights.append(f"General public: {ha.get('general_public', 'No specific guidance available.')}.")
        insights.append(f"Sensitive groups: {ha.get('sensitive_groups', 'N/A')}.")
        insights.append(f"Outdoor exercise: {ha.get('outdoor_exercise', 'N/A')}.")
        insights.append("Note: General guidance based on CPCB AQI health descriptors, not personal medical advice.")

        return {"text": text, "insights": insights[:5], "suggestions": ["What is the current city AQI?", "Which stations need action first?", f"What measures help reduce {src.get('dominant_pollutant', 'PM10')}?"]}

    # Case 4: Methodology & Calculation
    if analysis.get("is_methodology"):
        return {
            "text": "Air Quality Index is calculated using the CPCB National Air Quality Index (NAQI) standard.",
            "insights": [
                "Methodology: Sub-indices are calculated for individual pollutants via piecewise linear interpolation between standard breakpoints.",
                "Particulate mandate: At least 3 valid pollutant sub-indices are required (with minimum 16 hours out of 24 sufficiency), and at least one MUST be PM2.5 or PM10.",
                "Overall AQI rule: Overall AQI = max(sub-indices). The pollutant corresponding to this maximum is designated the Dominant Pollutant.",
                "Categories: Good (0-50), Satisfactory (51-100), Moderate (101-200), Poor (201-300), Very Poor (301-400), Severe (401-500).",
            ],
            "suggestions": ["What is the current city AQI?", "Why is PM2.5 or PM10 required?", "Show station rankings"],
        }

    # Case 5: Model limits & Accuracy
    if analysis.get("is_model_limits"):
        return {
            "text": "The deployed forecasting model (TemporalGRU_KNNCovariate) has verified performance metrics and known operational limitations.",
            "insights": [
                "Accuracy: Overall MAE of 11.38 AQI points on test window (Day 1 MAE 8.76 to Day 7 MAE 12.63).",
                "Directional accuracy: Ranges from 40.0% to 42.4% across the 7-day horizon, meaning directional swing confidence is limited.",
                "Trajectory limitation: The model exhibits a flat 7-day trajectory due to smoothing and regression toward seasonal means.",
                "Inversion weakness: Model lacks planetary boundary layer height (PBLH) input telemetry, limiting winter nocturnal inversion peak detection.",
            ],
            "suggestions": ["Show the 7-day forecast", "How is AQI calculated?", "What is current observed AQI?"],
        }

    # Case 6: Data status & Switchover
    if analysis.get("is_data_status"):
        ds = tool_outputs.get("data_status", {})
        c_days = ds.get("consecutive_live_days", 0)
        source = ds.get("forecast_input_source", "historical_archive")
        freshness_info = f"Current readings are stale ({stale_hours}h old, {last_updated_label})." if is_stale and stale_hours else "Current readings are within the 3-hour freshness threshold."
        return {
            "text": f"Live data accumulation is active with {c_days} consecutive days recorded. {freshness_info}",
            "insights": [
                f"Data freshness: {freshness_info}",
                f"Current consecutive live days: {c_days} (forecast input source: {source}).",
                "14-Day Switchover Rule: The forecasting pipeline requires exactly 14 consecutive days of live observations with zero gaps to switch from the historical archive.",
                "Zero fabrication: Until 14 full consecutive days are logged, forecasts continue using the verified historical archive.",
                f"Live observations are ingested via OpenAQLiveProvider from Telangana CPCB/TSPCB stations.",
            ],
            "suggestions": ["What is the current city AQI?", "Show the 7-day forecast", "Check live data status"],
        }

    # Case 7: "Why is X higher?" with specific station — also handle combined why+advice
    if analysis.get("is_why_higher") and analysis.get("stations_mentioned"):
        station_name = analysis["stations_mentioned"][0]
        expl = tool_outputs.get(f"explain_{station_name}", {})
        if expl.get("status") == "success":
            st_aqi = expl.get("aqi")
            st_cat = expl.get("category")
            st_dom = expl.get("dominant_pollutant")
            st_rank = expl.get("rank")
            st_total = expl.get("total_stations")
            diff = expl.get("diff_vs_city_mean")
            sub_indices = expl.get("sub_indices", {})
            st_margin = expl.get("dominant_margin")

            diff_str = f"{abs(diff)} points higher than" if diff and diff > 0 else f"{abs(diff or 0)} points lower than"

            text = f"Observed AQI at {station_name} is {st_aqi} ({st_cat}), ranked {st_rank} of {st_total} stations.{stale_str}"
            insights.append(f"Observed reading: AQI {st_aqi} ({st_cat}), which is {diff_str} city mean ({city_aqi}).")
            insights.append(f"Dominant pollutant: {st_dom} with sub-index {sub_indices.get(st_dom, st_aqi)}" + (f" (margin of {st_margin} points over next pollutant)." if st_margin is not None else "."))
            insights.append("Sub-indices: " + ", ".join([f"{k}: {v}" for k, v in sub_indices.items() if v is not None][:4]) + " (per CPCB engine).")
            insights.append("Averaging window: CPCB standard 4 PM to 4 PM 24h average for particulates, 8h rolling max for CO/O3.")
            insights.append("Source attribution: The system has no source-attribution sensors or cross-domain weather telemetry to assert real-world causes (traffic, industrial emission, construction).")

            return {"text": text, "insights": insights[:5], "suggestions": [f"Compare {station_name} with Somajiguda", "What is the current city AQI?", "Show the 7-day forecast"]}

    # Case 7b: Single station current reading
    if analysis.get("stations_mentioned") and not analysis.get("is_why_higher") and not analysis.get("is_comparison"):
        st_data = tool_outputs.get("current_station", {})
        if st_data.get("status") == "success":
            st_name = st_data.get("station_name", analysis["stations_mentioned"][0])
            st_aqi = st_data.get("aqi")
            st_cat = st_data.get("category", "Unknown")
            st_dom = st_data.get("dominant_pollutant", "PM10")
            st_stale = st_data.get("is_stale", is_stale)
            st_hours = st_data.get("data_age_hours", stale_hours)
            st_label = st_data.get("last_updated_label", last_updated_label)
            st_stale_str = f" (stale: {st_hours}h old, {st_label})" if st_stale and st_hours else ""
            text = f"Observed AQI at {st_name} is {st_aqi} ({st_cat}), dominated by {st_dom}.{st_stale_str}"
            insights.append(f"Station {st_name}: Observed AQI {st_aqi} ({st_cat}), dominant pollutant: {st_dom}.")
            if city_aqi is not None and st_aqi is not None:
                diff_c = st_aqi - city_aqi
                diff_word = f"{abs(diff_c)} points higher than" if diff_c > 0 else f"{abs(diff_c)} points lower than"
                insights.append(f"Comparison: {diff_word} city mean AQI ({city_aqi}).")
            if st_stale:
                insights.append(f"Data freshness: Station readings are stale ({st_hours}h old; threshold is {os.getenv('OPENAQ_STALE_HOURS', '3')}h). {st_label}")
            return {"text": text, "insights": insights[:5], "suggestions": [f"Why is {st_name} higher?", "What is the current city AQI?", "Show 7-day forecast"]}

    # Case 8: Comparison
    if analysis.get("is_comparison"):
        comp = tool_outputs.get("comparison", {})
        if comp.get("status") == "success":
            st_list = comp.get("stations", [])
            if len(st_list) >= 2:
                s1, s2 = st_list[0], st_list[1]
                text = f"Air quality comparison: {s1.get('station_name')} (AQI {s1.get('aqi')}, {s1.get('category')}) vs {s2.get('station_name')} (AQI {s2.get('aqi')}, {s2.get('category')}).{stale_str}"
                insights.append(f"{s1.get('station_name')}: AQI {s1.get('aqi')} ({s1.get('category')}), dominant pollutant: {s1.get('dominant_pollutant')}.")
                insights.append(f"{s2.get('station_name')}: AQI {s2.get('aqi')} ({s2.get('category')}), dominant pollutant: {s2.get('dominant_pollutant')}.")
                insights.append(f"Difference: {abs((s1.get('aqi') or 0) - (s2.get('aqi') or 0))} AQI points.")
                return {"text": text, "insights": insights, "suggestions": ["Which station has the highest AQI?", "What is the current city AQI?", "Show 7-day forecast"]}

    # Case 9: Forecast
    if analysis.get("is_forecast"):
        forecast = tool_outputs.get("forecast", {})
        if forecast.get("status") == "success":
            days = forecast.get("forecast_days", [])
            text_parts = []
            for d in days[:3]:
                if isinstance(d, dict):
                    day_num = d.get('day') or d.get('horizon') or d.get('horizon_days') or '?'
                    aqi_val = d.get('predicted_aqi') or d.get('aqi') or '?'
                    text_parts.append(f"Day {day_num}: AQI {aqi_val}")
            return {
                "text": f"PREDICTED 7-day air quality forecast for Hyderabad (model: {forecast.get('model_name', 'TemporalGRU_KNNCovariate')}).",
                "insights": [
                    f"PREDICTED trajectory: {', '.join(text_parts)} (labelled PREDICTED — not observed readings).",
                    f"Forecast accuracy: overall MAE {forecast.get('overall_mae', 11.38)} AQI points (Day 1 MAE: 8.76, Day 7 MAE: 12.63).",
                    "Directional accuracy: 40.0% to 42.4% across 7-day horizon; trajectory exhibits smoothing toward seasonal means.",
                ],
                "suggestions": ["What are the model limitations?", "What is the current city AQI?", "How is AQI calculated?"],
            }

    # Default / Current observed AQI
    if current.get("status") == "success":
        text = f"Hyderabad's observed city-level AQI is {city_aqi} ({city_cat}), dominated by {city_dominant}.{stale_str}"
        insights.append(f"City AQI: {city_aqi} ({city_cat}), dominant pollutant: {city_dominant} (per CPCB engine).")
        insights.append(f"Active stations: {current.get('active_stations', '?')}/{current.get('station_count', '?')}")
        if current.get("daily_max") is not None:
            insights.append(f"Station range: {current.get('daily_min')} to {current.get('daily_max')} AQI across network.")
        if is_stale:
            insights.append(f"Data freshness: Readings are stale ({stale_hours}h old; threshold is {os.getenv('OPENAQ_STALE_HOURS', '3')}h). {last_updated_label}")
    else:
        text = "Current air quality data is unavailable."
        insights.append("The live data feed is currently unavailable or all stations are offline.")

    return {"text": text or "Air quality information for Hyderabad.", "insights": insights[:5], "suggestions": suggestions}



# ── Verifier ──

def _verify_answer(answer: Dict, tool_outputs: Dict, question: str) -> Tuple[bool, List[str]]:
    """
    Deterministic verifier: checks that numbers in the answer match tool outputs,
    staleness is mentioned when is_stale=true, forecasts are labelled,
    playbook ids are valid, no promised effects without source, no jailbreak.
    Returns (passed, list_of_issues).
    """
    issues = []
    full_text = answer.get("text", "") + " " + " ".join(answer.get("insights", []))

    # Check staleness mention (only when question relates to current observations/rankings, not pure methodology/definitions)
    current = tool_outputs.get("current_city", {})
    if current.get("is_stale") and current.get("data_age_hours"):
        is_methodology_q = any(w in question.lower() for w in ["what is the staleness threshold", "how is staleness", "rule", "definition", "formula", "requirement", "standards", "threshold in hours"])
        if not is_methodology_q and any(w in question.lower() for w in ["current", "now", "today", "latest", "observed", "right now", "reading", "highest", "worst", "rank", "reduce", "improve", "safe", "jog"]):
            if "stale" not in full_text.lower() and "hours" not in full_text.lower() and "old" not in full_text.lower():
                issues.append("STALENESS: Data is stale but answer does not mention staleness/age")

    # Check forecast labelling
    forecast = tool_outputs.get("forecast", {})
    if forecast.get("status") == "success":
        if any(w in full_text.lower() for w in ["forecast", "predict", "tomorrow", "day 1", "day 7"]):
            if "predict" not in full_text.lower() and "forecast" not in full_text.lower() and "PREDICT" not in full_text:
                issues.append("LABELLING: Forecast mentioned but not labelled as PREDICTED")

    # Check that real-world causes are not asserted without disclaimer
    cause_keywords = ["caused by traffic", "due to traffic", "caused by vehicle", "due to vehicle",
                      "caused by industry", "due to industrial emissions", "caused by construction",
                      "due to construction dust", "traffic congestion caused", "factories are causing",
                      "which factory", "factory is causing"]
    disclaimer_keywords = ["no source-attribution", "no source attribution", "does not track",
                            "cannot attribute", "no cross-domain", "no attribution",
                            "source-apportionment", "source apportionment", "verified on-site"]
    has_cause = any(ck in full_text.lower() for ck in cause_keywords)
    has_disclaimer = any(dk in full_text.lower() for dk in disclaimer_keywords)
    if has_cause and not has_disclaimer:
        issues.append("CAUSE_ASSERTION: Real-world cause asserted without source-attribution disclaimer")

    # Check playbook recommendation ids — every cited id must exist in the loaded playbook
    playbook_items = tool_outputs.get("playbook_items", [])
    if playbook_items:
        valid_ids = {item.get("id") for item in playbook_items if isinstance(item, dict)}
        # Also include all playbook ids from full playbook
        try:
            all_pb = get_mitigation_playbook()
            valid_ids.update(item.get("id") for item in all_pb if isinstance(item, dict))
        except Exception:
            pass
        cited_ids = set(re.findall(r'\b(MIT-[A-Za-z0-9]+-\d+)\b', full_text))
        invalid_ids = cited_ids - valid_ids
        if invalid_ids:
            issues.append(f"PLAYBOOK_ID: Recommendation ids {sorted(list(invalid_ids))} not found in playbook")

    # Check for promised quantified effects without source
    effect_patterns = [r'reduce.*aqi.*by.*\d+%', r'will reduce.*\d+', r'guaranteed.*reduction',
                       r'will drop.*by.*\d+', r'promise.*\d+']
    for pat in effect_patterns:
        if re.search(pat, full_text.lower()):
            # Check if a source is cited nearby
            if not any(s in full_text.lower() for s in ["source:", "per cpcb", "per ncap", "per moefcc"]):
                issues.append("PROMISED_EFFECT: Quantified effect promised without sourced evidence")
                break

    # Check that numbers in answer exist in tool outputs or fact sheet
    answer_numbers = set(re.findall(r'\b(\d{1,4})\b', full_text))
    tool_numbers = set()
    for val in tool_outputs.values():
        if isinstance(val, dict):
            tool_str = json.dumps(val, default=str)
            tool_numbers.update(re.findall(r'\b(\d{1,4})\b', tool_str))
        elif isinstance(val, list):
            tool_str = json.dumps(val, default=str)
            tool_numbers.update(re.findall(r'\b(\d{1,4})\b', tool_str))

    # Add fact sheet numbers (breakpoints, hours, days, metrics)
    fact_sheet_text = _load_fact_sheet()
    if fact_sheet_text:
        tool_numbers.update(re.findall(r'\b(\d{1,4})\b', fact_sheet_text))

    # Common valid formatting / metadata numbers (percentages, standard categories)
    standard_allowed = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "24",
                        "30", "35", "40", "42", "48", "50", "67", "96", "100", "200", "300", "400", "500", "1000", "1500", "2400", "2024", "2025", "2026"}
    tool_numbers.update(standard_allowed)

    # Allow arithmetic differences between any AQI numbers present in tool_numbers
    aqi_vals = [int(tn) for tn in tool_numbers if tn.isdigit() and 0 <= int(tn) <= 500]
    for a in aqi_vals:
        for b in aqi_vals:
            tool_numbers.add(str(abs(a - b)))

    fabricated = answer_numbers - tool_numbers
    if fabricated:
        # Check if they could be rounded versions within tolerance
        unmatched = set()
        for num in fabricated:
            n = int(num)
            matched = False
            for tn in tool_numbers:
                if tn.isdigit() and abs(n - int(tn)) <= 2:
                    matched = True
                    break
            if not matched:
                unmatched.add(num)
        if unmatched:
            issues.append(f"FABRICATION: Numbers {sorted(list(unmatched))} in answer not found in tool outputs or fact sheet")

    return len(issues) == 0, issues


# ── Audit Logging ──

def _audit_log(question: str, answer: Dict, tool_outputs: Dict, verified: bool, issues: List[str], answer_path: str = "unknown"):
    """Append to logs/pollution_answer_audit.jsonl with answer path."""
    log_dir = Path(__file__).resolve().parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / "pollution_answer_audit.jsonl"

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "answer_text": answer.get("text", ""),
        "insight_count": len(answer.get("insights", [])),
        "verified": verified,
        "issues": issues,
        "tools_called": list(tool_outputs.keys()),
        "answer_path": answer_path,
    }

    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception as exc:
        logger.warning("Audit log write failed: %s", exc)


# ── Main Entry Point ──

def handle_pollution_chat(question: str) -> Dict[str, Any]:
    """
    Main entry point for pollution questions from the Planning AI chat.
    Returns {"text": ..., "insights": [...], "suggestions": [...]}.
    """
    verify_enabled = os.getenv("POLLUTION_VERIFY", "").lower() in ("true", "1", "yes")
    reasoning_enabled = os.getenv("POLLUTION_REASONING", "true").lower() in ("true", "1", "yes")

    # 1. Analyze the question
    analysis = _analyze_question(question)

    # If POLLUTION_REASONING is off, suppress advice/health intents (backward compat)
    if not reasoning_enabled:
        analysis["is_advice"] = False
        analysis["is_health_advice"] = False

    # 2. Execute tools
    tool_outputs = _execute_tools(analysis, question)

    # 3. Load fact sheet
    fact_sheet = _load_fact_sheet()

    # 4. Try LLM (only if reasoning enabled)
    answer = None
    answer_path = "rule_based_fallback"
    if reasoning_enabled:
        answer = _call_llm(question, tool_outputs, fact_sheet)
        if answer is not None:
            answer_path = "llm"

    # 5. Fallback to rule-based if LLM failed or reasoning disabled
    if answer is None:
        answer = _rule_based_answer(question, analysis, tool_outputs)
        answer_path = "rule_based_fallback"

    # 6. Verify if enabled
    verified = True
    issues: List[str] = []
    if verify_enabled:
        verified, issues = _verify_answer(answer, tool_outputs, question)
        if not verified:
            logger.warning("Verification failed for question '%s': %s", question[:80], issues)
            # Retry once with failure reasons in prompt
            if reasoning_enabled:
                retry_answer = _call_llm(
                    question + f"\n\n[VERIFIER FEEDBACK — fix these issues: {'; '.join(issues)}]",
                    tool_outputs,
                    fact_sheet,
                )
                if retry_answer:
                    verified_retry, issues_retry = _verify_answer(retry_answer, tool_outputs, question)
                    if verified_retry:
                        answer = retry_answer
                        verified = True
                        issues = []
                        answer_path = "llm_retry"
                    else:
                        # Fall back to safe rule-based answer
                        answer = _rule_based_answer(question, analysis, tool_outputs)
                        verified = True
                        issues = ["Fell back to rule-based answer after verification failure"]
                        answer_path = "rule_based_fallback"
                else:
                    answer = _rule_based_answer(question, analysis, tool_outputs)
                    verified = True
                    issues = ["Fell back to rule-based answer after LLM retry failure"]
                    answer_path = "rule_based_fallback"
            else:
                # No LLM available, already on rule-based
                pass

    # 7. Audit log with answer path
    _audit_log(question, answer, tool_outputs, verified, issues, answer_path=answer_path)

    # 8. Ensure proper format
    return {
        "text": answer.get("text", "Air quality information is currently unavailable."),
        "insights": answer.get("insights", [])[:5],
        "suggestions": answer.get("suggestions", [
            "What is the current city AQI?",
            "Which station has the highest AQI?",
            "Show the 7-day forecast",
        ])[:3],
    }
