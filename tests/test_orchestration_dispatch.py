"""
Unit and integration tests for Smart City Orchestrator Agent Dispatch & Planner Feedback.
"""

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.supervisor.main import app, AGENT_REGISTRY, orchestrator_tasks


class TestOrchestratorAgentDispatch(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_dispatch_traffic_and_weather(self):
        """Test that a traffic + weather request dispatches to Traffic & Weather agents and sends results to Planner."""
        payload = {
            "request_id": "REQ-TEST-TW-01",
            "workflow": "monitor-detect-understand",
            "steps": [],
            "priority": 3,
            "objective": "Find the risk of heavy traffic due to rainfall",
            "location": "Narayanguda",
            "domains": ["traffic", "weather"],
            "constraints": [],
        }

        response = self.client.post("/agents/orchestrator/execute", json=payload)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["request_id"], "REQ-TEST-TW-01")
        self.assertEqual(data["status"], "COMPLETED")
        self.assertIn("traffic", data["assigned_capabilities"])
        self.assertIn("weather", data["assigned_capabilities"])
        self.assertNotIn("energy", data["assigned_capabilities"])
        self.assertNotIn("pollution", data["assigned_capabilities"])
        self.assertNotIn("simulation", data["assigned_capabilities"])

        # Dispatched agents
        self.assertEqual(sorted(data["dispatched_agents"]), ["traffic_agent", "weather_agent"])

        # Collected results
        results = data["collected_results"]
        self.assertIn("traffic", results)
        self.assertIn("weather", results)
        self.assertNotIn("energy", results)
        self.assertNotIn("pollution", results)
        self.assertNotIn("simulation", results)

        # Verify real mock agent response structures
        traffic_data = results["traffic"]
        self.assertIn("active_vehicles", traffic_data)
        self.assertIn("corridors", traffic_data)
        self.assertIn("congestion_index", traffic_data)

        weather_data = results["weather"]
        self.assertIn("city", weather_data)
        self.assertIn("temperature_c", weather_data)
        self.assertIn("humidity_pct", weather_data)

        self.assertEqual(data["failures"], {})

        # Verify Planner Feedback in execute response
        self.assertIsNotNone(data["planner_feedback"])
        feedback = data["planner_feedback"]
        self.assertEqual(feedback["status"], "RECEIVED")
        self.assertEqual(feedback["decision"], "PROCEED_TO_EVALUATION")
        self.assertIn("traffic", feedback["received_results"])
        self.assertIn("weather", feedback["received_results"])
        self.assertEqual(feedback["received_results"]["traffic"], traffic_data)
        self.assertEqual(feedback["received_results"]["weather"], weather_data)
        self.assertIn("traffic_assessment", feedback["insights"])
        self.assertIn("weather_assessment", feedback["insights"])

        # Verify task detail endpoint
        task_id = data["task_id"]
        task_resp = self.client.get(f"/agents/orchestrator/tasks/{task_id}")
        self.assertEqual(task_resp.status_code, 200)
        task_data = task_resp.json()
        self.assertEqual(task_data["task_id"], task_id)
        self.assertEqual(task_data["status"], "COMPLETED")
        self.assertEqual(task_data["current_step"], "planner_feedback")
        self.assertEqual(task_data["completed_steps"], ["planner", "agent_dispatch", "planner_feedback"])
        self.assertEqual(task_data["dispatched_agents"], ["traffic_agent", "weather_agent"])
        self.assertIn("traffic", task_data["collected_results"])
        self.assertIn("weather", task_data["collected_results"])
        self.assertIsNotNone(task_data["planner_feedback"])
        self.assertEqual(task_data["planner_feedback"]["decision"], "PROCEED_TO_EVALUATION")

    def test_planner_feedback_receives_exact_results(self):
        """Verify that Planner feedback receives the exact unmodified mock results from specialist agents."""
        payload = {
            "request_id": "REQ-TEST-EXACT-01",
            "workflow": "monitor-detect-understand",
            "steps": [],
            "priority": 3,
            "objective": "Find the risk of heavy traffic due to rainfall",
            "location": "Narayanguda",
            "domains": ["traffic", "weather"],
            "constraints": [],
        }

        response = self.client.post("/agents/orchestrator/execute", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        collected = data["collected_results"]
        received = data["planner_feedback"]["received_results"]

        # Exact matching of collected and received payload
        self.assertEqual(collected, received)
        self.assertEqual(collected["traffic"]["active_vehicles"], 2342)
        self.assertEqual(collected["weather"]["temperature_c"], 31.5)

    def test_dispatch_energy_only(self):
        """Test that an energy-only objective only dispatches to the Energy agent and passes results to Planner."""
        payload = {
            "request_id": "REQ-TEST-ENERGY-01",
            "workflow": "monitor-detect-understand",
            "steps": [],
            "priority": 3,
            "objective": "Optimize substation energy grid load",
            "location": "Madhapur",
            "domains": ["energy"],
            "constraints": [],
        }

        response = self.client.post("/agents/orchestrator/execute", json=payload)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["status"], "COMPLETED")
        self.assertIn("energy", data["assigned_capabilities"])
        self.assertNotIn("traffic", data["assigned_capabilities"])
        self.assertNotIn("weather", data["assigned_capabilities"])

        self.assertEqual(data["dispatched_agents"], ["energy_agent"])
        self.assertIn("energy", data["collected_results"])
        self.assertIn("current_load_mw", data["collected_results"]["energy"])
        self.assertIn("substations", data["collected_results"]["energy"])

        # Planner feedback receives energy data
        self.assertIn("energy", data["planner_feedback"]["received_results"])
        self.assertIn("energy_assessment", data["planner_feedback"]["insights"])

    def test_dispatch_simulation(self):
        """Test dispatching to the Simulation agent and recording Planner feedback."""
        payload = {
            "request_id": "REQ-TEST-SIM-01",
            "workflow": "simulate-scenario",
            "steps": [],
            "priority": 2,
            "objective": "Run simulation of intersection traffic signal changes",
            "location": "Gachibowli",
            "domains": ["traffic"],
            "constraints": [],
        }

        response = self.client.post("/agents/orchestrator/execute", json=payload)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("simulation", data["assigned_capabilities"])
        self.assertIn("simulation_agent", data["dispatched_agents"])
        self.assertIn("simulation", data["collected_results"])
        sim_data = data["collected_results"]["simulation"]
        self.assertEqual(sim_data["status"], "COMPLETED")
        self.assertIn("metrics", sim_data)

        # Planner feedback
        self.assertIn("simulation", data["planner_feedback"]["received_results"])
        self.assertIn("simulation_assessment", data["planner_feedback"]["insights"])

    def test_selective_dispatch_does_not_call_unselected_agents(self):
        """Verify using mocks that unselected agents are never invoked."""
        payload = {
            "request_id": "REQ-TEST-SELECTIVE-01",
            "workflow": "monitor-detect-understand",
            "steps": [],
            "priority": 3,
            "objective": "Monitor weather updates for the city",
            "location": "Hyderabad",
            "domains": ["weather"],
            "constraints": [],
        }

        response = self.client.post("/agents/orchestrator/execute", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("weather", data["assigned_capabilities"])
        self.assertNotIn("traffic", data["assigned_capabilities"])
        self.assertNotIn("energy", data["assigned_capabilities"])
        self.assertEqual(data["dispatched_agents"], ["weather_agent"])
        self.assertIn("weather", data["collected_results"])
        self.assertNotIn("traffic", data["collected_results"])
        self.assertNotIn("energy", data["collected_results"])

    def test_agent_failure_handling(self):
        """Test handling of agent failure (e.g. connection error / bad URL) and reporting to Planner."""
        os.environ["TRAFFIC_AGENT_URL"] = "http://127.0.0.1:59999"
        try:
            payload = {
                "request_id": "REQ-TEST-FAIL-01",
                "workflow": "monitor-detect-understand",
                "steps": [],
                "priority": 3,
                "objective": "Monitor traffic congestion",
                "location": "Punjagutta",
                "domains": ["traffic"],
                "constraints": [],
            }

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
        self.assertEqual(data["detail"]["error"]["code"], "PLANNER_INPUT_MISSING")

    def test_planner_feedback_endpoint_direct(self):
        """Direct test of POST /agents/planner/feedback endpoint."""
        feedback_payload = {
            "request_id": "REQ-FEEDBACK-DIRECT",
            "task_id": "orctask_test123",
            "objective": "Mitigate peak traffic during storm",
            "location": "Narayanguda",
            "domains": ["traffic", "weather"],
            "assigned_capabilities": ["traffic", "weather"],
            "dispatched_agents": ["traffic_agent", "weather_agent"],
            "collected_results": {
                "traffic": {
                    "active_vehicles": 1850,
                    "congestion_index": 74.5,
                    "corridors": [{"id": "C1", "name": "Narayanguda Main", "status": "HEAVY"}]
                },
                "weather": {
                    "condition": "Heavy Rain",
                    "precipitation_mm": 22.5,
                    "temperature_c": 28.0
                }
            },
            "failures": {},
            "constraints": []
        }

        response = self.client.post("/agents/planner/feedback", json=feedback_payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "RECEIVED")
        self.assertEqual(data["decision"], "PROCEED_TO_EVALUATION")
        self.assertIn("traffic_assessment", data["insights"])
        self.assertEqual(data["insights"]["traffic_assessment"]["congestion_index"], 74.5)
        self.assertIn("weather_assessment", data["insights"])
        self.assertEqual(data["insights"]["weather_assessment"]["condition"], "Heavy Rain")

    def test_no_duplicate_feedback(self):
        """Verify that Planner feedback is executed once and recorded in completed_steps."""
        payload = {
            "request_id": "REQ-TEST-ONCE-01",
            "workflow": "monitor-detect-understand",
            "steps": [],
            "priority": 3,
            "objective": "Find the risk of heavy traffic due to rainfall",
            "location": "Narayanguda",
            "domains": ["traffic", "weather"],
            "constraints": [],
        }

        response = self.client.post("/agents/orchestrator/execute", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        task_id = data["task_id"]

        task_detail = orchestrator_tasks[task_id]
        self.assertEqual(task_detail.completed_steps.count("planner_feedback"), 1)

    def test_openapi_swagger_contract(self):
        """Smoke test FastAPI Swagger/OpenAPI contract generation."""
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        openapi = response.json()
        self.assertEqual(openapi["info"]["title"], "SUPADSP Unified API Contract")
        paths = openapi["paths"]
        self.assertIn("/agents/orchestrator/execute", paths)
        self.assertIn("/agents/orchestrator/tasks/{task_id}", paths)
        self.assertIn("/agents/planner/plan", paths)
        self.assertIn("/agents/planner/feedback", paths)


if __name__ == "__main__":
    unittest.main()
