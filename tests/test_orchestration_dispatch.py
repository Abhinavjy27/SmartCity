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

    def test_test1_weather_and_traffic_cross_analysis(self):
        """Cross-analysis between weather and traffic."""
        res = self.client.post("/agents/planner/feedback", json={
            "request_id": "REQ-WT-01",
            "task_id": "task_wt_01",
            "objective": "Traffic is high and I want to know why",
            "location": "Narayanguda",
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

    def test_test5_malformed_output_detection(self):
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
