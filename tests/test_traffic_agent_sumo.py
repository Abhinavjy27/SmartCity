"""
Unit and Integration Tests for Eclipse SUMO Traffic Agent.
Verifies real headless SUMO microsimulation, TraCI connectivity, deterministic synthetic demand,
per-vehicle lifecycle ledger, accurate wait and delay calculations, and zero fabricated metrics.
"""

import os
import unittest
from fastapi.testclient import TestClient

from backend.agents.traffic_agent.main import app
from backend.agents.traffic_agent.demand_generator import SyntheticDemandGenerator, SCENARIO_DEMAND_PROFILES
from backend.agents.traffic_agent.metrics import SumoMetricsCollector, VehicleRecord
from backend.agents.traffic_agent.schemas import TrafficAnalyzeRequest, TrafficEvidenceResponse
from backend.agents.traffic_agent.service import get_traffic_service
from backend.agents.traffic_agent.sumo_runner import SumoRunner, SumoExecutionError


class TestTrafficAgentSUMO(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.service = get_traffic_service()

    def test_1_traffic_agent_imports_correctly(self):
        """1. Traffic Agent modules, services, and runners import without errors."""
        self.assertIsNotNone(app)
        self.assertIsNotNone(self.service)
        self.assertIsNotNone(SumoRunner)
        self.assertIsNotNone(SyntheticDemandGenerator)
        self.assertIsNotNone(SumoMetricsCollector)

    def test_2_synthetic_demand_generation_is_deterministic(self):
        """2. Synthetic demand generation is strictly deterministic for identical seeds."""
        generator = SyntheticDemandGenerator()

        # Generate twice with seed 42
        f1 = generator.generate_route_file("synthetic_normal", duration_seconds=60, seed=42)
        with open(f1, "r", encoding="utf-8") as fp:
            content_1 = fp.read()

        # Clean and regenerate
        os.remove(f1)
        f2 = generator.generate_route_file("synthetic_normal", duration_seconds=60, seed=42)
        with open(f2, "r", encoding="utf-8") as fp:
            content_2 = fp.read()

        self.assertEqual(content_1, content_2, "Identical seed must yield identical route XML content")

        # Clean and generate with seed 99 (must differ)
        f3 = generator.generate_route_file("synthetic_normal", duration_seconds=60, seed=99)
        with open(f3, "r", encoding="utf-8") as fp:
            content_3 = fp.read()

        self.assertNotEqual(content_1, content_3, "Different seeds must produce different departure sequences")

    def test_3_synthetic_normal_accepted(self):
        """3. 'synthetic_normal' scenario is accepted and executed by Traffic Agent."""
        res = self.client.get("/api/v1/traffic/kpis?scenario=synthetic_normal&duration_seconds=30&seed=42")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["scenario"], "synthetic_normal")
        self.assertEqual(data["status"], "completed")
        self.assertIn("metrics", data)
        self.assertGreater(data["metrics"]["total_vehicles"], 0)

    def test_4_synthetic_peak_northbound_accepted(self):
        """4. 'synthetic_peak_northbound' scenario is accepted and executed."""
        res = self.client.get("/api/v1/traffic/kpis?scenario=synthetic_peak_northbound&duration_seconds=30&seed=42")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["scenario"], "synthetic_peak_northbound")
        self.assertEqual(data["status"], "completed")
        self.assertIn("metrics", data)
        self.assertGreater(data["metrics"]["total_vehicles"], 0)

    def test_5_invalid_scenarios_rejected_cleanly(self):
        """5. Invalid/unknown scenarios are rejected with clear HTTP 400 errors."""
        res = self.client.get("/api/v1/traffic/kpis?scenario=invalid_unknown_scenario")
        self.assertEqual(res.status_code, 400)
        err = res.json()
        self.assertIn("INVALID_SCENARIO", err["detail"]["error"])
        self.assertIn("Supported scenarios", err["detail"]["message"])

        # Also via POST /analyze
        res_post = self.client.post("/api/v1/traffic/analyze", json={"scenario": "nonexistent_mode"})
        self.assertEqual(res_post.status_code, 400)

    def test_6_planner_request_converted_into_traffic_agent_request(self):
        """6. Planner agent request payload is cleanly received and executed by Traffic Agent."""
        planner_request_payload = {
            "location": "Narayanguda, Hyderabad",
            "scenario": "synthetic_peak_northbound",
            "purpose": "baseline_traffic_analysis",
            "duration_seconds": 30,
            "seed": 42,
        }
        res = self.client.post("/api/v1/traffic/analyze", json=planner_request_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["location"], "Narayanguda, Hyderabad")
        self.assertEqual(data["scenario"], "synthetic_peak_northbound")
        self.assertEqual(data["status"], "completed")

    def test_7_sumo_baseline_actually_runs_using_existing_network(self):
        """7. SUMO baseline actually executes headless against narayanguda_network.net.xml."""
        net_path = self.service.network_path
        self.assertTrue(os.path.isfile(net_path), f"Narayanguda network must exist at {net_path}")

        gen = SyntheticDemandGenerator()
        rf = gen.generate_route_file("synthetic_normal", duration_seconds=25, seed=101)
        runner = SumoRunner()
        metrics, corridors = runner.run_simulation(net_path, rf, duration_seconds=25)

        self.assertIsInstance(metrics.active_vehicles, int)
        self.assertGreater(metrics.total_vehicles, 0)
        self.assertIsNotNone(metrics.average_speed_kmh)
        self.assertGreater(metrics.average_speed_kmh, 0.0)
        self.assertEqual(len(corridors), 4)

    def test_8_returned_metrics_come_from_actual_sumo_execution(self):
        """8. Returned metrics reflect real TraCI telemetry (speeds, delays, waiting times)."""
        res = self.client.get("/api/v1/traffic/kpis?duration_seconds=30&seed=42")
        self.assertEqual(res.status_code, 200)
        metrics = res.json()["metrics"]

        # Empirical non-zero vehicle observations
        self.assertGreater(metrics["active_vehicles"], 0)
        self.assertGreater(metrics["total_vehicles"], 0)
        self.assertIsNotNone(metrics["average_speed_kmh"])
        self.assertGreater(metrics["average_speed_kmh"], 0.0)
        self.assertLessEqual(metrics["average_speed_kmh"], 65.0)  # within city speed bounds
        self.assertGreaterEqual(metrics["congestion_index"], 0.0)
        self.assertLessEqual(metrics["congestion_index"], 1.0)
        self.assertGreaterEqual(metrics["average_delay_sec"], 0.0)
        self.assertGreaterEqual(metrics["average_waiting_time_sec"], 0.0)

    def test_9_output_contract_source_specification(self):
        """9. Output conforms to exact contract: source.type=simulation, engine=SUMO, synthetic=true."""
        res = self.client.get("/api/v1/traffic/kpis?duration_seconds=30&seed=42")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("source", data)
        src = data["source"]
        self.assertEqual(src["type"], "simulation")
        self.assertEqual(src["engine"], "SUMO")
        self.assertIs(src["synthetic"], True)
        self.assertIn("disclaimer", src)
        self.assertIn("Synthetic traffic demand", src["disclaimer"])

    def test_10_no_fake_or_hardcoded_traffic_metrics(self):
        """10. Metrics dynamically respond to simulation demand physics, proving no hardcoded constants."""
        ev_norm = self.service.run_baseline_simulation(
            scenario="synthetic_normal",
            duration_seconds=40,
            seed=42,
            force_fresh=True,
        )
        ev_peak = self.service.run_baseline_simulation(
            scenario="synthetic_peak_northbound",
            duration_seconds=40,
            seed=42,
            force_fresh=True,
        )

        # In peak northbound, total injected vehicles is higher and congestion is higher
        self.assertGreater(
            ev_peak.metrics.total_vehicles,
            ev_norm.metrics.total_vehicles,
            "Peak scenario must inject more vehicles than normal scenario",
        )
        self.assertGreater(
            ev_peak.metrics.congestion_index,
            ev_norm.metrics.congestion_index,
            "Peak northbound scenario must show higher congestion than balanced normal",
        )
        self.assertNotEqual(
            ev_norm.metrics.average_speed_kmh,
            ev_peak.metrics.average_speed_kmh,
            "Speeds must reflect microscopic physics rather than static hardcoded numbers",
        )

    def test_11_waiting_time_accumulated_across_waiting_steps_not_mean_counters(self):
        """11. Waiting time accumulates true duration (step length) and is not mean of running counters."""
        collector = SumoMetricsCollector(step_duration_sec=1.0)
        # Directly populate vehicle ledger simulating a vehicle that stops for 10s, moves, then stops for 5s
        v1 = VehicleRecord(vid="veh_nb_1", accumulated_waiting_time=15.0, final_time_loss=18.5)
        v2 = VehicleRecord(vid="veh_nb_2", accumulated_waiting_time=5.0, final_time_loss=7.2)
        collector.vehicles = {"veh_nb_1": v1, "veh_nb_2": v2}

        summary = collector.calculate_summary()
        # Average waiting time must be (15 + 5) / 2 = 10.0s
        self.assertEqual(summary.average_waiting_time_sec, 10.0)

    def test_12_waiting_time_survives_vehicle_arrival(self):
        """12. Vehicles that arrive and exit the network preserve their accumulated waiting time in ledger."""
        collector = SumoMetricsCollector(step_duration_sec=1.0)
        # Vehicle arrives before simulation end
        v_arrived = VehicleRecord(vid="veh_arrived", accumulated_waiting_time=25.0, final_time_loss=30.0, arrived=True)
        v_active = VehicleRecord(vid="veh_active", accumulated_waiting_time=10.0, final_time_loss=12.0, arrived=False)
        collector.vehicles = {"veh_arrived": v_arrived, "veh_active": v_active}

        summary = collector.calculate_summary()
        self.assertEqual(summary.throughput, 1)
        self.assertEqual(summary.total_vehicles, 2)
        self.assertEqual(summary.average_waiting_time_sec, 17.5)  # (25 + 10) / 2
        self.assertEqual(summary.average_delay_sec, 21.0)  # (30 + 12) / 2

    def test_13_delay_uses_final_time_loss_not_repeated_snapshots(self):
        """13. Delay uses final terminal time loss per vehicle, avoiding running snapshot integration."""
        collector = SumoMetricsCollector(step_duration_sec=1.0)
        # Vehicle 1 experienced total delay 20s, Vehicle 2 experienced total delay 10s
        collector.vehicles = {
            "v1": VehicleRecord(vid="v1", final_time_loss=20.0),
            "v2": VehicleRecord(vid="v2", final_time_loss=10.0),
        }
        summary = collector.calculate_summary()
        self.assertEqual(summary.average_delay_sec, 15.0)

    def test_14_total_vehicles_does_not_equal_simulation_step_count(self):
        """14. Total vehicles strictly represents unique vehicles, never simulation step count."""
        collector = SumoMetricsCollector(step_duration_sec=1.0)
        # Simulate 120 steps with 0 vehicles
        collector.active_vehicle_counts = [0] * 120
        collector.step_count = 120

        summary = collector.calculate_summary()
        self.assertEqual(summary.total_vehicles, 0, "Zero vehicles must produce total_vehicles = 0, NOT 120 steps")

    def test_15_zero_vehicle_simulation_returns_none_not_fabricated_free_flow(self):
        """15. Empty/zero-vehicle simulation returns None for speed and congestion, never fabricating 50 km/h or 0%."""
        collector = SumoMetricsCollector(free_flow_speed_kmh=50.0)
        summary = collector.calculate_summary()

        self.assertIsNone(summary.average_speed_kmh, "Speed must be None when 0 vehicles observed")
        self.assertIsNone(summary.congestion_index, "Congestion must be None when 0 vehicles observed")
        self.assertIsNone(summary.average_waiting_time_sec, "Waiting time must be None when 0 vehicles observed")
        self.assertIsNone(summary.average_delay_sec, "Delay must be None when 0 vehicles observed")
        self.assertEqual(summary.total_vehicles, 0)

    def test_16_empty_corridor_returns_no_data(self):
        """16. Empty corridor with zero observations returns NO_DATA and avg_speed=None, not 35 km/h or SMOOTH."""
        collector = SumoMetricsCollector(free_flow_speed_kmh=50.0)
        # Simulate speeds only on northbound corridor
        collector.corridor_speeds["northbound"] = [38.0, 42.0]
        # Southbound, eastbound, westbound remain empty

        corridors = collector.get_corridor_summaries()
        nb = next(c for c in corridors if c["id"] == "COR_NB")
        sb = next(c for c in corridors if c["id"] == "COR_SB")

        self.assertEqual(nb["status"], "SMOOTH")
        self.assertEqual(nb["avg_speed"], 40.0)

        self.assertEqual(sb["status"], "NO_DATA", "Empty corridor must be labeled NO_DATA")
        self.assertIsNone(sb["avg_speed"], "Empty corridor must have avg_speed = None")
        self.assertIsNone(sb["value"], "Empty corridor must have congestion value = None")
        self.assertEqual(sb["color"], "#6b7280", "Empty corridor must have neutral gray color")

    def test_17_traffic_analysis_contains_structured_observations(self):
        """17. Traffic response contains structured empirical observations container."""
        res = self.client.get("/api/v1/traffic/kpis?scenario=synthetic_normal&duration_seconds=30&seed=42")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("observations", data)
        obs = data["observations"]
        self.assertIsNotNone(obs)
        self.assertIn("network_average_speed_kmh", obs)
        self.assertIn("average_delay_sec", obs)
        self.assertIn("average_waiting_time_sec", obs)
        self.assertIn("congestion_index", obs)
        self.assertIn("total_vehicles", obs)
        self.assertIn("throughput", obs)
        self.assertIn("max_halting_vehicles", obs)
        self.assertIn("teleported_vehicles", obs)
        self.assertGreater(obs["total_vehicles"], 0)
        self.assertGreater(obs["network_average_speed_kmh"], 0.0)

    def test_18_bottleneck_detection_from_empirical_observations(self):
        """18. Bottleneck detection extracts diagnosed bottleneck from empirical corridor observations."""
        res = self.client.get("/api/v1/traffic/kpis?scenario=synthetic_normal&duration_seconds=60&seed=42")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("bottlenecks", data)
        bottlenecks = data["bottlenecks"]
        self.assertGreaterEqual(len(bottlenecks), 1)

        b0 = bottlenecks[0]
        self.assertIn("corridor", b0)
        self.assertIn("reason", b0)
        self.assertIn("evidence", b0)
        self.assertIn("severity", b0)
        self.assertIsNotNone(b0["evidence"]["speed_kmh"])
        self.assertIsNotNone(b0["evidence"]["network_average_speed_kmh"])

    def test_19_dynamic_bottleneck_detection_changes_with_demand(self):
        """19. Bottleneck detection is dynamic and evidence-based (not hardcoded to Westbound)."""
        # Under peak southbound demand, Southbound corridor experiences highest stress
        res_sb = self.client.get("/api/v1/traffic/kpis?scenario=synthetic_peak_southbound&duration_seconds=60&seed=42")
        self.assertEqual(res_sb.status_code, 200)
        data_sb = res_sb.json()

        bottlenecks_sb = data_sb.get("bottlenecks", [])
        self.assertGreaterEqual(len(bottlenecks_sb), 1)
        # Verify that bottleneck corridor is dynamically derived from evidence
        diagnosed_corridors = [b["corridor"] for b in bottlenecks_sb]
        corridor_speeds = {c["name"]: c["avg_speed"] for c in data_sb["corridors"] if c["avg_speed"] is not None}
        slowest_corridor = min(corridor_speeds, key=corridor_speeds.get)
        self.assertIn(slowest_corridor, diagnosed_corridors)

    def test_20_candidate_interventions_generated_across_categories(self):
        """20. Candidate interventions are generated across required categories (signal_timing, rerouting, lane_use, incident_response)."""
        res = self.client.get("/api/v1/traffic/kpis?scenario=synthetic_normal&duration_seconds=30&seed=42")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("candidate_interventions", data)
        cands = data["candidate_interventions"]
        self.assertGreaterEqual(len(cands), 4)

        categories = {c["type"] for c in cands}
        self.assertIn("signal_timing", categories)
        self.assertIn("rerouting", categories)
        self.assertIn("lane_use", categories)
        self.assertIn("incident_response", categories)

    def test_21_executable_vs_non_executable_distinction(self):
        """21. Interventions strictly distinguish executable (signal_timing) from candidate-only capabilities with rationale."""
        res = self.client.get("/api/v1/traffic/kpis?scenario=synthetic_normal&duration_seconds=30&seed=42")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        cands = data["candidate_interventions"]
        signal_cands = [c for c in cands if c["type"] == "signal_timing"]
        reroute_cands = [c for c in cands if c["type"] == "rerouting"]
        lane_cands = [c for c in cands if c["type"] == "lane_use"]
        incident_cands = [c for c in cands if c["type"] == "incident_response"]

        # Signal timing and rerouting are executable via TraCI
        self.assertTrue(all(c["executable"] is True for c in signal_cands))
        self.assertTrue(all(c["executable"] is True for c in reroute_cands))
        self.assertTrue(all(c["execution_notes"] is not None for c in reroute_cands))

        # Lane use and incident response remain candidate-only
        self.assertTrue(all(c["executable"] is False for c in lane_cands))
        self.assertTrue(all(c["execution_notes"] is not None for c in lane_cands))

        self.assertTrue(all(c["executable"] is False for c in incident_cands))
        self.assertTrue(all(c["execution_notes"] is not None for c in incident_cands))

    def test_22_potential_trade_offs_generated(self):
        """22. Pre-simulation trade-off analysis generates potential benefits and corridor externalities."""
        res = self.client.get("/api/v1/traffic/kpis?scenario=synthetic_normal&duration_seconds=30&seed=42")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("trade_offs", data)
        trade_offs = data["trade_offs"]
        self.assertGreaterEqual(len(trade_offs), 1)

        for to in trade_offs:
            self.assertIn("intervention", to)
            self.assertIn("target", to)
            self.assertIn("potential_benefit", to)
            self.assertIn("potential_tradeoff", to)
            self.assertIn("affected_corridors", to)

    def test_23_signal_optimization_defensive_validation(self):
        """23. POST /api/v1/traffic/optimize-signal performs defensive parameter validation."""
        # Valid request
        res_valid = self.client.post("/api/v1/traffic/optimize-signal", json={
            "intersection_id": "cluster_308783170_3158879059_3217073805_4433969588",
            "target_corridor": "Westbound",
            "green_time_adjustment_sec": 15.0,
            "current_cycle_sec": 120,
        })
        self.assertEqual(res_valid.status_code, 200)
        data = res_valid.json()
        self.assertEqual(data["status"], "CANDIDATES_GENERATED")
        self.assertEqual(data["validation_status"], "VALID")
        self.assertGreaterEqual(len(data["candidates"]), 3)

        # Invalid green adjustment (out of safe range [1.0, 45.0])
        res_invalid_adj = self.client.post("/api/v1/traffic/optimize-signal", json={
            "green_time_adjustment_sec": 90.0,
        })
        self.assertEqual(res_invalid_adj.status_code, 400)
        self.assertIn("INVALID_SIGNAL_PARAMETERS", res_invalid_adj.json()["detail"]["error"])

        # Invalid cycle duration (out of safe range [30, 240])
        res_invalid_cyc = self.client.post("/api/v1/traffic/optimize-signal", json={
            "current_cycle_sec": 10,
        })
        self.assertEqual(res_invalid_cyc.status_code, 400)

    def test_24_edge_case_empty_or_no_vehicles_preserves_none(self):
        """24. Edge case with zero vehicles returns empty bottlenecks and does not fabricate measurements."""
        collector = SumoMetricsCollector(free_flow_speed_kmh=50.0)
        summary = collector.calculate_summary()
        corridors = collector.get_corridor_summaries()

        obs, bottlenecks, candidates, trade_offs = self.service.analyze_traffic_conditions(summary, corridors)
        self.assertIsNone(obs.network_average_speed_kmh)
        self.assertEqual(obs.total_vehicles, 0)
        self.assertEqual(len(bottlenecks), 0, "No bottlenecks should be fabricated when 0 vehicles observed")
        self.assertEqual(len(candidates), 0, "No candidates should be fabricated when 0 vehicles observed")
        self.assertEqual(len(trade_offs), 0)


if __name__ == "__main__":
    unittest.main()
