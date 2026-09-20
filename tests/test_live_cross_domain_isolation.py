"""
Tests for Live Planner Cross-Domain Isolation and Stale Evidence Prevention.
Covers:
- Section 18: Hard Cross-Domain Contamination Test (4-turn bidirectional isolation)
- Section 19: Hard Different-Data Test (Dynamic Traffic Bottleneck identification)
- Section 20: Hard Pollution Test (Dynamic Pollution AQI/PM adaptation)
"""

import pytest
from fastapi.testclient import TestClient

from backend.supervisor.main import app
from backend.agents.planner_agent.schema import LLMFinalReasoning
from backend.agents.planner_agent.scope import validate_and_enforce_response_scope


client = TestClient(app)


def test_section_18_cross_domain_4_turn_session_isolation():
    """
    Section 18:
    Verify that in a 4-turn conversation across Traffic -> Pollution -> PM2.5 -> Traffic,
    prior turns do not contaminate subsequent turns.
    """
    session_id = "test_cross_domain_isolation_session"

    # Turn 1: "What is the bottleneck corridor?"
    payload_1 = {
        "query": "What is the bottleneck corridor?",
        "objective": "What is the bottleneck corridor?",
        "location": "Narayanguda, Hyderabad",
        "session_id": session_id,
        "conversation_history": [],
    }
    r1 = client.post("/agents/planner/execute", json=payload_1).json()
    s1 = r1.get("final_response", {}).get("summary", "")
    agents_1 = r1.get("dispatched_agents", [])
    results_1 = r1.get("agent_results", {})

    assert "traffic_agent" in agents_1
    assert "pollution_agent" not in agents_1
    assert "traffic" in results_1
    assert "pollution" not in results_1
    assert "Bottleneck corridor" in s1

    # Turn 2: Immediately afterward: "what's the current pollution?"
    h2 = [
        {"role": "user", "content": "What is the bottleneck corridor?"},
        {"role": "assistant", "content": s1, "traffic_evidence": results_1.get("traffic")},
    ]
    payload_2 = {
        "query": "what's the current pollution?",
        "objective": "what's the current pollution?",
        "location": "Narayanguda, Hyderabad",
        "session_id": session_id,
        "conversation_history": h2,
    }
    r2 = client.post("/agents/planner/execute", json=payload_2).json()
    s2 = r2.get("final_response", {}).get("summary", "")
    agents_2 = r2.get("dispatched_agents", [])
    results_2 = r2.get("agent_results", {})

    assert "pollution_agent" in agents_2
    assert "traffic_agent" not in agents_2
    assert "pollution" in results_2
    assert "traffic" not in results_2
    assert "Air Quality" in s2
    assert "AQI" in s2
    # Ensure NO traffic contamination
    assert "bottleneck" not in s2.lower()
    assert "corridor" not in s2.lower()
    assert "network speed" not in s2.lower()
    assert "congestion" not in s2.lower()
    assert "waiting time" not in s2.lower()

    # Turn 3: "what is the PM2.5 level?"
    h3 = h2 + [
        {"role": "user", "content": "what's the current pollution?"},
        {"role": "assistant", "content": s2, "pollution_evidence": results_2.get("pollution")},
    ]
    payload_3 = {
        "query": "what is the PM2.5 level?",
        "objective": "what is the PM2.5 level?",
        "location": "Narayanguda, Hyderabad",
        "session_id": session_id,
        "conversation_history": h3,
    }
    r3 = client.post("/agents/planner/execute", json=payload_3).json()
    s3 = r3.get("final_response", {}).get("summary", "")
    agents_3 = r3.get("dispatched_agents", [])
    results_3 = r3.get("agent_results", {})

    assert "pollution_agent" in agents_3
    assert "traffic_agent" not in agents_3
    assert "pollution" in results_3
    assert "traffic" not in results_3
    assert "PM2.5" in s3
    assert "bottleneck" not in s3.lower()

    # Turn 4: "what is the bottleneck corridor?"
    h4 = h3 + [
        {"role": "user", "content": "what is the PM2.5 level?"},
        {"role": "assistant", "content": s3},
    ]
    payload_4 = {
        "query": "what is the bottleneck corridor?",
        "objective": "what is the bottleneck corridor?",
        "location": "Narayanguda, Hyderabad",
        "session_id": session_id,
        "conversation_history": h4,
    }
    r4 = client.post("/agents/planner/execute", json=payload_4).json()
    s4 = r4.get("final_response", {}).get("summary", "")
    agents_4 = r4.get("dispatched_agents", [])
    results_4 = r4.get("agent_results", {})

    assert "traffic_agent" in agents_4
    assert "traffic" in results_4
    assert "Bottleneck corridor" in s4


def test_section_19_hard_different_data_traffic_agent():
    """
    Section 19:
    Use controlled Traffic Agent test responses where Eastbound vs Westbound speeds vary.
    Verify the Planner does not have a permanent hardcoded corridor answer.
    """
    # Test A: Eastbound slower (30 km/h) than Westbound (50 km/h) -> Eastbound is bottleneck
    res1 = LLMFinalReasoning(
        summary="Placeholder",
        cross_domain_relationships="None",
        uncertainty_and_limitations="None",
        recommendation="",
        next_steps=[],
    )
    evidence1 = {
        "traffic": {
            "corridors": [
                {"name": "Narayanguda - Hyderguda (Eastbound)", "avg_speed": 30.0, "status": "HEAVY"},
                {"name": "Narayanguda - Hyderguda (Westbound)", "avg_speed": 50.0, "status": "MODERATE"},
            ]
        }
    }
    validate_and_enforce_response_scope(
        final_reasoning=res1,
        objective="What is the bottleneck corridor?",
        collected_results=evidence1,
    )
    assert "Eastbound" in res1.summary
    assert "Westbound" not in res1.summary

    # Test B: Westbound slower (30 km/h) than Eastbound (50 km/h) -> Westbound is bottleneck
    res2 = LLMFinalReasoning(
        summary="Placeholder",
        cross_domain_relationships="None",
        uncertainty_and_limitations="None",
        recommendation="",
        next_steps=[],
    )
    evidence2 = {
        "traffic": {
            "corridors": [
                {"name": "Narayanguda - Hyderguda (Eastbound)", "avg_speed": 50.0, "status": "MODERATE"},
                {"name": "Narayanguda - Hyderguda (Westbound)", "avg_speed": 30.0, "status": "HEAVY"},
            ]
        }
    }
    validate_and_enforce_response_scope(
        final_reasoning=res2,
        objective="What is the bottleneck corridor?",
        collected_results=evidence2,
    )
    assert "Westbound" in res2.summary
    assert "Eastbound" not in res2.summary


def test_section_20_hard_pollution_test():
    """
    Section 20:
    Use controlled Pollution Agent evidence and verify final response reflects the exact evidence.
    """
    # Evidence 1: AQI=88, PM2.5=14.2, PM10=28.5
    res1 = LLMFinalReasoning(
        summary="Placeholder",
        cross_domain_relationships="None",
        uncertainty_and_limitations="None",
        recommendation="",
        next_steps=[],
    )
    evidence1 = {
        "pollution": {
            "city_avg_aqi": 88,
            "pm25": 14.2,
            "pm10": 28.5,
        }
    }
    validate_and_enforce_response_scope(
        final_reasoning=res1,
        objective="what's the current pollution?",
        collected_results=evidence1,
    )
    assert "88" in res1.summary
    assert "14.2" in res1.summary
    assert "28.5" in res1.summary

    # Evidence 2: AQI=151, PM2.5=72.4, PM10=109.1
    res2 = LLMFinalReasoning(
        summary="Placeholder",
        cross_domain_relationships="None",
        uncertainty_and_limitations="None",
        recommendation="",
        next_steps=[],
    )
    evidence2 = {
        "pollution": {
            "city_avg_aqi": 151,
            "pm25": 72.4,
            "pm10": 109.1,
        }
    }
    validate_and_enforce_response_scope(
        final_reasoning=res2,
        objective="what's the current pollution?",
        collected_results=evidence2,
    )
    assert "151" in res2.summary
    assert "72.4" in res2.summary
    assert "109.1" in res2.summary

    assert res1.summary != res2.summary
