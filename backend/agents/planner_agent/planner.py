"""
Core Planner Agent implementation for the SUPADSP Smart City platform.
Receives user natural-language queries, runs gatekeeping checks, extracts objectives,
generates structured execution plans, and performs result evaluation / dynamic re-planning.
Equipped with robust multi-recommendation synthesis and resilient rule-based semantic planning.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from backend.agents.planner_agent.llm_client import LLMClient
from backend.agents.planner_agent.prompts import (
    PLANNER_EVALUATION_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    build_evaluation_prompt,
)
from backend.agents.planner_agent.schema import (
    PlannerEvaluationResponse,
    PlannerResponse,
)

logger = logging.getLogger("planner_agent")

KNOWN_LOCATIONS = [
    "tarnaka", "narayanguda", "madhapur", "gachibowli", "financial district",
    "kukatpally", "secunderabad", "charminar", "nacharam", "begumpet",
    "jubilee hills", "sanathnagar", "miyapur", "lb nagar", "hitech city",
    "koti", "ameerpet", "banjara hills", "panjagutta", "somajiguda",
    "kondapur", "dilsukhnagar", "uppal", "kokapet"
]

DOMAIN_KEYWORDS = {
    "energy": [
        "energy", "power", "electricity", "grid", "substation", "transformer",
        "load", "consumption", "solar", "watt", "mwh", "mw", "voltage", "feeder",
        "peak shaving", "bess", "battery", "efficient", "efficiency"
    ],
    "traffic": [
        "traffic", "congestion", "speed", "vehicle", "jam", "signal", "corridor",
        "intersection", "flyover", "car", "delay", "queue", "route", "divergence"
    ],
    "pollution": [
        "pollution", "aqi", "air quality", "pm2.5", "pm10", "smoke", "emission",
        "pollutant", "smog", "carbon", "particulate"
    ],
    "weather": [
        "weather", "rain", "temperature", "forecast", "heatwave", "storm",
        "flood", "inundation", "precipitation", "wind"
    ],
    "simulation": [
        "simulation", "sumo", "simulate", "model", "scenario", "run simulation"
    ]
}


OUT_OF_SCOPE_PATTERNS = [
    "python", "java", "javascript", "c++", "golang", "ruby", "rust", "php",
    "code", "programming", "reverse a string", "reverse string", "function",
    "array", "linked list", "binary tree", "regex", "sql query", "html", "css",
    "capital of", "who is", "who won", "tell me a joke", "tell a joke",
    "recipe", "cook", "movie", "song", "meaning of life", "how to make",
    "write an essay", "translate", "poem", "story", "crypto", "bitcoin",
    "stock market", "diet", "gym", "horoscope", "dating"
]


def is_out_of_scope_query(text: str) -> bool:
    """Check if query is explicitly asking for general programming, trivia, or non-smart-city topics."""
    lower = text.lower().strip()
    
    # Direct match against out-of-scope patterns
    for pattern in OUT_OF_SCOPE_PATTERNS:
        if pattern in lower:
            # If it's a coding or trivia query and doesn't explicitly talk about smart city power/traffic/pollution
            has_smart_city_keyword = any(
                kw in lower for d in DOMAIN_KEYWORDS for kw in DOMAIN_KEYWORDS[d]
            )
            if not has_smart_city_keyword:
                return True
    return False


def extract_location_from_text(text: str) -> Optional[str]:
    """Extract known Hyderabad location from text."""
    lower = text.lower()
    for loc in KNOWN_LOCATIONS:
        if loc in lower:
            return loc.title() + ", Hyderabad"
    return None


def detect_domain_from_text(text: str) -> Optional[str]:
    """Detect most prominent domain from text. Returns None if query matches no domain."""
    lower = text.lower()
    scores: Dict[str, int] = {d: 0 for d in DOMAIN_KEYWORDS}
    for domain, kw_list in DOMAIN_KEYWORDS.items():
        for kw in kw_list:
            if kw in lower:
                scores[domain] += 1
    best_domain = max(scores, key=scores.get)
    if scores[best_domain] > 0:
        return best_domain
    return None


def rule_based_plan(user_query: str) -> PlannerResponse:
    """Resilient rule-based planner fallback and gatekeeper when LLM is unavailable."""
    # 1. Gatekeeping check for irrelevant / out-of-scope queries
    if is_out_of_scope_query(user_query):
        return PlannerResponse(
            relevant=False,
            domain=None,
            objective=None,
            plan=[],
            response="This query is outside the scope of the SUPADSP Smart City Decision Support System. Supported domains include: Traffic & Mobility, Smart Energy Grid, Air Quality & Pollution, and Weather & Stormwater Management."
        )

    domain = detect_domain_from_text(user_query)
    location = extract_location_from_text(user_query)

    # If no domain matched and no known location was found, reject as out-of-scope
    if domain is None and location is None:
        return PlannerResponse(
            relevant=False,
            domain=None,
            objective=None,
            plan=[],
            response="This question is outside the scope of the Smart City system. Please submit an inquiry regarding traffic, energy grid, air quality, or flood management in Hyderabad."
        )

    # Fallback to traffic domain if location is specified but domain was implicit
    domain = domain or "traffic"
    location = location or "Hyderabad Metro Region"

    if domain == "energy":
        plan_steps = [
            f"Retrieve real-time substation load telemetry for {location}",
            "Analyze transformer stress and diurnal peak curve",
            "Synthesize peak shaving, demand response, and solar integration recommendations"
        ]
        objective = f"Optimize power consumption and energy efficiency in {location}"
    elif domain == "pollution":
        plan_steps = [
            f"Query TSPCB air quality sensor telemetry for {location}",
            "Analyze PM2.5 and PM10 particulate dispersion",
            "Generate localized emission mitigation policy"
        ]
        objective = f"Mitigate air quality and pollution levels in {location}"
    elif domain == "weather":
        plan_steps = [
            f"Fetch meteorological telemetry and precipitation forecast for {location}",
            "Assess urban heatwave or flood inundation risks",
            "Formulate municipal weather advisory"
        ]
        objective = f"Assess weather impact and environmental risks in {location}"
    else:
        plan_steps = [
            f"Collect traffic sensor volume and corridor speed data for {location}",
            "Evaluate bottleneck intersections and queue lengths",
            "Recommend adaptive signal timing overrides"
        ]
        objective = f"Mitigate vehicle congestion and improve flow in {location}"

    return PlannerResponse(
        relevant=True,
        domain=domain,
        objective=objective,
        plan=plan_steps,
        response=None
    )


class PlannerAgent:
    """
    Planner Agent acts as the front gatekeeper, strategic planning brain, and re-planning engine.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        if llm_client is not None:
            self.llm_client = llm_client
        else:
            try:
                self.llm_client = LLMClient()
            except Exception as exc:
                logger.info(f"LLMClient initialized without external API key: {exc}")
                self.llm_client = None

    def plan(self, user_query: str) -> PlannerResponse:
        """
        Process a user query and return a validated PlannerResponse.
        """
        if not user_query or not user_query.strip():
            return PlannerResponse(
                relevant=False,
                response="Please provide a valid query or description of the urban situation.",
            )

        sanitized_query = user_query.strip()

        # 1. Try LLM if available
        if self.llm_client is not None:
            try:
                raw_json_str = self.llm_client.generate_json_plan(
                    system_prompt=PLANNER_SYSTEM_PROMPT,
                    user_query=sanitized_query,
                )
                parsed_dict = json.loads(raw_json_str)
                validated_response = PlannerResponse.model_validate(parsed_dict)
                return validated_response
            except Exception as exc:
                logger.warning(f"LLM plan generation failed, switching to semantic rule-based planner: {exc}")

        # 2. Resilient Rule-Based Semantic Plan Fallback
        return rule_based_plan(sanitized_query)

    def evaluate_and_replan(
        self,
        objective: str,
        plan: List[str],
        collected_results: Dict[str, Any],
        failures: Optional[Dict[str, Any]] = None,
    ) -> PlannerEvaluationResponse:
        """
        Evaluate specialist agent telemetry against the original objective and synthesize multiple actionable recommendations.
        """
        eval_prompt = build_evaluation_prompt(
            objective=objective,
            plan=plan,
            collected_results=collected_results,
            failures=failures or {},
        )

        if self.llm_client is not None:
            try:
                raw_json_str = self.llm_client.generate_json_plan(
                    system_prompt=PLANNER_EVALUATION_SYSTEM_PROMPT,
                    user_query=eval_prompt,
                )
                parsed_dict = json.loads(raw_json_str)
                return PlannerEvaluationResponse.model_validate(parsed_dict)
            except Exception as exc:
                logger.warning(f"LLM evaluation failed, using dynamic multi-recommendation synthesis: {exc}")

        # Multi-Recommendation Dynamic Synthesis
        has_failures = bool(failures and not collected_results)
        recommendations_list: List[str] = []
        analysis_text = "Evaluated with collected specialist telemetry."

        if "energy" in collected_results:
            energy_data = collected_results["energy"]
            load_pct = energy_data.get("load_pct", 78.0)
            current_mw = energy_data.get("current_load_mw", 4000.0)
            loc = energy_data.get("location", "Hyderabad")
            substations = energy_data.get("substations", [])
            sub_names = [s.get("name") for s in substations if isinstance(s, dict)]
            primary_sub = sub_names[0] if sub_names else f"{loc} Substation"
            agent_recs = energy_data.get("recommendations", [])

            if agent_recs and isinstance(agent_recs, list) and len(agent_recs) >= 3:
                recommendations_list = []
                for idx, r in enumerate(agent_recs, 1):
                    if isinstance(r, dict):
                        title = r.get("title", "")
                        impact = r.get("impact", "")
                        priority = r.get("priority", "MEDIUM")
                        savings = r.get("estimated_savings_mw")
                        savings_str = f" (Est. {savings} MW savings)" if savings else ""
                        recommendations_list.append(f"{idx}. [{priority}] {title}: Expected impact {impact}{savings_str}.")
                    elif isinstance(r, str):
                        recommendations_list.append(f"{idx}. {r}")
            else:
                recommendations_list = [
                    f"1. [HIGH] Demand Response & Peak Shaving: Shift non-critical industrial & commercial HVAC loads away from the evening peak window (18:00–21:30) to reduce stress on {primary_sub} (Est. 12–18% load reduction).",
                    f"2. [HIGH] Rooftop Solar & Microgrid Offsets: Integrate solar-assisted microgrid power on institutional, commercial, and government buildings across {loc} to buffer midday transformer draw (Est. 15–20% peak offset).",
                    f"3. [MEDIUM] Dynamic Street-Lighting Dimming: Implement automated LED dimming schedules calibrated with traffic flow volume after 22:00 (Est. 10–15% municipal energy savings).",
                    f"4. [HIGH] Battery Energy Storage (BESS) Dispatch: Discharge localized 20–40 MWh BESS battery packs during peak transformer load hours to avoid feeder line tripping.",
                    f"5. [MEDIUM] Smart EV Fast-Charging Modulation: Dynamically throttle high-power DC fast-charging hubs during critical load alerts (load > 85%) to prevent feeder congestion."
                ]
            analysis_text = f"Energy Agent monitored {len(substations)} substation nodes ({', '.join(sub_names[:3])}) for {loc}. Current load: {load_pct}% ({current_mw} MW), Status: {energy_data.get('severity', 'NORMAL')}."

        elif "traffic" in collected_results:
            traffic_data = collected_results["traffic"]
            speed = traffic_data.get("average_speed_kmh", 23.6)
            congestion = traffic_data.get("congestion_index", 68.2)
            recommendations_list = [
                "1. [HIGH] Adaptive Signal Cycle Timing: Extend green phase allocations by +25s at primary bottleneck intersections to clear queue spillbacks.",
                "2. [HIGH] Dynamic Route Divergence: Display automated variable message signs (VMS) directing vehicles toward the Outer Ring Road corridor.",
                "3. [MEDIUM] Dedicated Reversible Lane Control: Allocate dynamic reversible lanes during peak morning and evening directional flows.",
                "4. [HIGH] Public Transit Priority Dispatch: Increase Metro & feeder shuttle frequency to 3-minute headways to reduce private vehicle ingress.",
                "5. [MEDIUM] Intelligent Incident Clearance: Dispatch rapid-response towing units to high-risk arterial junctions."
            ]
            analysis_text = f"Traffic Agent monitored active vehicles ({traffic_data.get('active_vehicles', 2342)}). Congestion severity: {congestion}%."

        elif "pollution" in collected_results:
            poll_data = collected_results["pollution"]
            aqi = poll_data.get("city_avg_aqi", 136)
            pollutant = poll_data.get("primary_pollutant", "PM2.5")
            recommendations_list = [
                "1. [CRITICAL] Industrial Emission Buffering: Enforce temporary capacity throttling on heavy industrial boilers during low wind dispersion hours.",
                "2. [HIGH] Anti-Smog Cannon Deployment: Dispatch automated mist cannons and water sprinklers at high-density road intersections.",
                "3. [HIGH] Heavy Commercial Vehicle Diversion: Reroute non-essential BS-IV diesel freight trucks around the outer perimeter bypass.",
                "4. [MEDIUM] Traffic Anti-Idling Signal Synchronization: Synchronize signal progression in high AQI corridors to minimize stop-and-go emissions.",
                "5. [MEDIUM] Urban Bio-Filter Activation: Activate roadside vertical green bio-filtration arrays."
            ]
            analysis_text = f"Pollution Agent reported AQI {aqi} ({poll_data.get('category', 'MODERATE')})."

        elif "weather" in collected_results:
            weather_data = collected_results["weather"]
            temp = weather_data.get("temperature_c", 32.0)
            rain = weather_data.get("rain_mm", 0.0)
            recommendations_list = [
                "1. [CRITICAL] Auxiliary Stormwater Pump Activation: Engage high-capacity stormwater pumps at vulnerable low-lying underpasses.",
                "2. [HIGH] Automated Underpass Barrier Gate Deployment: Close flooded underpass approaches to prevent stranded vehicles.",
                "3. [HIGH] Hydro-Meteorological Advisory Broadcast: Push localized weather alerts to civic notification networks and navigation systems.",
                "4. [MEDIUM] Retention Basin Sluice Gate Adjustment: Regulate urban lake discharge rates to optimize drainage throughput.",
                "5. [MEDIUM] Emergency Municipal Crew Pre-positioning: Station emergency response teams at known inundation hotspots."
            ]
            analysis_text = f"Weather Agent recorded temp: {temp}°C, rain: {rain} mm/hr."

        else:
            recommendations_list = [
                "1. [HIGH] Multi-Domain Operational Tuning: Synchronize traffic signals with street lighting dimming offsets.",
                "2. [HIGH] Substation Peak Balancing: Re-route feeder lines from high-stress nodes to adjacent under-utilized substations.",
                "3. [MEDIUM] Dynamic Congestion Diversion: Broadcast detour routes via digital variable message signs.",
                "4. [MEDIUM] Battery Storage Grid Support: Stand by 20 MWh battery storage assets for frequency stabilization.",
                "5. [MEDIUM] Automated Real-Time Monitoring: Maintain automated 5-minute telemetry polling cycle across all sensor nodes."
            ]

        final_rec_formatted = "\n\n".join(recommendations_list)

        return PlannerEvaluationResponse(
            goal_achieved=not has_failures,
            decision="HANDLE_AGENT_FAILURES" if has_failures else "PROCEED_TO_RECOMMENDATION",
            analysis=analysis_text if not has_failures else "Agent telemetry collection encountered errors.",
            final_recommendation=final_rec_formatted if not has_failures else None,
            revised_plan=["Retry telemetry retrieval", "Check connectivity"] if has_failures else [],
            confidence=0.95 if not has_failures else 0.5,
        )


# Default factory function
def get_planner_agent() -> PlannerAgent:
    return PlannerAgent()
