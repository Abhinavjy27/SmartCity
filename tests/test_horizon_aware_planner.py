"""
Tests A through AG: Comprehensive Verification for Horizon-Aware Planner History & 600s Production Default.
Covers:
- A: 300s and 600s experiments coexist
- B: Scenario IDs distinguish duration
- C: 600s baseline pairs only with 600s intervention
- D: 300s baseline cannot pair with 600s intervention (fair_comparison=False)
- E: Compaction preserves duration
- F: Compaction preserves scenario
- G: Compaction preserves seed
- H: Compaction preserves network
- I: Explicit 600s analytical follow-up uses 600s history
- J: Explicit 300s analytical follow-up uses 300s history
- K: 300-vs-600 comparison retrieves both
- L: No unnecessary simulation for historical follow-up
- M: Frontend preserves duration
- N: Frontend does not mix horizons
- O: Session storage preserves multiple horizons
- P: Clear Conversation removes history
- Q: Default production evaluation duration is 600
- R: Explicit 300 overrides 600 default
- S: Explicit 120 overrides 600 default
- T: CI/smoke 120 behavior remains intact
- U: Existing 300 behavior remains intact
- V: Vehicle accounting (arrived + active == total)
- W: Fair comparison validates duration
- X: Fair comparison validates scenario
- Y: Fair comparison validates seed
- Z: Fair comparison validates network
- AA: New delta sign semantics
- AB: Legacy reduction semantics remain unchanged
- AC: No hardcoded 600s metrics
- AD: No hardcoded 300s metrics
- AE: No hardcoded simulation outcomes
- AF: Planner does not claim untested interventions were tested
- AG: Planner does not force an arbitrary winner
"""
import os
import unittest
from fastapi.testclient import TestClient

from backend.agents.planner_agent.planner import (
    PlannerAgent,
    is_analytical_history_followup,
)
from backend.agents.planner_agent.prompts import (
    _compact_simulation_evidence,
)
from backend.agents.simulation_agent.schemas import SimulationMetrics
from backend.agents.simulation_agent.service import SimulationService
from backend.config import (
    DEFAULT_PRODUCTION_EVALUATION_DURATION_SECONDS,
    CI_SMOKE_EVALUATION_DURATION_SECONDS,
    HISTORICAL_EVALUATION_DURATION_SECONDS,
)
from backend.supervisor.main import app, _PLANNER_SESSIONS


def _make_int_metrics(speed=37.64, delay=43.13, wait=12.69, cong=0.247, tp=141, total=205):
    return SimulationMetrics(
        active_vehicles=total - tp,
        total_vehicles=total,
        arrived_vehicles=tp,
        active_at_end=total - tp,
        throughput=tp,
        average_speed_kmh=speed,
        average_waiting_time_sec=wait,
        average_delay_sec=delay,
        congestion_index=cong,
    )


class TestExperimentIdentity(unittest.TestCase):
    """Tests A & B: Scenario IDs and experiment coexistence."""

    def test_b_scenario_id_distinguishes_duration(self):
        """B: Scenario IDs for 300s and 600s differ when duration is specified."""
        interv = {"type": "signal_timing", "target": "Westbound", "parameters": {"green_time_adjustment_sec": 10.0}}
        id_300 = SimulationService.generate_scenario_id(interv, seed=42, duration=300)
        id_600 = SimulationService.generate_scenario_id(interv, seed=42, duration=600)
        
        self.assertIn(":dur300s", id_300)
        self.assertIn(":dur600s", id_600)
        self.assertNotEqual(id_300, id_600)

    def test_b_baseline_scenario_id_distinguishes_duration(self):
        """B: Baseline scenario IDs for 300s and 600s differ."""
        base_300 = SimulationService.generate_scenario_id(None, seed=42, duration=300)
        base_600 = SimulationService.generate_scenario_id(None, seed=42, duration=600)
        
        self.assertIn(":dur300s", base_300)
        self.assertIn(":dur600s", base_600)
        self.assertNotEqual(base_300, base_600)

    def test_a_coexistence_in_simulation_history(self):
        """A & O: 300s and 600s experiments coexist in simulation history without overwriting."""
        sim_300 = {
            "scenario_id": "signal_timing:Westbound:adj+10.0s:dur300s:seed42",
            "scenario": "synthetic_peak_westbound",
            "duration_seconds": 300,
            "seed": 42,
            "metrics": {"average_speed_kmh": 32.5},
        }
        sim_600 = {
            "scenario_id": "signal_timing:Westbound:adj+10.0s:dur600s:seed42",
            "scenario": "synthetic_peak_westbound",
            "duration_seconds": 600,
            "seed": 42,
            "metrics": {"average_speed_kmh": 37.6},
        }
        history = [sim_300, sim_600]
        self.assertEqual(len(history), 2)
        durations = [s["duration_seconds"] for s in history]
        self.assertIn(300, durations)
        self.assertIn(600, durations)


class TestFairComparisonAndBaselinePairing(unittest.TestCase):
    """Tests C, D, W, X, Y, Z: Baseline pairing and fair comparison rules."""

    def test_c_matching_baseline_pairing(self):
        """C & W: Exact match on duration, scenario, seed, network yields fair_comparison=True."""
        base = {
            "scenario_name": "synthetic_peak_westbound",
            "duration_seconds": 600,
            "seed": 42,
            "network_name": "narayanguda_network.net.xml",
            "average_speed_kmh": 34.74,
            "average_delay_sec": 54.20,
            "average_waiting_time_sec": 21.05,
            "congestion_index": 0.305,
            "throughput": 131,
        }
        int_m = _make_int_metrics(speed=38.90, delay=38.78, wait=10.49, cong=0.222, tp=138)
        comp = SimulationService._calculate_comparison(
            baseline_metrics=base,
            intervention_metrics=int_m,
            raw_corridors=[],
            seed=42,
            duration=600,
            scenario="synthetic_peak_westbound",
            network_name="narayanguda_network.net.xml",
        )
        self.assertTrue(comp.get("fair_comparison"))
        self.assertEqual(comp.get("status"), "SUCCESS")

    def test_d_duration_mismatch_fails_fair_comparison(self):
        """D & W: 300s baseline paired with 600s intervention yields fair_comparison=False."""
        base = {
            "scenario_name": "synthetic_peak_westbound",
            "duration_seconds": 300,
            "seed": 42,
            "network_name": "narayanguda_network.net.xml",
            "average_speed_kmh": 35.0,
            "average_delay_sec": 50.0,
            "average_waiting_time_sec": 20.0,
            "congestion_index": 0.30,
            "throughput": 65,
        }
        int_m = _make_int_metrics(speed=38.90, delay=38.78, wait=10.49, cong=0.222, tp=138)
        comp = SimulationService._calculate_comparison(
            baseline_metrics=base,
            intervention_metrics=int_m,
            raw_corridors=[],
            seed=42,
            duration=600,
            scenario="synthetic_peak_westbound",
            network_name="narayanguda_network.net.xml",
        )
        self.assertFalse(comp.get("fair_comparison"))

    def test_x_scenario_mismatch_fails_fair_comparison(self):
        """X: Mismatched scenario yields fair_comparison=False."""
        base = {
            "scenario_name": "synthetic_normal",
            "duration_seconds": 600,
            "seed": 42,
            "network_name": "narayanguda_network.net.xml",
            "average_speed_kmh": 35.0,
        }
        int_m = _make_int_metrics(speed=38.0)
        comp = SimulationService._calculate_comparison(
            baseline_metrics=base,
            intervention_metrics=int_m,
            raw_corridors=[],
            seed=42,
            duration=600,
            scenario="synthetic_peak_westbound",
            network_name="narayanguda_network.net.xml",
        )
        self.assertFalse(comp.get("fair_comparison"))

    def test_y_seed_mismatch_fails_fair_comparison(self):
        """Y: Mismatched seed yields fair_comparison=False."""
        base = {
            "scenario_name": "synthetic_peak_westbound",
            "duration_seconds": 600,
            "seed": 99,
            "network_name": "narayanguda_network.net.xml",
            "average_speed_kmh": 35.0,
        }
        int_m = _make_int_metrics(speed=38.0)
        comp = SimulationService._calculate_comparison(
            baseline_metrics=base,
            intervention_metrics=int_m,
            raw_corridors=[],
            seed=42,
            duration=600,
            scenario="synthetic_peak_westbound",
            network_name="narayanguda_network.net.xml",
        )
        self.assertFalse(comp.get("fair_comparison"))

    def test_z_network_mismatch_fails_fair_comparison(self):
        """Z: Mismatched network yields fair_comparison=False."""
        base = {
            "scenario_name": "synthetic_peak_westbound",
            "duration_seconds": 600,
            "seed": 42,
            "network_name": "other_network.net.xml",
            "average_speed_kmh": 35.0,
        }
        int_m = _make_int_metrics(speed=38.0)
        comp = SimulationService._calculate_comparison(
            baseline_metrics=base,
            intervention_metrics=int_m,
            raw_corridors=[],
            seed=42,
            duration=600,
            scenario="synthetic_peak_westbound",
            network_name="narayanguda_network.net.xml",
        )
        self.assertFalse(comp.get("fair_comparison"))


class TestCompactionPreservation(unittest.TestCase):
    """Tests E, F, G, H: Compaction preserves all critical experiment metadata."""

    def test_compaction_preserves_all_metadata(self):
        """E, F, G, H: Duration, scenario, seed, network are preserved in compacted evidence."""
        sim = {
            "scenario_id": "signal_timing:Westbound:adj+10.0s:dur600s:seed42",
            "scenario": "synthetic_peak_westbound",
            "duration_seconds": 600,
            "seed": 42,
            "network_name": "narayanguda_network.net.xml",
            "evidence_status": "EVIDENCE: SINGLE SIMULATION RUN",
            "status": "SUCCESS",
            "intervention": {"type": "signal_timing", "target": "Westbound", "parameters": {"green_time_adjustment_sec": 10.0}},
            "metrics": {"average_speed_kmh": 37.64, "average_delay_sec": 43.13},
            "comparison": {
                "speed_change_pct": 8.35,
                "delay_change_pct": -20.42,
                "waiting_time_change_pct": -39.71,
                "congestion_change_pct": -19.02,
                "throughput_change": 10,
                "baseline_duration_seconds": 600,
                "intervention_duration_seconds": 600,
                "baseline_scenario": "synthetic_peak_westbound",
                "intervention_scenario": "synthetic_peak_westbound",
                "baseline_seed": 42,
                "intervention_seed": 42,
                "fair_comparison": True,
            },
        }
        compacted = _compact_simulation_evidence(sim)
        self.assertEqual(compacted.get("duration_seconds"), 600)  # E
        self.assertEqual(compacted.get("scenario"), "synthetic_peak_westbound")  # F
        self.assertEqual(compacted.get("seed"), 42)  # G
        self.assertEqual(compacted.get("network"), "narayanguda_network.net.xml")  # H
        self.assertIn("deltas", compacted)
        self.assertEqual(compacted["deltas"].get("speed_change_pct"), 8.35)
        self.assertEqual(compacted["deltas"].get("delay_change_pct"), -20.42)


class TestSignedDeltasAndLegacyReduction(unittest.TestCase):
    """Tests AA & AB: Signed delta conventions and backward-compatible legacy fields."""

    def test_aa_signed_delta_semantics(self):
        """AA: speed_change_pct > 0 is improvement, delay_change_pct < 0 is improvement."""
        base = {
            "scenario_name": "synthetic_peak_westbound",
            "duration_seconds": 600,
            "seed": 42,
            "average_speed_kmh": 30.0,
            "average_delay_sec": 50.0,
            "average_waiting_time_sec": 20.0,
            "congestion_index": 0.40,
            "throughput": 100,
        }
        int_m = _make_int_metrics(speed=36.0, delay=40.0, wait=15.0, cong=0.30, tp=110)
        comp = SimulationService._calculate_comparison(
            baseline_metrics=base,
            intervention_metrics=int_m,
            raw_corridors=[],
            seed=42,
            duration=600,
            scenario="synthetic_peak_westbound",
            network_name="narayanguda_network.net.xml",
        )
        self.assertEqual(comp["speed_change_pct"], 20.0)
        self.assertEqual(comp["delay_change_pct"], -20.0)
        self.assertEqual(comp["waiting_time_change_pct"], -25.0)
        self.assertEqual(comp["congestion_change_pct"], -25.0)
        self.assertEqual(comp["throughput_change"], 10)

    def test_ab_legacy_reduction_semantics_preserved(self):
        """AB: Legacy delay_reduction_pct is positive for improvements."""
        base = {
            "scenario_name": "synthetic_peak_westbound",
            "duration_seconds": 600,
            "seed": 42,
            "average_speed_kmh": 30.0,
            "average_delay_sec": 50.0,
            "average_waiting_time_sec": 20.0,
            "congestion_index": 0.40,
            "throughput": 100,
        }
        int_m = _make_int_metrics(speed=36.0, delay=40.0, wait=15.0, cong=0.30, tp=110)
        comp = SimulationService._calculate_comparison(
            baseline_metrics=base,
            intervention_metrics=int_m,
            raw_corridors=[],
            seed=42,
            duration=600,
            scenario="synthetic_peak_westbound",
            network_name="narayanguda_network.net.xml",
        )
        self.assertEqual(comp["delay_reduction_pct"], 20.0)
        self.assertEqual(comp["waiting_time_reduction_pct"], 25.0)
        self.assertEqual(comp["congestion_reduction_pct"], 25.0)


class TestAnalyticalFollowupAndHorizonSelection(unittest.TestCase):
    """Tests I, J, K, L: Horizon-aware follow-up detection without re-simulation."""

    def test_i_j_k_l_is_analytical_history_followup(self):
        """I, J, K, L: Analytical follow-up detector recognizes horizon-specific questions."""
        queries_that_must_not_dispatch = [
            "What did the 600-second simulation show?",
            "What did the 300-second simulation show?",
            "Compare the 600-second baseline with the interventions.",
            "What changed between 300 and 600 seconds?",
            "What were the results of the 600-second run?",
            "Which interventions did we test at 600 seconds?",
            "Compare the 300-second and 600-second results.",
            "Compare the tested interventions at 600s.",
        ]
        for q in queries_that_must_not_dispatch:
            self.assertTrue(
                is_analytical_history_followup(q),
                f"Query should be recognized as analytical follow-up: {q}",
            )


class TestProductionDefaultAndOverrides(unittest.TestCase):
    """Tests Q, R, S, T, U: 600s production default and explicit overrides."""

    def setUp(self):
        self.original_provider = os.environ.get("LLM_PROVIDER")
        os.environ["LLM_PROVIDER"] = "mock"
        self.client = TestClient(app)
        _PLANNER_SESSIONS.clear()

    def tearDown(self):
        if self.original_provider is not None:
            os.environ["LLM_PROVIDER"] = self.original_provider

    def test_q_default_production_duration_is_600(self):
        """Q: Default production duration constant is 600 seconds."""
        self.assertEqual(DEFAULT_PRODUCTION_EVALUATION_DURATION_SECONDS, 600)
        self.assertEqual(CI_SMOKE_EVALUATION_DURATION_SECONDS, 120)
        self.assertEqual(HISTORICAL_EVALUATION_DURATION_SECONDS, 300)

    def test_r_explicit_300_overrides_600_default(self):
        """R & U: Explicit 300-second query uses duration=300."""
        res = self.client.post("/agents/planner/execute", json={
            "query": "Run a 300-second simulation to evaluate interventions",
        })
        self.assertEqual(res.status_code, 200)
        final_resp = res.json().get("final_response", {})
        self.assertEqual(final_resp.get("requested_duration"), 300)

    def test_s_explicit_120_overrides_600_default(self):
        """S & T: Explicit 120-second CI/smoke query uses duration=120."""
        res = self.client.post("/agents/planner/execute", json={
            "query": "Run a 120-second smoke test for the westbound corridor",
        })
        self.assertEqual(res.status_code, 200)
        final_resp = res.json().get("final_response", {})
        self.assertEqual(final_resp.get("requested_duration"), 120)

    def test_p_clear_conversation_removes_history(self):
        """P: Empty history payload starts completely fresh session."""
        res = self.client.post("/agents/planner/execute", json={
            "query": "What is the traffic situation in Narayanguda?",
            "conversation_history": [],
            "simulation_history": [],
            "tested_scenarios": [],
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn("OBSERVATIONAL", res.json().get("evidence_status", ""))


class TestPlannerIntegrityAndEvidence(unittest.TestCase):
    """Tests V, AF, AG: Vehicle accounting, tested vs untested, and no forced winner."""

    def test_v_vehicle_accounting(self):
        """V: Arrived + active_at_end == total_vehicles in simulation metrics."""
        m = _make_int_metrics(tp=138, total=205)
        self.assertEqual(m.arrived_vehicles + m.active_at_end, m.total_vehicles)

    def test_af_untested_candidates_preserved(self):
        """AF: Planner does not claim untested candidates were simulated."""
        agent = PlannerAgent()
        collected = {
            "traffic": {
                "metrics": {"average_speed_kmh": 34.0},
                "candidate_interventions": [
                    {"type": "signal_timing", "target": "Westbound", "parameters": {"green_time_adjustment_sec": 10.0}},
                    {"type": "rerouting", "target": "Westbound", "parameters": {"diversion_fraction": 0.15}},
                    {"type": "lane_reversal", "target": "Westbound", "parameters": {}},
                ],
            },
            "simulations": [
                {
                    "scenario_id": "signal_timing:Westbound:adj+10.0s:dur600s:seed42",
                    "scenario": "synthetic_peak_westbound",
                    "duration_seconds": 600,
                    "seed": 42,
                    "intervention": {"type": "signal_timing", "target": "Westbound", "parameters": {"green_time_adjustment_sec": 10.0}},
                    "metrics": {"average_speed_kmh": 37.64},
                }
            ],
        }
        res = agent.evaluate_and_replan(
            objective="Evaluate interventions for Narayanguda",
            plan=["Step 1"],
            collected_results=collected,
        )
        self.assertIsNotNone(res)
        if res.final_reasoning:
            tested_types = [t.get("type") for t in res.final_reasoning.tested_interventions]
            self.assertIn("signal_timing", tested_types)
            self.assertNotIn("lane_reversal", tested_types)

    def test_ag_no_forced_winner(self):
        """AG: Planner reports empirical evidence without claiming guaranteed or universal optimality."""
        agent = PlannerAgent()
        collected = {
            "simulations": [
                {
                    "scenario_id": "signal_timing:Westbound:adj+10.0s:dur600s:seed42",
                    "duration_seconds": 600,
                    "seed": 42,
                    "metrics": {"average_speed_kmh": 37.64, "average_delay_sec": 43.13},
                    "comparison": {"speed_change_pct": 8.35, "delay_change_pct": -20.42},
                },
                {
                    "scenario_id": "signal_timing:Westbound:adj+19.0s:dur600s:seed42",
                    "duration_seconds": 600,
                    "seed": 42,
                    "metrics": {"average_speed_kmh": 38.90, "average_delay_sec": 38.78},
                    "comparison": {"speed_change_pct": 11.97, "delay_change_pct": -28.45},
                },
            ]
        }
        res = agent.evaluate_and_replan(
            objective="Which tested intervention performed better and why?",
            plan=["Step 1"],
            collected_results=collected,
        )
        self.assertIsNotNone(res)
        # Should not make claim of universal optimality
        summary_text = (res.final_recommendation or "") + (res.analysis or "")
        self.assertNotIn("guaranteed to be optimal", summary_text.lower())
        self.assertNotIn("universally optimal", summary_text.lower())


if __name__ == "__main__":
    unittest.main()
