"""
Full Closed-Loop Integration Test:
Planner -> Traffic Baseline (SUMO) -> Planner -> Simulation Agent (SUMO Intervention) -> Planner Comparison -> Final Decision.

Objective:
"Diagnose traffic congestion at Narayanguda and determine whether signal timing optimization could improve the bottleneck."

Architecture:
Frontend -> LLM Planner -> Specialist Agents -> LLM Planner -> Frontend.
Strict Invariant: NO Orchestrator.
"""

import os
import unittest
from fastapi.testclient import TestClient

from backend.supervisor.main import app
from backend.supervisor.agent_client import dispatch_agent


class TestPlannerSimulationClosedLoop(unittest.TestCase):
    def setUp(self):
        os.environ["LLM_PROVIDER"] = "mock"
        self.client = TestClient(app)
        self.request_id = "TEST-LOOP-001"
        self.objective = (
            "Diagnose traffic congestion at Narayanguda and determine whether "
            "signal timing optimization could improve the bottleneck."
        )

    def tearDown(self):
        os.environ.pop("LLM_PROVIDER", None)

    def test_1_autonomous_multicycle_execution(self):
        """
        Executes the autonomous closed-loop pipeline via POST /agents/planner/execute.
        Verifies that:
        1. Cycle 1 collects real SUMO baseline from Traffic Agent.
        2. Planner identifies bottleneck and requests simulation.
        3. Cycle 2 dispatches Simulation Agent to run real SUMO intervention.
        4. Planner evaluates baseline vs intervention comparison metrics and finalizes.
        """
        res = self.client.post("/agents/planner/execute", json={
            "request_id": self.request_id,
            "objective": self.objective,
            "location": "Narayanguda, Hyderabad",
            "max_cycles": 3,
        })
        self.assertEqual(res.status_code, 200, f"Execute failed: {res.text}")
        data = res.json()

        self.assertEqual(data["request_id"], self.request_id)
        self.assertEqual(data["status"], "COMPLETED")
        self.assertGreaterEqual(data["cycle"], 2)

        # Dispatched agents must include both specialist agents
        self.assertIn("traffic_agent", data["dispatched_agents"])
        self.assertIn("simulation_agent", data["dispatched_agents"])

        # Agent results must preserve both baseline and intervention scenarios
        self.assertIn("traffic", data["agent_results"])
        self.assertIn("simulation", data["agent_results"])

        trf_res = data["agent_results"]["traffic"]
        sim_res = data["agent_results"]["simulation"]

        # Check empirical SUMO origin
        self.assertEqual(trf_res.get("source", {}).get("engine"), "SUMO")
        if isinstance(sim_res, list):
            self.assertGreaterEqual(len(sim_res), 1)
            for sc in sim_res:
                self.assertEqual(sc.get("source", {}).get("engine"), "SUMO")
                self.assertTrue(sc.get("source", {}).get("synthetic"))
        else:
            self.assertEqual(sim_res.get("source", {}).get("engine"), "SUMO")
            self.assertTrue(sim_res.get("source", {}).get("synthetic"))

        # Verify final response structure
        final_resp = data.get("final_response") or {}
        self.assertIn("summary", final_resp)
        self.assertIn("recommendation", final_resp)

        # Check diagnosed bottlenecks
        bottlenecks = final_resp.get("diagnosed_bottlenecks") or []
        self.assertGreater(len(bottlenecks), 0)
        bottleneck_text = " ".join(bottlenecks)
        self.assertIn("lowest observed-speed corridor", bottleneck_text.lower())
        self.assertNotIn("lowest flow corridor", bottleneck_text.lower())

        # Check comparison in final reasoning / simulation comparison
        comparison = (
            final_resp.get("metric_changes")
            or final_resp.get("simulation_comparison", {}).get("comparison")
            or (sim_res[0].get("comparison") if isinstance(sim_res, list) else sim_res.get("comparison"))
        )
        self.assertIsNotNone(comparison, "Comparison between baseline and intervention was not returned!")
        self.assertIn("speed_change_pct", comparison)
        self.assertIn("delay_reduction_pct", comparison)

        # Multi-scenario verification: all tested scenarios retained with unique scenario IDs
        tested_scens = final_resp.get("tested_scenarios") or []
        if tested_scens:
            self.assertGreaterEqual(len(tested_scens), 2, "Multi-cycle execution should evaluate at least 2 simulation scenarios")
            scen_ids = [s.get("scenario_id") for s in tested_scens if s.get("scenario_id")]
            self.assertEqual(len(scen_ids), len(set(scen_ids)), "Scenario IDs must be unique across tested configurations")
            # Verify fair comparison
            for s in tested_scens:
                self.assertTrue(s.get("fair_comparison", True), "Scenarios must use identical seeds/parameters for fair comparison")
            # Verify corridor trade-offs
            self.assertIn("corridor_trade_offs", final_resp)
            self.assertGreater(len(final_resp["corridor_trade_offs"]), 0, "Corridor trade-offs must be identified")


    def test_2_step_by_step_granular_loop(self):
        """
        Exercises the granular step-by-step endpoint sequence:
        1. POST /agents/planner/plan
        2. GET /api/v1/traffic/kpis (or dispatch_agent)
        3. POST /agents/planner/feedback (evaluates baseline, decides run_simulation)
        4. POST /api/v1/simulation/run (executes intervention)
        5. POST /agents/planner/feedback (evaluates simulation, finalizes)
        """
        # Step 1: Initial plan
        res1 = self.client.post("/agents/planner/plan", json={
            "request_id": self.request_id,
            "objective": self.objective,
            "location": "Narayanguda, Hyderabad",
        })
        self.assertEqual(res1.status_code, 200)
        plan_data = res1.json()
        self.assertEqual(plan_data["next_action"], "collect_evidence")
        self.assertIn("traffic", plan_data["required_capabilities"])

        # Step 2: Traffic Agent baseline execution
        trf_evidence = dispatch_agent("traffic", {
            "location": "Narayanguda, Hyderabad",
            "purpose": "baseline_traffic_analysis",
            "duration_seconds": 60,
        })
        self.assertIn("metrics", trf_evidence)

        # Step 3: Planner feedback on baseline -> decides run_simulation
        res2 = self.client.post("/agents/planner/feedback", json={
            "request_id": self.request_id,
            "objective": self.objective,
            "cycle": 1,
            "agent": "traffic",
            "result": trf_evidence,
        })
        self.assertEqual(res2.status_code, 200)
        fb1_data = res2.json()
        self.assertEqual(fb1_data["next_action"], "run_simulation")
        self.assertIn("simulation", fb1_data["required_capabilities"])

        # Step 4: Simulation Agent intervention execution
        sim_evidence = dispatch_agent("simulation", {
            "location": "Narayanguda, Hyderabad",
            "scenario_name": "synthetic_normal",
            "duration_seconds": 60,
            "seed": 42,
            "intervention": {
                "type": "signal_timing",
                "target": "Westbound",
                "parameters": {"green_time_adjustment_sec": 19.0},
            },
            "baseline_metrics": trf_evidence,
        })
        self.assertIn("metrics", sim_evidence)

        # Step 5: Planner feedback on first simulation evidence -> identifies trade-off & requests second simulation
        res3 = self.client.post("/agents/planner/feedback", json={
            "request_id": self.request_id,
            "objective": self.objective,
            "cycle": 2,
            "collected_results": {
                "traffic": trf_evidence,
                "simulation": sim_evidence,
            },
        })
        self.assertEqual(res3.status_code, 200)
        fb2_data = res3.json()
        self.assertEqual(fb2_data["decision"], "run_simulation")
        self.assertEqual(fb2_data["next_action"], "run_simulation")
        self.assertIn("simulation", fb2_data["required_capabilities"])

        # Step 6: Simulation Agent second candidate execution (balanced +10.0s green)
        sim_evidence_2 = dispatch_agent("simulation", {
            "location": "Narayanguda, Hyderabad",
            "scenario_name": "synthetic_normal",
            "duration_seconds": 60,
            "seed": 42,
            "intervention": {
                "type": "signal_timing",
                "target": "Westbound",
                "parameters": {"green_time_adjustment_sec": 10.0},
            },
            "baseline_metrics": trf_evidence,
        })
        self.assertIn("metrics", sim_evidence_2)

        # Step 7: Planner feedback on both simulations (cycle 3) -> compares & finalizes
        res4 = self.client.post("/agents/planner/feedback", json={
            "request_id": self.request_id,
            "objective": self.objective,
            "cycle": 3,
            "collected_results": {
                "traffic": trf_evidence,
                "simulation": [sim_evidence, sim_evidence_2],
            },
        })
        self.assertEqual(res4.status_code, 200)
        fb3_data = res4.json()
        self.assertEqual(fb3_data["decision"], "finalize")
        self.assertEqual(fb3_data["next_action"], "finalize")
        self.assertEqual(fb3_data["status"], "SUCCESS")
        self.assertIsNotNone(fb3_data["final_reasoning"])
        self.assertIn("tested_scenarios", fb3_data["final_reasoning"])
        self.assertEqual(len(fb3_data["final_reasoning"]["tested_scenarios"]), 2)

    def test_3_strict_no_orchestrator_invariance(self):
        """
        Verify that no Orchestrator endpoints, routes, or modules exist anywhere in the app.
        """
        openapi = self.client.get("/openapi.json").json()
        paths = openapi.get("paths", {})

        for path in paths.keys():
            self.assertNotIn("orchestrat", path.lower(), f"Forbidden orchestrator path found: {path}")

        for route in app.routes:
            path = getattr(route, "path", "")
            self.assertNotIn("orchestrat", path.lower(), f"Forbidden orchestrator route: {path}")

    def test_4_scenario_identity_and_duplicate_detection(self):
        """
        Verify scenario identities are deterministic and identical requests are detected as duplicates.
        """
        from backend.agents.simulation_agent.service import SimulationService
        from backend.agents.simulation_agent.schemas import InterventionPayload

        # Identical parameters produce identical scenario IDs
        payload1 = InterventionPayload(type="signal_timing", target="Westbound", parameters={"green_time_adjustment_sec": 19.0})
        payload2 = InterventionPayload(type="signal_timing", target="Westbound", parameters={"green_time_adjustment_sec": 19.0})
        id1 = SimulationService.generate_scenario_id(payload1, seed=42)
        id2 = SimulationService.generate_scenario_id(payload2, seed=42)
        self.assertEqual(id1, id2)
        self.assertIn("Westbound", id1)
        self.assertIn("19.0s", id1)
        self.assertIn("seed42", id1)

        # Different parameters produce distinct scenario IDs
        payload_diff = InterventionPayload(type="signal_timing", target="Westbound", parameters={"green_time_adjustment_sec": 10.0})
        id3 = SimulationService.generate_scenario_id(payload_diff, seed=42)
        self.assertNotEqual(id1, id3)

    def test_5_corridor_trade_offs_and_fair_comparison(self):
        """
        Verify that corridor-level degradation and fair comparison checks are computed accurately.
        """
        from backend.agents.simulation_agent.service import get_simulation_service
        from backend.agents.simulation_agent.schemas import SimulationScenarioRequest, InterventionPayload

        service = get_simulation_service()
        baseline_mock = {
            "metadata": {"random_seed": 42, "duration_seconds": 60},
            "metrics": {
                "average_speed_kmh": 39.75,
                "average_delay_sec": 13.80,
                "average_waiting_time_sec": 3.11,
                "congestion_index": 0.205,
                "throughput": 0,
            },
            "corridors": [
                {"id": "COR_NB", "name": "Narayanguda - Chikkadapally Corridor (Northbound)", "avg_speed": 38.8},
                {"id": "COR_SB", "name": "Narayanguda - Barkatpura Corridor (Southbound)", "avg_speed": 37.6},
                {"id": "COR_EB", "name": "Himayat Nagar - Barkatpura (Eastbound)", "avg_speed": 46.3},
                {"id": "COR_WB", "name": "Narayanguda - Hyderguda (Westbound)", "avg_speed": 35.0},
            ]
        }

        req = SimulationScenarioRequest(
            location="Narayanguda, Hyderabad",
            duration_seconds=60,
            seed=42,
            intervention=InterventionPayload(
                type="signal_timing",
                target="Westbound",
                parameters={"green_time_adjustment_sec": 19.0},
            ),
            baseline_metrics=baseline_mock,
        )
        res = service.run_intervention_simulation(req)
        self.assertIsNotNone(res.comparison)
        comp = res.comparison

        # Fair comparison verified
        self.assertTrue(comp.get("fair_comparison"))
        self.assertEqual(comp.get("baseline_seed"), 42)
        self.assertEqual(comp.get("intervention_seed"), 42)

        # Trade-offs identified on non-target corridors
        self.assertIn("corridor_trade_offs", comp)
        trade_offs = comp["corridor_trade_offs"]
        self.assertGreater(len(trade_offs), 0, "Corridor degradation must be identified")
        trade_off_text = " ".join(trade_offs).lower()
        self.assertTrue(any(c in trade_off_text for c in ["southbound", "eastbound", "barkatpura"]))

    def test_6_closed_loop_rerouting_pipeline(self):
        """
        Closed-loop autonomous pipeline where Planner evaluates evidence,
        selects rerouting candidate intervention, executes in real SUMO via TraCI, and synthesizes final result.
        """
        req_body = {
            "request_id": "TEST-REROUTE-LOOP-001",
            "objective": "Diagnose traffic congestion at Narayanguda and evaluate whether dynamic traffic rerouting could reduce the bottleneck.",
            "location": "Narayanguda, Hyderabad",
            "max_cycles": 3,
        }
        res = self.client.post("/agents/planner/execute", json=req_body)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["status"], "COMPLETED")
        self.assertIn("traffic_agent", data["dispatched_agents"])
        self.assertIn("simulation_agent", data["dispatched_agents"])

        # Traffic agent candidate interventions include executable rerouting
        trf_res = data["agent_results"]["traffic"]
        cands = trf_res.get("candidate_interventions", [])
        reroute_cands = [c for c in cands if c["type"] == "rerouting"]
        self.assertGreater(len(reroute_cands), 0)
        self.assertTrue(reroute_cands[0]["executable"])

        # Simulation agent executed real rerouting intervention
        sim_res = data["agent_results"]["simulation"]
        sim_obj = sim_res if isinstance(sim_res, dict) else sim_res[0]
        self.assertEqual(sim_obj.get("status"), "COMPLETED")
        exec_meta = sim_obj.get("execution")
        self.assertIsNotNone(exec_meta)
        self.assertIn(exec_meta.get("status"), ("completed", "partial"))
        self.assertGreater(exec_meta.get("eligible_vehicle_count", 0), 0)
        self.assertGreater(exec_meta.get("rerouted_vehicle_count", 0), 0)
        self.assertGreater(exec_meta.get("actual_diversion_fraction", 0.0), 0.0)

        # Final reasoning synthesizes rerouting evidence
        final_resp = data.get("final_response") or {}
        self.assertIn("summary", final_resp)
        self.assertIn("recommendation", final_resp)


if __name__ == "__main__":
    unittest.main()

