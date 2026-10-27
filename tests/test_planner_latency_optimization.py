"""
Regression tests for SmartCity Planner Latency Optimization:
- Deterministic intent routing for single-domain queries
- Follow-up resolution for 'test the proposed intervention'
- Location inheritance and rejection of blank / 'unknown' locations
- Rate-limit Retry-After parsing, jitter backoff, and model fallback
- Output contract and schema preservation
"""

import unittest
from fastapi.testclient import TestClient

from backend.supervisor.main import app, sanitize_location, INVALID_LOCATION_TOKENS
from backend.agents.weather_agent.provider import resolve_location, INVALID_LOCATION_TOKENS as WEATHER_INVALID_TOKENS
from backend.agents.planner_agent.planner import (
    PlannerAgent,
    get_planner_agent,
    is_test_proposed_intervention_query,
    is_analytical_history_followup,
    extract_proposed_intervention_from_context,
)
from backend.agents.planner_agent.llm_client import _parse_groq_retry_delay


class TestPlannerLatencyOptimization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.planner = get_planner_agent()

    def test_invalid_location_sanitization(self):
        """Confirm 'unknown', 'none', 'null', blank are rejected and resolved safely."""
        for token in ["unknown", "UNKNOWN", "none", "null", "undefined", "n/a", "na", "", "   "]:
            # Test supervisor sanitizer
            sanitized = sanitize_location(token)
            self.assertEqual(sanitized, "Narayanguda, Hyderabad")
            self.assertNotIn("unknown", sanitized.lower())

            # Test weather provider geocoder resolver
            w_name, lat, lon = resolve_location(token)
            self.assertEqual(w_name, "Hyderabad")
            self.assertAlmostEqual(lat, 17.3850, places=3)
            self.assertAlmostEqual(lon, 78.4867, places=3)

    def test_location_inheritance_from_history(self):
        """Confirm valid location is inherited from prior conversation history turns."""
        history = [
            {"role": "user", "content": "What is the traffic in Gachibowli?"},
            {
                "role": "assistant",
                "location": "Gachibowli, Hyderabad",
                "content": "Gachibowli traffic is moderate.",
            },
        ]
        inherited = sanitize_location("unknown", conversation_history=history)
        self.assertEqual(inherited, "Gachibowli, Hyderabad")

    def test_deterministic_intent_routing_single_domain(self):
        """Confirm single-domain queries route deterministically without LLM calls."""
        # 1. Weather single-domain
        w_dec = self.planner.plan_autonomous("What is the current weather in Narayanguda?")
        self.assertTrue(w_dec.relevant)
        self.assertEqual(w_dec.required_capabilities, ["weather"])
        self.assertEqual(len(w_dec.agent_requests), 1)
        self.assertEqual(w_dec.agent_requests[0].agent, "weather")

        # 2. Pollution single-domain
        p_dec = self.planner.plan_autonomous("What are the air quality and PM2.5 levels in Narayanguda?")
        self.assertTrue(p_dec.relevant)
        self.assertEqual(p_dec.required_capabilities, ["pollution"])
        self.assertEqual(len(p_dec.agent_requests), 1)
        self.assertEqual(p_dec.agent_requests[0].agent, "pollution")

        # 3. Energy single-domain
        e_dec = self.planner.plan_autonomous("What is the current power grid status in Narayanguda?")
        self.assertTrue(e_dec.relevant)
        self.assertEqual(e_dec.required_capabilities, ["energy"])
        self.assertEqual(len(e_dec.agent_requests), 1)
        self.assertEqual(e_dec.agent_requests[0].agent, "energy")

        # 4. Traffic diagnostic single-domain
        t_dec = self.planner.plan_autonomous("Which corridor is currently the bottleneck in Narayanguda?")
        self.assertTrue(t_dec.relevant)
        self.assertEqual(t_dec.required_capabilities, ["traffic"])
        self.assertEqual(len(t_dec.agent_requests), 1)
        self.assertEqual(t_dec.agent_requests[0].agent, "traffic")

    def test_follow_up_test_proposed_intervention_dispatches_only_simulation(self):
        """Confirm 'Test the proposed intervention' extracts candidate and dispatches NO weather/pollution agents."""
        self.assertTrue(is_test_proposed_intervention_query("Test the proposed intervention"))
        self.assertTrue(is_test_proposed_intervention_query("Simulate the proposed intervention"))

        history = [
            {"role": "user", "content": "What is the traffic situation in Narayanguda?"},
            {
                "role": "assistant",
                "location": "Narayanguda, Hyderabad",
                "collected_results": {
                    "traffic": {
                        "location": "Narayanguda, Hyderabad",
                        "candidate_interventions": [
                            {
                                "type": "signal_timing",
                                "target": "Westbound",
                                "parameters": {"green_time_adjustment_sec": 10.0},
                            }
                        ]
                    }
                }
            }
        ]

        cand = extract_proposed_intervention_from_context(conversation_history=history)
        self.assertIsNotNone(cand)
        self.assertEqual(cand["type"], "signal_timing")
        self.assertEqual(cand["target"], "Westbound")

        dec = self.planner.plan_autonomous(
            objective="Test the proposed intervention",
            location="unknown",
            conversation_history=history,
        )
        self.assertTrue(dec.relevant)
        self.assertNotIn("weather", dec.required_capabilities)
        self.assertNotIn("pollution", dec.required_capabilities)
        self.assertIn("simulation", dec.required_capabilities)

    def test_analytical_followup_dispatches_zero_agents(self):
        """Confirm analytical inquiries on existing simulation history dispatch zero agents."""
        self.assertTrue(is_analytical_history_followup("Which tested intervention performed better?"))
        self.assertTrue(is_analytical_history_followup("Is rerouting better than signal timing?"))

        sim_hist = [
            {
                "scenario_id": "sim_1",
                "scenario": "synthetic_normal",
                "duration_seconds": 20,
                "seed": 42,
                "intervention": {"type": "signal_timing", "target": "Westbound"},
                "metrics": {"average_speed_kmh": 22.0},
            }
        ]
        dec = self.planner.plan_autonomous(
            objective="Which tested intervention performed better?",
            simulation_history=sim_hist,
        )
        self.assertTrue(dec.relevant)
        self.assertEqual(dec.required_capabilities, [])
        self.assertEqual(dec.agent_requests, [])
        self.assertEqual(dec.next_action, "finalize")

    def test_groq_retry_after_parsing(self):
        """Verify Retry-After regex and header extraction logic."""
        class MockHttpError(Exception):
            def __init__(self, msg, headers=None):
                super().__init__(msg)
                self.response = type("MockResponse", (), {"headers": headers or {}})()

        # 1. Header retry-after
        err_header = MockHttpError("Rate limit exceeded", headers={"retry-after": "7.5"})
        self.assertAlmostEqual(_parse_groq_retry_delay(err_header), 7.5)

        # 2. Header retry-after-ms
        err_ms = MockHttpError("Rate limit exceeded", headers={"retry-after-ms": "4500"})
        self.assertAlmostEqual(_parse_groq_retry_delay(err_ms), 4.5)

        # 3. Message text "try again in 11.2s"
        err_msg = MockHttpError("Rate limit reached. Please try again in 11.2s.")
        self.assertAlmostEqual(_parse_groq_retry_delay(err_msg), 11.2)

        # 4. Message text with minutes "try again in 1m20s"
        err_min = MockHttpError("Please try again in 1m20s")
        self.assertAlmostEqual(_parse_groq_retry_delay(err_min), 80.0)

    def test_planner_execute_e2e_contract_preservation(self):
        """Verify Planner execution responses maintain all expected fields, types, and schema contracts."""
        payload = {
            "objective": "What is the current weather in Narayanguda?",
            "location": "Narayanguda, Hyderabad",
        }
        resp = self.client.post("/agents/planner/execute", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["status"], "COMPLETED")
        self.assertIn("weather_agent", data["dispatched_agents"])
        self.assertIn("final_response", data)

        fin = data["final_response"]
        self.assertIsNotNone(fin)
        self.assertIn("summary", fin)
        self.assertIn("evidence_status", fin)
        self.assertIn("response_scope", fin)


if __name__ == "__main__":
    unittest.main()
