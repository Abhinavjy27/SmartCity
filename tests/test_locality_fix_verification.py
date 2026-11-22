"""
Targeted Verification Suite for SmartCity Locality Resolution & Precedence Fixes.

Directly tests:
1. Four independent single-turn queries:
   - "Pollution in Secunderabad" -> Secunderabad (lat 17.4344, lon 78.5013)
   - "Traffic in Tarnaka" -> Tarnaka (lat 17.4290, lon 78.5320)
   - "Pollution in Madhapur" -> Madhapur (lat 17.4480, lon 78.3912)
   - "Weather in Gachibowli" -> Gachibowli (lat 17.4401, lon 78.3489)
2. Multi-turn follow-up sequence:
   - Turn 1: "Traffic in Tarnaka" -> Tarnaka
   - Turn 2: "What about pollution there?" -> Tarnaka
   - Turn 3: "Now check Secunderabad" -> Secunderabad
3. Locality Precedence & No Silent Substitution of Narayanguda:
   - Unrecognized/out-of-bounds locality does not silently become Narayanguda.
"""

import os
import unittest
from fastapi.testclient import TestClient

from backend.supervisor.main import app, _PLANNER_SESSIONS
from backend.agents.traffic_agent.location_resolver import LocationResolver
from backend.agents.pollution_agent.current_client import OpenMeteoCurrentClient
from backend.agents.weather_agent.provider import resolve_location, get_weather_provider


class TestLocalityFixVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["LLM_PROVIDER"] = "mock"
        cls.client = TestClient(app)

    def setUp(self):
        _PLANNER_SESSIONS.clear()

    # -------------------------------------------------------------------------
    # 1. Four Independent Single-Turn Locality Queries
    # -------------------------------------------------------------------------
    def test_query_pollution_in_secunderabad(self):
        """User enters 'Pollution in Secunderabad' -> Must resolve to Secunderabad."""
        # 1. Verify coordinate resolution
        lat, lon, name = OpenMeteoCurrentClient.resolve_coordinates("Secunderabad")
        self.assertAlmostEqual(lat, 17.4344, places=3)
        self.assertAlmostEqual(lon, 78.5013, places=3)
        self.assertIn("Secunderabad", name)

        # 2. Verify end-to-end execute request
        resp = self.client.post("/agents/planner/execute", json={
            "query": "Pollution in Secunderabad",
            "conversation_id": "test_secunderabad_1",
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("Secunderabad", data.get("location", ""))
        self.assertNotIn("Narayanguda", data.get("location", ""))

        # Check pollution agent results
        pol = data.get("agent_results", {}).get("pollution", {})
        self.assertIn("Secunderabad", pol.get("location", ""))
        self.assertNotIn("Narayanguda", pol.get("location", ""))

    def test_query_traffic_in_tarnaka(self):
        """User enters 'Traffic in Tarnaka' -> Must resolve to Tarnaka coordinates & TomTom."""
        loc = LocationResolver.resolve(query_text="Traffic in Tarnaka")
        self.assertIsNotNone(loc)
        self.assertEqual(loc.name, "Tarnaka")
        self.assertAlmostEqual(loc.lat, 17.4290, places=3)
        self.assertAlmostEqual(loc.lon, 78.5320, places=3)

        resp = self.client.post("/agents/planner/execute", json={
            "query": "Traffic in Tarnaka",
            "conversation_id": "test_tarnaka_1",
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("Tarnaka", data.get("location", ""))
        self.assertNotIn("Narayanguda", data.get("location", ""))

        trf = data.get("agent_results", {}).get("traffic", {})
        trf_loc = trf.get("location", "")
        self.assertIn("Tarnaka", trf_loc)

    def test_query_pollution_in_madhapur(self):
        """User enters 'Pollution in Madhapur' -> Must resolve to Madhapur coordinates."""
        lat, lon, name = OpenMeteoCurrentClient.resolve_coordinates("Madhapur")
        self.assertAlmostEqual(lat, 17.4480, places=3)
        self.assertAlmostEqual(lon, 78.3912, places=3)
        self.assertIn("Madhapur", name)

        resp = self.client.post("/agents/planner/execute", json={
            "query": "Pollution in Madhapur",
            "conversation_id": "test_madhapur_1",
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("Madhapur", data.get("location", ""))
        self.assertNotIn("Narayanguda", data.get("location", ""))

    def test_query_weather_in_gachibowli(self):
        """User enters 'Weather in Gachibowli' -> Must resolve to Gachibowli coordinates."""
        name, lat, lon = resolve_location("Weather in Gachibowli")
        self.assertEqual(name, "Gachibowli")
        self.assertAlmostEqual(lat, 17.4401, places=3)
        self.assertAlmostEqual(lon, 78.3489, places=3)

        resp = self.client.post("/agents/planner/execute", json={
            "query": "Weather in Gachibowli",
            "conversation_id": "test_gachibowli_1",
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("Gachibowli", data.get("location", ""))
        self.assertNotIn("Narayanguda", data.get("location", ""))

        wth = data.get("agent_results", {}).get("weather", {})
        self.assertIn("Gachibowli", wth.get("location", "") or wth.get("city", ""))

    # -------------------------------------------------------------------------
    # 2. Multi-Turn Follow-Up Sequence
    # -------------------------------------------------------------------------
    def test_multiturn_sequence(self):
        """
        Turn 1: "Traffic in Tarnaka" -> Tarnaka
        Turn 2: "What about pollution there?" -> Tarnaka
        Turn 3: "Now check Secunderabad" -> Secunderabad
        """
        conv_id = "conv_multiturn_seq_1"

        # Turn 1: Traffic in Tarnaka
        res1 = self.client.post("/agents/planner/execute", json={
            "conversation_id": conv_id,
            "request_id": "req_seq_1",
            "query": "Traffic in Tarnaka",
            "conversation_history": [],
        })
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertIn("Tarnaka", data1.get("location", ""))
        self.assertNotIn("Narayanguda", data1.get("location", ""))

        # Turn 2: "What about pollution there?" -> Context must resolve to Tarnaka
        res2 = self.client.post("/agents/planner/execute", json={
            "conversation_id": conv_id,
            "request_id": "req_seq_2",
            "query": "What about pollution there?",
            "conversation_history": [
                {
                    "role": "user",
                    "content": "Traffic in Tarnaka",
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
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertIn("Tarnaka", data2.get("location", ""))
        self.assertNotIn("Narayanguda", data2.get("location", ""))
        pol2 = data2.get("agent_results", {}).get("pollution", {})
        self.assertIn("Tarnaka", pol2.get("location", ""))

        # Turn 3: "Now check Secunderabad" -> Explicit locality overrides past context
        res3 = self.client.post("/agents/planner/execute", json={
            "conversation_id": conv_id,
            "request_id": "req_seq_3",
            "query": "Now check Secunderabad",
            "conversation_history": [
                {
                    "role": "user",
                    "content": "Traffic in Tarnaka",
                    "location": data1.get("location"),
                },
                {
                    "role": "assistant",
                    "content": data1.get("final_response", {}).get("summary", ""),
                    "location": data1.get("location"),
                },
                {
                    "role": "user",
                    "content": "What about pollution there?",
                    "location": data2.get("location"),
                },
                {
                    "role": "assistant",
                    "content": data2.get("final_response", {}).get("summary", ""),
                    "location": data2.get("location"),
                }
            ],
        })
        self.assertEqual(res3.status_code, 200)
        data3 = res3.json()
        self.assertIn("Secunderabad", data3.get("location", ""))
        self.assertNotIn("Tarnaka", data3.get("location", ""))
        self.assertNotIn("Narayanguda", data3.get("location", ""))

    def test_exact_user_5_turn_sequence(self):
        """
        Exact user validation sequence:
        Turn 1: 'Pollution in Tarnaka' -> Tarnaka
        Turn 2: 'How about traffic there?' -> Tarnaka (context inheritance)
        Turn 3: 'Traffic in Secunderabad' -> Secunderabad (explicit query overrides context)
        Turn 4: 'What about pollution there?' -> Secunderabad (context inheritance)
        Turn 5: 'Now check Madhapur' -> Madhapur (explicit query overrides context)
        """
        conv_id = "conv_user_5turn_exact"

        # Turn 1: Pollution in Tarnaka
        res1 = self.client.post("/agents/planner/execute", json={
            "conversation_id": conv_id,
            "request_id": "req_turn_1",
            "query": "Pollution in Tarnaka",
            "conversation_history": [],
        })
        self.assertEqual(res1.status_code, 200)
        d1 = res1.json()
        self.assertIn("Tarnaka", d1.get("location", ""))
        self.assertNotIn("Narayanguda", d1.get("location", ""))
        pol1 = d1.get("agent_results", {}).get("pollution", {})
        self.assertIn("Tarnaka", pol1.get("location", ""))

        # Turn 2: How about traffic there?
        h1 = [
            {"role": "user", "content": "Pollution in Tarnaka", "location": d1.get("location")},
            {"role": "assistant", "content": d1.get("final_response", {}).get("summary", ""), "location": d1.get("location"), "pollution_evidence": pol1},
        ]
        res2 = self.client.post("/agents/planner/execute", json={
            "conversation_id": conv_id,
            "request_id": "req_turn_2",
            "query": "How about traffic there?",
            "conversation_history": h1,
        })
        self.assertEqual(res2.status_code, 200)
        d2 = res2.json()
        self.assertIn("Tarnaka", d2.get("location", ""))
        trf2 = d2.get("agent_results", {}).get("traffic", {})
        self.assertIn("Tarnaka", trf2.get("location", ""))

        # Turn 3: Traffic in Secunderabad (Must override Tarnaka context!)
        h2 = list(h1) + [
            {"role": "user", "content": "How about traffic there?", "location": d2.get("location")},
            {"role": "assistant", "content": d2.get("final_response", {}).get("summary", ""), "location": d2.get("location"), "traffic_evidence": trf2},
        ]
        res3 = self.client.post("/agents/planner/execute", json={
            "conversation_id": conv_id,
            "request_id": "req_turn_3",
            "query": "Traffic in Secunderabad",
            "conversation_history": h2,
        })
        self.assertEqual(res3.status_code, 200)
        d3 = res3.json()
        self.assertIn("Secunderabad", d3.get("location", ""))
        self.assertNotIn("Tarnaka", d3.get("location", ""))
        self.assertNotIn("Narayanguda", d3.get("location", ""))
        trf3 = d3.get("agent_results", {}).get("traffic", {})
        self.assertIn("Secunderabad", trf3.get("location", ""))

        # Turn 4: What about pollution there? (Must inherit Secunderabad context!)
        h3 = list(h2) + [
            {"role": "user", "content": "Traffic in Secunderabad", "location": d3.get("location")},
            {"role": "assistant", "content": d3.get("final_response", {}).get("summary", ""), "location": d3.get("location"), "traffic_evidence": trf3},
        ]
        res4 = self.client.post("/agents/planner/execute", json={
            "conversation_id": conv_id,
            "request_id": "req_turn_4",
            "query": "What about pollution there?",
            "conversation_history": h3,
        })
        self.assertEqual(res4.status_code, 200)
        d4 = res4.json()
        self.assertIn("Secunderabad", d4.get("location", ""))
        self.assertNotIn("Tarnaka", d4.get("location", ""))
        self.assertNotIn("Narayanguda", d4.get("location", ""))
        pol4 = d4.get("agent_results", {}).get("pollution", {})
        self.assertIn("Secunderabad", pol4.get("location", ""))

        # Turn 5: Now check Madhapur (Must override Secunderabad context!)
        h4 = list(h3) + [
            {"role": "user", "content": "What about pollution there?", "location": d4.get("location")},
            {"role": "assistant", "content": d4.get("final_response", {}).get("summary", ""), "location": d4.get("location"), "pollution_evidence": pol4},
        ]
        res5 = self.client.post("/agents/planner/execute", json={
            "conversation_id": conv_id,
            "request_id": "req_turn_5",
            "query": "Now check Madhapur",
            "conversation_history": h4,
        })
        self.assertEqual(res5.status_code, 200)
        d5 = res5.json()
        self.assertIn("Madhapur", d5.get("location", ""))
        self.assertNotIn("Secunderabad", d5.get("location", ""))
        self.assertNotIn("Tarnaka", d5.get("location", ""))

    # -------------------------------------------------------------------------
    # 3. No Silent Narayanguda Substitution for Unknown Locality
    # -------------------------------------------------------------------------
    def test_unsupported_locality_does_not_silently_substitute_narayanguda(self):
        """Querying an unknown location outside Hyderabad must NOT silently substitute Narayanguda."""
        loc = LocationResolver.resolve(explicit_location="Paris")
        self.assertIsNone(loc)

        from backend.agents.traffic_agent.service import get_traffic_service
        trf_svc = get_traffic_service()
        res = trf_svc.get_traffic_kpis(location="Paris")
        self.assertEqual(res.status, "unavailable")
        self.assertNotIn("Narayanguda", res.location)


if __name__ == "__main__":
    unittest.main()

