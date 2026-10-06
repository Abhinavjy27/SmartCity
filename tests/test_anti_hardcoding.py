"""
Anti-Hardcoding Verification Test Suite.
Verifies that the Planner dynamically derives bottlenecks and interventions
strictly from Traffic Agent evidence and does NOT return hardcoded corridor answers
(e.g., answering "Westbound" when the actual evidence specifies "Eastbound").
"""

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.supervisor.main import app
from backend.agents.planner_agent.llm_client import MockLLMProvider, get_llm_provider
from backend.agents.planner_agent.planner import PlannerAgent


class TestAntiHardcoding(unittest.TestCase):
    """
    Proves that the Planner reasoning adapts to Traffic Agent evidence.
    """

    def setUp(self):
        self.original_provider = os.environ.get("LLM_PROVIDER")
        os.environ["LLM_PROVIDER"] = "mock"
        self.client = TestClient(app)

    def tearDown(self):
        if self.original_provider is not None:
            os.environ["LLM_PROVIDER"] = self.original_provider
        else:
            os.environ.pop("LLM_PROVIDER", None)

    def test_bottleneck_derived_from_traffic_evidence_eastbound(self):
        """
        When Traffic Agent returns Eastbound as the lowest-speed corridor (14.2 km/h)
        and Westbound as high-speed (46.8 km/h), the Planner MUST diagnose Eastbound
        as the bottleneck, and MUST NOT diagnose Westbound.
        """
        mock_traffic_evidence = {
            "source": {
                "type": "simulation",
                "engine": "SUMO",
                "synthetic": True,
                "network": "narayanguda_network.net.xml",
                "sumo_version": "1.27.1",
            },
            "location": "Narayanguda, Hyderabad",
            "scenario": "synthetic_peak_eastbound",
            "status": "completed",
            "metrics": {
                "active_vehicles": 22,
                "total_vehicles": 25,
                "average_speed_kmh": 24.5,
                "average_waiting_time_sec": 8.5,
                "average_delay_sec": 19.2,
                "throughput": 12,
                "congestion_index": 0.51,
                "max_halting_vehicles": 6,
                "teleported_vehicles": 0,
                "free_flow_speed_kmh": 50.0,
            },
            "corridors": [
                {"id": "c_east", "name": "Eastbound", "avg_speed": 14.2, "status": "CRITICAL", "value": 71.6, "color": "#E5483F"},
                {"id": "c_west", "name": "Westbound", "avg_speed": 46.8, "status": "SMOOTH", "value": 6.4, "color": "#2F8F72"},
                {"id": "c_north", "name": "Northbound", "avg_speed": 38.0, "status": "SMOOTH", "value": 24.0, "color": "#2F8F72"},
                {"id": "c_south", "name": "Southbound", "avg_speed": 35.5, "status": "MODERATE", "value": 29.0, "color": "#F4A62A"},
            ],
            "bottlenecks": [
                {
                    "corridor": "Eastbound",
                    "corridor_id": "c_east",
                    "severity": "CRITICAL",
                    "reason": "Lowest observed-speed corridor on network (14.2 km/h vs 50.0 km/h free-flow)",
                    "evidence": {
                        "speed_kmh": 14.2,
                        "network_average_speed_kmh": 24.5,
                        "speed_deficit_pct": 71.6,
                        "waiting_time_sec": 8.5,
                        "delay_sec": 19.2,
                    }
                }
            ],
            "candidate_interventions": [
                {
                    "type": "signal_timing",
                    "target": "Eastbound",
                    "parameters": {"green_time_adjustment_sec": 15.0},
                    "reason": "Extend green split on Eastbound phase to alleviate severe queuing",
                    "potential_benefit": "Estimated speed gain on Eastbound corridor",
                    "potential_tradeoff": "Slight delay increase on cross phases",
                }
            ],
            "trade_offs": [],
            "average_speed_kmh": 24.5,
            "average_delay_sec": 19.2,
            "average_waiting_time_sec": 8.5,
            "congestion_index": 0.51,
        }

        with patch("backend.supervisor.main.dispatch_agent") as mock_dispatch:
            mock_dispatch.return_value = mock_traffic_evidence

            # Ask Planner: Which corridor is the bottleneck?
            res = self.client.post("/agents/planner/execute", json={
                "query": "Which corridor is the bottleneck?",
                "location": "Narayanguda, Hyderabad",
            })

            self.assertEqual(res.status_code, 200, res.text)
            data = res.json()

            # 1. Traffic Agent must have been dispatched
            self.assertIn("traffic_agent", data.get("dispatched_agents", []))

            # 2. Diagnosed bottlenecks must contain Eastbound
            final_resp = data.get("final_response", {})
            diagnosed = final_resp.get("diagnosed_bottlenecks", [])

            # Join all text to verify presence
            full_text = " ".join([
                str(diagnosed),
                final_resp.get("summary", ""),
                final_resp.get("recommendation", ""),
                str(final_resp.get("key_findings", []))
            ]).lower()

            self.assertIn("eastbound", full_text, "Planner failed to identify 'Eastbound' as the bottleneck from returned evidence!")
            self.assertNotIn("lowest observed-speed corridor: 'westbound'", full_text, "Planner incorrectly claimed Westbound was the bottleneck!")

    def test_bottleneck_derived_from_traffic_evidence_northbound(self):
        """
        When Traffic Agent returns Northbound as the lowest-speed corridor (11.0 km/h),
        the Planner MUST diagnose Northbound as the bottleneck.
        """
        mock_traffic_evidence = {
            "source": {"type": "simulation", "engine": "SUMO"},
            "location": "Narayanguda, Hyderabad",
            "scenario": "synthetic_peak_northbound",
            "metrics": {
                "active_vehicles": 20,
                "total_vehicles": 25,
                "average_speed_kmh": 22.0,
                "average_waiting_time_sec": 9.0,
                "average_delay_sec": 21.0,
                "throughput": 10,
                "congestion_index": 0.56,
            },
            "corridors": [
                {"id": "c_north", "name": "Northbound", "avg_speed": 11.0, "status": "CRITICAL", "value": 78.0, "color": "#E5483F"},
                {"id": "c_south", "name": "Southbound", "avg_speed": 40.0, "status": "SMOOTH", "value": 20.0, "color": "#2F8F72"},
                {"id": "c_west", "name": "Westbound", "avg_speed": 44.0, "status": "SMOOTH", "value": 12.0, "color": "#2F8F72"},
                {"id": "c_east", "name": "Eastbound", "avg_speed": 39.0, "status": "SMOOTH", "value": 22.0, "color": "#2F8F72"},
            ],
            "bottlenecks": [
                {
                    "corridor": "Northbound",
                    "severity": "CRITICAL",
                    "reason": "Lowest observed-speed corridor on network (11.0 km/h)",
                    "evidence": {"speed_kmh": 11.0, "delay_sec": 21.0}
                }
            ],
            "average_speed_kmh": 22.0,
        }

        with patch("backend.supervisor.main.dispatch_agent") as mock_dispatch:
            mock_dispatch.return_value = mock_traffic_evidence

            res = self.client.post("/agents/planner/execute", json={
                "query": "Where is the bottleneck located?",
                "location": "Narayanguda, Hyderabad",
            })

            self.assertEqual(res.status_code, 200, res.text)
            data = res.json()

            final_resp = data.get("final_response", {})
            diagnosed = final_resp.get("diagnosed_bottlenecks", [])
            full_text = " ".join([
                str(diagnosed),
                final_resp.get("summary", ""),
                final_resp.get("recommendation", ""),
                str(final_resp.get("key_findings", []))
            ]).lower()

            self.assertIn("northbound", full_text, "Planner failed to identify 'Northbound' as the bottleneck from returned evidence!")
            self.assertNotIn("lowest observed-speed corridor: 'westbound'", full_text)


if __name__ == "__main__":
    unittest.main()
