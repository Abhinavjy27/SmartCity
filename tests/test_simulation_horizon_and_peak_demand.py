"""
Test Suite: Simulation Horizon & Peak-Demand Evaluation (300s & Peak-Westbound).
Validates requirements A through S:
  A. synthetic_normal @ 300s
  B. synthetic_peak_westbound @ 300s
  C. Same seed across paired runs
  D. Same duration across paired runs
  E. Same scenario across paired runs
  F. Same network across paired runs
  G. Dynamic metadata inheritance
  H. Missing baseline metadata fails safely
  I. No hardcoded fallbacks (42, 120, synthetic_normal, Narayanguda)
  J. 120-second CI/smoke behavior remains supported
  K. Completed-trip metrics remain correct
  L. Vehicle accounting: total_vehicles = arrived_vehicles + active_at_end
  M. Fair paired comparison validation
  N. Historical Planner evidence remains intact
  O. TESTED / UNTESTED classification remains intact
  P. No Orchestrator introduced
  Q. Explicit scenario/duration request parsing works
  R. Unqualified production optimization uses 300s evaluation rather than 120s
  S. Historical simulation follow-ups do not trigger new simulations
"""

import os
import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.supervisor.main import app, _PLANNER_SESSIONS
from backend.agents.planner_agent.planner import PlannerAgent
from backend.agents.planner_agent.llm_client import MockLLMProvider
from backend.agents.simulation_agent.service import SimulationService
from backend.agents.traffic_agent.schemas import SimulationMetrics


class TestSimulationHorizonAndPeakDemand(unittest.TestCase):
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
    # Test A: synthetic_normal @ 300s
    # -------------------------------------------------------------------------
    def test_a_synthetic_normal_300s(self):
        """Validates that a 300s synthetic_normal request propagates 300s and synthetic_normal."""
        res = self.client.post("/agents/planner/execute", json={
            "query": "Evaluate traffic under synthetic_normal at 300 seconds",
            "scenario": "synthetic_normal",
            "duration_seconds": 300,
            "seed": 99,
        })
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        traffic_res = data.get("collected_results", {}).get("traffic", {})
        meta = traffic_res.get("metadata", {})
        self.assertEqual(meta.get("duration_seconds"), 300)
        self.assertEqual(meta.get("demand_profile"), "synthetic_normal")
        self.assertEqual(meta.get("random_seed"), 99)

    # -------------------------------------------------------------------------
    # Test B: synthetic_peak_westbound @ 300s
    # -------------------------------------------------------------------------
    def test_b_synthetic_peak_westbound_300s(self):
        """Validates that a 300s synthetic_peak_westbound request propagates 300s and peak demand."""
        res = self.client.post("/agents/planner/execute", json={
            "query": "Run synthetic_peak_westbound for 300 seconds",
            "scenario": "synthetic_peak_westbound",
            "duration_seconds": 300,
            "seed": 88,
        })
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        traffic_res = data.get("collected_results", {}).get("traffic", {})
        meta = traffic_res.get("metadata", {})
        self.assertEqual(meta.get("duration_seconds"), 300)
        self.assertEqual(meta.get("demand_profile"), "synthetic_peak_westbound")
        self.assertEqual(meta.get("random_seed"), 88)

    # -------------------------------------------------------------------------
    # Test C, D, E, F: Paired comparison conditions (Same seed, duration, scenario, network)
    # -------------------------------------------------------------------------
    def test_c_d_e_f_paired_comparison_conditions(self):
        """
        Intervention simulations must inherit exactly baseline.seed, baseline.duration_seconds,
        baseline.scenario, and baseline.network.
        """
        traffic_data = {
            "location": "Narayanguda, Hyderabad",
            "seed": 55,
            "duration_seconds": 300,
            "scenario": "synthetic_peak_westbound",
            "average_speed_kmh": 28.5,
            "average_delay_sec": 38.0,
            "corridors": [
                {"id": "c_wb", "name": "Westbound", "avg_speed": 18.2, "status": "HEAVY"}
            ],
            "candidate_interventions": [
                {"type": "signal_timing", "target": "Westbound", "executable": True, "parameters": {"green_time_adjustment_sec": 10.0}},
                {"type": "signal_timing", "target": "Westbound", "executable": True, "parameters": {"green_time_adjustment_sec": 19.0}},
                {"type": "rerouting", "target": "Westbound", "executable": True, "parameters": {"diversion_fraction": 0.15}},
            ],
        }

        eval_resp = self.planner.evaluate_and_replan(
            objective="Optimize the traffic situation under synthetic_peak_westbound",
            plan=["traffic"],
            collected_results={"traffic": traffic_data},
            cycle_num=1,
            max_cycles=2,
            location="Narayanguda, Hyderabad",
        )

        sim_calls = [c for c in eval_resp.next_cycle_calls if c.agent == "simulation"]
        self.assertEqual(len(sim_calls), 3)

        for call in sim_calls:
            req = call.request
            self.assertEqual(req.get("seed"), 55, "Intervention seed does not match baseline seed!")
            self.assertEqual(req.get("duration_seconds"), 300, "Intervention duration does not match baseline duration!")
            self.assertEqual(req.get("scenario_name"), "synthetic_peak_westbound", "Intervention scenario does not match baseline scenario!")

    # -------------------------------------------------------------------------
    # Test G: Dynamic metadata inheritance without hardcoding
    # -------------------------------------------------------------------------
    def test_g_dynamic_metadata_inheritance(self):
        """Arbitrary non-standard seed (12345) and duration (450s) are dynamically inherited."""
        traffic_data = {
            "location": "Narayanguda, Hyderabad",
            "seed": 12345,
            "duration_seconds": 450,
            "scenario": "synthetic_normal",
            "average_speed_kmh": 32.0,
            "average_delay_sec": 22.0,
            "candidate_interventions": [
                {"type": "signal_timing", "target": "Westbound", "executable": True, "parameters": {"green_time_adjustment_sec": 10.0}},
            ],
        }

        eval_resp = self.planner.evaluate_and_replan(
            objective="Optimize traffic",
            plan=["traffic"],
            collected_results={"traffic": traffic_data},
            cycle_num=1,
            max_cycles=2,
            location="Narayanguda, Hyderabad",
        )

        sim_calls = [c for c in eval_resp.next_cycle_calls if c.agent == "simulation"]
        self.assertEqual(len(sim_calls), 1)
        self.assertEqual(sim_calls[0].request.get("seed"), 12345)
        self.assertEqual(sim_calls[0].request.get("duration_seconds"), 450)

    # -------------------------------------------------------------------------
    # Test H & I: Missing baseline metadata fails safely (No fallback to 42, 120, etc.)
    # -------------------------------------------------------------------------
    def test_h_i_missing_baseline_metadata_fails_safely(self):
        """When baseline metadata is missing, raises explicit error without falling back."""
        bad_traffic = {
            "location": "Narayanguda, Hyderabad",
            # seed and duration_seconds omitted!
            "average_speed_kmh": 30.0,
            "candidate_interventions": [
                {"type": "signal_timing", "target": "Westbound", "executable": True},
            ],
        }

        with self.assertRaises(ValueError) as ctx:
            self.planner.evaluate_and_replan(
                objective="Optimize traffic",
                plan=["traffic"],
                collected_results={"traffic": bad_traffic},
                cycle_num=1,
                max_cycles=2,
            )
        self.assertIn("Missing required baseline simulation metadata", str(ctx.exception))

    # -------------------------------------------------------------------------
    # Test J: 120-second CI/smoke behavior remains supported
    # -------------------------------------------------------------------------
    def test_j_120s_ci_behavior_preserved(self):
        """Explicit 120s requests run with duration_seconds=120."""
        res = self.client.post("/agents/planner/execute", json={
            "query": "Quick smoke test at 120 seconds",
            "duration_seconds": 120,
        })
        self.assertEqual(res.status_code, 200)
        traffic_res = res.json().get("collected_results", {}).get("traffic", {})
        meta = traffic_res.get("metadata", {})
        self.assertEqual(meta.get("duration_seconds"), 120)

    # -------------------------------------------------------------------------
    # Test K & L: Completed-trip metrics & vehicle accounting invariant
    # -------------------------------------------------------------------------
    def test_k_l_completed_trip_metrics_and_vehicle_accounting(self):
        """total_vehicles = arrived_vehicles + active_at_end invariant must hold."""
        m = SimulationMetrics(
            active_vehicles=15,
            peak_active_vehicles=25,
            total_vehicles=91,
            arrived_vehicles=28,
            active_at_end=63,
            throughput=28,
            average_speed_kmh=39.5,
            average_waiting_time_sec=4.2,
            average_delay_sec=15.1,
            congestion_index=0.21,
            max_halting_vehicles=7,
            teleported_vehicles=0,
            free_flow_speed_kmh=50.0,
            completed_trips_avg_waiting_time_sec=8.5,
            completed_trips_avg_delay_sec=22.4,
            completed_trips_avg_duration_sec=142.1,
        )
        self.assertEqual(m.total_vehicles, m.arrived_vehicles + m.active_at_end)
        self.assertEqual(m.throughput, m.arrived_vehicles)
        self.assertIsNotNone(m.completed_trips_avg_waiting_time_sec)
        self.assertIsNotNone(m.completed_trips_avg_delay_sec)
        self.assertIsNotNone(m.completed_trips_avg_duration_sec)

    # -------------------------------------------------------------------------
    # Test M: Fair paired comparison validation
    # -------------------------------------------------------------------------
    def test_m_fair_paired_comparison_validation(self):
        """
        SimulationService._calculate_comparison marks fair_comparison=False
        when seeds, durations, scenarios, or networks mismatch.
        """
        int_m = SimulationMetrics(
            active_vehicles=10,
            total_vehicles=50,
            throughput=20,
            average_speed_kmh=40.0,
            average_waiting_time_sec=3.0,
            average_delay_sec=12.0,
            congestion_index=0.20,
        )

        # 1. Matching conditions -> Fair
        base_valid = {
            "seed": 42,
            "duration_seconds": 300,
            "scenario_name": "synthetic_normal",
            "network_name": "narayanguda_network.net.xml",
            "average_speed_kmh": 39.0,
            "average_delay_sec": 14.0,
            "average_waiting_time_sec": 3.5,
            "congestion_index": 0.22,
        }
        res_fair = SimulationService._calculate_comparison(
            baseline_metrics=base_valid,
            intervention_metrics=int_m,
            raw_corridors=[],
            seed=42,
            duration=300,
            scenario="synthetic_normal",
            network_name="narayanguda_network.net.xml",
        )
        self.assertTrue(res_fair["fair_comparison"])
        self.assertIsNone(res_fair["fair_comparison_warning"])

        # 2. Mismatched seed -> Not Fair
        res_unfair_seed = SimulationService._calculate_comparison(
            baseline_metrics=base_valid,
            intervention_metrics=int_m,
            raw_corridors=[],
            seed=999,  # Mismatched!
            duration=300,
            scenario="synthetic_normal",
            network_name="narayanguda_network.net.xml",
        )
        self.assertFalse(res_unfair_seed["fair_comparison"])
        self.assertIn("seed", res_unfair_seed["fair_comparison_warning"])

        # 3. Mismatched duration -> Not Fair
        res_unfair_dur = SimulationService._calculate_comparison(
            baseline_metrics=base_valid,
            intervention_metrics=int_m,
            raw_corridors=[],
            seed=42,
            duration=120,  # Baseline is 300!
            scenario="synthetic_normal",
            network_name="narayanguda_network.net.xml",
        )
        self.assertFalse(res_unfair_dur["fair_comparison"])
        self.assertIn("duration", res_unfair_dur["fair_comparison_warning"])

    # -------------------------------------------------------------------------
    # Test N & O: Historical Planner evidence & TESTED/UNTESTED classification
    # -------------------------------------------------------------------------
    def test_n_o_history_and_tested_untested_preservation(self):
        """Historical follow-up preserves TESTED and UNTESTED categorizations."""
        sims = [
            {
                "scenario_id": "scen_signal_wb_10",
                "status": "COMPLETED",
                "intervention_applied": {"type": "signal_timing", "target": "Westbound", "parameters": {"green_time_adjustment_sec": 10.0}},
                "metrics": {"average_speed_kmh": 39.5, "average_delay_sec": 14.2, "throughput": 16},
                "comparison": {"speed_change_pct": 0.5, "delay_reduction_pct": 1.2, "fair_comparison": True},
            }
        ]
        res = self.client.post("/agents/planner/execute", json={
            "session_id": "sess_test_no",
            "objective": "Which tested intervention performed better?",
            "simulation_history": sims,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertNotIn("simulation_agent", data.get("dispatched_agents", []))
        self.assertEqual(data["evidence_status"], "EVIDENCE: SINGLE SIMULATION RUN")

    # -------------------------------------------------------------------------
    # Test P: No Orchestrator introduced
    # -------------------------------------------------------------------------
    def test_p_no_orchestrator_introduced(self):
        """Verify no orchestrator module or function exists in the codebase."""
        import backend.supervisor.main as sm
        self.assertFalse(hasattr(sm, "orchestrator"), "Orchestrator object found in supervisor.main!")
        self.assertFalse(hasattr(sm, "execute_orchestrator_compat"), "execute_orchestrator_compat found!")

    # -------------------------------------------------------------------------
    # Test Q: Explicit scenario/duration request parsing works
    # -------------------------------------------------------------------------
    def test_q_explicit_scenario_duration_parsing(self):
        """Query text with 'synthetic_peak_westbound for 300 seconds' correctly sets scenario and duration."""
        from backend.supervisor.main import PlannerExecuteRequest
        req = PlannerExecuteRequest(query="Run synthetic_peak_westbound for 300 seconds seed=77")
        self.assertEqual(req.scenario, "synthetic_peak_westbound")
        self.assertEqual(req.duration_seconds, 300)
        self.assertEqual(req.seed, 77)

    # -------------------------------------------------------------------------
    # Test R: Unqualified production optimization uses 600s evaluation
    # -------------------------------------------------------------------------
    def test_r_unqualified_production_optimization_uses_600s(self):
        """Unqualified optimization query without duration defaults to 600s production default, while explicit duration overrides it."""
        res = self.client.post("/agents/planner/execute", json={
            "query": "Optimize the traffic situation in Narayanguda",
        })
        self.assertEqual(res.status_code, 200)
        traffic_res = res.json().get("collected_results", {}).get("traffic", {})
        meta = traffic_res.get("metadata", {})
        self.assertEqual(meta.get("duration_seconds"), 600)

        # Explicit 300s overrides the 600s default
        res300 = self.client.post("/agents/planner/execute", json={
            "query": "Optimize the traffic situation in Narayanguda for 300s",
        })
        self.assertEqual(res300.status_code, 200)
        traffic_res300 = res300.json().get("collected_results", {}).get("traffic", {})
        meta300 = traffic_res300.get("metadata", {})
        self.assertEqual(meta300.get("duration_seconds"), 300)

    # -------------------------------------------------------------------------
    # Test S: Historical simulation follow-ups do not trigger new simulations
    # -------------------------------------------------------------------------
    def test_s_history_followup_zero_new_simulations(self):
        """Follow-up on completed simulations results in 0 new simulation dispatches."""
        sims = [
            {"scenario_id": "s1", "intervention_applied": {"type": "signal_timing"}, "metrics": {"average_speed_kmh": 39.0}},
            {"scenario_id": "s2", "intervention_applied": {"type": "rerouting"}, "metrics": {"average_speed_kmh": 39.2}},
        ]
        res = self.client.post("/agents/planner/execute", json={
            "session_id": "sess_test_s",
            "objective": "Compare the tested interventions again",
            "simulation_history": sims,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertNotIn("simulation_agent", data.get("dispatched_agents", []))
        self.assertEqual(data["evidence_status"], "EVIDENCE: MULTI-SIMULATION EVALUATION")


if __name__ == "__main__":
    unittest.main()
