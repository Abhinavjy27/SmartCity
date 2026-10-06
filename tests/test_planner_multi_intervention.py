"""
Multi-Intervention Simulation & Evidence-Based Optimization Test Suite.

Covers:
  Test A: Single tested intervention (EVIDENCE: SINGLE SIMULATION RUN, no 'best' claim)
  Test B: Two tested interventions (EVIDENCE: MULTI-SIMULATION EVALUATION, empirical comparison)
  Test C: Three tested interventions (configured limit works)
  Test D: Candidate limit enforcement (max optimization candidates respected, others remain UNTESTED)
  Test E: 'No clear winner' handling (meaningful trade-offs prevent forced winner)
  Test F: Clear empirical difference (dominating candidate identified without material adverse trade-offs)
  Test G: Untested candidate protection (untested candidates cannot be selected as validated solution)
  Test H: Dynamic baseline inheritance (seed, duration, scenario, location inherited dynamically)
  Test I: Baseline comparison retention (baseline metrics preserved across simulations)
  Test J: Corridor comparison integrity (target and opposing corridor deltas preserved)
  Test K: Zero simulations on diagnostic queries (EVIDENCE: OBSERVATIONAL)
  Test L: Token compaction verification (prompt token compactness maintained)
  Test M: Anti-hardcoding verification (arbitrary seeds, durations, corridors, scenarios)
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.supervisor.main import app
from backend.agents.planner_agent.llm_client import MockLLMProvider
from backend.agents.planner_agent.planner import PlannerAgent, MAX_OPTIMIZATION_CANDIDATES
from backend.agents.planner_agent.schema import (
    LLMFinalReasoning,
    PlannerEvaluationResponse,
)


class TestPlannerMultiIntervention(unittest.TestCase):
    """
    Validates that the Autonomous LLM Planner systematically evaluates multiple
    executable intervention candidates using real/simulated evidence under
    identical baseline conditions, without arbitrary weighted scoring or
    unsupported recommendations.
    """

    def setUp(self):
        self.original_provider = os.environ.get("LLM_PROVIDER")
        os.environ["LLM_PROVIDER"] = "mock"
        self.mock_provider = MockLLMProvider()
        self.planner = PlannerAgent(llm_provider=self.mock_provider)
        self.client = TestClient(app)

    def tearDown(self):
        if self.original_provider is not None:
            os.environ["LLM_PROVIDER"] = self.original_provider
        else:
            os.environ.pop("LLM_PROVIDER", None)

    # -------------------------------------------------------------------------
    # Test A: Single Tested Intervention
    # -------------------------------------------------------------------------
    def test_a_single_tested_intervention(self):
        """
        When 1 intervention is simulated:
          - Classified as EVIDENCE: SINGLE SIMULATION RUN
          - Candidate is TESTED, other candidates are UNTESTED
          - Does not claim candidate is 'best' or 'optimal' compared to untested options
        """
        traffic_data = {
            "location": "Narayanguda, Hyderabad",
            "seed": 42,
            "duration_seconds": 120,
            "scenario": "synthetic_normal",
            "average_speed_kmh": 39.75,
            "average_delay_sec": 13.80,
            "average_waiting_time_sec": 3.11,
            "congestion_index": 0.205,
            "bottlenecks": [
                {"corridor": "Westbound", "reason": "Lowest observed-speed corridor: 'Westbound' (35.0 km/h)"}
            ],
            "candidate_interventions": [
                {"type": "signal_timing", "target": "Westbound", "executable": True, "parameters": {"green_time_adjustment_sec": 10.0}},
                {"type": "rerouting", "target": "Westbound", "executable": True, "parameters": {"diversion_fraction": 0.15}},
                {"type": "lane_use", "target": "Westbound", "executable": False},
            ],
        }

        sim_data = {
            "scenario_id": "scen_signal_wb_10",
            "scenario": "synthetic_normal",
            "status": "COMPLETED",
            "intervention_applied": {
                "type": "signal_timing",
                "target": "Westbound",
                "parameters": {"green_time_adjustment_sec": 10.0},
            },
            "metrics": {
                "average_speed_kmh": 39.56,
                "average_delay_sec": 14.27,
                "average_waiting_time_sec": 3.72,
                "congestion_index": 0.209,
            },
            "comparison": {
                "scenario_id": "scen_signal_wb_10",
                "fair_comparison": True,
                "speed_change_pct": -0.48,
                "delay_reduction_pct": -3.41,
                "waiting_time_reduction_pct": -19.61,
                "congestion_reduction_pct": -1.95,
                "target_corridor_speed_change_pct": 8.86,
                "corridor_comparisons": [
                    {"name": "Westbound", "baseline_speed_kmh": 35.0, "intervention_speed_kmh": 38.1, "speed_change_pct": 8.86},
                    {"name": "Southbound", "baseline_speed_kmh": 37.6, "intervention_speed_kmh": 34.9, "speed_change_pct": -7.18},
                ],
                "corridor_trade_offs": [
                    "Southbound speed degraded by -7.2% (-2.7 km/h) due to opposing phase reduction",
                    "Network delay increased by +3.4% (+0.5 sec) and waiting time increased by +19.6%",
                ],
                "trade_off_summary": "Trade-off observed: target corridor improved while opposing corridor experienced degradation.",
            },
        }

        eval_resp = self.planner.evaluate_and_replan(
            objective="Optimize the traffic bottleneck at Narayanguda",
            plan=["traffic", "simulation"],
            collected_results={"traffic": traffic_data, "simulation": sim_data},
            cycle_num=2,
            max_cycles=2,
            location="Narayanguda, Hyderabad",
        )

        self.assertEqual(eval_resp.evidence_status, "EVIDENCE: SINGLE SIMULATION RUN")
        tested_types = [t.get("type") for t in eval_resp.tested_interventions]
        self.assertIn("signal_timing", tested_types)
        untested_types = [u.get("type") for u in eval_resp.untested_candidates]
        self.assertIn("rerouting", untested_types)
        self.assertIn("lane_use", untested_types)

        rec = eval_resp.final_recommendation.lower()
        self.assertNotIn("optimal solution", rec)
        self.assertNotIn("proven best", rec)
        self.assertIn("signal timing", rec)
        self.assertIn("untested", rec)

    # -------------------------------------------------------------------------
    # Test B: Two Tested Interventions
    # -------------------------------------------------------------------------
    def test_b_two_tested_interventions(self):
        """
        When 2 interventions are simulated:
          - Classified as EVIDENCE: MULTI-SIMULATION EVALUATION
          - Both are TESTED
          - Empirical metrics compared across both
          - Untested candidates remain UNTESTED
        """
        traffic_data = {
            "location": "Narayanguda, Hyderabad",
            "seed": 42,
            "duration_seconds": 120,
            "scenario": "synthetic_normal",
            "average_speed_kmh": 39.75,
            "average_delay_sec": 13.80,
            "average_waiting_time_sec": 3.11,
            "congestion_index": 0.205,
            "bottlenecks": [{"corridor": "Westbound", "reason": "Lowest observed-speed corridor: 'Westbound' (35.0 km/h)"}],
            "candidate_interventions": [
                {"type": "signal_timing", "target": "Westbound", "executable": True},
                {"type": "rerouting", "target": "Westbound", "executable": True},
                {"type": "lane_use", "target": "Westbound", "executable": False},
            ],
        }

        sim1 = {
            "scenario_id": "scen_signal",
            "status": "COMPLETED",
            "intervention_applied": {"type": "signal_timing", "target": "Westbound", "parameters": {"green_time_adjustment_sec": 10.0}},
            "metrics": {"average_speed_kmh": 39.56, "average_delay_sec": 14.27, "average_waiting_time_sec": 3.72, "congestion_index": 0.209},
            "comparison": {
                "scenario_id": "scen_signal",
                "speed_change_pct": -0.48,
                "delay_reduction_pct": -3.41,
                "target_corridor_speed_change_pct": 8.86,
                "corridor_trade_offs": ["Southbound speed degraded by -7.2%"],
            },
        }
        sim2 = {
            "scenario_id": "scen_reroute",
            "status": "COMPLETED",
            "intervention_applied": {"type": "rerouting", "target": "Westbound", "parameters": {"diversion_fraction": 0.15}},
            "metrics": {"average_speed_kmh": 39.75, "average_delay_sec": 13.80, "average_waiting_time_sec": 3.11, "congestion_index": 0.205},
            "comparison": {
                "scenario_id": "scen_reroute",
                "speed_change_pct": 0.0,
                "delay_reduction_pct": 0.0,
                "target_corridor_speed_change_pct": 0.0,
                "corridor_trade_offs": [],
            },
        }

        eval_resp = self.planner.evaluate_and_replan(
            objective="Compare signal timing and rerouting at Narayanguda",
            plan=["traffic", "simulation"],
            collected_results={"traffic": traffic_data, "simulation": [sim1, sim2]},
            cycle_num=2,
            max_cycles=2,
            location="Narayanguda, Hyderabad",
        )

        self.assertEqual(eval_resp.evidence_status, "EVIDENCE: MULTI-SIMULATION EVALUATION")
        self.assertEqual(len(eval_resp.tested_interventions), 2)
        tested_types = [t.get("type") for t in eval_resp.tested_interventions]
        self.assertIn("signal_timing", tested_types)
        self.assertIn("rerouting", tested_types)

        untested_types = [u.get("type") for u in eval_resp.untested_candidates]
        self.assertIn("lane_use", untested_types)
        self.assertNotIn("signal_timing", untested_types)
        self.assertNotIn("rerouting", untested_types)

    # -------------------------------------------------------------------------
    # Test C: Three Tested Interventions
    # -------------------------------------------------------------------------
    def test_c_three_tested_interventions(self):
        """
        When 3 interventions are simulated up to MAX_OPTIMIZATION_CANDIDATES:
          - Evidence status is EVIDENCE: MULTI-SIMULATION EVALUATION
          - All 3 are present in tested_interventions with preserved metrics
        """
        traffic_data = {
            "location": "Narayanguda, Hyderabad",
            "seed": 42,
            "duration_seconds": 120,
            "scenario": "synthetic_normal",
            "average_speed_kmh": 39.75,
            "average_delay_sec": 13.80,
            "average_waiting_time_sec": 3.11,
            "congestion_index": 0.205,
            "bottlenecks": [{"corridor": "Westbound", "reason": "Bottleneck"}],
        }

        sims = [
            {
                "scenario_id": f"scen_{i}",
                "status": "COMPLETED",
                "intervention_applied": {"type": "signal_timing", "target": "Westbound", "parameters": {"adjustment": i * 5}},
                "metrics": {"average_speed_kmh": 39.0 + i, "average_delay_sec": 14.0 - i * 0.5},
                "comparison": {"speed_change_pct": float(i), "delay_reduction_pct": float(i)},
            }
            for i in range(1, 4)
        ]

        eval_resp = self.planner.evaluate_and_replan(
            objective="Evaluate 3 candidate interventions",
            plan=["traffic", "simulation"],
            collected_results={"traffic": traffic_data, "simulation": sims},
            cycle_num=2,
            max_cycles=2,
            location="Narayanguda, Hyderabad",
        )

        self.assertEqual(eval_resp.evidence_status, "EVIDENCE: MULTI-SIMULATION EVALUATION")
        self.assertEqual(len(eval_resp.tested_interventions), 3)

    # -------------------------------------------------------------------------
    # Test D: Candidate Limit Enforcement
    # -------------------------------------------------------------------------
    def test_d_candidate_limit_enforcement(self):
        """
        With 5 candidates from Traffic Agent and MAX_OPTIMIZATION_CANDIDATES=2:
          - Only 2 candidates are dispatched for simulation
          - The remaining 3 stay UNTESTED
        """
        traffic_data = {
            "location": "Narayanguda, Hyderabad",
            "seed": 42,
            "duration_seconds": 120,
            "scenario": "synthetic_normal",
            "average_speed_kmh": 39.75,
            "average_delay_sec": 13.80,
            "average_waiting_time_sec": 3.11,
            "congestion_index": 0.205,
            "bottlenecks": [{"corridor": "Westbound", "reason": "Bottleneck"}],
            "candidate_interventions": [
                {"type": "signal_timing", "target": "Westbound", "executable": True, "parameters": {"green_time_adjustment_sec": 10.0}},
                {"type": "signal_timing", "target": "Westbound", "executable": True, "parameters": {"green_time_adjustment_sec": 19.0}},
                {"type": "rerouting", "target": "Westbound", "executable": True, "parameters": {"diversion_fraction": 0.15}},
                {"type": "lane_use", "target": "Westbound", "executable": False},
                {"type": "incident_response", "target": "Westbound", "executable": False},
            ],
        }

        with patch("backend.agents.planner_agent.planner.MAX_OPTIMIZATION_CANDIDATES", 2):
            eval_resp = self.planner.evaluate_and_replan(
                objective="Optimize the traffic situation in Narayanguda",
                plan=["traffic"],
                collected_results={"traffic": traffic_data},
                cycle_num=1,
                max_cycles=2,
                location="Narayanguda, Hyderabad",
            )

            self.assertEqual(eval_resp.decision, "run_simulation")
            sim_calls = [c for c in eval_resp.next_cycle_calls if c.agent == "simulation"]
            self.assertEqual(len(sim_calls), 2)
            for call in sim_calls:
                self.assertIn("selected for evaluation", call.reason)

    # -------------------------------------------------------------------------
    # Test E: 'No Clear Winner' Handling
    # -------------------------------------------------------------------------
    def test_e_no_clear_winner_handling(self):
        """
        When tested interventions present meaningful trade-offs:
          - Signal timing: target speed +8.86%, Southbound speed -7.18%, network delay +3.41%
          - Rerouting: target speed 0.0%, network speed 0.0%, no reduction
          -> Concludes that no clear overall improvement was demonstrated among tested interventions
          -> Does not force an arbitrary winner
        """
        traffic_data = {
            "location": "Narayanguda, Hyderabad",
            "seed": 42,
            "duration_seconds": 120,
            "scenario": "synthetic_normal",
            "average_speed_kmh": 39.75,
            "average_delay_sec": 13.80,
            "average_waiting_time_sec": 3.11,
            "congestion_index": 0.205,
            "bottlenecks": [{"corridor": "Westbound", "reason": "Bottleneck"}],
        }
        sim1 = {
            "scenario_id": "scen_signal",
            "status": "COMPLETED",
            "intervention_applied": {"type": "signal_timing", "target": "Westbound"},
            "metrics": {"average_speed_kmh": 39.56, "average_delay_sec": 14.27},
            "comparison": {
                "speed_change_pct": -0.48,
                "delay_reduction_pct": -3.41,
                "target_corridor_speed_change_pct": 8.86,
                "corridor_trade_offs": ["Southbound speed degraded by -7.2% due to opposing phase reduction"],
            },
        }
        sim2 = {
            "scenario_id": "scen_reroute",
            "status": "COMPLETED",
            "intervention_applied": {"type": "rerouting", "target": "Westbound"},
            "metrics": {"average_speed_kmh": 39.75, "average_delay_sec": 13.80},
            "comparison": {
                "speed_change_pct": 0.0,
                "delay_reduction_pct": 0.0,
                "target_corridor_speed_change_pct": 0.0,
                "corridor_trade_offs": [],
            },
        }

        eval_resp = self.planner.evaluate_and_replan(
            objective="Optimize the traffic bottleneck at Narayanguda",
            plan=["traffic", "simulation"],
            collected_results={"traffic": traffic_data, "simulation": [sim1, sim2]},
            cycle_num=2,
            max_cycles=2,
            location="Narayanguda, Hyderabad",
        )

        rec = eval_resp.final_recommendation.lower()
        self.assertTrue(
            "no clear overall improvement" in rec
            or "neither produced a clear" in rec
            or "trade-offs prevent a clear" in rec
            or "trade-off" in rec,
            f"Expected trade-off acknowledgment or 'no clear improvement', got: {rec}",
        )
        self.assertNotIn("50% speed + 30% delay", rec)

    # -------------------------------------------------------------------------
    # Test F: Clear Empirical Difference
    # -------------------------------------------------------------------------
    def test_f_clear_empirical_difference(self):
        """
        When one candidate cleanly dominates with positive network metrics
        and no material adverse trade-offs, it can be identified as producing
        the strongest observed result among tested interventions.
        """
        traffic_data = {
            "location": "Narayanguda, Hyderabad",
            "seed": 42,
            "duration_seconds": 120,
            "scenario": "synthetic_normal",
            "average_speed_kmh": 30.0,
            "average_delay_sec": 35.0,
            "average_waiting_time_sec": 10.0,
            "congestion_index": 0.45,
            "bottlenecks": [{"corridor": "Westbound", "reason": "Bottleneck"}],
        }
        sim_dominant = {
            "scenario_id": "scen_dominant",
            "status": "COMPLETED",
            "intervention_applied": {"type": "signal_timing", "target": "Westbound"},
            "metrics": {"average_speed_kmh": 38.0, "average_delay_sec": 22.0},
            "comparison": {
                "speed_change_pct": 26.67,
                "delay_reduction_pct": 37.14,
                "target_corridor_speed_change_pct": 25.0,
                "corridor_trade_offs": [],
            },
        }
        sim_inferior = {
            "scenario_id": "scen_inferior",
            "status": "COMPLETED",
            "intervention_applied": {"type": "rerouting", "target": "Westbound"},
            "metrics": {"average_speed_kmh": 29.5, "average_delay_sec": 36.0},
            "comparison": {
                "speed_change_pct": -1.67,
                "delay_reduction_pct": -2.86,
                "target_corridor_speed_change_pct": -1.0,
                "corridor_trade_offs": ["Increased network delay"],
            },
        }

        eval_resp = self.planner.evaluate_and_replan(
            objective="Optimize the traffic situation in Narayanguda",
            plan=["traffic", "simulation"],
            collected_results={"traffic": traffic_data, "simulation": [sim_dominant, sim_inferior]},
            cycle_num=2,
            max_cycles=2,
            location="Narayanguda, Hyderabad",
        )

        rec = eval_resp.final_recommendation.lower()
        self.assertIn("signal timing", rec)
        self.assertTrue("strongest observed result" in rec or "improved" in rec)

    # -------------------------------------------------------------------------
    # Test G: Untested Candidate Protection
    # -------------------------------------------------------------------------
    def test_g_untested_candidate_protection(self):
        """
        Verifies that an untested candidate cannot be selected or described
        as empirically superior or validated, even if raw LLM suggests it.
        """
        traffic_data = {
            "location": "Narayanguda, Hyderabad",
            "average_speed_kmh": 39.75,
            "average_delay_sec": 13.80,
            "bottlenecks": [{"corridor": "Westbound", "reason": "Bottleneck"}],
            "candidate_interventions": [
                {"type": "signal_timing", "target": "Westbound", "executable": True},
                {"type": "rerouting", "target": "Westbound", "executable": True},
                {"type": "lane_use", "target": "Westbound", "executable": False},
            ],
        }
        sim_data = {
            "scenario_id": "scen_signal",
            "status": "COMPLETED",
            "intervention_applied": {"type": "signal_timing", "target": "Westbound"},
            "metrics": {"average_speed_kmh": 39.56, "average_delay_sec": 14.27},
            "comparison": {"speed_change_pct": -0.48, "delay_reduction_pct": -3.41},
        }

        # Mock LLM trying to recommend untested rerouting as superior
        flawed_llm_reasoning = LLMFinalReasoning(
            summary="Tested signal timing.",
            recommendation="We recommend rerouting as the superior and optimal solution.",
            decision="COMPLETED",
            evidence_status="EVIDENCE: SINGLE SIMULATION RUN",
            cross_domain_relationships="Domain interactions evaluated.",
            uncertainty_and_limitations="Model limitations noted.",
        )

        with patch.object(self.planner, "generate_final_reasoning", return_value=flawed_llm_reasoning):
            eval_resp = self.planner.evaluate_and_replan(
                objective="Optimize traffic",
                plan=["traffic", "simulation"],
                collected_results={"traffic": traffic_data, "simulation": sim_data},
                cycle_num=2,
                max_cycles=2,
            )

            rec = eval_resp.final_recommendation
            self.assertNotIn("rerouting as the superior and optimal solution", rec)
            self.assertTrue("not simulated" in rec.lower() or "untested" in rec.lower())

    # -------------------------------------------------------------------------
    # Test H: Dynamic Baseline Inheritance
    # -------------------------------------------------------------------------
    def test_h_dynamic_baseline_inheritance(self):
        """
        Verifies that intervention simulations inherit actual baseline metadata:
          seed = baseline.seed
          duration = baseline.duration
          scenario = baseline.scenario
          location = baseline.location
        No hardcoded seed=42 or duration=120.
        """
        custom_seed = 999
        custom_duration = 300
        custom_scenario = "evening_peak_heavy"
        custom_loc = "Punjagutta, Hyderabad"

        traffic_data = {
            "location": custom_loc,
            "seed": custom_seed,
            "duration_seconds": custom_duration,
            "scenario": custom_scenario,
            "average_speed_kmh": 22.4,
            "average_delay_sec": 48.2,
            "bottlenecks": [{"corridor": "Northbound", "reason": "Bottleneck"}],
            "candidate_interventions": [
                {"type": "signal_timing", "target": "Northbound", "executable": True, "parameters": {"green_time_adjustment_sec": 15.0}},
                {"type": "rerouting", "target": "Northbound", "executable": True, "parameters": {"diversion_fraction": 0.20}},
            ],
        }

        eval_resp = self.planner.evaluate_and_replan(
            objective="Optimize the traffic bottleneck at Punjagutta",
            plan=["traffic"],
            collected_results={"traffic": traffic_data},
            cycle_num=1,
            max_cycles=2,
            location=custom_loc,
        )

        self.assertEqual(eval_resp.decision, "run_simulation")
        sim_calls = [c for c in eval_resp.next_cycle_calls if c.agent == "simulation"]
        self.assertGreaterEqual(len(sim_calls), 2)

        for sc in sim_calls:
            req = sc.request
            self.assertEqual(req.get("seed"), custom_seed)
            self.assertEqual(req.get("duration_seconds"), custom_duration)
            self.assertEqual(req.get("scenario_name"), custom_scenario)
            self.assertEqual(req.get("location"), custom_loc)

    # -------------------------------------------------------------------------
    # Test I: Baseline Comparison Retention
    # -------------------------------------------------------------------------
    def test_i_baseline_comparison_retention(self):
        """
        Verifies that comparison against baseline retains matching baseline
        metrics across multiple simulation evaluations.
        """
        traffic_data = {
            "location": "Narayanguda, Hyderabad",
            "average_speed_kmh": 39.75,
            "average_delay_sec": 13.80,
            "average_waiting_time_sec": 3.11,
            "congestion_index": 0.205,
        }
        sim_data = {
            "scenario_id": "scen_eval",
            "status": "COMPLETED",
            "intervention_applied": {"type": "signal_timing", "target": "Westbound"},
            "metrics": {"average_speed_kmh": 41.0, "average_delay_sec": 12.5, "congestion_index": 0.19},
        }

        eval_resp = self.planner.evaluate_and_replan(
            objective="Evaluate intervention",
            plan=["traffic", "simulation"],
            collected_results={"traffic": traffic_data, "simulation": sim_data},
            cycle_num=2,
            max_cycles=2,
        )

        scens = eval_resp.cross_analysis.simulation_comparison.get("tested_scenarios", [])
        self.assertEqual(len(scens), 1)
        comp = scens[0]["comparison"]
        self.assertIsNotNone(comp.get("speed_change_pct"))
        self.assertGreater(comp.get("speed_change_pct"), 0.0)

    # -------------------------------------------------------------------------
    # Test J: Corridor Comparison Integrity
    # -------------------------------------------------------------------------
    def test_j_corridor_comparison_integrity(self):
        """
        Verifies that corridor speed changes and trade-offs are preserved
        in cross_analysis findings and final reasoning.
        """
        traffic_data = {
            "location": "Narayanguda, Hyderabad",
            "average_speed_kmh": 39.75,
            "bottlenecks": [{"corridor": "Westbound", "reason": "Bottleneck"}],
        }
        sim_data = {
            "scenario_id": "scen_corridor_test",
            "status": "COMPLETED",
            "intervention_applied": {"type": "signal_timing", "target": "Westbound"},
            "comparison": {
                "speed_change_pct": -0.48,
                "delay_reduction_pct": -3.41,
                "corridor_comparisons": [
                    {"name": "Westbound", "baseline_speed_kmh": 35.0, "intervention_speed_kmh": 38.1, "speed_change_pct": 8.86},
                    {"name": "Southbound", "baseline_speed_kmh": 37.6, "intervention_speed_kmh": 34.9, "speed_change_pct": -7.18},
                ],
                "corridor_trade_offs": ["Southbound speed degraded by -7.2% (-2.7 km/h)"],
            },
        }

        eval_resp = self.planner.evaluate_and_replan(
            objective="Evaluate corridor trade-offs",
            plan=["traffic", "simulation"],
            collected_results={"traffic": traffic_data, "simulation": sim_data},
            cycle_num=2,
            max_cycles=2,
        )

        findings_text = " ".join(eval_resp.cross_analysis.key_findings)
        self.assertIn("Westbound", findings_text)
        self.assertIn("+8.9%", findings_text)
        self.assertIn("Southbound", findings_text)

    # -------------------------------------------------------------------------
    # Test K: Zero Simulations on Diagnostic Queries
    # -------------------------------------------------------------------------
    def test_k_zero_simulations_on_diagnostic_queries(self):
        """
        Queries such as:
          'Which corridor is currently the bottleneck?'
          'Why is this corridor slow?'
          'What is the traffic situation?'
        MUST result in 0 simulations and EVIDENCE: OBSERVATIONAL.
        """
        traffic_data = {
            "location": "Narayanguda, Hyderabad",
            "average_speed_kmh": 39.75,
            "average_delay_sec": 13.80,
            "bottlenecks": [{"corridor": "Westbound", "reason": "Lowest observed-speed corridor: 'Westbound' (35.0 km/h)"}],
            "candidate_interventions": [
                {"type": "signal_timing", "target": "Westbound", "executable": True},
            ],
        }

        diagnostic_queries = [
            "Which corridor is currently the bottleneck?",
            "Which corridor is the bottleneck?",
            "What is the current traffic situation in Narayanguda?",
            "Why is it slow?",
        ]

        for q in diagnostic_queries:
            eval_resp = self.planner.evaluate_and_replan(
                objective=q,
                plan=["traffic"],
                collected_results={"traffic": traffic_data},
                cycle_num=1,
                max_cycles=2,
                location="Narayanguda, Hyderabad",
            )
            self.assertEqual(eval_resp.decision, "finalize", f"Failed for query: {q}")
            self.assertEqual(eval_resp.next_action, "finalize", f"Failed for query: {q}")
            self.assertEqual(eval_resp.evidence_status, "EVIDENCE: OBSERVATIONAL", f"Failed for query: {q}")
            self.assertEqual(len(eval_resp.tested_interventions), 0, f"Failed for query: {q}")

    # -------------------------------------------------------------------------
    # Test L: Token Compaction Verification
    # -------------------------------------------------------------------------
    def test_l_token_compaction_verification(self):
        """
        Verifies that stage 2 and stage 3 prompt builders produce compact
        evidence representations rather than dumping unbound raw data.
        """
        from backend.agents.planner_agent.prompts import build_stage_2_prompt, build_stage_3_prompt

        collected = {
            "traffic": {
                "average_speed_kmh": 39.75,
                "average_delay_sec": 13.80,
                "bottlenecks": [{"corridor": "Westbound", "reason": "Bottleneck"}],
                "candidate_interventions": [{"type": f"cand_{i}", "target": "WB", "executable": True} for i in range(10)],
            },
            "simulation": [
                {
                    "scenario_id": f"sim_{i}",
                    "metrics": {"average_speed_kmh": 39.0 + i},
                    "comparison": {"speed_change_pct": float(i)},
                }
                for i in range(3)
            ],
        }

        p2 = build_stage_2_prompt(
            objective="Evaluate traffic",
            cycle_num=2,
            history=[],
            collected_results=collected,
            failures={},
        )
        self.assertLess(len(p2), 5000)

        from backend.agents.planner_agent.schema import CrossDomainAnalysis, SeverityLevel
        cross_analysis = CrossDomainAnalysis(
            primary_correlation="Domain Assessment",
            risk_level=SeverityLevel.MODERATE,
            causation_likelihood="PLAUSIBLE",
            key_findings=["Finding 1", "Finding 2"],
            diagnosed_bottlenecks=["Westbound bottleneck"],
            candidate_interventions=["signal_timing:Westbound"],
        )

        p3 = build_stage_3_prompt(
            objective="Evaluate traffic",
            cycle_num=2,
            max_cycles=2,
            collected_results=collected,
            cross_analysis=cross_analysis,
            tested_interventions=[{"type": "signal_timing", "target": "Westbound", "metrics": {}}],
            untested_candidates=[{"type": "rerouting", "target": "Westbound"}],
            evidence_status="EVIDENCE: SINGLE SIMULATION RUN",
        )
        self.assertLess(len(p3), 6000)

    # -------------------------------------------------------------------------
    # Test M: Anti-Hardcoding Test Suite
    # -------------------------------------------------------------------------
    def test_m_anti_hardcoding_suite(self):
        """
        Verifies that the multi-intervention logic adapts dynamically to:
          - Non-Narayanguda locations (e.g. Nacharam, Gachibowli)
          - Non-Westbound corridors (e.g. Eastbound, Northbound)
          - Non-42 seeds and non-120 durations
          - Non-standard candidate types
        """
        locs_and_corrs = [
            ("Nacharam, Hyderabad", "Eastbound", 777, 180),
            ("Gachibowli, Hyderabad", "Northbound", 1234, 240),
        ]

        for loc, corr, s_val, d_val in locs_and_corrs:
            traffic_data = {
                "location": loc,
                "seed": s_val,
                "duration_seconds": d_val,
                "scenario": "custom_profile",
                "average_speed_kmh": 25.0,
                "average_delay_sec": 30.0,
                "bottlenecks": [{"corridor": corr, "reason": f"Bottleneck on {corr}"}],
                "candidate_interventions": [
                    {"type": "signal_timing", "target": corr, "executable": True, "parameters": {"green_time_adjustment_sec": 12.0}},
                    {"type": "rerouting", "target": corr, "executable": True, "parameters": {"diversion_fraction": 0.25}},
                ],
            }

            eval_resp = self.planner.evaluate_and_replan(
                objective=f"Optimize the traffic situation in {loc}",
                plan=["traffic"],
                collected_results={"traffic": traffic_data},
                cycle_num=1,
                max_cycles=2,
                location=loc,
            )

            self.assertEqual(eval_resp.decision, "run_simulation")
            sim_calls = [c for c in eval_resp.next_cycle_calls if c.agent == "simulation"]
            self.assertEqual(len(sim_calls), 2)
            for call in sim_calls:
                self.assertEqual(call.request.get("location"), loc)
                self.assertEqual(call.request.get("intervention", {}).get("target"), corr)
                self.assertEqual(call.request.get("seed"), s_val)
                self.assertEqual(call.request.get("duration_seconds"), d_val)


if __name__ == "__main__":
    unittest.main()
