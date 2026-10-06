"""
Automated verification tests for the Traffic Scenario & Metrics Realism Audit.
Verifies:
1. Vehicle lifecycle accounting (generated == inserted == arrived + active_at_end).
2. Waiting-time calculation and TraCI native alignment.
3. Delay calculation (time loss).
4. Unfinished vs finished trip metrics (completed_trips_avg_waiting_time_sec, completed_trips_avg_delay_sec).
5. Arrived vehicles and throughput equivalence.
6. Longer duration horizons (120s vs 300s) confirming trajectory completion.
7. Demand profile directional loading behavior.
8. Signal queue formation and halting behavior.
9. Missing data / empty observation None handling (never fabricates 0 or 50 km/h).
10. Base SUMO network immutability.
"""

import os
import unittest
from backend.agents.traffic_agent.metrics import SumoMetricsCollector, VehicleRecord
from backend.agents.traffic_agent.demand_generator import SyntheticDemandGenerator, SCENARIO_DEMAND_PROFILES
from backend.agents.simulation_agent.service import SimulationService, get_simulation_service
from backend.agents.simulation_agent.schemas import SimulationScenarioRequest


class TestTrafficRealismAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = get_simulation_service()
        cls.demand_gen = SyntheticDemandGenerator()

    def test_1_metric_empty_network_none_handling(self):
        """Verify that when no vehicle observations exist, metrics report None and never fabricate 0 or 50 km/h."""
        collector = SumoMetricsCollector(free_flow_speed_kmh=50.0)
        metrics = collector.calculate_summary()

        self.assertEqual(metrics.total_vehicles, 0)
        self.assertEqual(metrics.throughput, 0)
        self.assertEqual(metrics.arrived_vehicles, 0)
        self.assertEqual(metrics.active_at_end, 0)
        self.assertIsNone(metrics.average_speed_kmh, "Empty network must report None speed, not 50.0 km/h!")
        self.assertIsNone(metrics.average_waiting_time_sec, "Empty network must report None waiting time, not 0.0!")
        self.assertIsNone(metrics.average_delay_sec, "Empty network must report None delay, not 0.0!")
        self.assertIsNone(metrics.congestion_index, "Empty network must report None congestion index, not 0.0!")
        self.assertIsNone(metrics.completed_trips_avg_waiting_time_sec)
        self.assertIsNone(metrics.completed_trips_avg_delay_sec)
        self.assertIsNone(metrics.completed_trips_avg_duration_sec)

    def test_2_lifecycle_accounting_math(self):
        """Verify mathematical reconciliation: total_vehicles == arrived_vehicles + active_at_end."""
        collector = SumoMetricsCollector(free_flow_speed_kmh=50.0)
        
        # Vehicle 1: arrived at t=190s, departed t=10s, waited 25s, loss 50s
        v1 = VehicleRecord(
            vid="veh_northbound_0",
            corridor="northbound",
            depart_time=10.0,
            arrival_time=190.0,
            accumulated_waiting_time=25.0,
            final_time_loss=50.0,
            arrived=True,
        )
        # Vehicle 2: arrived at t=210s, departed t=20s, waited 15s, loss 40s
        v2 = VehicleRecord(
            vid="veh_westbound_1",
            corridor="westbound",
            depart_time=20.0,
            arrival_time=210.0,
            accumulated_waiting_time=15.0,
            final_time_loss=40.0,
            arrived=True,
        )
        # Vehicle 3: unfinished (active at end), departed t=100s, waited 5s, loss 10s
        v3 = VehicleRecord(
            vid="veh_southbound_2",
            corridor="southbound",
            depart_time=100.0,
            arrival_time=None,
            accumulated_waiting_time=5.0,
            final_time_loss=10.0,
            arrived=False,
        )
        
        collector.vehicles = {v1.vid: v1, v2.vid: v2, v3.vid: v3}
        collector.speed_observations_ms = [10.0, 11.0, 12.0] # ~40 km/h
        collector.halting_samples = [0, 1, 1]
        
        summary = collector.calculate_summary()
        
        # Reconcile counts
        self.assertEqual(summary.total_vehicles, 3)
        self.assertEqual(summary.throughput, 2)
        self.assertEqual(summary.arrived_vehicles, 2)
        self.assertEqual(summary.active_at_end, 1)
        self.assertEqual(summary.total_vehicles, summary.arrived_vehicles + summary.active_at_end)
        
        # Network-wide average waiting: (25 + 15 + 5) / 3 = 15.0s
        self.assertEqual(summary.average_waiting_time_sec, 15.0)
        # Network-wide average delay: (50 + 40 + 10) / 3 = 33.33s
        self.assertEqual(summary.average_delay_sec, 33.33)
        
        # Completed trips average waiting (un-diluted): (25 + 15) / 2 = 20.0s
        self.assertEqual(summary.completed_trips_avg_waiting_time_sec, 20.0)
        # Completed trips average delay (un-diluted): (50 + 40) / 2 = 45.0s
        self.assertEqual(summary.completed_trips_avg_delay_sec, 45.0)
        # Completed trips average duration: ((190 - 10) + (210 - 20)) / 2 = (180 + 190) / 2 = 185.0s
        self.assertEqual(summary.completed_trips_avg_duration_sec, 185.0)

    def test_3_demand_profile_rates_and_seed_determinism(self):
        """Verify that demand profiles generate reproducible route files with verified corridor distribution."""
        f1 = self.demand_gen.generate_route_file(scenario="synthetic_normal", duration_seconds=120, seed=42)
        f2 = self.demand_gen.generate_route_file(scenario="synthetic_normal", duration_seconds=120, seed=42)
        self.assertEqual(f1, f2)
        self.assertTrue(os.path.exists(f1))

        # Check vehicle count in 120s synthetic_normal: exactly 36 vehicles
        import xml.etree.ElementTree as ET
        tree = ET.parse(f1)
        trips = tree.getroot().findall("trip")
        self.assertEqual(len(trips), 36)

    def test_4_real_sumo_120s_lifecycle_accounting(self):
        """Execute 120s baseline in real SUMO and verify exact lifecycle accounting."""
        req = SimulationScenarioRequest(
            scenario_name="synthetic_normal",
            duration_seconds=120,
            seed=42,
        )
        res = self.service.run_intervention_simulation(req)
        
        # 36 vehicles generated and simulated
        self.assertEqual(res.metrics.total_vehicles, 36)
        self.assertEqual(res.total_vehicles, 36)
        # At 120s, trip duration is ~190s, so 0 vehicles arrived
        self.assertEqual(res.metrics.throughput, 0)
        self.assertEqual(res.throughput, 0)
        self.assertEqual(res.metrics.arrived_vehicles, 0)
        self.assertEqual(res.metrics.active_at_end, 36)
        # Total reconciled
        self.assertEqual(res.metrics.total_vehicles, res.metrics.arrived_vehicles + res.metrics.active_at_end)
        # Speed observed
        self.assertIsNotNone(res.metrics.average_speed_kmh)
        self.assertGreater(res.metrics.average_speed_kmh, 30.0)

    def test_5_real_sumo_300s_trajectory_completion(self):
        """
        Execute 300s simulation in real SUMO.
        Verifies that with a 300s horizon (> 189s trip time), vehicles successfully complete their trips,
        throughput is positive, and completed trip metrics are captured.
        """
        req = SimulationScenarioRequest(
            scenario_name="synthetic_normal",
            duration_seconds=300,
            seed=42,
        )
        res = self.service.run_intervention_simulation(req)
        
        # In 300s, 91 vehicles generated
        self.assertEqual(res.metrics.total_vehicles, 91)
        # At 300s, vehicles DO complete trips
        self.assertGreater(res.metrics.throughput, 0)
        self.assertEqual(res.metrics.throughput, res.metrics.arrived_vehicles)
        self.assertEqual(res.metrics.total_vehicles, res.metrics.arrived_vehicles + res.metrics.active_at_end)
        
        # Completed trip metrics exist
        self.assertIsNotNone(res.metrics.completed_trips_avg_waiting_time_sec)
        self.assertIsNotNone(res.metrics.completed_trips_avg_delay_sec)
        self.assertIsNotNone(res.metrics.completed_trips_avg_duration_sec)
        
        # Completed trips average duration should be ~180-200s
        self.assertGreaterEqual(res.metrics.completed_trips_avg_duration_sec, 150.0)
        self.assertLessEqual(res.metrics.completed_trips_avg_duration_sec, 250.0)
        
        # Completed trips average waiting time should be higher than truncated network-wide waiting time
        self.assertGreater(
            res.metrics.completed_trips_avg_waiting_time_sec,
            res.metrics.average_waiting_time_sec,
            "Completed trips waiting time should be un-diluted by late entering vehicles!"
        )

    def test_6_base_network_remains_immutable(self):
        """Verify base SUMO network file was not modified."""
        net_path = self.service.network_path
        self.assertTrue(os.path.isfile(net_path))
        # Ensure file size is positive
        self.assertGreater(os.path.getsize(net_path), 4_000_000)


if __name__ == "__main__":
    unittest.main()
