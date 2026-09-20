"""
Contract-Aware Autonomous Planner Dispatch and Execution Tests.
Architecture: Frontend -> LLM Planner -> Specialist Agents -> LLM Planner -> Frontend.
No Orchestrator.
"""

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.supervisor.main import app


class TestPlannerContractAwareArchitecture(unittest.TestCase):
    def setUp(self):
        os.environ["LLM_PROVIDER"] = "mock"
        self.client = TestClient(app)

    def tearDown(self):
        os.environ.pop("LLM_PROVIDER", None)

    def test_existing_specialist_apis_functional(self):
        """All 5 specialist APIs respond to health/status queries."""
        r_trf = self.client.get("/api/v1/traffic/kpis?location=Narayanguda")
        self.assertEqual(r_trf.status_code, 200)

        r_wtr = self.client.get("/api/v1/weather/current?location=Narayanguda")
        self.assertEqual(r_wtr.status_code, 200)

        r_pol = self.client.get("/api/v1/pollution/aqi-summary?location=Narayanguda")
        self.assertEqual(r_pol.status_code, 200)

        r_eng = self.client.get("/api/v1/energy/grid-status?location=Narayanguda")
        self.assertEqual(r_eng.status_code, 200)

        r_sim = self.client.post("/api/v1/simulation/run", json={
            "scenario_name": "narayanguda_test",
            "target_location": "Narayanguda",
        })
        self.assertEqual(r_sim.status_code, 200)

    def test_openapi_swagger_contract(self):
        """OpenAPI schema is valid and accessible."""
        res = self.client.get("/openapi.json")
        self.assertEqual(res.status_code, 200)
        schema = res.json()
        self.assertIn("paths", schema)
        self.assertIn("/api/v1/traffic/kpis", schema["paths"])

    def test_planner_traffic_only(self):
        """Basic traffic planning request."""
        res = self.client.post("/agents/planner/plan", json={
            "request_id": "REQ-TRF-01",
            "objective": "Traffic congestion is high at Narayanguda",
            "location": "Narayanguda",
            "domains": ["traffic"],
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["request_id"], "REQ-TRF-01")

    def test_production_without_llm_api_key_fails_structured(self):
        """In production without LLM_API_KEY, planner returns clear 503 error."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "groq", "LLM_API_KEY": ""}, clear=True):
            res = self.client.post("/agents/planner/plan", json={
                "request_id": "REQ-NO-KEY",
                "objective": "Heavy traffic at Gachibowli",
                "location": "Gachibowli",
                "domains": ["traffic"],
            })
            self.assertEqual(res.status_code, 503)

            response = self.client.post("/agents/orchestrator/execute", json=payload)
            self.assertEqual(response.status_code, 200)
            data = response.json()

            self.assertEqual(data["status"], "FAILED")
            self.assertIn("traffic", data["failures"])
            self.assertEqual(data["failures"]["traffic"]["agent"], "traffic_agent")
            self.assertEqual(data["failures"]["traffic"]["status"], "FAILED")
            self.assertIn("unavailable", data["failures"]["traffic"]["error"].lower())

            # Planner feedback reflects failure
            self.assertIsNotNone(data["planner_feedback"])
            feedback = data["planner_feedback"]
            self.assertIn("traffic", feedback["failures"])
            self.assertEqual(feedback["decision"], "HANDLE_AGENT_FAILURES")
            self.assertIn("agent_failures", feedback["insights"])
        finally:
            os.environ.pop("TRAFFIC_AGENT_URL", None)

    def test_dispatch_pollution_only(self):
        """Test that a pollution-only objective only dispatches to the Pollution agent."""
        payload = {
            "request_id": "REQ-TEST-POLL-01",
            "workflow": "monitor-detect-understand",
            "steps": [],
            "priority": 3,
            "objective": "Monitor city-wide AQI and air pollution levels",
            "location": "Bollaram",
            "domains": [],
            "constraints": [],
        }

        response = self.client.post("/agents/orchestrator/execute", json=payload)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["status"], "COMPLETED")
        self.assertIn("pollution", data["assigned_capabilities"])
        self.assertNotIn("traffic", data["assigned_capabilities"])
        self.assertEqual(data["dispatched_agents"], ["pollution_agent"])
        self.assertIn("pollution", data["collected_results"])
        poll_data = data["collected_results"]["pollution"]
        self.assertIn("city_avg_aqi", poll_data)
        self.assertIn("stations", poll_data)

        # Planner feedback receives pollution data
        self.assertIn("pollution", data["planner_feedback"]["received_results"])
        self.assertIn("pollution_assessment", data["planner_feedback"]["insights"])

    def test_unknown_capability_error(self):
        """Test that an unknown capability requested from planner returns 400."""
        from backend.supervisor.main import _extract_required_capabilities, PlannerPlanResponse
        fake_plan = PlannerPlanResponse(
            request_id="REQ-TEST-UNKNOWN",
            objective="Travel to Mars",
            likely_causes=["unknown"],
            interventions=["launch"],
            required_data=["rocket"],
            scenarios=[],
            planner_confidence=0.5,
            required_capabilities=["quantum_teleportation"],
        )
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            _extract_required_capabilities(fake_plan)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail["error"]["code"], "UNKNOWN_CAPABILITY")

    def test_missing_objective_error(self):
        """Test error when objective is missing and request not found in planning requests."""
        payload = {
            "request_id": "REQ-NO-OBJ",
            "workflow": "monitor-detect-understand",
            "steps": [],
            "priority": 3,
        }
        response = self.client.post("/agents/orchestrator/execute", json=payload)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        error_obj = data.get("detail", data).get("error", {})
        self.assertEqual(error_obj["code"], "PLANNER_INPUT_MISSING")

    def test_planner_feedback_endpoint_direct(self):
        """Direct test of POST /agents/planner/feedback endpoint."""
        feedback_payload = {
            "request_id": "REQ-FEEDBACK-DIRECT",
            "task_id": "orctask_test123",
            "objective": "Mitigate peak traffic during storm",    def test_test1_weather_and_traffic_cross_analysis(self):
        """Cross-analysis between weather and traffic."""
        res = self.client.post("/agents/planner/feedback", json={
            "request_id": "REQ-WT-01",
            "task_id": "task_wt_01",
            "objective": "Traffic is high and I want to know why",            "location": "Narayanguda",
            "domains": ["traffic", "weather"],
            "assigned_capabilities": ["traffic", "weather"],
            "dispatched_agents": ["traffic_agent", "weather_agent"],
            "collected_results": {
                "traffic": {"congestion_index": 78.5, "average_speed_kmh": 18.2, "corridors": []},
                "weather": {"condition": "Rain", "precipitation_mm": 15.0, "temperature_c": 26.0},
            },
            "failures": {},
        })
        self.assertEqual(res.status_code, 200)

    def test_test2_traffic_diagnosis_before_intervention(self):
        """Traffic diagnosis evaluated before intervention."""
        res = self.client.post("/agents/planner/feedback", json={
            "request_id": "REQ-DIAG-01",
            "task_id": "task_diag_01",
            "objective": "Diagnose corridor bottlenecks",
            "location": "Narayanguda",
            "domains": ["traffic"],
            "assigned_capabilities": ["traffic"],
            "dispatched_agents": ["traffic_agent"],
            "collected_results": {
                "traffic": {"congestion_index": 65.0, "average_speed_kmh": 22.0, "corridors": []},
            },
            "failures": {},
        })
        self.assertEqual(res.status_code, 200)

    def test_test3_simulation_payload_derived_from_traffic_results(self):
        """Simulation context derived properly."""
        res = self.client.post("/agents/planner/feedback", json={
            "request_id": "REQ-SIM-01",
            "task_id": "task_sim_01",
            "objective": "How can we reduce traffic at Narayanguda?",
            "location": "Narayanguda",
            "domains": ["traffic"],
            "assigned_capabilities": ["traffic"],
            "dispatched_agents": ["traffic_agent"],
            "collected_results": {
                "traffic": {"congestion_index": 82.0, "average_speed_kmh": 14.5, "corridors": []},
            },
            "failures": {},
        })
        self.assertEqual(res.status_code, 200)

    def test_test4_missing_information_check(self):
        """Missing information triggers replanning."""
        res = self.client.post("/agents/planner/feedback", json={
            "request_id": "REQ-MISSING-01",
            "task_id": "task_missing_01",
            "objective": "Reduce congestion with signal timing",
            "location": "Narayanguda",
            "domains": ["traffic"],
            "assigned_capabilities": ["traffic"],
            "dispatched_agents": ["traffic_agent"],
            "collected_results": {
                "traffic": {"congestion_index": 80.0, "average_speed_kmh": 15.0},
            },
            "failures": {},
        })
        self.assertEqual(res.status_code, 200)

    def test_out_of_scope_gatekeeping_priority(self):
        """Test that explicit programming/trivia query is rejected even if domain keyword is present."""
        payload = {
            "request_id": "REQ-TEST-OOS-01",
            "objective": "Write python code to compute traffic congestion",
        }
        response = self.client.post("/agents/planner/plan", json=payload)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        error_info = data.get("error") or data.get("detail", {}).get("error", {})
        self.assertEqual(error_info.get("code"), "QUERY_OUT_OF_SCOPE")

    def test_domain_tailored_causes_and_evidence_for_energy(self):
        """Test that an energy query receives energy-specific likely causes, required data, and scenarios."""
        payload = {
            "request_id": "REQ-TEST-ENERGY-PLAN",
            "objective": "Optimize substation power load and transformer capacity in HITECH City",
            "domains": ["energy"],
        }
        response = self.client.post("/agents/planner/plan", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("energy", data["required_capabilities"])
        # Verify energy-tailored causes and data
        self.assertTrue(any("transformer" in cause or "demand" in cause or "peak" in cause for cause in data["likely_causes"]))
        self.assertTrue(any("substation" in req or "load" in req for req in data["required_data"]))
        self.assertTrue(any("grid" in s["label"] or "peak-shaving" in s["label"] for s in data["scenarios"]))

    def test_cross_domain_dispatch_with_energy(self):
        """Test dispatching energy capability in orchestrator execute."""
        payload = {
            "request_id": "REQ-TEST-ENERGY-ORC",
            "workflow": "monitor-detect-understand",
            "steps": [],
            "priority": 3,
            "objective": "Optimize power consumption and peak load in Madhapur",
            "location": "Madhapur",
            "domains": ["energy"],
            "constraints": [],
        }
        response = self.client.post("/agents/orchestrator/execute", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "COMPLETED")
        self.assertIn("energy", data["assigned_capabilities"])
        self.assertIn("energy", data["collected_results"])
        self.assertIn("load_pct", data["collected_results"]["energy"])    def test_test5_malformed_output_detection(self):
        """Malformed output is handled safely."""
        res = self.client.post("/agents/planner/feedback", json={
            "request_id": "REQ-MALFORMED-01",
            "task_id": "task_malformed_01",
            "objective": "Assess traffic",
            "location": "Narayanguda",
            "domains": ["traffic"],
            "assigned_capabilities": ["traffic"],
            "dispatched_agents": ["traffic_agent"],
            "collected_results": {
                "traffic": {"corrupted": True},
            },
            "failures": {},
        })
        self.assertEqual(res.status_code, 200)
    def test_test6_multi_cycle_reasoning_optimization(self):
        """Multi-cycle reasoning with simulation."""
        res = self.client.post("/agents/planner/feedback", json={
            "request_id": "REQ-CYCLE-01",
            "task_id": "task_cycle_01",
            "objective": "Optimize corridor flow",
            "location": "Narayanguda",
            "domains": ["traffic", "simulation"],
            "assigned_capabilities": ["traffic", "simulation"],
            "dispatched_agents": ["traffic_agent", "simulation_agent"],
            "collected_results": {
                "traffic": {"congestion_index": 70.0, "average_speed_kmh": 20.0},
                "simulation": {"status": "SUCCESS", "metrics": {"avg_speed_kmh": 26.5, "avg_waiting_time_sec": 35.0}},
            },
            "failures": {},
        })
        self.assertEqual(res.status_code, 200)

    def test_test7_traffic_and_pollution_cross_analysis(self):
        """Traffic and pollution cross-analysis."""
        res = self.client.post("/agents/planner/feedback", json={
            "request_id": "REQ-TP-01",
            "task_id": "task_tp_01",
            "objective": "Correlate traffic emissions with air quality",
            "location": "Nacharam",
            "domains": ["traffic", "pollution"],
            "assigned_capabilities": ["traffic", "pollution"],
            "dispatched_agents": ["traffic_agent", "pollution_agent"],
            "collected_results": {
                "traffic": {"congestion_index": 75.0, "average_speed_kmh": 17.0},
                "pollution": {"city_avg_aqi": 165, "dominant_pollutant": "PM2.5"},
            },
            "failures": {},
        })
        self.assertEqual(res.status_code, 200)

    def test_test8_traffic_and_energy_cross_analysis(self):
        """Traffic and energy cross-analysis."""
        res = self.client.post("/agents/planner/feedback", json={
            "request_id": "REQ-TE-01",
            "task_id": "task_te_01",
            "objective": "Correlate evening rush hour with grid substation load",
            "location": "Gachibowli",
            "domains": ["traffic", "energy"],
            "assigned_capabilities": ["traffic", "energy"],
            "dispatched_agents": ["traffic_agent", "energy_agent"],
            "collected_results": {
                "traffic": {"congestion_index": 72.0, "average_speed_kmh": 19.0},
                "energy": {"load_pct": 82.5, "current_load_mw": 5120.0},
            },
            "failures": {},
        })
        self.assertEqual(res.status_code, 200)
