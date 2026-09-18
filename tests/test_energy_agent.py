"""
Comprehensive Unit and Integration Tests for Real-Time SUPADSP Energy Agent.
Validates contract compliance, Pydantic schemas, evidence extraction severity thresholds,
cross-domain context ingestion, and dual ASGI/HTTP transport execution.
"""

import time
import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.agents.energy_agent.load_calculator import (
    calculate_traffic_ev_impact,
    calculate_weather_impact,
    compute_diurnal_factor,
    compute_solar_generation,
    compute_telemetry_state,
    map_load_to_severity,
    map_substation_status,
)
from backend.agents.energy_agent.main import app
from backend.agents.energy_agent.optimizer import execute_peak_shaving, generate_recommendations
from backend.agents.energy_agent.schema import (
    EnergyAnalyzeRequest,
    GridStatusResponse,
    PeakShavingRequest,
    SeverityLevel,
    SubstationData,
    SubstationStatus,
)
from backend.agents.energy_agent.substations import SUBSTATIONS_DB, match_substations_by_location
from backend.supervisor.agent_client import dispatch_agent


class TestEnergyAgent(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_endpoint(self):
        """Test GET /health returns ONLINE status."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["agent"], "Energy Agent")
        self.assertEqual(data["status"], "ONLINE")

    def test_contract_compliance_grid_status(self):
        """Test GET /api/v1/energy/grid-status satisfies all required platform contract fields."""
        response = self.client.get("/api/v1/energy/grid-status")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Required fields according to contracts.py and architecture specs
        self.assertIn("load_pct", data)
        self.assertIn("current_load_mw", data)
        self.assertIn("substations", data)
        self.assertIn("capacity_mw", data)
        self.assertIn("solar_generation_mw", data)
        self.assertIn("total_consumption_mwh", data)
        self.assertIn("efficiency_score_pct", data)
        self.assertIn("hourly_load", data)
        self.assertIn("zone_data", data)
        self.assertIn("recommendations", data)
        self.assertIn("source", data)
        self.assertIn("timestamp", data)
        self.assertIn("severity", data)

        # Validate types
        self.assertIsInstance(data["load_pct"], (int, float))
        self.assertIsInstance(data["current_load_mw"], (int, float))
        self.assertIsInstance(data["substations"], list)
        self.assertGreater(len(data["substations"]), 0)

        # Substation item schema verification
        for sub in data["substations"]:
            self.assertIn("id", sub)
            self.assertIn("name", sub)
            self.assertIn("load_pct", sub)
            self.assertIn("status", sub)
            self.assertIn("capacity_mw", sub)
            self.assertIn("current_load_mw", sub)
            self.assertIn(sub["status"], ["CRITICAL", "HIGH", "NORMAL"])

        # Validate through Pydantic model
        validated = GridStatusResponse.model_validate(data)
        self.assertIsNotNone(validated)

    def test_location_filtering_narayanguda(self):
        """Test location query for 'Narayanguda, Hyderabad' focuses on Narayanguda substation."""
        response = self.client.get("/api/v1/energy/grid-status?location=Narayanguda, Hyderabad")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        sub_names = [s["name"] for s in data["substations"]]
        self.assertTrue(any("Narayanguda" in name for name in sub_names))

    def test_location_filtering_tarnaka(self):
        """Test location query for 'Tarnaka, Hyderabad' focuses on Tarnaka substation."""
        response = self.client.get("/api/v1/energy/grid-status?location=Tarnaka, Hyderabad")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        sub_names = [s["name"] for s in data["substations"]]
        self.assertTrue(any("Tarnaka" in name for name in sub_names))

    def test_location_filtering_hitech_city(self):
        """Test location query for 'Madhapur' / 'HITECH City'."""
        response = self.client.get("/api/v1/energy/grid-status?location=Madhapur")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        sub_names = [s["name"] for s in data["substations"]]
        self.assertTrue(any("Madhapur" in name for name in sub_names))

    def test_cross_domain_weather_context_ingestion(self):
        """Test ingesting high ambient temperature (heatwave) increases load and generates heatwave response."""
        # Baseline temperature (28°C)
        resp_base = self.client.get("/api/v1/energy/grid-status?ambient_temp_c=28.0")
        data_base = resp_base.json()

        # Heatwave temperature (42°C)
        resp_heat = self.client.get("/api/v1/energy/grid-status?ambient_temp_c=42.0")
        data_heat = resp_heat.json()

        # Heatwave load must be higher than base
        self.assertGreater(data_heat["load_pct"], data_base["load_pct"])
        self.assertGreater(data_heat["current_load_mw"], data_base["current_load_mw"])
        self.assertGreater(data_heat["weather_impact_mw"], 0.0)

        # Check that heatwave mitigation or BESS recommendation was synthesized
        rec_titles = [r["title"] for r in data_heat["recommendations"]]
        self.assertTrue(any("Heatwave" in t or "BESS" in t or "Battery" in t or "demand response" in t for t in rec_titles))

    def test_cross_domain_traffic_ev_context_ingestion(self):
        """Test ingesting traffic occupancy and EV count increases load."""
        resp_base = self.client.get("/api/v1/energy/grid-status?traffic_occupancy_pct=40.0&ev_count=50")
        data_base = resp_base.json()

        resp_busy = self.client.get("/api/v1/energy/grid-status?traffic_occupancy_pct=95.0&ev_count=1200")
        data_busy = resp_busy.json()

        self.assertGreaterEqual(data_busy["current_load_mw"], data_base["current_load_mw"])
        self.assertGreater(data_busy["ev_traffic_impact_mw"], 0.0)

    def test_evidence_extraction_severity_thresholds(self):
        """
        Test that load_pct maps deterministically to extract_evidence() thresholds:
        - CRITICAL: load_pct >= 85.0
        - HIGH:     load_pct >= 75.0
        - MODERATE: load_pct < 75.0
        """
        self.assertEqual(map_load_to_severity(85.0), "CRITICAL")
        self.assertEqual(map_load_to_severity(92.4), "CRITICAL")
        self.assertEqual(map_load_to_severity(75.0), "HIGH")
        self.assertEqual(map_load_to_severity(84.9), "HIGH")
        self.assertEqual(map_load_to_severity(74.9), "MODERATE")
        self.assertEqual(map_load_to_severity(55.0), "MODERATE")

        # Substation statuses
        self.assertEqual(map_substation_status(85.0), "CRITICAL")
        self.assertEqual(map_substation_status(75.0), "HIGH")
        self.assertEqual(map_substation_status(65.0), "NORMAL")

    def test_dispatch_agent_transport_compatibility(self):
        """Test dispatching energy capability via agent_client.dispatch_agent in-process ASGI fallback."""
        result = dispatch_agent("energy")
        self.assertIsInstance(result, dict)
        self.assertIn("load_pct", result)
        self.assertIn("current_load_mw", result)
        self.assertIn("substations", result)

    def test_analyze_energy_endpoint(self):
        """Test POST /api/v1/energy/analyze specialist endpoint."""
        payload = {
            "location": "Financial District Substation",
            "scenario": "peak_load_dimming",
            "ambient_temp_c": 36.0,
            "traffic_occupancy_pct": 82.0,
        }
        response = self.client.post("/api/v1/energy/analyze", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["status"], "COMPLETED")
        self.assertEqual(data["domain"], "energy")
        self.assertEqual(data["location"], "Financial District Substation")
        self.assertIn("current_load_mw", data)
        self.assertIn("load_pct", data)
        self.assertIn("severity", data)
        self.assertIn("projected_savings_mw", data)
        self.assertIn("grid_stability_index", data)
        self.assertGreater(data["confidence"], 0.8)

    def test_peak_shave_endpoint(self):
        """Test POST /api/v1/energy/peak-shave optimization endpoint."""
        payload = {
            "zone": "HITECH City",
            "target_reduction_mw": 30.0,
        }
        response = self.client.post("/api/v1/energy/peak-shave", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["status"], "OPTIMIZED")
        self.assertEqual(data["zone"], "HITECH City")
        self.assertGreater(data["bess_discharge_mw"], 0)
        self.assertGreater(data["solar_offset_mw"], 0)
        self.assertIsInstance(data["actions"], list)
        self.assertGreater(len(data["actions"]), 0)

    def test_substations_and_zones_endpoints(self):
        """Test GET /api/v1/energy/substations and GET /api/v1/energy/zones."""
        resp_subs = self.client.get("/api/v1/energy/substations")
        self.assertEqual(resp_subs.status_code, 200)
        subs = resp_subs.json()
        self.assertIsInstance(subs, list)
        self.assertGreaterEqual(len(subs), 10)

        # Filter by zone
        resp_filtered = self.client.get("/api/v1/energy/substations?zone=Gachibowli")
        self.assertEqual(resp_filtered.status_code, 200)
        filtered = resp_filtered.json()
        self.assertTrue(all(s["zone"] == "Gachibowli" for s in filtered))

        # Zones endpoint
        resp_zones = self.client.get("/api/v1/energy/zones")
        self.assertEqual(resp_zones.status_code, 200)
        zones = resp_zones.json()
        self.assertIsInstance(zones, list)
        self.assertGreater(len(zones), 0)

    def test_dataset_loader_integration(self):
        """Test that the empirical dataset loader aggregates household_power_consumption.txt."""
        from backend.agents.energy_agent.dataset_loader import load_energy_dataset_stats, get_empirical_hourly_factor
        profile, stats = load_energy_dataset_stats()
        self.assertIsInstance(profile, dict)
        self.assertEqual(len(profile), 24)
        self.assertIn("avg_active_power_kw", stats)
        
        # Test empirical factor calculation for sample hours
        factor_noon = get_empirical_hourly_factor(14)
        factor_night = get_empirical_hourly_factor(3)
        self.assertIsInstance(factor_noon, float)
        self.assertIsInstance(factor_night, float)
        self.assertGreater(factor_noon, 0.0)
        self.assertGreater(factor_night, 0.0)

    def test_execution_latency(self):
        """Test sub-5-second execution latency requirement (< 100ms expected)."""
        start_time = time.perf_counter()
        response = self.client.get("/api/v1/energy/grid-status?location=Financial District&ambient_temp_c=35.0")
        elapsed = time.perf_counter() - start_time

        self.assertEqual(response.status_code, 200)
        self.assertLess(elapsed, 5.0, f"Execution latency too high: {elapsed}s")
        # Ensure ultra-fast in-process execution
        self.assertLess(elapsed, 0.5, f"Expected < 500ms in-process, took {elapsed}s")


if __name__ == "__main__":
    unittest.main()
