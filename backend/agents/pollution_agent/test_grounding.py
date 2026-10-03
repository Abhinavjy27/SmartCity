"""
Unit tests for Pollution Agent Grounding & Verification subsystem.

Covers:
1. Tool execution and output schemas (get_current, explain_station_aqi, compare_stations, get_forecast, get_data_status, compute_aqi)
2. Station resolver (exact match, alias match, fuzzy match threshold 0.75, unknown/unmonitored locations)
3. Deterministic Verifier (_verify_answer: numbers check, staleness enforcement, forecast labelling, causal assertion disclaimer)
4. Domain detection & Prompt routing (is_pollution_question, non-pollution queries)
5. Fallback & Safe Handling (when LLM unavailable or flag off)
"""

import pytest
import os
import json
from unittest.mock import patch, MagicMock

from backend.agents.pollution_agent.grounding.tools import (
    resolve_station,
    get_current,
    explain_station_aqi,
    compare_stations,
    get_forecast,
    get_data_status,
    compute_aqi,
    TOOLS,
)
from backend.agents.pollution_agent.grounding.prompts import is_pollution_question
from backend.agents.pollution_agent.grounding.handler import (
    _analyze_question,
    _verify_answer,
    _rule_based_answer,
    handle_pollution_chat,
)


# ==============================================================================
# 1. Station Resolver Tests
# ==============================================================================

class TestStationResolver:
    def test_exact_match(self):
        res = resolve_station("Zoo Park")
        assert res["found"] is True
        assert res["station_name"] == "Zoo Park"

    def test_alias_match(self):
        res = resolve_station("Sanath Nagar")
        assert res["found"] is True
        assert res["station_name"] == "Sanathnagar"

    def test_case_insensitivity(self):
        res = resolve_station("bollaram industrial")
        assert res["found"] is True
        assert res["station_name"] == "Bollaram Industrial"

    def test_fuzzy_match_above_threshold(self):
        res = resolve_station("Kompally")
        assert res["found"] is True
        assert res["station_name"] == "Kompally Municipal"

    def test_unmonitored_station_rejected(self):
        # Kukatpally should not falsely match Kompally (similarity ratio ~0.67 < 0.75)
        res = resolve_station("Kukatpally")
        assert res["found"] is False
        assert "Kompally Municipal" in res["known_stations"]

    def test_completely_unknown_location(self):
        res = resolve_station("Antarctica Station")
        assert res["found"] is False
        assert len(res["known_stations"]) > 0


# ==============================================================================
# 2. Tool Execution Schema Tests
# ==============================================================================

class TestTools:
    def test_compute_aqi_deterministic(self):
        pollutants = {"PM2.5": 45.0, "PM10": 85.0, "NO2": 22.0}
        res = compute_aqi(pollutants)
        assert "aqi" in res
        assert "dominant_pollutant" in res
        assert res["aqi"] is not None

    def test_get_current_schema(self):
        res = get_current()
        assert res["status"] in ("success", "unavailable")
        assert "type" in res
        assert res["type"] == "observed"
        if res["status"] == "success":
            assert "aqi" in res
            assert "dominant_pollutant" in res
            assert "active_stations" in res
            assert "is_stale" in res

    def test_explain_station_aqi(self):
        res = explain_station_aqi("Zoo Park")
        assert res["status"] in ("success", "unavailable")
        if res["status"] == "success":
            assert res["station_name"] == "Zoo Park"
            assert "sub_indices" in res
            assert "dominant_pollutant" in res

    def test_compare_stations(self):
        res = compare_stations("Zoo Park", "Sanathnagar")
        assert res["status"] in ("success", "unavailable")
        if res["status"] == "success":
            assert "stations" in res
            assert len(res["stations"]) == 2

    def test_get_forecast_schema(self):
        res = get_forecast(horizon=7)
        assert res["status"] in ("success", "unavailable")
        if res["status"] == "success":
            assert res["type"] == "PREDICTED"
            assert "PREDICTED" in res["label"]
            assert "model_name" in res
            assert "forecast_days" in res
            assert "overall_mae" in res

    def test_get_data_status_schema(self):
        res = get_data_status()
        assert "consecutive_live_days" in res
        assert "forecast_input_source" in res


# ==============================================================================
# 3. Deterministic Verifier Tests
# ==============================================================================

class TestVerifier:
    def test_fabrication_detection(self):
        # Answer contains fabricated number '9999' not present in tools or fact sheet
        tool_outputs = {"current_city": {"aqi": 87, "dominant_pollutant": "PM10", "is_stale": False}}
        answer = {
            "text": "The AQI is 9999 today.",
            "insights": ["Unverified concentration is 8888."],
            "suggestions": [],
        }
        passed, issues = _verify_answer(answer, tool_outputs, "What is current AQI?")
        assert passed is False
        assert any("FABRICATION" in iss for iss in issues)

    def test_staleness_enforcement(self):
        # Data is stale, but answer omits stale/hours/age
        tool_outputs = {
            "current_city": {
                "aqi": 87,
                "dominant_pollutant": "PM10",
                "is_stale": True,
                "data_age_hours": 64.0,
            }
        }
        answer = {
            "text": "Hyderabad observed city-level AQI is 87.",
            "insights": ["Dominant pollutant is PM10."],
            "suggestions": [],
        }
        passed, issues = _verify_answer(answer, tool_outputs, "What is current AQI right now?")
        assert passed is False
        assert any("STALENESS" in iss for iss in issues)

    def test_staleness_satisfied(self):
        # Data is stale and answer explicitly mentions staleness
        tool_outputs = {
            "current_city": {
                "aqi": 87,
                "dominant_pollutant": "PM10",
                "is_stale": True,
                "data_age_hours": 64.0,
            }
        }
        answer = {
            "text": "Hyderabad observed city-level AQI is 87 (stale: 64.0 hours old).",
            "insights": ["Readings are stale by 64.0 hours."],
            "suggestions": [],
        }
        passed, issues = _verify_answer(answer, tool_outputs, "What is current AQI right now?")
        assert passed is True
        assert len(issues) == 0

    def test_causal_assertion_rejected_without_disclaimer(self):
        tool_outputs = {"current_city": {"aqi": 87, "dominant_pollutant": "PM10"}}
        answer = {
            "text": "AQI is 87 caused by traffic congestion on the corridor.",
            "insights": [],
            "suggestions": [],
        }
        passed, issues = _verify_answer(answer, tool_outputs, "Why is AQI high?")
        assert passed is False
        assert any("CAUSE_ASSERTION" in iss for iss in issues)

    def test_causal_assertion_accepted_with_disclaimer(self):
        tool_outputs = {"current_city": {"aqi": 87, "dominant_pollutant": "PM10"}}
        answer = {
            "text": "AQI is 87. The system cannot attribute cause to traffic as there are no source-attribution sensors.",
            "insights": [],
            "suggestions": [],
        }
        passed, issues = _verify_answer(answer, tool_outputs, "Why is AQI high?")
        assert passed is True


# ==============================================================================
# 4. Domain & Question Analysis Tests
# ==============================================================================

class TestDomainAnalysis:
    def test_is_pollution_question_keywords(self):
        assert is_pollution_question("Why is the AQI higher in Nacharam?") is True
        assert is_pollution_question("What is the PM2.5 level right now?") is True
        assert is_pollution_question("Show the 7-day pollution forecast") is True
        assert is_pollution_question("Explain CPCB NAQI breakpoints") is True

    def test_is_not_pollution_question(self):
        assert is_pollution_question("Optimize the traffic light timings on Corridor 4") is False
        assert is_pollution_question("What is the peak energy demand today?") is False
        assert is_pollution_question("Show tomorrow's rain forecast") is False

    def test_analyze_question_routing(self):
        analysis = _analyze_question("Why is the AQI higher in Zoo Park?")
        assert "Zoo Park" in analysis["stations_mentioned"]
        assert analysis["is_why_higher"] is True

        analysis_out = _analyze_question("What is the air quality in Delhi?")
        assert analysis_out["is_out_of_scope"] is True

        analysis_offline = _analyze_question("What if a station sensor is completely offline?")
        assert analysis_offline["is_sensors_offline"] is True

        analysis_suff = _analyze_question("What is the CPCB data sufficiency requirement?")
        assert analysis_suff["is_data_sufficiency"] is True


# ==============================================================================
# 5. Handler & Fallback Tests
# ==============================================================================

class TestHandlerExecution:
    def test_handle_pollution_chat_format(self):
        res = handle_pollution_chat("What is the current AQI in Hyderabad?")
        assert "text" in res
        assert "insights" in res
        assert "suggestions" in res
        assert isinstance(res["insights"], list)
        assert 1 <= len(res["insights"]) <= 5
        assert len(res["suggestions"]) <= 3

    def test_unknown_station_response(self):
        res = handle_pollution_chat("What is the AQI at Kukatpally housing board?")
        t = res["text"].lower()
        assert any(w in t for w in ["not monitored", "not match", "not part of the monitored", "unmonitored", "unavailable"])

    def test_out_of_scope_city_response(self):
        res = handle_pollution_chat("What is the air quality in Bengaluru today?")
        t = res["text"].lower()
        assert any(w in t for w in ["outside", "exclusively covers", "not covered", "unavailable", "hyderabad"])

    def test_offline_sensor_response(self):
        res = handle_pollution_chat("What does the system report when a station sensor is completely offline?")
        t = res["text"].lower()
        assert any(w in t for w in ["unavailable", "offline", "excludes", "staleness", "null"])


# ==============================================================================
# 6. Reasoning, Advice & Playbook Tests (STEP 8)
# ==============================================================================

class TestReasoningAndMitigation:
    def test_advice_intent_detection_english(self):
        from backend.agents.pollution_agent.grounding.prompts import is_advice_question
        assert is_advice_question("how to reduce aqi in kapra") is True
        assert is_advice_question("what can be done about PM10 at Bollaram") is True
        assert is_advice_question("suggest measures to improve Hyderabad air quality") is True
        assert is_advice_question("recommend actions to fix pollution at Sanathnagar") is True
        analysis = _analyze_question("how to reduce aqi in kapra")
        assert analysis["is_advice"] is True

    def test_advice_intent_detection_hinglish(self):
        from backend.agents.pollution_agent.grounding.prompts import is_advice_question, is_health_advice_question
        assert is_advice_question("kapra mein aqi kaise kam kare") is True
        assert is_advice_question("kya karna chahiye pollution kam karne ke liye") is True
        assert is_advice_question("bollaram ki hawa kaise sudhare") is True
        assert is_health_advice_question("mask pehne kya zoo park mein") is True
        assert is_health_advice_question("zoo park mein jogging karna safe hai kya") is True

    def test_advice_intent_detection_typos(self):
        from backend.agents.pollution_agent.grounding.prompts import is_advice_question
        assert is_advice_question("how to redue aqi at kapra") is True
        assert is_advice_question("sugest measurs for pollutoin at Bollaram") is True
        assert is_advice_question("how to improv air qualty in Hyderabad") is True
        assert is_advice_question("mitigtion plan for Sanathnagar") is True

    def test_playbook_validation_sources_required(self):
        from pathlib import Path
        pb_path = Path(__file__).resolve().parent / "knowledge" / "mitigation_playbook.json"
        with open(pb_path, "r", encoding="utf-8") as f:
            pb_data = json.load(f)

        assert pb_data.get("_meta", {}).get("status") == "REVIEW BEFORE RELEASE"
        interventions = pb_data.get("interventions", [])
        assert len(interventions) >= 12
        for item in interventions:
            assert "id" in item and item["id"].startswith("MIT-")
            assert "action" in item and len(item["action"]) > 10
            assert "who" in item and len(item["who"]) > 0
            assert "time_horizon" in item and item["time_horizon"] in ("immediate", "short_term", "medium_term", "long_term")
            assert "source" in item and len(item["source"].strip()) > 0, f"Item {item['id']} missing source!"
            assert "confidence_label" in item

    def test_id_only_recommendations_verification(self):
        tool_outputs = {
            "current_station": {"station_name": "ECIL Kapra", "aqi": 69, "dominant_pollutant": "PM10", "is_stale": False},
            "playbook_items": [
                {"id": "MIT-PM10-01", "action": "Deploy mechanical sweepers", "who": "GHMC", "time_horizon": "immediate"}
            ]
        }
        # Valid ID in answer
        valid_answer = {
            "text": "Observed AQI at ECIL Kapra is 69.",
            "insights": [
                "Dominant pollutant is PM10.",
                "Action MIT-PM10-01: Deploy mechanical sweepers by GHMC (immediate).",
                "The system cannot attribute local cause without source-apportionment surveys."
            ],
            "suggestions": ["Forecast?", "Compare?", "Status?"]
        }
        passed, issues = _verify_answer(valid_answer, tool_outputs, "how to reduce aqi in kapra")
        assert passed is True, f"Valid answer failed: {issues}"

        # Invalid fake ID
        invalid_answer = {
            "text": "Observed AQI at ECIL Kapra is 69.",
            "insights": [
                "Dominant pollutant is PM10.",
                "Action MIT-FAKE-99: Invented action without playbook entry.",
                "The system cannot attribute local cause without source-apportionment surveys."
            ],
            "suggestions": ["Forecast?", "Compare?", "Status?"]
        }
        passed, issues = _verify_answer(invalid_answer, tool_outputs, "how to reduce aqi in kapra")
        assert passed is False
        assert any("PLAYBOOK_ID" in iss for iss in issues)

    def test_chip_consistency(self):
        from backend.agents.pollution_agent.grounding.handler import _build_advice_chips
        analysis = {"is_advice": True, "stations_mentioned": ["ECIL Kapra"]}
        tool_outputs = {
            "current_station": {"station_name": "ECIL Kapra", "aqi": 69, "dominant_pollutant": "PM10", "is_stale": False},
            "current_city": {"aqi": 75},
            "explain_ECIL Kapra": {"diff_vs_city_mean": -6, "dominant_pollutant": "PM10"}
        }
        chips = _build_advice_chips(analysis, tool_outputs)
        assert len(chips) == 3
        for c in chips:
            assert "higher than other stations" not in c.lower()
            assert "higher than the city mean" not in c.lower()

    def test_think_block_stripping(self):
        from backend.agents.pollution_agent.grounding.handler import _strip_think_blocks
        raw_with_think = "<think>\nThinking through the CPCB rules...\nKapra is 69.\n</think>\n{\"text\": \"AQI is 69\", \"insights\": [\"PM10\"], \"suggestions\": [\"A\", \"B\", \"C\"]}"
        cleaned = _strip_think_blocks(raw_with_think)
        assert "<think>" not in cleaned
        assert "</think>" not in cleaned
        parsed = json.loads(cleaned)
        assert parsed["text"] == "AQI is 69"

    def test_flag_off_identity(self):
        with patch.dict(os.environ, {"POLLUTION_REASONING": "false"}):
            analysis = _analyze_question("how to reduce aqi in kapra")
            assert analysis["is_advice"] is False
            assert analysis["is_health_advice"] is False

    def test_fallback_path_execution(self):
        with patch("backend.agents.pollution_agent.grounding.handler._call_llm", return_value=None):
            res = handle_pollution_chat("how to reduce aqi in kapra")
            assert "text" in res
            assert len(res["insights"]) >= 2
            assert len(res["suggestions"]) == 3
            full_resp = res["text"] + " " + " ".join(res["insights"])
            assert any(term in full_resp for term in ["MIT-", "playbook", "sweepers", "dust", "maintenance", "Satisfactory"])
            assert any(caveat in full_resp.lower() for caveat in ["source-apportionment", "on-site", "cannot attribute"])


