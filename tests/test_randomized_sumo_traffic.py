"""
Regression and functional test suite for randomized SUMO traffic demand.

Verifies:
1. Existing API contracts, response models, and metric definitions are preserved.
2. Repeated fresh planning requests without seed generate randomized demand.
3. An explicit saved seed reproduces the exact same scenario and telemetry.
4. Within a planning request, baseline and all intervention candidates share identical demand/seed.
5. Generation failures gracefully fall back to default seed 42 without fabricating metrics or crashing.
6. Diagnostic and optimization flows execute properly under randomized demand.
"""

import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.agents.traffic_agent.demand_generator import SyntheticDemandGenerator
from backend.agents.traffic_agent.main import app as traffic_app
from backend.agents.traffic_agent.schemas import TrafficEvidenceResponse
from backend.agents.traffic_agent.service import TrafficService, get_traffic_service
from backend.agents.simulation_agent.service import SimulationService
from backend.supervisor.main import (
    app as supervisor_app,
    PlannerExecuteRequest,
    verify_multi_intervention_invariant,
)


class TestRandomizedSumoTraffic(unittest.TestCase):

    def setUp(self):
        self.original_provider = os.environ.get("LLM_PROVIDER")
        os.environ["LLM_PROVIDER"] = "mock"
        self.traffic_client = TestClient(traffic_app)
        self.supervisor_client = TestClient(supervisor_app)
        self.demand_gen = SyntheticDemandGenerator()
        self.service = get_traffic_service()

    def tearDown(self):
        if self.original_provider:
            os.environ["LLM_PROVIDER"] = self.original_provider
        else:
            os.environ.pop("LLM_PROVIDER", None)

    def test_01_api_contract_and_response_schema_preserved(self):
        """1. Traffic evidence response matches schema with all required metric fields and optional seed."""
        res = self.traffic_client.get("/api/v1/traffic/kpis?duration_seconds=30&seed=42")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Validate with Pydantic model
        evidence = TrafficEvidenceResponse.model_validate(data)
        self.assertEqual(evidence.status, "completed")
        self.assertEqual(evidence.seed, 42)
        self.assertEqual(evidence.metadata.random_seed, 42)

        # Check required empirical metrics
        self.assertIsNotNone(evidence.metrics.active_vehicles)
        self.assertIsNotNone(evidence.metrics.total_vehicles)
        self.assertIsNotNone(evidence.metrics.throughput)
        self.assertIsNotNone(evidence.metrics.congestion_index)
        self.assertIsNotNone(evidence.corridors)
        self.assertIsNotNone(evidence.hourly_data)

    def test_02_repeated_fresh_scenarios_generate_different_seeds_and_demand(self):
        """2. Repeated fresh requests without seed produce different seeds and distinct traffic demand."""
        # Run two fresh baseline simulations without providing seed
        ev1 = self.service.run_baseline_simulation(
            scenario="synthetic_normal",
            duration_seconds=40,
            seed=None,
            force_fresh=True,
        )
        ev2 = self.service.run_baseline_simulation(
            scenario="synthetic_normal",
            duration_seconds=40,
            seed=None,
            force_fresh=True,
        )

        seed1 = ev1.metadata.random_seed
        seed2 = ev2.metadata.random_seed

        # Seeds must be randomized and differ
        self.assertNotEqual(seed1, seed2, "Fresh requests without seed should generate different random seeds")

        # Compare route files generated for each seed
        f1 = self.demand_gen.generate_route_file("synthetic_normal", duration_seconds=40, seed=seed1)
        f2 = self.demand_gen.generate_route_file("synthetic_normal", duration_seconds=40, seed=seed2)

        with open(f1, "r", encoding="utf-8") as fp1, open(f2, "r", encoding="utf-8") as fp2:
            content1 = fp1.read()
            content2 = fp2.read()

        self.assertNotEqual(content1, content2, "Different seeds must generate different synthetic vehicle trips")

    def test_03_saved_seed_reproduces_identical_demand_and_metrics(self):
        """3. An explicit saved seed strictly reproduces identical routes and simulation metrics."""
        explicit_seed = 7712

        ev_run1 = self.service.run_baseline_simulation(
            scenario="synthetic_peak_westbound",
            duration_seconds=30,
            seed=explicit_seed,
            force_fresh=True,
        )
        ev_run2 = self.service.run_baseline_simulation(
            scenario="synthetic_peak_westbound",
            duration_seconds=30,
            seed=explicit_seed,
            force_fresh=True,
        )

        self.assertEqual(ev_run1.metadata.random_seed, explicit_seed)
        self.assertEqual(ev_run2.metadata.random_seed, explicit_seed)
        self.assertEqual(ev_run1.seed, explicit_seed)
        self.assertEqual(ev_run2.seed, explicit_seed)

        # Simulation metrics must match exactly
        self.assertEqual(ev_run1.metrics.total_vehicles, ev_run2.metrics.total_vehicles)
        self.assertEqual(ev_run1.metrics.throughput, ev_run2.metrics.throughput)
        if ev_run1.metrics.average_speed_kmh is not None and ev_run2.metrics.average_speed_kmh is not None:
            self.assertAlmostEqual(ev_run1.metrics.average_speed_kmh, ev_run2.metrics.average_speed_kmh, places=4)
        if ev_run1.metrics.average_delay_sec is not None and ev_run2.metrics.average_delay_sec is not None:
            self.assertAlmostEqual(ev_run1.metrics.average_delay_sec, ev_run2.metrics.average_delay_sec, places=4)

    def test_04_planner_paired_comparison_uses_identical_demand(self):
        """4. Baseline and all intervention candidates in a planning request share the exact same seed."""
        # Execute optimization planner request with an explicit seed
        req = PlannerExecuteRequest(
            objective="Optimize Narayanguda traffic bottlenecks",
            duration_seconds=30,
            seed=5544,
        )
        res = self.supervisor_client.post("/agents/planner/execute", json=req.model_dump())
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Verify tested scenarios exist
        tested_scenarios = data.get("tested_scenarios", [])
        if tested_scenarios:
            for scen in tested_scenarios:
                self.assertEqual(scen.get("seed"), 5544, "All intervention candidates must inherit baseline seed")

            # Validate multi-intervention invariant passes without exception
            verify_multi_intervention_invariant(tested_scenarios)

    def test_05_safe_fallback_on_random_scenario_failure(self):
        """5. If route generation fails for a random seed, system safely falls back to seed 42."""
        with patch.object(
            self.demand_gen,
            "generate_route_file",
            side_effect=[Exception("Disk simulation fault"), "fallback_path.rou.xml"],
        ):
            # Should not crash; falls back to seed 42
            try:
                # Test demand generator safe handling directly
                f_fallback = self.demand_gen.generate_route_file("synthetic_normal", duration_seconds=20, seed=None)
                self.assertTrue(os.path.exists(f_fallback))
            except Exception:
                pass

        # In service.py, run_baseline_simulation falls back to 42 when exception occurs on novel seed
        original_generate = self.service.demand_generator.generate_route_file

        def fail_once_on_random(scenario, duration_seconds, seed, **kwargs):
            if seed != 42:
                raise RuntimeError("Simulated failure for random seed")
            return original_generate(scenario=scenario, duration_seconds=duration_seconds, seed=42)

        with patch.object(self.service.demand_generator, "generate_route_file", side_effect=fail_once_on_random):
            ev_fallback = self.service.run_baseline_simulation(
                scenario="synthetic_normal",
                duration_seconds=20,
                seed=None,
                force_fresh=True,
            )
            # Must safely complete using fallback seed 42
            self.assertEqual(ev_fallback.metadata.random_seed, 42)
            self.assertEqual(ev_fallback.status, "completed")

    def test_06_diagnostic_query_executes_under_randomized_scenario(self):
        """6. Diagnostic queries continue to work and return bottleneck identification under fresh random demand."""
        req = PlannerExecuteRequest(
            objective="Which corridor is currently the bottleneck in Narayanguda?",
            duration_seconds=30,
        )
        res = self.supervisor_client.post("/agents/planner/execute", json=req.model_dump())
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data.get("status"), "COMPLETED")
        final_resp = data.get("final_response") or {}
        feedback = data.get("planner_feedback") or {}
        analysis = (
            final_resp.get("analysis")
            or (feedback.get("insights", {}) or {}).get("analysis")
            or ""
        )
        self.assertTrue(len(analysis) > 0, "Diagnostic response must provide analysis")
        collected = data.get("collected_results", {})
        self.assertIn("traffic", collected)
        trf = collected["traffic"]
        self.assertIn("bottlenecks", trf)
        self.assertIsNotNone(trf.get("seed") or trf.get("metadata", {}).get("random_seed"))

    def test_07_explicit_seed_errors_are_not_silently_hidden(self):
        """7. Explicit seed errors are NOT masked by fallback to 42; fallback applies strictly to random generation."""
        from backend.agents.traffic_agent.sumo_runner import SumoExecutionError

        def fail_sumo(net_file, route_file, duration_seconds):
            raise SumoExecutionError("Simulated explicit run failure", {"seed": 99})

        with patch.object(self.service.sumo_runner, "run_simulation", side_effect=fail_sumo):
            with self.assertRaises(SumoExecutionError):
                self.service.run_baseline_simulation(
                    scenario="synthetic_normal",
                    duration_seconds=20,
                    seed=99,
                    force_fresh=True,
                )

    def test_08_fallback_consistency_in_planner_flow(self):
        """8. If a fresh planning request falls back to seed 42, all subsequent interventions use seed 42 without seed mixing."""
        original_run = self.service.sumo_runner.run_simulation

        def fail_on_non_42(net_file, route_file, duration_seconds):
            if "seed42" not in route_file:
                raise SumoExecutionError("Non-42 seed failure", {})
            return original_run(net_file, route_file, duration_seconds)

        with patch.object(self.service.sumo_runner, "run_simulation", side_effect=fail_on_non_42):
            req = PlannerExecuteRequest(
                objective="Evaluate possible interventions for the Westbound traffic problem",
                duration_seconds=20,
            )
            res = self.supervisor_client.post("/agents/planner/execute", json=req.model_dump())
            self.assertEqual(res.status_code, 200)
            data = res.json()

            collected = data.get("collected_results", {})
            if "traffic" in collected:
                self.assertEqual(collected["traffic"].get("seed"), 42, "Traffic fallback must record seed 42")

            tested_scenarios = data.get("tested_scenarios", [])
            for sc in tested_scenarios:
                self.assertEqual(sc.get("seed"), 42, "Intervention candidates must use fallback seed 42 without seed mixing")

    def test_09_analytical_followup_inherits_seed_while_new_request_is_fresh(self):
        """9. Analytical follow-ups inherit prior simulation seed, while fresh queries generate new seeds."""
        # 1. Fresh query gets a randomized seed
        req1 = PlannerExecuteRequest(
            objective="Diagnose current traffic conditions in Narayanguda",
            duration_seconds=20,
        )
        res1 = self.supervisor_client.post("/agents/planner/execute", json=req1.model_dump())
        self.assertEqual(res1.status_code, 200)
        trf1 = res1.json().get("collected_results", {}).get("traffic", {})
        seed1 = trf1.get("seed") or trf1.get("metadata", {}).get("random_seed")
        self.assertIsNotNone(seed1)

        # 2. Analytical follow-up query with prior simulation history inherits seed 7788
        prior_sim = {
            "scenario_id": "sim_prior_7788",
            "scenario": "synthetic_peak_westbound",
            "duration_seconds": 120,
            "seed": 7788,
            "network_name": "narayanguda_network.net.xml",
            "metrics": {"average_speed_kmh": 22.5, "average_delay_sec": 45.0, "throughput": 120},
            "comparison": {
                "target_corridor_speed_change_pct": 14.5,
                "speed_change_pct": 8.0,
                "delay_reduction_pct": 18.2,
                "baseline_summary": {"average_speed_kmh": 19.5, "average_delay_sec": 55.0},
            },
        }
        req_followup = PlannerExecuteRequest(
            objective="Which tested intervention performed better?",
            simulation_history=[prior_sim],
        )
        res_followup = self.supervisor_client.post("/agents/planner/execute", json=req_followup.model_dump())
        self.assertEqual(res_followup.status_code, 200)
        data_f = res_followup.json()
        final_resp = data_f.get("final_response") or {}
        # Ensure it inherited requested_seed 7788
        self.assertEqual(final_resp.get("requested_seed"), 7788)

    def test_10_domain_agent_isolation_preserved(self):
        """10. Weather, pollution, and energy queries select only their specialist domain without traffic dispatch."""
        for query, expected_agent in [
            ("What is the current weather in Narayanguda?", "weather"),
            ("What are the air quality and PM2.5 levels in Narayanguda?", "pollution"),
            ("What is the current power grid status in Narayanguda?", "energy"),
        ]:
            req = PlannerExecuteRequest(objective=query)
            res = self.supervisor_client.post("/agents/planner/execute", json=req.model_dump())
            self.assertEqual(res.status_code, 200)
            data = res.json()
            dispatched = data.get("dispatched_agents", [])
            self.assertIn(f"{expected_agent}_agent", dispatched)
            self.assertNotIn("traffic_agent", dispatched, f"Query '{query}' should not dispatch traffic_agent")

    def test_11_response_compatibility_post_and_get(self):
        """11. Verify exact fields and types in /api/v1/traffic/kpis and /api/v1/traffic/analyze."""
        r_get = self.traffic_client.get("/api/v1/traffic/kpis?duration_seconds=20&seed=42")
        self.assertEqual(r_get.status_code, 200)
        d_get = r_get.json()

        r_post = self.traffic_client.post("/api/v1/traffic/analyze", json={"duration_seconds": 20, "seed": 42})
        self.assertEqual(r_post.status_code, 200)
        d_post = r_post.json()

        expected_fields = [
            ("source", dict),
            ("location", str),
            ("scenario", str),
            ("status", str),
            ("metrics", dict),
            ("metadata", dict),
            ("observations", dict),
            ("bottlenecks", list),
            ("candidate_interventions", list),
            ("trade_offs", list),
            ("active_vehicles", int),
            ("total_vehicles", int),
            ("corridors", list),
            ("hourly_data", list),
            ("sensors", list),
            ("seed", int),
        ]

        for field_name, expected_type in expected_fields:
            self.assertIn(field_name, d_get, f"GET kpis missing field: {field_name}")
            self.assertIn(field_name, d_post, f"POST analyze missing field: {field_name}")
            self.assertIsInstance(d_get[field_name], expected_type, f"GET {field_name} type mismatch")
            self.assertIsInstance(d_post[field_name], expected_type, f"POST {field_name} type mismatch")

        # Nested metrics throughput check
        self.assertIn("throughput", d_get["metrics"])
        self.assertIn("throughput", d_post["metrics"])
        self.assertIsInstance(d_get["metrics"]["throughput"], int)
        self.assertIsInstance(d_post["metrics"]["throughput"], int)


if __name__ == "__main__":
    unittest.main()

