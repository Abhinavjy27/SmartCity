"""
Comprehensive Verification Suite for SmartCity Conversation Context & Locality Persistence.

Validates:
1. Stable conversation_id across turns with independent per-request request_id.
2. Multi-turn cross-domain context preservation:
   - Turn 1: "What is the traffic situation in Tarnaka?" -> Tarnaka traffic
   - Turn 2: "What's the pollution level there?" -> Tarnaka pollution (NOT Narayanguda)
3. New explicit locality overrides past conversation context:
   - Turn 3: "Now check pollution in Madhapur." -> Madhapur pollution
4. Follow-up anaphora references ("there", "same location", "that corridor", "test it")
   resolve to the last verified locality of the specific conversation.
5. Conversation isolation:
   - Conversation B with no locality specified does NOT inherit from Conversation A; defaults to Narayanguda.
6. Locality precedence hierarchy:
   explicit query text locality > explicit request parameter > conversation context > default fallback.
7. Validation of specialist agent returned locality (no silent substitution).
"""

import os
import unittest
from fastapi.testclient import TestClient

from backend.supervisor.main import (
    app,
    _PLANNER_SESSIONS,
    sanitize_location,
    has_contextual_reference,
    validate_agent_locality,
)
from backend.agents.planner_agent.planner import PlannerAgent
from backend.agents.planner_agent.llm_client import MockLLMProvider


class TestConversationContextPersistence(unittest.TestCase):
    def setUp(self):
        self.original_provider = os.environ.get("LLM_PROVIDER")
        os.environ["LLM_PROVIDER"] = "mock"
        self.mock_provider = MockLLMProvider()
        self.planner = PlannerAgent(llm_provider=self.mock_provider)
        self.client = TestClient(app)
        _PLANNER_SESSIONS.clear()

    def tearDown(self):
        if self.original_provider is not None:
            os.environ["LLM_PROVIDER"] = self.original_provider
        else:
            os.environ.pop("LLM_PROVIDER", None)
        _PLANNER_SESSIONS.clear()

    # -------------------------------------------------------------------------
    # 1. Core Bug Verification: Tarnaka Traffic -> Pollution "there"
    # -------------------------------------------------------------------------
    def test_core_bug_tarnaka_traffic_then_pollution_there(self):
        """
        Turn 1: 'What is the traffic situation in Tarnaka?' (session conv_core_1)
        Turn 2: 'What\'s the pollution level there?' (session conv_core_1)
        Turn 2 MUST retrieve pollution data for Tarnaka, NOT default Narayanguda.
        """
        conv_id = "conv_core_1"

        # Turn 1: Traffic in Tarnaka
        res1 = self.client.post("/agents/planner/execute", json={
            "conversation_id": conv_id,
            "request_id": "req_101",
            "query": "What is the traffic situation in Tarnaka?",
            "conversation_history": [],
        })
        self.assertEqual(res1.status_code, 200, res1.text)
        data1 = res1.json()

        self.assertIn("Tarnaka", data1.get("location", ""))
        self.assertIn("traffic_agent", data1.get("dispatched_agents", []))
        trf = data1.get("agent_results", {}).get("traffic", {})
        trf_loc = (trf.get("location") or "") + " " + ((trf.get("metadata") or {}).get("locality") or "")
        self.assertIn("tarnaka", trf_loc.lower())

        # Turn 2: Follow-up asking about pollution "there"
        res2 = self.client.post("/agents/planner/execute", json={
            "conversation_id": conv_id,
            "request_id": "req_102",
            "query": "What's the pollution level there?",
            "conversation_history": [
                {
                    "role": "user",
                    "content": "What is the traffic situation in Tarnaka?",
                    "location": data1.get("location"),
                },
                {
                    "role": "assistant",
                    "content": data1.get("final_response", {}).get("summary", ""),
                    "location": data1.get("location"),
                    "collected_results": data1.get("collected_results", {}),
                }
            ],
        })
        self.assertEqual(res2.status_code, 200, res2.text)
        data2 = res2.json()

        # Location MUST be Tarnaka, Hyderabad
        self.assertIn("Tarnaka", data2.get("location", ""))
        self.assertNotIn("Narayanguda", data2.get("location", ""))

        # Pollution agent must have been dispatched with Tarnaka
        self.assertIn("pollution_agent", data2.get("dispatched_agents", []))
        pol = data2.get("agent_results", {}).get("pollution", {})
        self.assertIn("Tarnaka", pol.get("location", ""))

    # -------------------------------------------------------------------------
    # 2. Explicitly Stated New Locality Overrides Previous Context
    # -------------------------------------------------------------------------
    def test_new_explicit_locality_overrides_previous_context(self):
        """
        Turn 1: Query Tarnaka traffic.
        Turn 2: Follow-up pollution "there" -> Tarnaka.
        Turn 3: 'Now check pollution in Madhapur.' -> MUST override Tarnaka with Madhapur.
        Turn 4: 'What is the weather there?' -> MUST resolve to Madhapur.
        """
        conv_id = "conv_override_1"

        # Turn 1: Tarnaka
        res1 = self.client.post("/agents/planner/execute", json={
            "conversation_id": conv_id,
            "request_id": "req_201",
            "query": "What is the traffic situation in Tarnaka?",
            "conversation_history": [],
        })
        self.assertEqual(res1.status_code, 200)
        self.assertIn("Tarnaka", res1.json().get("location", ""))

        # Turn 2: Pollution "there" -> Tarnaka
        res2 = self.client.post("/agents/planner/execute", json={
            "conversation_id": conv_id,
            "request_id": "req_202",
            "query": "What's the pollution level there?",
            "conversation_history": [
                {"role": "user", "content": "What is the traffic situation in Tarnaka?", "location": "Tarnaka, Hyderabad"},
                {"role": "assistant", "content": "Traffic in Tarnaka is moderate.", "location": "Tarnaka, Hyderabad"}
            ],
        })
        self.assertEqual(res2.status_code, 200)
        self.assertIn("Tarnaka", res2.json().get("location", ""))

        # Turn 3: New explicit locality: Madhapur
        res3 = self.client.post("/agents/planner/execute", json={
            "conversation_id": conv_id,
            "request_id": "req_203",
            "query": "Now check pollution in Madhapur.",
            "conversation_history": [
                {"role": "user", "content": "What is the traffic situation in Tarnaka?", "location": "Tarnaka, Hyderabad"},
                {"role": "assistant", "content": "Traffic in Tarnaka is moderate.", "location": "Tarnaka, Hyderabad"},
                {"role": "user", "content": "What's the pollution level there?", "location": "Tarnaka, Hyderabad"},
                {"role": "assistant", "content": "Pollution in Tarnaka is Moderate.", "location": "Tarnaka, Hyderabad"}
            ],
        })
        self.assertEqual(res3.status_code, 200)
        data3 = res3.json()
        self.assertIn("Madhapur", data3.get("location", ""))
        self.assertNotIn("Tarnaka", data3.get("location", ""))
        pol3 = data3.get("agent_results", {}).get("pollution", {})
        self.assertIn("Madhapur", pol3.get("location", ""))

        # Turn 4: Weather "there" -> Should now resolve to Madhapur
        res4 = self.client.post("/agents/planner/execute", json={
            "conversation_id": conv_id,
            "request_id": "req_204",
            "query": "What is the weather there?",
            "conversation_history": [
                {"role": "user", "content": "Now check pollution in Madhapur.", "location": "Madhapur, Hyderabad"},
                {"role": "assistant", "content": "Pollution in Madhapur is Moderate.", "location": "Madhapur, Hyderabad"}
            ],
        })
        self.assertEqual(res4.status_code, 200)
        data4 = res4.json()
        self.assertIn("Madhapur", data4.get("location", ""))
        self.assertNotIn("Tarnaka", data4.get("location", ""))

    # -------------------------------------------------------------------------
    # 3. Conversation Isolation: Distinct Conversations Must Not Leak
    # -------------------------------------------------------------------------
    def test_conversation_isolation(self):
        """
        Conversation A queries Gachibowli.
        Conversation B (a fresh conversation) queries traffic without a location.
        Conversation B MUST NOT inherit Gachibowli from Conversation A.
        It must fall back to the documented system default (Narayanguda).
        """
        # Conv A
        res_a = self.client.post("/agents/planner/execute", json={
            "conversation_id": "conv_alpha",
            "request_id": "req_a1",
            "query": "What is the traffic situation in Gachibowli?",
            "conversation_history": [],
        })
        self.assertEqual(res_a.status_code, 200)
        self.assertIn("Gachibowli", res_a.json().get("location", ""))

        # Conv B: fresh conversation
        res_b = self.client.post("/agents/planner/execute", json={
            "conversation_id": "conv_beta",
            "request_id": "req_b1",
            "query": "What is the traffic situation?",
            "conversation_history": [],
        })
        self.assertEqual(res_b.status_code, 200)
        data_b = res_b.json()
        # MUST NOT be Gachibowli
        self.assertNotIn("Gachibowli", data_b.get("location", ""))
        self.assertIn("Narayanguda", data_b.get("location", ""))

    # -------------------------------------------------------------------------
    # 4. Reference Expressions Detection & Resolution
    # -------------------------------------------------------------------------
    def test_anaphoric_reference_detection(self):
        """Verify regex detection of contextual references."""
        self.assertTrue(has_contextual_reference("What's the pollution level there?"))
        self.assertTrue(has_contextual_reference("How is traffic around there?"))
        self.assertTrue(has_contextual_reference("Check power load in the same location"))
        self.assertTrue(has_contextual_reference("Now test that corridor"))
        self.assertTrue(has_contextual_reference("Test it"))
        self.assertTrue(has_contextual_reference("Simulate it with 10s green time"))
        self.assertTrue(has_contextual_reference("How is weather in that area?"))
        self.assertFalse(has_contextual_reference("What is traffic in Ameerpet?"))
        self.assertFalse(has_contextual_reference("Reduce peak hour congestion"))

    # -------------------------------------------------------------------------
    # 5. Locality Precedence Hierarchy
    # -------------------------------------------------------------------------
    def test_locality_precedence_hierarchy(self):
        """
        Precedence:
        1. Explicit locality in current query text
        2. Explicit caller-provided request parameter (if not anaphoric query)
        3. Conversation context
        4. Default fallback
        """
        # Case 1: Explicit query text overrides parameter AND conversation context
        _PLANNER_SESSIONS["conv_prec_1"] = {"last_locality": "Tarnaka, Hyderabad"}
        loc1 = sanitize_location(
            location="Gachibowli, Hyderabad",
            query_text="What is the air quality in Madhapur?",
            conversation_id="conv_prec_1",
        )
        self.assertEqual(loc1, "Madhapur, Hyderabad")

        # Case 2: Anaphoric query ('there') resolves to conversation context even if default parameter was passed
        _PLANNER_SESSIONS["conv_prec_2"] = {"last_locality": "Tarnaka, Hyderabad"}
        loc2 = sanitize_location(
            location="Narayanguda, Hyderabad",
            query_text="What is the air quality there?",
            conversation_id="conv_prec_2",
        )
        self.assertEqual(loc2, "Tarnaka, Hyderabad")

        # Case 3: Explicit parameter used when query is non-anaphoric and has no city
        _PLANNER_SESSIONS["conv_prec_3"] = {"last_locality": "Tarnaka, Hyderabad"}
        loc3 = sanitize_location(
            location="Begumpet, Hyderabad",
            query_text="Assess substation power stability",
            conversation_id="conv_prec_3",
        )
        self.assertEqual(loc3, "Begumpet, Hyderabad")

        # Case 4: Default fallback only when no query locality, no param, and no context
        loc4 = sanitize_location(
            location=None,
            query_text="Check road condition",
            conversation_id="conv_nonexistent",
        )
        self.assertEqual(loc4, "Narayanguda, Hyderabad")

    # -------------------------------------------------------------------------
    # 6. Specialist Agent Locality Validation
    # -------------------------------------------------------------------------
    def test_specialist_agent_locality_validation(self):
        """
        Returned specialist evidence must match expected locality.
        Mismatched localities must be detected and rejected (no silent substitution).
        """
        # Matching locality
        match_res = {"location": "Tarnaka, Hyderabad", "city_avg_aqi": 82}
        self.assertTrue(validate_agent_locality("Tarnaka, Hyderabad", match_res, "pollution"))

        # Mismatched locality: expected Tarnaka, received Narayanguda
        mismatch_res = {"location": "Narayanguda, Hyderabad", "city_avg_aqi": 110}
        self.assertFalse(validate_agent_locality("Tarnaka, Hyderabad", mismatch_res, "pollution"))

    # -------------------------------------------------------------------------
    # 7. Cross-Domain Context Propagation (Traffic -> Weather -> Energy)
    # -------------------------------------------------------------------------
    def test_cross_domain_context_propagation(self):
        """
        Turn 1: Traffic in Nacharam.
        Turn 2: 'What is the weather there?' -> Nacharam weather.
        Turn 3: 'How is the substation grid load in that area?' -> Nacharam energy.
        """
        conv_id = "conv_cross_1"

        # Turn 1: Nacharam traffic
        res1 = self.client.post("/agents/planner/execute", json={
            "conversation_id": conv_id,
            "request_id": "req_x1",
            "query": "What is the traffic situation in Nacharam?",
            "conversation_history": [],
        })
        self.assertEqual(res1.status_code, 200)
        self.assertIn("Nacharam", res1.json().get("location", ""))

        # Turn 2: Weather there
        res2 = self.client.post("/agents/planner/execute", json={
            "conversation_id": conv_id,
            "request_id": "req_x2",
            "query": "What is the weather there?",
            "conversation_history": [
                {"role": "user", "content": "What is the traffic situation in Nacharam?", "location": "Nacharam, Hyderabad"},
                {"role": "assistant", "content": "Traffic in Nacharam is flowing smoothly.", "location": "Nacharam, Hyderabad"}
            ],
        })
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertIn("Nacharam", data2.get("location", ""))
        self.assertIn("weather_agent", data2.get("dispatched_agents", []))

        # Turn 3: Energy in that area
        res3 = self.client.post("/agents/planner/execute", json={
            "conversation_id": conv_id,
            "request_id": "req_x3",
            "query": "How is the substation grid load in that area?",
            "conversation_history": [
                {"role": "user", "content": "What is the traffic situation in Nacharam?", "location": "Nacharam, Hyderabad"},
                {"role": "assistant", "content": "Traffic in Nacharam is flowing smoothly.", "location": "Nacharam, Hyderabad"},
                {"role": "user", "content": "What is the weather there?", "location": "Nacharam, Hyderabad"},
                {"role": "assistant", "content": "Weather in Nacharam is clear.", "location": "Nacharam, Hyderabad"}
            ],
        })
        self.assertEqual(res3.status_code, 200)
        data3 = res3.json()
        self.assertIn("Nacharam", data3.get("location", ""))
        self.assertIn("energy_agent", data3.get("dispatched_agents", []))


if __name__ == "__main__":
    unittest.main()
