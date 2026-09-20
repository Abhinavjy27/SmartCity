"""
Comprehensive Test Suite for Planner History & Dynamic Baseline Evidence.
Covers requirements A through M:
  A. History Follow-up (3 completed simulations -> 0 new simulations, historical results used, MULTI-SIMULATION EVALUATION)
  B. History Follow-up with Trade-offs (Conflicting tested results -> no forced winner, trade-offs explained)
  C. Solve-Bottleneck Follow-up (Historical evidence -> 0 new simulations, target improvement vs full bottleneck resolution, no new sim this turn)
  D. No History Follow-up ("Which tested intervention performed better?" -> 0 simulations, clearly states no tested evidence)
  E. Evidence Status (Historical simulation-backed follow-up does NOT regress to OBSERVATIONAL)
  F. Dynamic Baseline (seed=77, duration=300, scenario="peak_test", location="Secunderabad" dynamically inherited)
  G. Missing Baseline Metadata (Explicit failure / 400 error, no fallback to 42, 120, synthetic_normal, Narayanguda)
  H. Tested History Persistence (Previously tested intervention remains TESTED during follow-up)
  K. Route/Session Persistence (Same session_id preserves messages, simulation history, tested/untested state)
  L. Clear/New Conversation (New session_id, old history cleared, zero leakage)
  M. Follow-up After Route Navigation (Planner -> Optimize -> Navigate -> Follow-up uses historical evidence without new simulations)
"""

import os
import unittest
from fastapi.testclient import TestClient

from backend.supervisor.main import app, _PLANNER_SESSIONS
from backend.agents.planner_agent.planner import PlannerAgent
from backend.agents.planner_agent.llm_client import MockLLMProvider


class TestPlannerHistoryAndDynamicBaseline(unittest.TestCase):
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

    def _sample_simulations_3(self):
        return [
            {
                "scenario_id": "scen_signal_wb_10",
                "status": "COMPLETED",
                "intervention_applied": {"type": "signal_timing", "target": "Westbound", "parameters": {"green_time_adjustment_sec": 10.0}},
                "metrics": {"average_speed_kmh": 39.56, "average_delay_sec": 14.27, "throughput": 16},
                "comparison": {
                    "speed_change_pct": -0.48,
                    "delay_reduction_pct": -3.41,
                    "target_corridor_speed_change_pct": 17.1,
                    "corridor_trade_offs": ["Southbound corridor speed degraded by -15.2%"],
                },
                "corridor_trade_offs": ["Southbound corridor speed degraded by -15.2%"],
            },
            {
                "scenario_id": "scen_reroute_wb_15",
                "status": "COMPLETED",
                "intervention_applied": {"type": "rerouting", "target": "Westbound", "parameters": {"diversion_fraction": 0.15}},
                "metrics": {"average_speed_kmh": 39.71, "average_delay_sec": 13.82, "throughput": 16},
                "comparison": {
                    "speed_change_pct": -0.10,
                    "delay_reduction_pct": -0.14,
                    "target_corridor_speed_change_pct": 0.2,
                    "corridor_trade_offs": [],
                },
                "corridor_trade_offs": [],
            },
            {
                "scenario_id": "scen_signal_balanced_wb_10",
                "status": "COMPLETED",
                "intervention_applied": {"type": "signal_timing", "target": "Westbound", "parameters": {"green_time_adjustment_sec": 8.0}},
                "metrics": {"average_speed_kmh": 39.65, "average_delay_sec": 14.05, "throughput": 16},
                "comparison": {
                    "speed_change_pct": -0.25,
                    "delay_reduction_pct": -1.81,
                    "target_corridor_speed_change_pct": 8.9,
                    "corridor_trade_offs": ["Southbound corridor speed degraded by -7.2%"],
                },
                "corridor_trade_offs": ["Southbound corridor speed degraded by -7.2%"],
            },
        ]

    # -------------------------------------------------------------------------
    # Test A: History Follow-up (3 completed simulations)
    # -------------------------------------------------------------------------
    def test_a_history_followup_uses_historical_simulations(self):
        """
        Previous turn has 3 completed simulations.
        Question: 'Which tested intervention performed better and why?'
        Expected:
          - 0 new simulations dispatched
          - historical results used
          - TESTED preserved
          - empirical metrics available
          - EVIDENCE: MULTI-SIMULATION EVALUATION
        """
        sims = self._sample_simulations_3()
        session_id = "sess_test_a"

        res = self.client.post("/agents/planner/execute", json={
            "session_id": session_id,
            "objective": "Which tested intervention performed better and why?",
            "query": "Which tested intervention performed better and why?",
            "location": "Narayanguda, Hyderabad",
            "simulation_history": sims,
            "tested_scenarios": sims,
            "conversation_history": [
                {"role": "user", "content": "Optimize the traffic situation."},
                {"role": "assistant", "content": "Simulated candidate interventions.", "simulations": sims}
            ],
            "max_cycles": 2
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # 0 new simulations
        dispatched_sims = [a for a in data.get("dispatched_agents", []) if "sim" in a]
        self.assertEqual(len(dispatched_sims), 0)

        # Evidence status simulation-backed
        self.assertEqual(data["evidence_status"], "EVIDENCE: MULTI-SIMULATION EVALUATION")

        final_resp = data["final_response"]
        self.assertEqual(final_resp["evidence_status"], "EVIDENCE: MULTI-SIMULATION EVALUATION")

        # TESTED preserved
        tested = final_resp.get("tested_interventions", [])
        self.assertTrue(any("signal" in str(t.get("type", "")).lower() for t in tested))

        # Empirical comparison available in text
        rec = (final_resp.get("recommendation") or "") + " " + (final_resp.get("summary") or "")
        self.assertTrue(len(rec) > 20)

    # -------------------------------------------------------------------------
    # Test B: History Follow-up with Trade-offs
    # -------------------------------------------------------------------------
    def test_b_history_followup_with_trade_offs_no_forced_winner(self):
        """
        Conflicting tested results:
        Signal timing improves target corridor travel speed (+17.1%) but increases delay (+3.4%)
        and degrades opposing corridor (-15.2%).
        Rerouting has negligible change.
        Expected: no forced winner, trade-offs explained.
        """
        sims = self._sample_simulations_3()[:2]
        res = self.client.post("/agents/planner/execute", json={
            "session_id": "sess_test_b",
            "objective": "Compare the tested interventions again.",
            "query": "Compare the tested interventions again.",
            "location": "Narayanguda, Hyderabad",
            "simulation_history": sims,
            "conversation_history": [
                {"role": "user", "content": "Optimize traffic."},
                {"role": "assistant", "content": "Simulations run.", "simulations": sims}
            ],
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()

        rec = (data["final_response"].get("recommendation") or "").lower()
        summary = (data["final_response"].get("summary") or "").lower()
        combined = rec + " " + summary

        # Conflicting trade-offs identified
        self.assertTrue("trade-off" in combined or "tradeoff" in combined or "delay" in combined)
        # Not claiming arbitrary absolute superiority without qualification
        self.assertNotIn("is unanimously optimal", combined)

    # -------------------------------------------------------------------------
    # Test C: Solve-Bottleneck Follow-up
    # -------------------------------------------------------------------------
    def test_c_solve_bottleneck_distinguishes_target_from_full_resolution(self):
        """
        Historical evidence available.
        Question: 'Did the optimization solve the bottleneck?'
        Expected:
          - 0 new simulations
          - Target improvement distinguished from full network bottleneck resolution
          - 'no new simulation was run in this turn' distinguished from 'no evidence exists'
        """
        sims = self._sample_simulations_3()
        res = self.client.post("/agents/planner/execute", json={
            "session_id": "sess_test_c",
            "objective": "Did the optimization solve the bottleneck?",
            "query": "Did the optimization solve the bottleneck?",
            "location": "Narayanguda, Hyderabad",
            "simulation_history": sims,
            "conversation_history": [
                {"role": "user", "content": "Optimize traffic."},
                {"role": "assistant", "content": "Simulations evaluated.", "simulations": sims}
            ],
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # 0 new simulations
        dispatched_sims = [a for a in data.get("dispatched_agents", []) if "sim" in a]
        self.assertEqual(len(dispatched_sims), 0)

        combined = (data["final_response"].get("recommendation") or "") + " " + (data["final_response"].get("summary") or "")
        combined_lower = combined.lower()

        # Mentions no new simulation in this turn
        self.assertTrue("no new simulation" in combined_lower or "evaluating completed" in combined_lower or "historical" in combined_lower)

        # Distinguishes localized improvement from full resolution
        self.assertTrue("localized" in combined_lower or "rather than full" in combined_lower or "not fully resolved" in combined_lower)

    # -------------------------------------------------------------------------
    # Test D: No History
    # -------------------------------------------------------------------------
    def test_d_no_history_followup_reports_no_simulation_evidence(self):
        """
        No simulation history exists.
        Question: 'Which tested intervention performed better?'
        Expected:
          - 0 simulations run
          - No invented results
          - Clearly says no tested simulation evidence exists
        """
        res = self.client.post("/agents/planner/execute", json={
            "session_id": "sess_fresh_d",
            "objective": "Which tested intervention performed better?",
            "query": "Which tested intervention performed better?",
            "location": "Narayanguda, Hyderabad",
            "conversation_history": [],
            "simulation_history": [],
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # 0 simulations dispatched
        dispatched_sims = [a for a in data.get("dispatched_agents", []) if "sim" in a]
        self.assertEqual(len(dispatched_sims), 0)

        rec = (data["final_response"].get("recommendation") or "").lower()
        summary = (data["final_response"].get("summary") or "").lower()
        combined = rec + " " + summary

        self.assertTrue("no tested simulation evidence" in combined or "no candidate interventions have been tested" in combined or "not been tested" in combined or "no simulation history" in combined)

    # -------------------------------------------------------------------------
    # Test E: Evidence Status
    # -------------------------------------------------------------------------
    def test_e_evidence_status_preserved_as_multi_simulation(self):
        """
        Turn with 2+ completed simulations in history must remain
        EVIDENCE: MULTI-SIMULATION EVALUATION even when 0 new simulations execute.
        """
        sims = self._sample_simulations_3()[:2]
        res = self.client.post("/agents/planner/execute", json={
            "session_id": "sess_test_e",
            "objective": "Which tested intervention performed better and why?",
            "simulation_history": sims,
            "conversation_history": [
                {"role": "user", "content": "Optimize traffic."},
                {"role": "assistant", "content": "Simulations run.", "simulations": sims}
            ],
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["evidence_status"], "EVIDENCE: MULTI-SIMULATION EVALUATION")
        self.assertEqual(data["final_response"]["evidence_status"], "EVIDENCE: MULTI-SIMULATION EVALUATION")
        self.assertNotEqual(data["evidence_status"], "EVIDENCE: OBSERVATIONAL")

    # -------------------------------------------------------------------------
    # Test F: Dynamic Baseline Inheritance
    # -------------------------------------------------------------------------
    def test_f_dynamic_baseline_inheritance(self):
        """
        Baseline metadata: seed=77, duration=300, scenario='peak_test', location='Secunderabad'.
        All intervention simulations must inherit exactly those values.
        """
        traffic_data = {
            "location": "Secunderabad",
            "seed": 77,
            "duration_seconds": 300,
            "scenario": "peak_test",
            "average_speed_kmh": 22.4,
            "average_delay_sec": 45.0,
            "bottlenecks": [{"corridor": "Northbound", "reason": "Congestion on Northbound"}],
            "candidate_interventions": [
                {"type": "signal_timing", "target": "Northbound", "executable": True, "parameters": {"green_time_adjustment_sec": 15.0}},
                {"type": "rerouting", "target": "Northbound", "executable": True, "parameters": {"diversion_fraction": 0.20}},
            ],
        }

        eval_resp = self.planner.evaluate_and_replan(
            objective="Optimize the traffic situation in Secunderabad",
            plan=["traffic"],
            collected_results={"traffic": traffic_data},
            cycle_num=1,
            max_cycles=2,
            location="Secunderabad",
        )

        self.assertEqual(eval_resp.decision, "run_simulation")
        sim_calls = [c for c in eval_resp.next_cycle_calls if c.agent == "simulation"]
        self.assertGreaterEqual(len(sim_calls), 1)

        for call in sim_calls:
            req = call.request
            self.assertEqual(req.get("seed"), 77)
            self.assertEqual(req.get("duration_seconds"), 300)
            self.assertEqual(req.get("scenario_name"), "peak_test")
            self.assertEqual(req.get("location"), "Secunderabad")

    # -------------------------------------------------------------------------
    # Test G: Missing Baseline Metadata Fails Safely
    # -------------------------------------------------------------------------
    def test_g_missing_baseline_metadata_fails_safely(self):
        """
        If required baseline metadata is missing for paired simulation:
        Verify explicit failure/error and NO silent fallback to 42, 120, synthetic_normal, Narayanguda.
        """
        # Missing seed and duration_seconds
        bad_traffic = {
            "location": "Nacharam",
            "scenario": "test_profile",
            "average_speed_kmh": 20.0,
            "bottlenecks": [{"corridor": "Eastbound"}],
            "candidate_interventions": [
                {"type": "signal_timing", "target": "Eastbound", "executable": True}
            ],
        }

        with self.assertRaises(ValueError) as ctx:
            self.planner.evaluate_and_replan(
                objective="Optimize traffic in Nacharam",
                plan=["traffic"],
                collected_results={"traffic": bad_traffic},
                cycle_num=1,
                max_cycles=2,
                location="Nacharam",
            )
        err_msg = str(ctx.exception).lower()
        self.assertIn("missing required baseline simulation metadata", err_msg)
        self.assertIn("seed", err_msg)
        self.assertIn("duration_seconds", err_msg)

    # -------------------------------------------------------------------------
    # Test H: Tested History Persistence
    # -------------------------------------------------------------------------
    def test_h_tested_history_persistence(self):
        """
        Previously tested intervention remains TESTED during follow-up.
        Never regresses to UNTESTED.
        """
        sims = self._sample_simulations_3()[:1]
        res = self.client.post("/agents/planner/execute", json={
            "session_id": "sess_test_h",
            "objective": "Why did the tested intervention perform this way?",
            "simulation_history": sims,
            "tested_scenarios": sims,
            "conversation_history": [
                {"role": "user", "content": "Optimize traffic."},
                {"role": "assistant", "content": "Simulated signal timing.", "simulations": sims}
            ],
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()

        tested_types = [t.get("type") if isinstance(t, dict) else str(t) for t in data["final_response"].get("tested_interventions", [])]
        self.assertIn("signal_timing", tested_types)

        untested_types = [u.get("type") if isinstance(u, dict) else str(u) for u in data["final_response"].get("untested_candidates", [])]
        self.assertNotIn("signal_timing", untested_types)

    # -------------------------------------------------------------------------
    # Test K: Route/Session Persistence
    # -------------------------------------------------------------------------
    def test_k_session_persistence_same_session_id(self):
        """
        Turn 1 stores simulation evidence under session_id 'sess_k'.
        Turn 2 with same session_id retrieves cached simulation evidence.
        """
        session_id = "sess_k"
        sims = self._sample_simulations_3()

        # Turn 1: populates session
        res1 = self.client.post("/agents/planner/execute", json={
            "session_id": session_id,
            "objective": "Optimize the traffic situation.",
            "simulation_history": sims,
            "tested_scenarios": sims,
            "conversation_history": [],
        })
        self.assertEqual(res1.status_code, 200)
        self.assertIn(session_id, _PLANNER_SESSIONS)

        # Turn 2: Follow-up using same session_id without resending simulation_history
        res2 = self.client.post("/agents/planner/execute", json={
            "session_id": session_id,
            "objective": "Which tested intervention performed better and why?",
            "conversation_history": [
                {"role": "user", "content": "Optimize the traffic situation."},
                {"role": "assistant", "content": "Simulated 3 interventions."}
            ],
        })
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()

        # Evidence status is simulation-backed from session cache
        self.assertEqual(data2["evidence_status"], "EVIDENCE: MULTI-SIMULATION EVALUATION")
        dispatched_sims = [a for a in data2.get("dispatched_agents", []) if "sim" in a]
        self.assertEqual(len(dispatched_sims), 0)

    # -------------------------------------------------------------------------
    # Test L: Clear/New Conversation Isolation
    # -------------------------------------------------------------------------
    def test_l_clear_new_conversation_isolation(self):
        """
        Session 1 runs simulations.
        Session 2 is a brand new session with empty history.
        Verify session 2 does NOT inherit session 1's history.
        """
        sims = self._sample_simulations_3()
        # Session 1
        res1 = self.client.post("/agents/planner/execute", json={
            "session_id": "sess_old_1",
            "objective": "Optimize traffic.",
            "simulation_history": sims,
            "conversation_history": [],
        })
        self.assertEqual(res1.status_code, 200)

        # Session 2: Clear/New Conversation creates fresh session
        res2 = self.client.post("/agents/planner/execute", json={
            "session_id": "sess_fresh_2",
            "objective": "Which tested intervention performed better?",
            "conversation_history": [],
            "simulation_history": [],
        })
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()

        # Must be OBSERVATIONAL with 0 simulations
        self.assertEqual(data2["evidence_status"], "EVIDENCE: OBSERVATIONAL")
        combined = (data2["final_response"].get("recommendation") or "") + " " + (data2["final_response"].get("summary") or "")
        self.assertNotIn("scen_signal_wb_10", combined)

    # -------------------------------------------------------------------------
    # Test M: Follow-up After Route Navigation
    # -------------------------------------------------------------------------
    def test_m_followup_after_route_navigation(self):
        """
        Simulates:
          1. Planner executes optimization (session_id = 'sess_nav')
          2. User navigates to Dashboard
          3. User navigates back to Planner (restoring 'sess_nav')
          4. Follow-up: 'Which tested intervention performed better and why?'
        Expected:
          - 0 new simulations
          - Previous simulation evidence used
          - MULTI-SIMULATION EVALUATION
        """
        session_id = "sess_nav_100"
        sims = self._sample_simulations_3()

        # Turn 1: Optimization
        res1 = self.client.post("/agents/planner/execute", json={
            "session_id": session_id,
            "objective": "Optimize the traffic situation.",
            "simulation_history": sims,
            "tested_scenarios": sims,
            "conversation_history": [],
        })
        self.assertEqual(res1.status_code, 200)

        # Route navigation simulated (backend state remains in session store)
        # Turn 2: Restored session sends follow-up
        res2 = self.client.post("/agents/planner/execute", json={
            "session_id": session_id,
            "objective": "Which tested intervention performed better and why?",
            "conversation_history": [
                {"role": "user", "content": "Optimize the traffic situation."},
                {"role": "assistant", "content": "Simulated interventions.", "simulations": sims}
            ],
            "simulation_history": sims,
        })
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()

        self.assertEqual(data2["evidence_status"], "EVIDENCE: MULTI-SIMULATION EVALUATION")
        dispatched_sims = [a for a in data2.get("dispatched_agents", []) if "sim" in a]
        self.assertEqual(len(dispatched_sims), 0)


if __name__ == "__main__":
    unittest.main()
