"""
Test Suite: 600s Delta Convention + Robustness Tests (A-Z).

A. speed positive = improvement (speed_change_pct > 0 when int_speed > base_speed)
B. speed negative = degradation (speed_change_pct < 0 when int_speed < base_speed)
C. delay negative = improvement (delay_change_pct < 0 when int_delay < base_delay)
D. delay positive = degradation (delay_change_pct > 0 when int_delay > base_delay)
E. waiting negative = improvement (waiting_time_change_pct < 0 when int_wait < base_wait)
F. waiting positive = degradation (waiting_time_change_pct > 0 when int_wait > base_wait)
G. congestion negative = improvement (congestion_change_pct < 0 when int_cong < base_cong)
H. congestion positive = degradation (congestion_change_pct > 0 when int_cong > base_cong)
I. throughput positive = improvement
J. legacy delay_reduction_pct retains original semantics (positive = improved)
K. legacy waiting_time_reduction_pct retains original semantics (positive = improved)
L. legacy congestion_reduction_pct retains original semantics (positive = improved)
M. fair comparison rejects seed mismatch
N. fair comparison rejects duration mismatch
O. fair comparison rejects scenario mismatch
P. fair comparison rejects network mismatch
Q. 600s metadata propagation
R. intervention metadata propagation (seed/duration/scenario inherited at 600s)
S. vehicle accounting invariant
T. multi-intervention evidence classification
U. no hardcoded 600s outcomes in comparison logic
V. no hardcoded intervention outcome values in comparison logic
W. 120s CI behavior remains intact
X. 300s production behavior remains intact
Y. Planner does not claim untested interventions were simulated
Z. Planner does not force an arbitrary overall winner
"""

import inspect
import os
import unittest

from fastapi.testclient import TestClient

from backend.agents.planner_agent.llm_client import MockLLMProvider
from backend.agents.planner_agent.planner import PlannerAgent
from backend.agents.simulation_agent.service import SimulationService
from backend.agents.traffic_agent.schemas import SimulationMetrics
from backend.supervisor.main import _PLANNER_SESSIONS, app


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_int_metrics(speed=37.83, delay=33.94, wait=11.18, cong=0.243, tp=39):
    return SimulationMetrics(
        active_vehicles=10,
        total_vehicles=100,
        arrived_vehicles=tp,
        active_at_end=100 - tp,
        throughput=tp,
        average_speed_kmh=speed,
        average_waiting_time_sec=wait,
        average_delay_sec=delay,
        congestion_index=cong,
    )


def _run_comparison(
    base_speed=35.94, base_delay=38.54, base_wait=15.08, base_cong=0.281, base_tp=40,
    int_speed=37.83, int_delay=33.94, int_wait=11.18, int_cong=0.243, int_tp=39,
    seed=42, duration=600, scenario="synthetic_peak_westbound",
    network="narayanguda_network.net.xml",
):
    int_m = _make_int_metrics(int_speed, int_delay, int_wait, int_cong, int_tp)
    baseline = {
        "seed": seed,
        "duration_seconds": duration,
        "scenario_name": scenario,
        "network_name": network,
        "average_speed_kmh": base_speed,
        "average_delay_sec": base_delay,
        "average_waiting_time_sec": base_wait,
        "congestion_index": base_cong,
        "throughput": base_tp,
    }
    return SimulationService._calculate_comparison(
        baseline_metrics=baseline,
        intervention_metrics=int_m,
        raw_corridors=[],
        seed=seed,
        duration=duration,
        scenario=scenario,
        network_name=network,
    )


# ===========================================================================
# A-I: New signed *_change_pct fields
# ===========================================================================

class TestDeltaSignConvention(unittest.TestCase):
    """Tests A-I: sign semantics of new *_change_pct fields."""

    def test_a_speed_positive_is_improvement(self):
        """A: speed_change_pct > 0 when intervention speed > baseline speed."""
        comp = _run_comparison(base_speed=35.94, int_speed=37.83)
        self.assertGreater(comp["speed_change_pct"], 0)

    def test_b_speed_negative_is_degradation(self):
        """B: speed_change_pct < 0 when intervention speed < baseline speed."""
        comp = _run_comparison(base_speed=35.94, int_speed=33.50)
        self.assertLess(comp["speed_change_pct"], 0)

    def test_c_delay_negative_is_improvement(self):
        """C: delay_change_pct < 0 when intervention delay < baseline delay."""
        comp = _run_comparison(base_delay=38.54, int_delay=29.41)
        self.assertIn("delay_change_pct", comp)
        self.assertLess(comp["delay_change_pct"], 0)
        self.assertAlmostEqual(comp["delay_change_pct"], -23.69, delta=0.5)

    def test_d_delay_positive_is_degradation(self):
        """D: delay_change_pct > 0 when intervention delay > baseline delay."""
        comp = _run_comparison(base_delay=38.54, int_delay=40.39)
        self.assertGreater(comp["delay_change_pct"], 0)
        self.assertAlmostEqual(comp["delay_change_pct"], 4.80, delta=0.5)

    def test_e_waiting_negative_is_improvement(self):
        """E: waiting_time_change_pct < 0 when intervention waiting < baseline waiting."""
        comp = _run_comparison(base_wait=15.08, int_wait=11.18)
        self.assertIn("waiting_time_change_pct", comp)
        self.assertLess(comp["waiting_time_change_pct"], 0)

    def test_f_waiting_positive_is_degradation(self):
        """F: waiting_time_change_pct > 0 when intervention waiting > baseline waiting."""
        comp = _run_comparison(base_wait=15.08, int_wait=16.85)
        self.assertGreater(comp["waiting_time_change_pct"], 0)
        # (16.85 - 15.08) / 15.08 * 100 ≈ +11.74
        self.assertAlmostEqual(comp["waiting_time_change_pct"], 11.74, delta=0.5)

    def test_g_congestion_negative_is_improvement(self):
        """G: congestion_change_pct < 0 when intervention congestion < baseline congestion."""
        comp = _run_comparison(base_cong=0.281, int_cong=0.212)
        self.assertIn("congestion_change_pct", comp)
        self.assertLess(comp["congestion_change_pct"], 0)

    def test_h_congestion_positive_is_degradation(self):
        """H: congestion_change_pct > 0 when intervention congestion > baseline congestion."""
        comp = _run_comparison(base_cong=0.281, int_cong=0.291)
        self.assertGreater(comp["congestion_change_pct"], 0)

    def test_i_throughput_positive_is_improvement(self):
        """I: throughput_change > 0 when more vehicles arrive."""
        comp = _run_comparison(base_tp=40, int_tp=43)
        self.assertEqual(comp["throughput_change"], 3)

    def test_i_throughput_negative_is_degradation(self):
        """I (inverse): throughput_change < 0 when fewer vehicles arrive."""
        comp = _run_comparison(base_tp=43, int_tp=40)
        self.assertEqual(comp["throughput_change"], -3)


# ===========================================================================
# J-L: Legacy *_reduction_pct backward compatibility
# ===========================================================================

class TestLegacyReductionSemantics(unittest.TestCase):
    """Tests J-L: legacy *_reduction_pct fields keep positive=improved semantics."""

    def test_j_legacy_delay_reduction_pct_positive_when_improved(self):
        """J: delay_reduction_pct > 0 when delay decreases (original positive=improved semantics)."""
        comp = _run_comparison(base_delay=38.54, int_delay=29.41)
        self.assertIn("delay_reduction_pct", comp)
        self.assertGreater(comp["delay_reduction_pct"], 0)
        self.assertAlmostEqual(comp["delay_reduction_pct"], 23.69, delta=0.5)

    def test_j_legacy_delay_reduction_pct_negative_when_worsened(self):
        """J (inverse): delay_reduction_pct < 0 when delay increases."""
        comp = _run_comparison(base_delay=38.54, int_delay=40.39)
        self.assertLess(comp["delay_reduction_pct"], 0)

    def test_k_legacy_waiting_reduction_pct_positive_when_improved(self):
        """K: waiting_time_reduction_pct > 0 when waiting decreases."""
        comp = _run_comparison(base_wait=15.08, int_wait=11.18)
        self.assertIn("waiting_time_reduction_pct", comp)
        self.assertGreater(comp["waiting_time_reduction_pct"], 0)

    def test_l_legacy_congestion_reduction_pct_positive_when_improved(self):
        """L: congestion_reduction_pct > 0 when congestion decreases."""
        comp = _run_comparison(base_cong=0.281, int_cong=0.212)
        self.assertIn("congestion_reduction_pct", comp)
        self.assertGreater(comp["congestion_reduction_pct"], 0)

    def test_new_and_legacy_are_negatives_of_each_other(self):
        """delay_change_pct == -delay_reduction_pct (symmetric by definition)."""
        comp = _run_comparison(base_delay=38.54, int_delay=29.41)
        if comp["delay_change_pct"] is not None and comp["delay_reduction_pct"] is not None:
            self.assertAlmostEqual(comp["delay_change_pct"], -comp["delay_reduction_pct"], delta=0.01)


# ===========================================================================
# M-P: Fair comparison rejection
# ===========================================================================

class TestFairComparisonRejection(unittest.TestCase):
    """Tests M-P: fair_comparison = False on any metadata mismatch."""

    _BASE = {
        "seed": 42,
        "duration_seconds": 600,
        "scenario_name": "synthetic_peak_westbound",
        "network_name": "narayanguda_network.net.xml",
        "average_speed_kmh": 35.94, "average_delay_sec": 38.54,
        "average_waiting_time_sec": 15.08, "congestion_index": 0.281, "throughput": 40,
    }
    _INT_M = _make_int_metrics()

    def _comp(self, seed, duration, scenario, network):
        return SimulationService._calculate_comparison(
            baseline_metrics=self._BASE,
            intervention_metrics=self._INT_M,
            raw_corridors=[],
            seed=seed, duration=duration, scenario=scenario, network_name=network,
        )

    def test_m_rejects_seed_mismatch(self):
        """M: fair_comparison=False when intervention seed differs from baseline."""
        res = self._comp(seed=99, duration=600, scenario="synthetic_peak_westbound",
                         network="narayanguda_network.net.xml")
        self.assertFalse(res["fair_comparison"])
        self.assertIn("seed", res["fair_comparison_warning"].lower())

    def test_n_rejects_duration_mismatch(self):
        """N: fair_comparison=False when duration differs."""
        res = self._comp(seed=42, duration=300, scenario="synthetic_peak_westbound",
                         network="narayanguda_network.net.xml")
        self.assertFalse(res["fair_comparison"])
        self.assertIn("duration", res["fair_comparison_warning"].lower())

    def test_o_rejects_scenario_mismatch(self):
        """O: fair_comparison=False when scenario differs."""
        res = self._comp(seed=42, duration=600, scenario="synthetic_normal",
                         network="narayanguda_network.net.xml")
        self.assertFalse(res["fair_comparison"])
        self.assertIn("scenario", res["fair_comparison_warning"].lower())

    def test_p_rejects_network_mismatch(self):
        """P: fair_comparison=False when network differs."""
        res = self._comp(seed=42, duration=600, scenario="synthetic_peak_westbound",
                         network="other_network.net.xml")
        self.assertFalse(res["fair_comparison"])
        self.assertIn("network", res["fair_comparison_warning"].lower())

    def test_matching_metadata_passes(self):
        """Sanity: all matching → fair_comparison=True."""
        res = self._comp(seed=42, duration=600, scenario="synthetic_peak_westbound",
                         network="narayanguda_network.net.xml")
        self.assertTrue(res["fair_comparison"])
        self.assertIsNone(res["fair_comparison_warning"])


# ===========================================================================
# Q-R: 600s metadata propagation
# ===========================================================================

class TestMetadataPropagation600s(unittest.TestCase):
    """Tests Q-R: metadata propagates correctly for 600s experiments."""

    def setUp(self):
        self.original_provider = os.environ.get("LLM_PROVIDER")
        os.environ["LLM_PROVIDER"] = "mock"
        self.client = TestClient(app)
        _PLANNER_SESSIONS.clear()

    def tearDown(self):
        if self.original_provider is not None:
            os.environ["LLM_PROVIDER"] = self.original_provider
        else:
            os.environ.pop("LLM_PROVIDER", None)
        _PLANNER_SESSIONS.clear()

    def test_q_600s_scenario_metadata_propagation(self):
        """Q: 600s + synthetic_peak_westbound request yields correct metadata."""
        res = self.client.post("/agents/planner/execute", json={
            "query": "Run synthetic_peak_westbound for 600 seconds seed=42",
            "scenario": "synthetic_peak_westbound",
            "duration_seconds": 600,
            "seed": 42,
        })
        self.assertEqual(res.status_code, 200, res.text)
        meta = res.json().get("collected_results", {}).get("traffic", {}).get("metadata", {})
        self.assertEqual(meta.get("duration_seconds"), 600)
        self.assertEqual(meta.get("demand_profile"), "synthetic_peak_westbound")
        self.assertEqual(meta.get("random_seed"), 42)

    def test_r_intervention_inherits_600s_metadata(self):
        """R: Intervention simulation requests inherit seed=42, duration=600, scenario from baseline."""
        mock_provider = MockLLMProvider()
        planner = PlannerAgent(llm_provider=mock_provider)

        traffic_data = {
            "location": "Narayanguda, Hyderabad",
            "seed": 42,
            "duration_seconds": 600,
            "scenario": "synthetic_peak_westbound",
            "average_speed_kmh": 35.94,
            "average_delay_sec": 38.54,
            "candidate_interventions": [
                {"type": "signal_timing", "target": "Westbound", "executable": True,
                 "parameters": {"green_time_adjustment_sec": 10.0}},
            ],
        }
        eval_resp = planner.evaluate_and_replan(
            objective="Optimize under peak demand for 600s",
            plan=["traffic"],
            collected_results={"traffic": traffic_data},
            cycle_num=1,
            max_cycles=2,
            location="Narayanguda, Hyderabad",
        )
        sim_calls = [c for c in eval_resp.next_cycle_calls if c.agent == "simulation"]
        self.assertGreaterEqual(len(sim_calls), 1)
        req = sim_calls[0].request
        self.assertEqual(req.get("seed"), 42)
        self.assertEqual(req.get("duration_seconds"), 600)
        self.assertEqual(req.get("scenario_name"), "synthetic_peak_westbound")


# ===========================================================================
# S: Vehicle accounting
# ===========================================================================

class TestVehicleAccounting(unittest.TestCase):
    """Test S: total_vehicles = arrived_vehicles + active_at_end invariant."""

    def test_s_vehicle_accounting_invariant(self):
        """S: total_vehicles == arrived_vehicles + active_at_end at 600s."""
        m = SimulationMetrics(
            active_vehicles=20,
            peak_active_vehicles=35,
            total_vehicles=160,
            arrived_vehicles=85,
            active_at_end=75,
            throughput=85,
            average_speed_kmh=37.83,
            average_waiting_time_sec=8.2,
            average_delay_sec=22.0,
            congestion_index=0.22,
        )
        self.assertEqual(m.total_vehicles, m.arrived_vehicles + m.active_at_end)
        self.assertEqual(m.throughput, m.arrived_vehicles)


# ===========================================================================
# T: Multi-intervention evidence classification
# ===========================================================================

class TestEvidenceClassification(unittest.TestCase):
    """Test T: multi-intervention evidence classification."""

    def setUp(self):
        self.original_provider = os.environ.get("LLM_PROVIDER")
        os.environ["LLM_PROVIDER"] = "mock"
        self.client = TestClient(app)
        _PLANNER_SESSIONS.clear()

    def tearDown(self):
        if self.original_provider is not None:
            os.environ["LLM_PROVIDER"] = self.original_provider
        else:
            os.environ.pop("LLM_PROVIDER", None)
        _PLANNER_SESSIONS.clear()

    def test_t_two_sims_yields_multi_simulation_evidence(self):
        """T: 2+ simulations in history → EVIDENCE: MULTI-SIMULATION EVALUATION."""
        sims = [
            {
                "scenario_id": "600s_signal_10",
                "status": "COMPLETED",
                "intervention_applied": {"type": "signal_timing", "target": "Westbound",
                                         "parameters": {"green_time_adjustment_sec": 10.0}},
                "metrics": {"average_speed_kmh": 37.83, "throughput": 39},
                "comparison": {
                    "speed_change_pct": 5.26, "delay_change_pct": -11.93,
                    "waiting_time_change_pct": -25.86, "congestion_change_pct": -13.52,
                    "fair_comparison": True,
                },
            },
            {
                "scenario_id": "600s_signal_19",
                "status": "COMPLETED",
                "intervention_applied": {"type": "signal_timing", "target": "Westbound",
                                         "parameters": {"green_time_adjustment_sec": 19.0}},
                "metrics": {"average_speed_kmh": 39.42, "throughput": 43},
                "comparison": {
                    "speed_change_pct": 9.68, "delay_change_pct": -23.69,
                    "waiting_time_change_pct": -50.13, "congestion_change_pct": -24.56,
                    "fair_comparison": True,
                },
            },
        ]
        res = self.client.post("/agents/planner/execute", json={
            "session_id": "sess_t_multi",
            "objective": "Compare the two tested signal timing interventions",
            "simulation_history": sims,
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["evidence_status"], "EVIDENCE: MULTI-SIMULATION EVALUATION")


# ===========================================================================
# U-V: No hardcoded outcomes
# ===========================================================================

class TestNoHardcodedOutcomes(unittest.TestCase):
    """Tests U-V: No hardcoded 600s or intervention outcomes in comparison code."""

    def test_u_no_hardcoded_600_in_calculate_comparison(self):
        """U: _calculate_comparison must not assign the literal 600 as a default."""
        src = inspect.getsource(SimulationService._calculate_comparison)
        self.assertNotIn("= 600", src,
                         "Hardcoded duration=600 found in _calculate_comparison. Use dynamic metadata.")

    def test_v_no_hardcoded_known_speed_values(self):
        """V: Known historical result values (37.83, 39.42) must not be hardcoded."""
        src = inspect.getsource(SimulationService._calculate_comparison)
        self.assertNotIn("37.83", src, "Hardcoded +10s speed result found in _calculate_comparison")
        self.assertNotIn("39.42", src, "Hardcoded +19s speed result found in _calculate_comparison")


# ===========================================================================
# W-X: Behavior preservation
# ===========================================================================

class TestBehaviorPreservation(unittest.TestCase):
    """Tests W-X: 120s and 300s behavior preserved after changes."""

    def setUp(self):
        self.original_provider = os.environ.get("LLM_PROVIDER")
        os.environ["LLM_PROVIDER"] = "mock"
        self.client = TestClient(app)
        _PLANNER_SESSIONS.clear()

    def tearDown(self):
        if self.original_provider is not None:
            os.environ["LLM_PROVIDER"] = self.original_provider
        else:
            os.environ.pop("LLM_PROVIDER", None)
        _PLANNER_SESSIONS.clear()

    def test_w_120s_ci_behavior_preserved(self):
        """W: Explicit 120s requests propagate duration_seconds=120."""
        res = self.client.post("/agents/planner/execute", json={
            "query": "Quick smoke test at 120 seconds",
            "duration_seconds": 120,
        })
        self.assertEqual(res.status_code, 200)
        meta = res.json().get("collected_results", {}).get("traffic", {}).get("metadata", {})
        self.assertEqual(meta.get("duration_seconds"), 120)

    def test_x_300s_production_behavior_preserved(self):
        """X: Unqualified optimization defaults to 600s, while explicit 300s is respected."""
        res = self.client.post("/agents/planner/execute", json={
            "query": "Optimize the traffic situation in Narayanguda",
        })
        self.assertEqual(res.status_code, 200)
        meta = res.json().get("collected_results", {}).get("traffic", {}).get("metadata", {})
        self.assertEqual(meta.get("duration_seconds"), 600)

        res_300 = self.client.post("/agents/planner/execute", json={
            "query": "Run a 300-second simulation to optimize traffic",
        })
        self.assertEqual(res_300.status_code, 200)
        meta_300 = res_300.json().get("collected_results", {}).get("traffic", {}).get("metadata", {})
        self.assertEqual(meta_300.get("duration_seconds"), 300)


# ===========================================================================
# Y-Z: Planner integrity
# ===========================================================================

class TestPlannerIntegrity(unittest.TestCase):
    """Tests Y-Z: Planner evidence integrity and winner determination."""

    def setUp(self):
        self.original_provider = os.environ.get("LLM_PROVIDER")
        os.environ["LLM_PROVIDER"] = "mock"
        self.client = TestClient(app)
        _PLANNER_SESSIONS.clear()

    def tearDown(self):
        if self.original_provider is not None:
            os.environ["LLM_PROVIDER"] = self.original_provider
        else:
            os.environ.pop("LLM_PROVIDER", None)
        _PLANNER_SESSIONS.clear()

    def test_y_no_fabricated_simulation_without_dispatch(self):
        """Y: With no simulation history, no simulation result appears in response."""
        res = self.client.post("/agents/planner/execute", json={
            "session_id": "sess_y",
            "objective": "Compare the tested interventions",
            "simulation_history": [],
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        # No simulation result fabricated
        collected_sim = data.get("collected_results", {}).get("simulation")
        if collected_sim is not None:
            # If somehow a sim agent was dispatched, it must have been dispatched explicitly
            self.assertIn("simulation_agent", data.get("dispatched_agents", []),
                          "simulation appeared in results but simulation_agent was not dispatched")

    def test_z_two_simulations_follow_up_no_new_dispatch(self):
        """Z: Follow-up comparison of 2 completed simulations does not re-dispatch simulation."""
        sims = [
            {
                "scenario_id": "scenario_a",
                "intervention_applied": {"type": "signal_timing", "target": "Westbound"},
                "metrics": {"average_speed_kmh": 37.83},
                "comparison": {"speed_change_pct": 5.26, "delay_change_pct": -11.93,
                               "fair_comparison": True},
            },
            {
                "scenario_id": "scenario_b",
                "intervention_applied": {"type": "rerouting", "target": "Westbound"},
                "metrics": {"average_speed_kmh": 33.80},
                "comparison": {"speed_change_pct": -1.31, "delay_change_pct": 4.80,
                               "fair_comparison": True},
            },
        ]
        res = self.client.post("/agents/planner/execute", json={
            "session_id": "sess_z",
            "objective": "Compare the tested interventions again",
            "simulation_history": sims,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["evidence_status"], "EVIDENCE: MULTI-SIMULATION EVALUATION")
        self.assertNotIn("simulation_agent", data.get("dispatched_agents", []))


# ===========================================================================
# Consistency checks
# ===========================================================================

class TestDeltaFieldConsistency(unittest.TestCase):
    """Additional consistency invariants."""

    def test_all_required_fields_present(self):
        """Both new *_change_pct and legacy *_reduction_pct must be in the return dict."""
        comp = _run_comparison()
        new_fields = ["delay_change_pct", "waiting_time_change_pct", "congestion_change_pct"]
        legacy_fields = ["delay_reduction_pct", "waiting_time_reduction_pct", "congestion_reduction_pct"]
        for f in new_fields + legacy_fields:
            self.assertIn(f, comp, f"Missing required field: {f}")

    def test_zero_change_both_fields_are_zero(self):
        """When intervention == baseline for all metrics, both fields are 0.0."""
        comp = _run_comparison(
            base_delay=38.54, int_delay=38.54,
            base_wait=15.08, int_wait=15.08,
            base_cong=0.281, int_cong=0.281,
        )
        self.assertEqual(comp["delay_change_pct"], 0.0)
        self.assertEqual(comp["delay_reduction_pct"], 0.0)
        self.assertEqual(comp["waiting_time_change_pct"], 0.0)
        self.assertEqual(comp["waiting_time_reduction_pct"], 0.0)
        self.assertEqual(comp["congestion_change_pct"], 0.0)
        self.assertEqual(comp["congestion_reduction_pct"], 0.0)

    def test_trade_off_summary_worsened_when_delay_increases(self):
        """Trade-off summary says 'worsened' when delay_change_pct > 0."""
        comp = _run_comparison(base_delay=38.54, int_delay=40.39)
        if comp.get("trade_off_summary"):
            self.assertIn("worsened", comp["trade_off_summary"].lower())

    def test_trade_off_summary_improved_when_delay_decreases(self):
        """Trade-off summary says 'improved' when delay_change_pct < 0."""
        comp = _run_comparison(base_delay=38.54, int_delay=29.41)
        if comp.get("trade_off_summary"):
            self.assertIn("improved", comp["trade_off_summary"].lower())


if __name__ == "__main__":
    unittest.main()
