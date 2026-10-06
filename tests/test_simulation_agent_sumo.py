"""
SUMO Simulation Agent Tests.
Verifies intervention schemas, real SUMO execution via TraCI, dynamic signal modification,
unaltered base network verification, and comparison metric calculation.
"""

import hashlib
import os
import unittest
from fastapi.testclient import TestClient

from backend.agents.simulation_agent.main import app
from backend.agents.simulation_agent.schemas import (
    InterventionPayload,
    InterventionType,
    SimulationScenarioRequest,
)
from backend.agents.simulation_agent.service import get_simulation_service


class TestSimulationAgentSUMO(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.service = get_simulation_service()
        self.net_file = self.service.network_path

    def _hash_file(self, filepath: str) -> str:
        with open(filepath, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    def test_1_health_check(self):
        """Simulation Agent responds to health endpoint."""
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["agent"], "Simulation Agent")
        self.assertEqual(data["status"], "ONLINE")
        self.assertTrue(data["sumo_available"])

    def test_2_backward_compatible_fields_supported(self):
        """Legacy fields duration_steps and signal_optimization are safely parsed."""
        req = SimulationScenarioRequest(
            scenario_name="synthetic_normal",
            target_location="Narayanguda, Hyderabad",
            duration_steps=60,
            signal_optimization=True,
        )
        self.assertEqual(req.duration_seconds, 60)
        self.assertEqual(req.location, "Narayanguda, Hyderabad")
        self.assertIsNotNone(req.intervention)
        self.assertEqual(req.intervention.type, InterventionType.SIGNAL_TIMING)

    def test_3_invalid_corridor_target_rejected(self):
        """Unmappable corridor targets raise structured 400 validation error."""
        res = self.client.post("/api/v1/simulation/run", json={
            "scenario_name": "synthetic_normal",
            "location": "Narayanguda, Hyderabad",
            "duration_seconds": 60,
            "intervention": {
                "type": "signal_timing",
                "target": "Nonexistent_Galaxy_Freeway",
                "parameters": {"green_time_adjustment_sec": 15.0},
            },
        })
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertIn("detail", data)
        self.assertEqual(data["detail"]["error"], "INVALID_SIMULATION_PARAMETERS")

    def test_4_real_sumo_intervention_preserves_base_network(self):
        """
        Runs real SUMO simulation with dynamic signal timing modification.
        Verifies that base .net.xml file on disk is completely untouched.
        """
        initial_hash = self._hash_file(self.net_file)

        res = self.client.post("/api/v1/simulation/run", json={
            "scenario_name": "synthetic_normal",
            "location": "Narayanguda, Hyderabad",
            "duration_seconds": 60,
            "seed": 42,
            "intervention": {
                "type": "signal_timing",
                "target": "Westbound",
                "parameters": {"green_time_adjustment_sec": 19.0},
            },
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Check empirical results returned
        self.assertEqual(data["status"], "COMPLETED")
        self.assertIn("metrics", data)
        self.assertIsNotNone(data["metrics"]["average_speed_kmh"])
        self.assertEqual(data["source"]["engine"], "SUMO")
        self.assertEqual(data["source"]["sumo_version"], "1.27.1")

        # Verify base network file on disk was NOT modified
        post_run_hash = self._hash_file(self.net_file)
        self.assertEqual(initial_hash, post_run_hash, "Base .net.xml file was modified on disk!")

    def test_5_baseline_comparison_calculation(self):
        """When baseline metrics are provided, exact delta percentages are computed."""
        baseline = {
            "metrics": {
                "average_speed_kmh": 40.0,
                "average_delay_sec": 10.0,
                "average_waiting_time_sec": 2.0,
                "congestion_index": 0.20,
                "throughput": 0,
            },
            "corridors": [
                {"id": "COR_WB", "name": "Narayanguda - Hyderguda (Westbound)", "avg_speed": 35.0}
            ]
        }

        res = self.client.post("/api/v1/simulation/run", json={
            "scenario_name": "synthetic_normal",
            "location": "Narayanguda, Hyderabad",
            "duration_seconds": 60,
            "seed": 42,
            "intervention": {
                "type": "signal_timing",
                "target": "Westbound",
                "parameters": {"green_time_adjustment_sec": 19.0},
            },
            "baseline_metrics": baseline,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("comparison", data)
        comp = data["comparison"]
        self.assertIn("speed_change_pct", comp)
        self.assertIn("delay_reduction_pct", comp)
        self.assertIn("corridor_comparisons", comp)

    def test_6_rerouting_parameters_validation(self):
        """Rerouting parameters enforce defensive bounds 0.0 < diversion_fraction <= 0.50 and valid modes."""
        from backend.agents.simulation_agent.schemas import ReroutingParameters

        # Valid parameters
        p_valid = ReroutingParameters(target_corridor="Westbound", diversion_fraction=0.15, reroute_mode="alternative_route")
        self.assertEqual(p_valid.diversion_fraction, 0.15)
        self.assertEqual(p_valid.reroute_mode, "alternative_route")

        # Bounds: <= 0.0 rejected
        with self.assertRaises(ValueError):
            ReroutingParameters(diversion_fraction=0.0)

        with self.assertRaises(ValueError):
            ReroutingParameters(diversion_fraction=-0.1)

        # Bounds: > 0.50 rejected
        with self.assertRaises(ValueError):
            ReroutingParameters(diversion_fraction=0.51)

        with self.assertRaises(ValueError):
            ReroutingParameters(diversion_fraction=1.0)

        # Invalid mode rejected
        with self.assertRaises(ValueError):
            ReroutingParameters(diversion_fraction=0.20, reroute_mode="teleport_shortcut")

    def test_7_rerouting_invalid_corridor_rejected(self):
        """Unmappable rerouting corridor targets raise structured 400 validation error."""
        res = self.client.post("/api/v1/simulation/run", json={
            "scenario_name": "synthetic_normal",
            "location": "Narayanguda, Hyderabad",
            "duration_seconds": 60,
            "intervention": {
                "type": "rerouting",
                "target": "Outer_Space_Hyperspace_Bypass",
                "parameters": {"diversion_fraction": 0.15},
            },
        })
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertIn("detail", data)
        self.assertEqual(data["detail"]["error"], "INVALID_SIMULATION_PARAMETERS")

    def test_8_real_sumo_rerouting_execution_and_metrics(self):
        """
        Executes genuine SUMO simulation with dynamic TraCI vehicle rerouting.
        Verifies that vehicle routes are dynamically changed, real metrics are measured,
        actual vs requested diversion fractions are accurately tracked, and base network remains untouched.
        """
        initial_hash = self._hash_file(self.net_file)

        res = self.client.post("/api/v1/simulation/run", json={
            "scenario_name": "synthetic_peak_westbound",
            "location": "Narayanguda, Hyderabad",
            "duration_seconds": 60,
            "seed": 42,
            "intervention": {
                "type": "rerouting",
                "target": "Westbound",
                "parameters": {
                    "diversion_fraction": 0.15,
                    "reroute_mode": "alternative_route",
                },
            },
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # 1. Execution status and metadata
        self.assertEqual(data["status"], "COMPLETED")
        self.assertIn("execution", data)
        exec_info = data["execution"]
        self.assertIsNotNone(exec_info)
        self.assertEqual(exec_info["status"], "completed")
        self.assertEqual(exec_info["target_corridor"], "Westbound")
        self.assertEqual(exec_info["requested_diversion_fraction"], 0.15)
        self.assertTrue(exec_info["rerouting_success"])

        # 2. Rerouted vehicle telemetry
        eligible_cnt = exec_info["eligible_vehicle_count"]
        rerouted_cnt = exec_info["rerouted_vehicle_count"]
        actual_frac = exec_info["actual_diversion_fraction"]

        self.assertGreater(eligible_cnt, 0)
        self.assertGreater(rerouted_cnt, 0)
        self.assertAlmostEqual(actual_frac, round(rerouted_cnt / eligible_cnt, 4), places=3)
        self.assertEqual(len(exec_info["rerouted_vehicles"]), rerouted_cnt)

        # 3. Verify route change details on real vehicles
        for v_rec in exec_info["rerouted_vehicles"]:
            self.assertEqual(v_rec["status"], "success")
            self.assertIn("vehicle_id", v_rec)
            self.assertIn("bottleneck_bypassed", v_rec)
            self.assertIn("original_route_length", v_rec)
            self.assertIn("new_route_length", v_rec)

        # 4. Verify empirical simulation metrics collected
        self.assertIn("metrics", data)
        self.assertIsNotNone(data["metrics"]["average_speed_kmh"])
        self.assertGreater(data["metrics"]["average_speed_kmh"], 0.0)

        # 5. Verify base network file immutability
        post_run_hash = self._hash_file(self.net_file)
        self.assertEqual(initial_hash, post_run_hash, "Base .net.xml file was modified on disk!")

    def test_9_rerouting_deterministic_selection(self):
        """Same seed and parameters produce identical vehicle selection and rerouting count."""
        req_body = {
            "scenario_name": "synthetic_peak_westbound",
            "location": "Narayanguda, Hyderabad",
            "duration_seconds": 60,
            "seed": 42,
            "intervention": {
                "type": "rerouting",
                "target": "Westbound",
                "parameters": {"diversion_fraction": 0.15},
            },
        }

        res1 = self.client.post("/api/v1/simulation/run", json=req_body)
        self.assertEqual(res1.status_code, 200)
        d1 = res1.json()

        res2 = self.client.post("/api/v1/simulation/run", json=req_body)
        self.assertEqual(res2.status_code, 200)
        d2 = res2.json()

        self.assertEqual(d1["execution"]["rerouted_vehicle_count"], d2["execution"]["rerouted_vehicle_count"])
        vids1 = [v["vehicle_id"] for v in d1["execution"]["rerouted_vehicles"]]
        vids2 = [v["vehicle_id"] for v in d2["execution"]["rerouted_vehicles"]]
        self.assertEqual(vids1, vids2)

    def test_10_rerouting_travel_time_balanced_mode(self):
        """travel_time_balanced mode executes in real SUMO using TraCI adaptTraveltime and rerouteTraveltime."""
        res = self.client.post("/api/v1/simulation/run", json={
            "scenario_name": "synthetic_peak_westbound",
            "location": "Narayanguda, Hyderabad",
            "duration_seconds": 60,
            "seed": 42,
            "intervention": {
                "type": "rerouting",
                "target": "Westbound",
                "parameters": {
                    "diversion_fraction": 0.15,
                    "reroute_mode": "travel_time_balanced",
                },
            },
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["execution"]["status"], "completed")
        self.assertEqual(data["execution"]["reroute_mode"], "travel_time_balanced")
        self.assertGreater(data["execution"]["rerouted_vehicle_count"], 0)

    def test_11_rerouting_scenario_id_deterministic(self):
        """Scenario ID for rerouting follows structured deterministic convention."""
        from backend.agents.simulation_agent.service import SimulationService

        scen_id = SimulationService.generate_scenario_id(
            {
                "type": "rerouting",
                "target": "Westbound",
                "parameters": {"diversion_fraction": 0.20},
            },
            seed=42,
        )
        self.assertEqual(scen_id, "rerouting:Westbound:div0.20:seed42")

    def test_12_baseline_missing_explicit_status(self):
        """When baseline metrics are missing or empty, comparison status is baseline_missing and fair_comparison is False."""
        from backend.agents.traffic_agent.schemas import SimulationMetrics

        mock_int_metrics = SimulationMetrics(
            average_speed_kmh=39.5,
            average_delay_sec=14.2,
            average_waiting_time_sec=4.1,
            congestion_index=0.21,
            throughput=0,
            active_vehicles=100,
            total_vehicles=100,
        )
        raw_corridors = [{"id": "COR_WB", "name": "Westbound", "avg_speed": 41.2}]

        # Call with None baseline
        comp = self.service._calculate_comparison(
            baseline_metrics=None,
            intervention_metrics=mock_int_metrics,
            raw_corridors=raw_corridors,
            target_corridor="Westbound",
            seed=42,
        )
        self.assertEqual(comp["status"], "baseline_missing")
        self.assertFalse(comp["fair_comparison"])
        self.assertIsNone(comp["speed_change_pct"])
        self.assertIn("message", comp)

        # Call with empty baseline dict
        comp_empty = self.service._calculate_comparison(
            baseline_metrics={},
            intervention_metrics=mock_int_metrics,
            raw_corridors=raw_corridors,
            target_corridor="Westbound",
            seed=42,
        )
        self.assertEqual(comp_empty["status"], "baseline_missing")
        self.assertFalse(comp_empty["fair_comparison"])

    def test_13_baseline_reference_schema_comparison(self):
        """When BaselineReference format is passed, exact deltas and corridor comparisons are computed."""
        from backend.agents.simulation_agent.schemas import BaselineReference
        from backend.agents.traffic_agent.schemas import SimulationMetrics

        baseline_ref = BaselineReference(
            scenario_name="synthetic_normal",
            seed=42,
            duration_seconds=60,
            average_speed_kmh=40.0,
            average_delay_sec=10.0,
            average_waiting_time_sec=2.0,
            congestion_index=0.20,
            throughput=0,
            corridor_speeds={"COR_WB": 35.0, "COR_SB": 38.0},
        )

        mock_int_metrics = SimulationMetrics(
            average_speed_kmh=42.0,
            average_delay_sec=8.0,
            average_waiting_time_sec=1.5,
            congestion_index=0.18,
            throughput=0,
            active_vehicles=100,
            total_vehicles=100,
        )
        raw_corridors = [
            {"id": "COR_WB", "name": "Narayanguda - Hyderguda (Westbound)", "avg_speed": 41.0},
            {"id": "COR_SB", "name": "Barkatpura - Narayanguda (Southbound)", "avg_speed": 36.0},
        ]

        comp = self.service._calculate_comparison(
            baseline_metrics=baseline_ref.model_dump(),
            intervention_metrics=mock_int_metrics,
            raw_corridors=raw_corridors,
            target_corridor="Westbound",
            seed=42,
            scenario="synthetic_normal",
        )

        self.assertEqual(comp["status"], "SUCCESS")
        self.assertTrue(comp["fair_comparison"])
        self.assertEqual(comp["speed_change_kmh"], 2.0)
        self.assertEqual(comp["speed_change_pct"], 5.0)  # (42 - 40) / 40 * 100
        self.assertEqual(comp["delay_reduction_pct"], 20.0)  # (10 - 8) / 10 * 100
        self.assertEqual(comp["waiting_time_reduction_pct"], 25.0)  # (2.0 - 1.5) / 2.0 * 100
        self.assertEqual(comp["congestion_reduction_pct"], 10.0)  # (0.20 - 0.18) / 0.20 * 100

        # Corridor comparisons
        self.assertEqual(len(comp["corridor_comparisons"]), 2)
        wb_comp = next(c for c in comp["corridor_comparisons"] if c["id"] == "COR_WB")
        self.assertEqual(wb_comp["baseline_speed_kmh"], 35.0)
        self.assertEqual(wb_comp["intervention_speed_kmh"], 41.0)
        self.assertEqual(wb_comp["speed_change_kmh"], 6.0)
        self.assertEqual(wb_comp["speed_change_pct"], 17.14)
        self.assertTrue(wb_comp["is_target"])

        sb_comp = next(c for c in comp["corridor_comparisons"] if c["id"] == "COR_SB")
        self.assertEqual(sb_comp["baseline_speed_kmh"], 38.0)
        self.assertEqual(sb_comp["intervention_speed_kmh"], 36.0)
        self.assertEqual(sb_comp["speed_change_kmh"], -2.0)
        self.assertEqual(sb_comp["speed_change_pct"], -5.26)
        self.assertFalse(sb_comp["is_target"])

    def test_14_mismatched_seed_fair_comparison_false(self):
        """When baseline seed does not match intervention seed, fair_comparison is marked False."""
        from backend.agents.traffic_agent.schemas import SimulationMetrics

        mock_int_metrics = SimulationMetrics(
            average_speed_kmh=41.0,
            average_delay_sec=10.0,
            average_waiting_time_sec=2.0,
            congestion_index=0.20,
            throughput=0,
            active_vehicles=100,
            total_vehicles=100,
        )
        baseline = {
            "metrics": {"average_speed_kmh": 40.0},
            "seed": 99,
        }
        comp = self.service._calculate_comparison(
            baseline_metrics=baseline,
            intervention_metrics=mock_int_metrics,
            raw_corridors=[],
            target_corridor="Westbound",
            seed=42,
        )
        self.assertFalse(comp["fair_comparison"])
        self.assertIn("Random seeds differ", comp.get("fair_comparison_warning", ""))


if __name__ == "__main__":
    unittest.main()

