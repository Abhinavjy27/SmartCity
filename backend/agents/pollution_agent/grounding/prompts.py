"""
Pollution Domain Prompt & Intent Classifier — for the Planning AI air quality module.
Injected into the LLM call when a pollution/air-quality question is detected.
Temperature: 0.1 (near-deterministic).
"""
import re

POLLUTION_DOMAIN_PROMPT = """You are the **Air Quality Intelligence & Advisory Module** within the SUPADSP Smart City Planning AI.
You answer questions about Hyderabad's air quality, diagnostics, and mitigation interventions using ONLY the tool outputs, verified playbook, and fact sheet provided below.

## STRICT INVARIANTS

1. **Numbers come from tools only.** Every AQI value, sub-index, concentration, forecast number,
   and station metric MUST come from the tool output or fact sheet provided.
   You MUST NOT compute, estimate, interpolate, or fabricate any number.

2. **Cite sources inline** (lightly). Example: "per live reading, Nacharam PM2.5 sub-index 142"
   or "per CPCB engine", or "per CPCB CAP guidelines".

3. **Observed vs Predicted**: Always label. Observations say "observed" or "live reading".
   Forecasts say "PREDICTED" and include the horizon MAE when relevant.
   Never present a forecast number as an observation.

4. **Staleness**: If the data has is_stale=true, you MUST state the data_age_hours and
   last_updated_label in your answer. Example: "Note: this reading is stale (42h old, last
   updated 2026-09-30 06:00 UTC)."

5. **"Why is X higher?" diagnostics** — follow this order:
   (a) The observed fact with timestamp and staleness status
   (b) DATA-SUPPORTED drivers ONLY: dominant pollutant and its sub-index, comparison baseline
       stated explicitly (vs city mean / other stations / own previous day), data-quality caveats
   (c) Real-world causes (traffic, industry, construction, weather) are NEVER asserted without disclaimer.
       The system has no source-apportionment sensors. Always include a disclaimer:
       "The system has no source-attribution sensors or cross-domain weather telemetry to assert real-world causes."

6. **Advice, Mitigation & Recommendations** — follow this strict structure:
   (a) Intro: Direct answer to the question with the observed reading, dominant pollutant, timestamp, and staleness age.
   (b) Key Insights:
       1. Baseline data: State observed AQI, category, dominant pollutant, and margin/rank vs city mean.
       2. Honest framing: If AQI is already Good or Satisfactory, state that reduction is about maintenance and preventing deterioration, not an emergency.
       3. Prioritized recommendations: Pick 2 to 4 interventions EXCLUSIVELY from the provided Playbook items (cite item id, action, who, and time horizon). Do NOT invent any action outside the playbook.
       4. Source attribution caveat: State explicitly: "Because the monitoring network does not have source-apportionment telemetry, local emission sources must be verified on-site before deploying capital resources."
       5. Staleness caveat: If reading is >3h old, highlight data age.
   (c) Never promise effects: Do NOT claim "this will reduce AQI by X%" unless an explicit percentage is cited from a named playbook source.

7. **Public Health Advice**:
   (a) Base health guidance strictly on official CPCB category descriptors (e.g., Good: minimal impact; Moderate: breathing discomfort to sensitive groups).
   (b) Always add disclaimer: "Note: General guidance based on CPCB AQI health descriptors, not personal medical advice."

8. **Unavailable data & Unknown stations**:
   - If a tool returns "unavailable", state what is unavailable and why. Never guess.
   - If station resolver returns found=false, say the station is unmonitored and list known stations.

9. **Qwen Thinking**: Never output `<think>...</think>` tags in your final answer.

## OUTPUT FORMAT

You MUST return a JSON object with exactly these fields:
```json
{
  "text": "<intro sentence summarizing the answer>",
  "insights": ["<bullet 1>", "<bullet 2>", "<bullet 3>"],
  "suggestions": ["<follow-up chip 1>", "<follow-up chip 2>", "<follow-up chip 3>"]
}
```

- `text`: A concise intro sentence (1-2 sentences max).
- `insights`: 2-5 bullet points with key facts/playbook recommendations.
- `suggestions`: Exactly 3 follow-up question chips that make sense given the data (e.g. if below city mean, do not ask 'why is it higher').

Output ONLY the JSON object. No markdown wrapping, no explanation outside the JSON.
"""

# Keywords indicating advice / mitigation / intervention / causal intent
ADVICE_KEYWORDS = [
    "reduce", "lower", "improve", "control", "cut", "fix", "bring down",
    "what can be done", "what can we do", "what should we do", "what to do",
    "what can the city do", "what actions", "actions can", "suggest",
    "suggest measures", "suggest actions", "recommend", "recommendations",
    "solutions", "mitigate", "mitigation", "measures", "measure",
    "preventive", "prevention", "action plan", "steps should", "what steps",
    "steps to", "how can we", "why", "cause", "source", "reasons", "reason for",
    "maintain", "maintaining", "keep", "upay", "upaye", "kaise kam kare",
    "kaise kam karein", "kaise sudhare", "sudhare", "kaise kam hoga",
    "kya karna chahiye", "kya kare", "kya karein", "how to redue",
    "how to reudce", "how to improv", "mitigtion", "recommed",
    "recomended", "sugest", "measurs"
]

# Keywords indicating public health advice intent
HEALTH_ADVICE_KEYWORDS = [
    "is it safe to", "safe to jog", "safe to run", "safe to walk", "safe to do", "safe for children",
    "safe for elderly", "safe for asthma", "safe for", "wear a mask", "should i wear a mask",
    "outdoor activity", "outdoor sports", "morning walk", "health advice", "health advisory", "mask pehne",
    "safe hai kya", "health impact", "exercise outside", "jogging", "jog", "cycling", "cycling outside",
    "sports", "exercise"
]

# Keywords that indicate a pollution/air-quality question
POLLUTION_KEYWORDS = [
    "aqi", "air quality", "pollution", "pollutant", "pm2.5", "pm10", "pm 2.5", "pm 10",
    "smog", "emission", "particulate", "air index",
    "so2", "no2", "co ", "o3", "ozone", "carbon monoxide", "nitrogen dioxide",
    "sulfur dioxide", "ammonia", "nh3",
    "nacharam", "sanathnagar", "bollaram", "zoo park", "somajiguda", "kokapet",
    "kompally", "icrisat", "patancheru", "ecil", "kapra", "malakpet", "central university",
    "ramachandrapuram", "ida pashamylaram", "kukatpally", "banjara hills", "secunderabad",
    "cpcb", "tspcb", "naqi", "sub-index", "sub index", "sub-indices", "sub indices", "breakpoint", "caaqms",
    "7-day forecast", "7 day forecast", "forecast model", "forecast accuracy", "forecast mae", "forecast trajectory", "forecast window",
    "forecast for hyderabad", "forecasted aqi", "predicted aqi", "air quality forecast", "model forecast", "forecast numbers",
    "trajectory", "mae", "rmse", "temporalgru", "pblh", "inversion",
    "model accuracy", "directional accuracy", "model limits", "held-out test",
    "dominant pollutant", "air monitoring", "station aqi", "all stations", "monitoring station",
    "which station", "worst station", "cleanest station", "station is worst", "station is cleanest", "station is highest", "worst right now",
    "stale reading", "data freshness", "live data status", "switchover", "switch over", "consecutive days",
    "data sufficiency", "sufficiency", "accumulation", "accumulated", "packet loss", "hourly reading", "16 hour", "hours old",
    "is the air", "air today", "breathing", "inhale", "sensor", "sensors", "offline", "online", "openaq", "archive", "live data",
    "staleness", "staleness threshold", "observation", "observations", "provider", "ingests",
] + ADVICE_KEYWORDS + HEALTH_ADVICE_KEYWORDS

NON_POLLUTION_EXCLUSIONS = [
    "rainfall", "rain", "wind speed", "precipitation", "power grid", "substation",
    "traffic signal", "signal timing", "vehicles/hour", "streetlights",
]


def is_pollution_question(text: str) -> bool:
    """Check if a question is about pollution/air quality."""
    ql = text.lower().strip()
    has_explicit_air = any(w in ql for w in ["aqi", "air quality", "pollution", "pollutant", "pm2.5", "pm10", "pm 2.5", "pm 10"])
    if any(ex in ql for ex in NON_POLLUTION_EXCLUSIONS) and not has_explicit_air:
        return False
    return any(kw in ql for kw in POLLUTION_KEYWORDS)


def is_advice_question(text: str) -> bool:
    """Check if question asks for recommendations, mitigation, or reduction actions."""
    ql = text.lower().strip()
    return any(w in ql for w in ADVICE_KEYWORDS)


def is_health_advice_question(text: str) -> bool:
    """Check if question asks for health, safety, mask, or exercise advice."""
    ql = text.lower().strip()
    return any(w in ql for w in HEALTH_ADVICE_KEYWORDS)
