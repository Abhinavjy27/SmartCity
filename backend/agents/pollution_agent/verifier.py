import json

VERIFIER_PROMPT = """You are a strict fact-checker. Compare the DRAFT with POLLUTION_FACTS, POLLUTION_REFERENCE and TOOL_RESULTS. Check: (1) every number, threshold, category, station, date, regulation and performance figure is supported; (2) observed vs forecast labelling is correct; (3) no AQI was computed outside a compute_aqi result; (4) statements not in the sources are labelled "General knowledge" or "General consideration" and contain no numbers, thresholds, laws, dates or statistics; (5) no claim about other domains the sources don't support; (6) archived data is never described as real-time, live, current or "today", and forecasts carry their error and test period; (7) trend words (rising, falling, spike) are backed by the trend rule; (8) coverage and scope claims are correct (Hyderabad only; no data for water, noise, soil, other cities, dates outside the archive); (9) the first sentence or bullet answers the question asked and nothing unrelated is included; (10) format: intro <= 2 sentences, 3-5 bullets of <= 25 words, exactly 3 chips of <= 6 words, no what-if chips.
Return ONLY JSON: {"verdict": "pass"|"revise"|"fail", "unsupported_claims": [], "mislabeled_data_type": [], "currency_violations": [], "coverage_errors": [], "off_topic_content": [], "format_violations": [], "feedback_for_rewrite": "short, specific instructions"}
Be conservative: if a claim can't be confirmed in the sources, list it."""

def verify_draft(draft_json: dict, kb_data: str, tool_data: str) -> dict:
    """
    In production, this would call the LLM with VERIFIER_PROMPT.
    Currently stubbed out due to no LLM key for robust multi-turn verification.
    """
    # Stub logic for test
    if "live" in draft_json.get("intro", "").lower() or "today" in draft_json.get("intro", "").lower():
        return {
            "verdict": "revise",
            "currency_violations": ["Used 'live' or 'today' for archived data"],
            "feedback_for_rewrite": "Remove 'live' and use 'latest archived observation'."
        }
    return {
        "verdict": "pass"
    }

def run_verifier_test():
    stub_draft_bad = {"intro": "The live AQI today is 136.", "key_insights": [], "chips": []}
    stub_draft_good = {"intro": "The latest archived observation (2025-12-31) AQI is 136.", "key_insights": [], "chips": []}
    print("Testing stub verifier...")
    print("Bad draft verdict:", verify_draft(stub_draft_bad, "", "")["verdict"])
    print("Good draft verdict:", verify_draft(stub_draft_good, "", "")["verdict"])

if __name__ == "__main__":
    run_verifier_test()
