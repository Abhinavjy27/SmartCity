"""
Regression Test Suite for Evidence-Grounded Planner Recommendations.

Covers:
  Test A: Single Tested + Untested Alternative
  Test B: Multiple Tested Interventions
  Test C: Zero Simulations (Observational Evidence)
  Test D: No Numerical Confidence
  Test E: Existing Baseline Comparison Integrity
  Test F: Existing Corridor Comparison Integrity
  Test G: Anti-Hardcoding and Dynamic Corridor Adaptation
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.supervisor.main import app
from backend.agents.planner_agent.llm_client import MockLLMProvider
from backend.agents.planner_agent.planner import PlannerAgent
from backend.agents.planner_agent.schema import (
    LLMFinalReasoning,
    PlannerEvaluationResponse,
)


class TestPlannerEvidenceRecommendations(unittest.TestCase):
    """
    Validates that the Autonomous LLM Planner is strictly evidence-grounded
    when recommending traffic interventions.
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
    # Test A: Single Tested + Untested Alternative
    # -------------------------------------------------------------------------
    def test_single_tested_with_untested_alternative(self):
        """
        When Candidate A (signal timing) is simulated and Candidate B (rerouting)
        exists only as a candidate:
          - A is classified as TESTED
          - B is classified as UNTESTED
          - Evidence status is EVIDENCE: SINGLE SIMULATION RUN
          - Planner does NOT claim B is better, preferred, or validated
          - If raw LLM recommended untested B, the safeguard structurally aligns it
        """
        traffic_data = {
            "location": "Nacharam, Hyderabad",
            "average_speed_kmh": 28.0,
            "average_delay_sec": 22.0,
            "average_waiting_time_sec": 6.5,
            "congestion_index": 0.35,
            "throughput": 40,
            "bottlenecks": [
                {"corridor": "Northbound", "reason": "Lowest observed-speed corridor: 'Northbound' (21.0 km/h)"}
            ],
            "corridors": [
                {"id": "COR_NB", "name": "Northbound", "avg_speed": 21.0, "status": "HEAVY"},
                {"id": "COR_SB", "name": "Southbound", "avg_speed": 35.0, "status": "MODERATE"},
            ],
            "candidate_interventions": [
                {
                    "type": "signal_timing",
                    "target": "Northbound",
                    "parameters": {"green_time_adjustment_sec": 12.0},
                    "reason": "Clear Northbound queues",
                    "executable": True,
                    "potential_benefit": "Increases Northbound throughput",
                    "potential_tradeoff": "May degrade Southbound phase",
                },
                {
                    "type": "rerouting",
                    "target": "Northbound",
                    "parameters": {"diversion_fraction": 0.15},
                    "reason": "Divert traffic away from Northbound bottleneck",
                    "executable": True,
                    "potential_benefit": "Reduces arrival demand on bottleneck",
                    "potential_tradeoff": "Increases travel distance on alternative routes",
                },
            ],
        }

        sim_data = {
            "scenario_id": "scen_signal_nb",
            "scenario": "intervention_experiment",
            "status": "SUCCESS",
            "intervention_applied": {
                "type": "signal_timing",
                "target": "Northbound",
                "parameters": {"green_time_adjustment_sec": 12.0},
            },
            "average_speed_kmh": 29.5,
            "average_delay_sec": 21.0,
            "metrics": {
                "average_speed_kmh": 29.5,
                "average_delay_sec": 21.0,
                "average_waiting_time_sec": 5.8,
                "congestion_index": 0.32,
                "throughput": 43,
            },
            "comparison": {
                "scenario_id": "scen_signal_nb",
                "speed_change_pct": 5.36,
                "delay_reduction_pct": 4.55,
                "waiting_time_reduction_pct": 10.77,
                "congestion_reduction_pct": 8.57,
                "target_corridor_speed_change_pct": 15.2,
                "corridor_trade_offs": ["Southbound corridor speed degraded by -8.1%"],
            },
            "corridor_trade_offs": ["Southbound corridor speed degraded by -8.1%"],
        }

        collected = {
            "traffic": traffic_data,
            "simulation": sim_data,
        }

        def rogue_llm_handler(sys_prompt, user_prompt):
            if "stage 3" in sys_prompt.lower() or "final cross-domain synthesis" in sys_prompt.lower() or "final cross-agent synthesis" in sys_prompt.lower():
                return {
                    "summary": "Simulation completed for signal timing on Northbound.",
                    "evidence_used": ["traffic.average_speed_kmh=28.0 km/h", "simulation.avg_speed_kmh=29.5 km/h"],
                    "cross_domain_relationships": "Signal timing alters corridor progression.",
                    "causation_likelihood": "PLAUSIBLE",
                    "simulation_findings": "Northbound speed increased by 15.2%, but Southbound dropped by 8.1%.",
                    "synthetic_data_note": "SUMO synthetic data notice.",
                    "uncertainty_and_limitations": "Driver compliance assumed.",
                    "recommendation": "Signal timing created adverse trade-offs on Southbound. We recommend deploying the 15% rerouting intervention instead for better overall performance.",
                    "evidence_status": "EVIDENCE: OBSERVATIONAL",
                    "next_action": "operational_implementation",
                }
            return None

        self.mock_provider.custom_handler = rogue_llm_handler

        eval_res = self.planner.evaluate_and_replan(
            objective="Optimize Northbound bottleneck at Nacharam",
            plan=["traffic", "simulation"],
            collected_results=collected,
            failures={},
            cycle_num=2,
            max_cycles=2,
            location="Nacharam, Hyderabad",
        )

        # 1. Deterministic evidence status
        self.assertEqual(eval_res.evidence_status, "EVIDENCE: SINGLE SIMULATION RUN")
        self.assertIsNotNone(eval_res.final_reasoning)
        self.assertEqual(eval_res.final_reasoning.evidence_status, "EVIDENCE: SINGLE SIMULATION RUN")

        # 2. Classification of tested vs untested
        tested = eval_res.final_reasoning.tested_interventions
        untested = eval_res.final_reasoning.untested_candidates

        self.assertEqual(len(tested), 1)
        self.assertEqual(tested[0]["type"], "signal_timing")
        self.assertEqual(tested[0]["target"], "Northbound")

        self.assertEqual(len(untested), 1)
        self.assertEqual(untested[0]["type"], "rerouting")
        self.assertEqual(untested[0]["target"], "Northbound")
        self.assertEqual(untested[0]["status"], "UNTESTED_IN_THIS_CYCLE")

        # 3. Safeguard: Untested candidate MUST NOT be recommended as proven solution
        rec = eval_res.final_reasoning.recommendation
        self.assertNotIn("We recommend deploying the 15% rerouting intervention instead", rec)
        self.assertIn("NOT simulated in this cycle", rec)
        self.assertIn("comparative effectiveness has not been established", rec)

    # -------------------------------------------------------------------------
    # Test B: Multiple Tested Interventions
    # -------------------------------------------------------------------------
    def test_multiple_tested_interventions_comparison(self):
        """
        When Candidates A and B are simulated, but Candidate C is unsimulated:
          - A and B are TESTED
          - C is UNTESTED
          - evidence_status is EVIDENCE: MULTI-SIMULATION EVALUATION
          - comparison is strictly based on tested A and B
        """
        traffic_data = {
            "location": "Gachibowli, Hyderabad",
            "average_speed_kmh": 32.0,
            "candidate_interventions": [
                {"type": "signal_timing", "target": "Eastbound", "parameters": {"adjustment_seconds": 15}},
                {"type": "rerouting", "target": "Eastbound", "parameters": {"diversion_fraction": 0.20}},
                {"type": "lane_use", "target": "Eastbound", "parameters": {"reversible_lane": True}},
            ],
        }

        sim_a = {
            "scenario_id": "scen_signal",
            "status": "SUCCESS",
            "intervention_applied": {"type": "signal_timing", "target": "Eastbound"},
            "metrics": {"average_speed_kmh": 34.0, "average_delay_sec": 18.0},
            "comparison": {"speed_change_pct": 6.25, "delay_reduction_pct": 5.0},
            "corridor_trade_offs": ["Westbound speed degraded by -5.0%"],
        }
        sim_b = {
            "scenario_id": "scen_reroute",
            "status": "SUCCESS",
            "intervention_applied": {"type": "rerouting", "target": "Eastbound"},
            "metrics": {"average_speed_kmh": 35.5, "average_delay_sec": 16.5},
            "comparison": {"speed_change_pct": 10.94, "delay_reduction_pct": 12.5},
            "corridor_trade_offs": [],
        }

        collected = {
            "traffic": traffic_data,
            "simulation": [sim_a, sim_b],
        }

        eval_res = self.planner.evaluate_and_replan(
            objective="Evaluate multiple interventions for Gachibowli",
            plan=["traffic", "simulation"],
            collected_results=collected,
            failures={},
            cycle_num=2,
            max_cycles=2,
            location="Gachibowli, Hyderabad",
        )

        self.assertEqual(eval_res.evidence_status, "EVIDENCE: MULTI-SIMULATION EVALUATION")
        final_r = eval_res.final_reasoning
        self.assertIsNotNone(final_r)
        self.assertEqual(final_r.evidence_status, "EVIDENCE: MULTI-SIMULATION EVALUATION")

        # 2 tested, 1 untested
        self.assertEqual(len(final_r.tested_interventions), 2)
        tested_types = [t["type"] for t in final_r.tested_interventions]
        self.assertIn("signal_timing", tested_types)
        self.assertIn("rerouting", tested_types)

        self.assertEqual(len(final_r.untested_candidates), 1)
        self.assertEqual(final_r.untested_candidates[0]["type"], "lane_use")

    # -------------------------------------------------------------------------
    # Test C: Zero Simulations (Observational Evidence)
    # -------------------------------------------------------------------------
    def test_zero_simulations_observational_status(self):
        """
        When 0 simulations have been executed:
          - evidence_status is EVIDENCE: OBSERVATIONAL
          - all candidates are UNTESTED
          - no empirical optimization recommendation is produced
        """
        traffic_data = {
            "location": "Punjagutta, Hyderabad",
            "average_speed_kmh": 22.4,
            "average_delay_sec": 35.0,
            "candidate_interventions": [
                {"type": "signal_timing", "target": "Flyover Approach", "parameters": {"adjustment_seconds": 10}},
                {"type": "rerouting", "target": "Flyover Approach", "parameters": {"diversion_fraction": 0.15}},
            ],
        }

        collected = {"traffic": traffic_data}

        eval_res = self.planner.evaluate_and_replan(
            objective="Diagnose current traffic conditions at Punjagutta",
            plan=["traffic"],
            collected_results=collected,
            failures={},
            cycle_num=1,
            max_cycles=1,
            location="Punjagutta, Hyderabad",
        )

        self.assertEqual(eval_res.evidence_status, "EVIDENCE: OBSERVATIONAL")
        final_r = eval_res.final_reasoning
        self.assertIsNotNone(final_r)
        self.assertEqual(final_r.evidence_status, "EVIDENCE: OBSERVATIONAL")
        self.assertEqual(len(final_r.tested_interventions), 0)
        self.assertEqual(len(final_r.untested_candidates), 2)

        self.assertIn("untested", final_r.recommendation.lower())

    # -------------------------------------------------------------------------
    # Test D: No Numerical Confidence
    # -------------------------------------------------------------------------
    def test_no_numerical_confidence_or_arbitrary_default(self):
        """
        Verify no hardcoded 95% confidence number appears in schemas or mock output.
        """
        eval_res = self.planner.evaluate_and_replan(
            objective="Check traffic at Begumpet",
            plan=["traffic"],
            collected_results={"traffic": {"average_speed_kmh": 30.0}},
            failures={},
            cycle_num=1,
            max_cycles=1,
            location="Begumpet, Hyderabad",
        )

        if eval_res.final_reasoning:
            self.assertIsNone(eval_res.final_reasoning.confidence)

        resp = self.client.post(
            "/agents/planner/execute",
            json={
                "query": "Diagnose traffic at Begumpet",
                "location": "Begumpet, Hyderabad",
                "max_cycles": 1,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("evidence_status", data)
        self.assertNotEqual(data.get("confidence"), 0.95)

    # -------------------------------------------------------------------------
    # Test E: Existing Baseline Comparison Integrity
    # -------------------------------------------------------------------------
    def test_baseline_and_intervention_comparison_propagation(self):
        """
        Verify that baseline metrics and intervention comparison deltas
        propagate correctly through the planner evaluation pipeline.
        """
        traffic_data = {
            "location": "Narayanguda, Hyderabad",
            "average_speed_kmh": 39.75,
            "average_delay_sec": 13.80,
            "average_waiting_time_sec": 3.11,
            "congestion_index": 0.205,
            "corridors": [
                {"id": "COR_WB", "name": "Westbound", "avg_speed": 35.0},
                {"id": "COR_SB", "name": "Southbound", "avg_speed": 37.6},
            ],
            "candidate_interventions": [
                {"type": "signal_timing", "target": "Westbound", "parameters": {"green_time_adjustment_sec": 10.0}}
            ],
        }

        sim_data = {
            "scenario_id": "scen_wb_10s",
            "status": "SUCCESS",
            "intervention_applied": {"type": "signal_timing", "target": "Westbound"},
            "metrics": {
                "average_speed_kmh": 39.56,
                "average_delay_sec": 14.27,
                "average_waiting_time_sec": 3.72,
                "congestion_index": 0.209,
            },
            "comparison": {
                "scenario_id": "scen_wb_10s",
                "speed_change_pct": -0.48,
                "delay_reduction_pct": -3.41,
                "waiting_time_reduction_pct": -19.61,
                "congestion_reduction_pct": -1.95,
                "target_corridor_speed_change_pct": 8.86,
                "corridor_comparisons": [
                    {"id": "COR_WB", "name": "Westbound", "baseline_speed_kmh": 35.0, "intervention_speed_kmh": 38.1, "speed_change_pct": 8.86},
                    {"id": "COR_SB", "name": "Southbound", "baseline_speed_kmh": 37.6, "intervention_speed_kmh": 34.9, "speed_change_pct": -7.18},
                ],
                "corridor_trade_offs": ["Southbound corridor speed degraded by -7.18%"],
            },
            "corridor_trade_offs": ["Southbound corridor speed degraded by -7.18%"],
        }

        collected = {"traffic": traffic_data, "simulation": sim_data}

        eval_res = self.planner.evaluate_and_replan(
            objective="Analyze traffic and compare baseline with optimized metrics",
            plan=["traffic", "simulation"],
            collected_results=collected,
            failures={},
            cycle_num=2,
            max_cycles=2,
            location="Narayanguda, Hyderabad",
        )

        final_r = eval_res.final_reasoning
        self.assertIsNotNone(final_r)
        self.assertIsNotNone(final_r.baseline_metrics)
        self.assertIsNotNone(final_r.metric_changes)
        self.assertEqual(final_r.metric_changes.get("speed_change_pct"), -0.48)
        self.assertEqual(final_r.metric_changes.get("delay_reduction_pct"), -3.41)

    # -------------------------------------------------------------------------
    # Test F: Existing Corridor Comparison Integrity
    # -------------------------------------------------------------------------
    def test_corridor_level_comparison_integrity(self):
        """
        Verify that corridor-level speed comparisons and trade-offs
        are preserved in final_reasoning.
        """
        traffic_data = {
            "location": "Kukatpally, Hyderabad",
            "average_speed_kmh": 30.0,
            "corridors": [
                {"id": "COR_EB", "name": "Eastbound", "avg_speed": 22.0},
                {"id": "COR_WB", "name": "Westbound", "avg_speed": 38.0},
            ],
        }

        sim_data = {
            "scenario_id": "scen_eb_opt",
            "status": "SUCCESS",
            "intervention_applied": {"type": "signal_timing", "target": "Eastbound"},
            "metrics": {"average_speed_kmh": 31.0},
            "comparison": {
                "corridor_comparisons": [
                    {"id": "COR_EB", "name": "Eastbound", "baseline_speed_kmh": 22.0, "intervention_speed_kmh": 27.0, "speed_change_pct": 22.7},
                    {"id": "COR_WB", "name": "Westbound", "baseline_speed_kmh": 38.0, "intervention_speed_kmh": 35.0, "speed_change_pct": -7.9},
                ],
                "corridor_trade_offs": ["Westbound speed degraded by -7.9%"],
            },
            "corridor_trade_offs": ["Westbound speed degraded by -7.9%"],
        }

        collected = {"traffic": traffic_data, "simulation": sim_data}

        eval_res = self.planner.evaluate_and_replan(
            objective="Optimize Eastbound corridor at Kukatpally",
            plan=["traffic", "simulation"],
            collected_results=collected,
            failures={},
            cycle_num=2,
            max_cycles=2,
            location="Kukatpally, Hyderabad",
        )

        final_r = eval_res.final_reasoning
        self.assertIsNotNone(final_r)
        self.assertIn("Westbound speed degraded by -7.9%", final_r.corridor_trade_offs)

    # -------------------------------------------------------------------------
    # Test G: Anti-Hardcoding & Dynamic Corridor Adaptation
    # -------------------------------------------------------------------------
    def test_anti_hardcoding_dynamic_location_and_target(self):
        """
        Proves that for arbitrary location (e.g. Financial District) and arbitrary corridor
        (e.g. Southbound), the Planner dynamically structures the tested vs untested evidence
        without hardcoding Narayanguda or Westbound.
        """
        traffic_data = {
            "location": "Financial District, Hyderabad",
            "average_speed_kmh": 25.0,
            "bottlenecks": [
                {"corridor": "Southbound", "reason": "Lowest observed-speed corridor: 'Southbound' (18.0 km/h)"}
            ],
            "candidate_interventions": [
                {"type": "adaptive_metering", "target": "Southbound", "parameters": {"rate": 0.8}},
                {"type": "incident_detour", "target": "Southbound", "parameters": {"active": True}},
            ],
        }

        sim_data = {
            "scenario_id": "scen_metering_sb",
            "status": "SUCCESS",
            "intervention_applied": {"type": "adaptive_metering", "target": "Southbound"},
            "metrics": {"average_speed_kmh": 27.5},
            "comparison": {
                "speed_change_pct": 10.0,
                "delay_reduction_pct": 8.0,
                "corridor_trade_offs": [],
            },
        }

        collected = {"traffic": traffic_data, "simulation": sim_data}

        eval_res = self.planner.evaluate_and_replan(
            objective="Resolve Southbound congestion at Financial District",
            plan=["traffic", "simulation"],
            collected_results=collected,
            failures={},
            cycle_num=2,
            max_cycles=2,
            location="Financial District, Hyderabad",
        )

        final_r = eval_res.final_reasoning
        self.assertIsNotNone(final_r)
        self.assertEqual(len(final_r.tested_interventions), 1)
        self.assertEqual(final_r.tested_interventions[0]["type"], "adaptive_metering")
        self.assertEqual(final_r.tested_interventions[0]["target"], "Southbound")

        self.assertEqual(len(final_r.untested_candidates), 1)
        self.assertEqual(final_r.untested_candidates[0]["type"], "incident_detour")

        rec = final_r.recommendation
        self.assertNotIn("Narayanguda", rec)
        self.assertNotIn("Westbound", rec)

    # -------------------------------------------------------------------------
    # Test H: Untested Causal Claim Prevention
    # -------------------------------------------------------------------------
    def test_untested_causal_claim_prohibited(self):
        """
        Regression Test 1: Given an untested rerouting candidate, verify that the final
        recommendation and summary do NOT claim rerouting will reduce arrivals, delay,
        congestion, or improve speed.
        """
        traffic_data = {
            "location": "Narayanguda, Hyderabad",
            "average_speed_kmh": 39.75,
            "average_delay_sec": 13.80,
            "average_waiting_time_sec": 3.11,
            "congestion_index": 0.205,
            "bottlenecks": [
                {"corridor": "Westbound", "reason": "Lowest observed-speed corridor: 'Westbound' (35.0 km/h)"}
            ],
            "corridors": [
                {"id": "COR_WB", "name": "Westbound", "avg_speed": 35.0, "status": "HEAVY"},
                {"id": "COR_SB", "name": "Southbound", "avg_speed": 37.6, "status": "MODERATE"},
            ],
            "candidate_interventions": [
                {
                    "type": "signal_timing",
                    "target": "Westbound",
                    "parameters": {"green_time_adjustment_sec": 10.0},
                    "reason": "Clear Westbound queues",
                    "executable": True,
                },
                {
                    "type": "rerouting",
                    "target": "Westbound",
                    "parameters": {"diversion_fraction": 0.15},
                    "reason": "Divert traffic away from Westbound bottleneck",
                    "executable": True,
                    "potential_benefit": "Directly reduces vehicle arrival rate entering the Westbound bottleneck corridor",
                },
            ],
        }

        sim_data = {
            "scenario_id": "scen_wb_10s",
            "status": "SUCCESS",
            "intervention_applied": {"type": "signal_timing", "target": "Westbound"},
            "metrics": {"average_speed_kmh": 39.56, "average_delay_sec": 14.27},
            "comparison": {
                "speed_change_pct": -0.48,
                "delay_reduction_pct": -3.41,
                "target_corridor_speed_change_pct": 8.86,
                "corridor_trade_offs": ["Southbound corridor speed degraded by -7.18%"],
            },
            "corridor_trade_offs": ["Southbound corridor speed degraded by -7.18%"],
        }

        collected = {"traffic": traffic_data, "simulation": sim_data}

        # Simulate an LLM attempting to produce the exact problematic wording reported
        def causal_claim_llm_handler(sys_prompt, user_prompt):
            if "stage 3" in sys_prompt.lower() or "final cross" in sys_prompt.lower():
                return {
                    "summary": (
                        "Instead, initiate a multi-phase optimization study that includes the untested "
                        "rerouting candidate (15% diversion to Perimeter Ring) to reduce arrival rates at the bottleneck, "
                        "as its operational effectiveness cannot be established."
                    ),
                    "evidence_used": ["traffic.average_speed_kmh=39.75 km/h"],
                    "cross_domain_relationships": "Signal timing affects downstream vehicle queues.",
                    "causation_likelihood": "PLAUSIBLE",
                    "simulation_findings": "Signal timing improved Westbound speed by 8.86% but reduced Southbound speed by 7.18%.",
                    "synthetic_data_note": "SUMO synthetic data notice.",
                    "uncertainty_and_limitations": "Driver compliance assumed.",
                    "recommendation": (
                        "The tested signal adjustment improved Westbound by 8.86%. "
                        "Initiate study with untested rerouting (15% diversion) to reduce arrival rates and relieve congestion at the bottleneck."
                    ),
                    "evidence_status": "EVIDENCE: OBSERVATIONAL",
                    "next_action": "operational_implementation",
                }
            return None

        self.mock_provider.custom_handler = causal_claim_llm_handler

        eval_res = self.planner.evaluate_and_replan(
            objective="Analyze traffic, optimize bottleneck, compare baseline with optimized metrics",
            plan=["traffic", "simulation"],
            collected_results=collected,
            failures={},
            cycle_num=2,
            max_cycles=2,
            location="Narayanguda, Hyderabad",
        )

        final_r = eval_res.final_reasoning
        self.assertIsNotNone(final_r)
        rec = final_r.recommendation
        summary = final_r.summary

        # Must NOT state or imply that the untested candidate will reduce arrival rates or relieve congestion
        self.assertNotIn("to reduce arrival rates", rec)
        self.assertNotIn("to reduce arrival rates", summary)
        self.assertNotIn("relieve congestion", rec)
        self.assertNotIn("will reduce", rec)
        self.assertNotIn("will improve", rec)

        # Must state that untested candidate requires simulation before effectiveness can be established
        self.assertIn("NOT simulated in this cycle", rec)
        self.assertIn("requires simulation", rec)

    # -------------------------------------------------------------------------
    # Test I: Bottleneck Resolution Language Prevention
    # -------------------------------------------------------------------------
    def test_bottleneck_resolution_language_prevented(self):
        """
        Regression Test 2: Given a target corridor improvement but an opposing corridor degradation,
        verify that the Planner reports the observed target improvement rather than claiming
        the bottleneck was 'successfully addressed', 'resolved', or 'fixed'.
        """
        traffic_data = {
            "location": "Narayanguda, Hyderabad",
            "average_speed_kmh": 39.75,
            "average_delay_sec": 13.80,
            "corridors": [
                {"id": "COR_WB", "name": "Westbound", "avg_speed": 35.0},
                {"id": "COR_SB", "name": "Southbound", "avg_speed": 37.6},
            ],
            "candidate_interventions": [
                {"type": "signal_timing", "target": "Westbound", "parameters": {"green_time_adjustment_sec": 10.0}}
            ],
        }

        sim_data = {
            "scenario_id": "scen_wb_10s",
            "status": "SUCCESS",
            "intervention_applied": {"type": "signal_timing", "target": "Westbound"},
            "metrics": {"average_speed_kmh": 39.56, "average_delay_sec": 14.27},
            "comparison": {
                "speed_change_pct": -0.48,
                "delay_reduction_pct": -3.41,
                "target_corridor_speed_change_pct": 8.86,
                "corridor_trade_offs": ["Southbound corridor speed degraded by -7.18%"],
            },
            "corridor_trade_offs": ["Southbound corridor speed degraded by -7.18%"],
        }

        collected = {"traffic": traffic_data, "simulation": sim_data}

        def premature_resolution_handler(sys_prompt, user_prompt):
            if "stage 3" in sys_prompt.lower() or "final cross" in sys_prompt.lower():
                return {
                    "summary": "The intervention successfully addressed the lowest observed-speed corridor bottleneck in Narayanguda.",
                    "evidence_used": ["traffic.average_speed_kmh=39.75 km/h"],
                    "cross_domain_relationships": "Signal timing alters corridor progression.",
                    "causation_likelihood": "PLAUSIBLE",
                    "simulation_findings": "The Westbound bottleneck was resolved with speed rising to 38.1 km/h.",
                    "synthetic_data_note": "SUMO synthetic data notice.",
                    "uncertainty_and_limitations": "Driver compliance assumed.",
                    "recommendation": "The intervention successfully addressed the bottleneck on Westbound. Deploy signal timing as the problem is solved.",
                    "intervention_assessment": "The intervention successfully addressed the lowest observed-speed corridor bottleneck.",
                    "evidence_status": "EVIDENCE: OBSERVATIONAL",
                    "next_action": "operational_implementation",
                }
            return None

        self.mock_provider.custom_handler = premature_resolution_handler

        eval_res = self.planner.evaluate_and_replan(
            objective="Analyze traffic and compare baseline with optimized metrics",
            plan=["traffic", "simulation"],
            collected_results=collected,
            failures={},
            cycle_num=2,
            max_cycles=2,
            location="Narayanguda, Hyderabad",
        )

        final_r = eval_res.final_reasoning
        self.assertIsNotNone(final_r)

        rec_lower = final_r.recommendation.lower()
        sum_lower = final_r.summary.lower()
        ass_lower = (final_r.intervention_assessment or "").lower()

        # Prohibited terms
        self.assertNotIn("successfully addressed", rec_lower)
        self.assertNotIn("successfully addressed", sum_lower)
        self.assertNotIn("successfully addressed", ass_lower)
        self.assertNotIn("resolved the bottleneck", rec_lower)
        self.assertNotIn("problem is solved", rec_lower)
        self.assertNotIn("problem solved", rec_lower)
        self.assertNotIn("fixed the bottleneck", rec_lower)

    # -------------------------------------------------------------------------
    # Test J: Structured Six-Step Evidence Recommendation
    # -------------------------------------------------------------------------
    def test_single_tested_six_step_recommendation_structure(self):
        """
        Verify that a single tested intervention with trade-offs produces the complete
        6-step evidence-grounded recommendation:
          1. Bottleneck identified
          2. Tested intervention identified
          3. Observed target corridor effect
          4. Observed network/opposing corridor trade-offs
          5. Standalone assessment ('should not be treated as a standalone solution')
          6. Untested candidates acknowledged as untested requiring simulation.
        """
        traffic_data = {
            "location": "Narayanguda, Hyderabad",
            "average_speed_kmh": 39.75,
            "average_delay_sec": 13.80,
            "bottlenecks": [{"corridor": "Westbound"}],
            "corridors": [
                {"id": "COR_WB", "name": "Westbound", "avg_speed": 35.0},
                {"id": "COR_SB", "name": "Southbound", "avg_speed": 37.6},
            ],
            "candidate_interventions": [
                {"type": "signal_timing", "target": "Westbound", "parameters": {"green_time_adjustment_sec": 10.0}},
                {"type": "rerouting", "target": "Westbound", "parameters": {"diversion_fraction": 0.15}},
            ],
        }

        sim_data = {
            "scenario_id": "scen_wb_10s",
            "status": "SUCCESS",
            "intervention_applied": {"type": "signal_timing", "target": "Westbound"},
            "metrics": {"average_speed_kmh": 39.56, "average_delay_sec": 14.27},
            "comparison": {
                "speed_change_pct": -0.48,
                "delay_reduction_pct": -3.41,
                "target_corridor_speed_change_pct": 8.86,
                "corridor_trade_offs": ["Southbound corridor speed degraded by -7.18%"],
            },
            "corridor_trade_offs": ["Southbound corridor speed degraded by -7.18%"],
        }

        collected = {"traffic": traffic_data, "simulation": sim_data}

        # LLM that claims untested rerouting is optimal
        def rogue_llm(sys_prompt, user_prompt):
            if "stage 3" in sys_prompt.lower() or "final cross" in sys_prompt.lower():
                return {
                    "summary": "Signal timing tested on Westbound corridor.",
                    "evidence_used": ["traffic.average_speed_kmh=39.75 km/h"],
                    "cross_domain_relationships": "Interactions noted.",
                    "causation_likelihood": "PLAUSIBLE",
                    "simulation_findings": "Westbound speed improved by 8.86%.",
                    "synthetic_data_note": "SUMO synthetic data notice.",
                    "uncertainty_and_limitations": "Driver compliance assumed.",
                    "recommendation": "Deploy rerouting intervention to relieve Westbound traffic.",
                    "evidence_status": "EVIDENCE: SINGLE SIMULATION RUN",
                    "next_action": "operational_implementation",
                }
            return None

        self.mock_provider.custom_handler = rogue_llm

        eval_res = self.planner.evaluate_and_replan(
            objective="Analyze traffic and compare baseline with optimized metrics",
            plan=["traffic", "simulation"],
            collected_results=collected,
            failures={},
            cycle_num=2,
            max_cycles=2,
            location="Narayanguda, Hyderabad",
        )

        rec = eval_res.final_reasoning.recommendation

        # 1. Bottleneck target corridor identified
        self.assertIn("Westbound", rec)
        # 2. Tested intervention identified
        self.assertIn("signal timing", rec)
        # 3. Observed target corridor effect
        self.assertIn("8.86%", rec)
        # 4. Observed network/opposing corridor trade-offs
        self.assertIn("network delay", rec)
        self.assertIn("Southbound", rec)
        # 5. Standalone assessment
        self.assertIn("should not be treated as a standalone solution", rec)
        # 6. Untested candidates acknowledged as untested requiring simulation
        self.assertIn("rerouting", rec)
        self.assertIn("15%", rec)
        self.assertIn("NOT simulated in this cycle", rec)
        self.assertIn("requires simulation", rec)


if __name__ == "__main__":
    unittest.main()

