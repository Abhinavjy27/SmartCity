"""
Live Integration Test: Planner -> Traffic Agent (SUMO 1.27.1) -> Planner Pipeline.
Objective: TEST-LIVE-001
"Diagnose current traffic congestion and identify main bottlenecks at Narayanguda, Hyderabad."

Architecture:
Frontend -> LLM Planner -> Specialist Agent (SUMO) -> LLM Planner -> Frontend.
No Orchestrator.
"""

import os
import unittest
from fastapi.testclient import TestClient

from backend.supervisor.main import app
from backend.supervisor.agent_client import dispatch_agent
from backend.agents.planner_agent.planner import get_planner_agent


class TestLivePlannerTrafficPipeline(unittest.TestCase):
    """
    Verification of the Planner -> Traffic Agent -> SUMO -> Traffic Evidence -> Planner loop.
    """

    def setUp(self):
        os.environ["LLM_PROVIDER"] = "mock"
        self.client = TestClient(app)
        self.request_id = "TEST-LIVE-001"
        self.objective = "Diagnose current traffic congestion and identify main bottlenecks at Narayanguda, Hyderabad."

    def tearDown(self):
        os.environ.pop("LLM_PROVIDER", None)

    def test_step1_planner_generates_traffic_request(self):
        """
        Step 1: Planner receives natural-language objective and emits structured agent request
        with next_action='collect_evidence'.
        """
        res = self.client.post("/agents/planner/plan", json={
            "request_id": self.request_id,
            "objective": self.objective,
            "location": "Narayanguda, Hyderabad",
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["request_id"], self.request_id)
        self.assertIn("traffic", data["required_capabilities"])
        self.assertEqual(data["next_action"], "collect_evidence")
        self.assertGreaterEqual(len(data["agent_requests"]), 1)

        req_item = data["agent_requests"][0]
        self.assertEqual(req_item["agent"], "traffic")
        self.assertIn("location", req_item["request"])

    def test_step2_traffic_agent_executes_real_sumo_evidence(self):
        """
        Step 2: Traffic Agent receives request and executes actual Eclipse SUMO 1.27.1
        returning real TraCI empirical telemetry.
        """
        # Dispatch using the client helper
        agent_res = dispatch_agent("traffic", {
            "location": "Narayanguda, Hyderabad",
            "purpose": "baseline_traffic_analysis",
            "duration_seconds": 60,
        })

        self.assertIn("metrics", agent_res)
        metrics = agent_res["metrics"]

        # Assert empirical SUMO values exist
        self.assertIn("average_speed_kmh", metrics)
        self.assertIn("congestion_index", metrics)
        self.assertIn("average_delay_sec", metrics)
        self.assertIn("average_waiting_time_sec", metrics)
        self.assertIn("total_vehicles", metrics)
        self.assertIn("throughput", metrics)

        # Confirm non-empty corridors and authentic SUMO source
        corridors = agent_res.get("corridors") or agent_res.get("corridor_results")
        self.assertIsNotNone(corridors)
        self.assertGreater(len(corridors), 0)
        source_info = agent_res.get("source", {})
        self.assertEqual(source_info.get("engine"), "SUMO")
        self.assertEqual(source_info.get("sumo_version"), "1.27.1")
        self.assertEqual(source_info.get("type"), "simulation")

    def test_step3_feedback_evidence_evaluated_by_planner(self):
        """
        Step 3: Actual SUMO evidence is fed back to the Planner via POST /agents/planner/feedback.
        Planner interprets the evidence and decides next_action='finalize'.
        """
        # 1. Obtain real SUMO evidence from Traffic Agent
        traffic_evidence = dispatch_agent("traffic", {
            "location": "Narayanguda, Hyderabad",
            "purpose": "baseline_traffic_analysis",
            "duration_seconds": 60,
        })

        # 2. Feed evidence to Planner feedback endpoint
        res = self.client.post("/agents/planner/feedback", json={
            "request_id": self.request_id,
            "objective": self.objective,
            "cycle": 1,
            "agent": "traffic",
            "result": traffic_evidence,
        })
        self.assertEqual(res.status_code, 200)
        feedback_data = res.json()

        self.assertEqual(feedback_data["request_id"], self.request_id)
        self.assertEqual(feedback_data["decision"], "finalize")
        self.assertEqual(feedback_data["next_action"], "finalize")
        self.assertIsNotNone(feedback_data.get("final_reasoning"))

        final_reasoning = feedback_data["final_reasoning"]
        self.assertIn("key_findings", final_reasoning)
        self.assertIn("diagnosed_bottlenecks", final_reasoning)

        # Verify findings reference actual SUMO values
        avg_speed = traffic_evidence["metrics"]["average_speed_kmh"]
        findings_text = " ".join(final_reasoning["key_findings"])
        self.assertIn(f"{avg_speed:.2f}", findings_text)

    def test_step4_end_to_end_planner_execute_pipeline(self):
        """
        Step 4: Full automated execution via POST /agents/planner/execute:
        Planner -> dispatch_agent (SUMO) -> Planner evaluate_and_replan.
        """
        res = self.client.post("/agents/planner/execute", json={
            "request_id": self.request_id,
            "objective": self.objective,
            "location": "Narayanguda, Hyderabad",
        })
        self.assertEqual(res.status_code, 200)
        exec_data = res.json()

        self.assertEqual(exec_data["request_id"], self.request_id)
        self.assertEqual(exec_data["status"], "COMPLETED")
        self.assertIn("traffic_agent", exec_data["dispatched_agents"])
        self.assertIn("traffic", exec_data["agent_results"])

        # Check that agent_results has actual SUMO metrics
        traffic_res = exec_data["agent_results"]["traffic"]
        self.assertEqual(traffic_res.get("source", {}).get("engine"), "SUMO")
        self.assertIsNotNone(traffic_res["metrics"]["average_speed_kmh"])
        self.assertIsNotNone(traffic_res["metrics"]["average_speed_kmh"])

        # Check final response
        self.assertIsNotNone(exec_data.get("final_response"))
        final_resp = exec_data["final_response"]
        self.assertIn("key_findings", final_resp)
        self.assertGreater(len(final_resp["key_findings"]), 0)

    def test_step5_strict_no_orchestrator_invariance(self):
        """
        Step 5: Architectural invariant: Ensure NO Orchestrator exists in routes or modules.
        """
        openapi = self.client.get("/openapi.json").json()
        paths = openapi.get("paths", {})

        for path in paths.keys():
            self.assertNotIn("orchestrat", path.lower(), f"Forbidden orchestrator path found: {path}")

        # Check app routes directly
        for route in app.routes:
            path = getattr(route, "path", "")
            self.assertNotIn("orchestrat", path.lower(), f"Forbidden orchestrator route: {path}")


if __name__ == "__main__":
    unittest.main()
