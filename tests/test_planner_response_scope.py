"""
Test Suite for Planner Response Scope and Direct Answering (Step 5.7.5).

Verifies that the LLM Planner answers the user's actual question directly
and only exposes the information needed to answer that question, while
preserving all internal specialist evidence (telemetry, bottlenecks, trade-offs, candidate interventions).
"""

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.agents.planner_agent.llm_client import MockLLMProvider
from backend.agents.planner_agent.planner import PlannerAgent
from backend.agents.planner_agent.scope import (
    apply_response_scope,
    classify_response_scope,
    extract_traffic_metrics_and_bottlenecks,
)
from backend.supervisor.main import app


class TestPlannerResponseScope(unittest.TestCase):
    """
    Test suite verifying that Planner scopes responses strictly to user queries.
    """

    def setUp(self):
        self.original_provider = os.environ.get("LLM_PROVIDER")
        os.environ["LLM_PROVIDER"] = "mock"
        self.mock_provider = MockLLMProvider()
        self.planner = PlannerAgent(llm_provider=self.mock_provider)
        self.client = TestClient(app)

        # Standard baseline mock traffic evidence
        self.mock_traffic_evidence = {
            "source": {
                "type": "simulation",
                "engine": "SUMO",
                "synthetic": True,
                "network": "narayanguda_network.net.xml",
            },
            "location": "Narayanguda, Hyderabad",
            "scenario": "synthetic_peak_westbound",
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
                {"id": "c_west", "name": "Westbound", "avg_speed": 13.7, "status": "CRITICAL", "value": 72.6},
                {"id": "c_east", "name": "Eastbound", "avg_speed": 46.8, "status": "SMOOTH", "value": 6.4},
                {"id": "c_north", "name": "Northbound", "avg_speed": 38.0, "status": "SMOOTH", "value": 24.0},
                {"id": "c_south", "name": "Southbound", "avg_speed": 35.5, "status": "MODERATE", "value": 29.0},
            ],
            "bottlenecks": [
                {
                    "corridor": "Westbound",
                    "corridor_id": "c_west",
                    "severity": "CRITICAL",
                    "reason": "Lowest observed-speed corridor on network (13.7 km/h vs 50.0 km/h free-flow)",
                    "evidence": {
                        "speed_kmh": 13.7,
                        "network_average_speed_kmh": 24.5,
                        "speed_deficit_pct": 72.6,
                        "waiting_time_sec": 8.5,
                        "delay_sec": 19.2,
                    },
                }
            ],
            "candidate_interventions": [
                {
                    "type": "signal_timing",
                    "target": "Westbound",
                    "parameters": {"green_time_adjustment_sec": 15.0},
                    "reason": "Extend green split on Westbound phase to alleviate severe queuing",
                    "executable": True,
                    "potential_benefit": "Estimated speed gain on Westbound corridor",
                    "potential_tradeoff": "Slight delay increase on cross phases",
                }
            ],
            "trade_offs": [],
            "average_speed_kmh": 24.5,
            "average_delay_sec": 19.2,
            "average_waiting_time_sec": 8.5,
            "congestion_index": 0.51,
        }

    def tearDown(self):
        if self.original_provider is not None:
            os.environ["LLM_PROVIDER"] = self.original_provider
        else:
            os.environ.pop("LLM_PROVIDER", None)

    # -------------------------------------------------------------------------
    # Test A: "What is the bottleneck corridor?"
    # -------------------------------------------------------------------------
    def test_a_bottleneck_corridor_scoped_response(self):
        """
        User asks: 'What is the bottleneck corridor?'
        Expected behavior:
          - Response contains the bottleneck corridor directly: 'Bottleneck corridor: Westbound.'
          - Response does NOT dump unrequested metrics (speed, congestion %, delay, waiting time, throughput, vehicle count).
          - Response does NOT include unsolicited recommendations or candidate interventions.
          - Recommendation card field is empty ("").
        """
        with patch("backend.supervisor.main.dispatch_agent") as mock_dispatch:
            mock_dispatch.return_value = self.mock_traffic_evidence

            res = self.client.post(
                "/agents/planner/execute",
                json={
                    "query": "What is the bottleneck corridor?",
                    "location": "Narayanguda, Hyderabad",
                },
            )

            self.assertEqual(res.status_code, 200, res.text)
            data = res.json()
            final_resp = data.get("final_response", {})

            summary = final_resp.get("summary", "")
            recommendation = final_resp.get("recommendation", "")

            # 1. Must contain the bottleneck corridor
            self.assertIn("Westbound", summary)
            self.assertEqual(summary.strip(), "Bottleneck corridor: Westbound.")

            # 2. Must NOT dump unrelated metrics
            self.assertNotIn("km/h", summary)
            self.assertNotIn("congestion", summary.lower())
            self.assertNotIn("delay", summary.lower())
            self.assertNotIn("waiting time", summary.lower())
            self.assertNotIn("throughput", summary.lower())
            self.assertNotIn("vehicles", summary.lower())

            # 3. Recommendation must be empty
            self.assertEqual(recommendation, "")

            # 4. Scope classification must be ["bottleneck_corridor"]
            self.assertEqual(final_resp.get("requested_scope"), ["bottleneck_corridor"])

    # -------------------------------------------------------------------------
    # Test B: "What is the average speed?"
    # -------------------------------------------------------------------------
    def test_b_average_speed_scoped_response(self):
        """
        User asks: 'What is the average speed?'
        Expected behavior:
          - Response focuses on average speed (e.g., 'Average speed: 24.5 km/h.').
          - Response does NOT dump unrequested bottleneck names or recommendations.
          - Recommendation field is empty ("").
        """
        with patch("backend.supervisor.main.dispatch_agent") as mock_dispatch:
            mock_dispatch.return_value = self.mock_traffic_evidence

            res = self.client.post(
                "/agents/planner/execute",
                json={
                    "query": "What is the average speed?",
                    "location": "Narayanguda, Hyderabad",
                },
            )

            self.assertEqual(res.status_code, 200, res.text)
            data = res.json()
            final_resp = data.get("final_response", {})

            summary = final_resp.get("summary", "")
            recommendation = final_resp.get("recommendation", "")

            # 1. Must focus on average speed
            self.assertIn("24.5 km/h", summary)
            self.assertEqual(summary.strip(), "Average speed: 24.5 km/h.")

            # 2. Must NOT include bottleneck name or recommendations
            self.assertNotIn("Bottleneck corridor:", summary)
            self.assertNotIn("Westbound", summary)
            self.assertEqual(recommendation, "")

            # 3. Scope classification
            self.assertEqual(final_resp.get("requested_scope"), ["average_speed"])

    # -------------------------------------------------------------------------
    # Test C: "Give me the bottleneck corridor and average speed."
    # -------------------------------------------------------------------------
    def test_c_bottleneck_and_average_speed_scoped_response(self):
        """
        User asks: 'Give me the bottleneck corridor and average speed.'
        Expected behavior:
          - Response contains BOTH bottleneck corridor and average speed.
          - Response does NOT dump unrequested recommendations or interventions.
          - Recommendation field is empty ("").
        """
        with patch("backend.supervisor.main.dispatch_agent") as mock_dispatch:
            mock_dispatch.return_value = self.mock_traffic_evidence

            res = self.client.post(
                "/agents/planner/execute",
                json={
                    "query": "Give me the bottleneck corridor and average speed.",
                    "location": "Narayanguda, Hyderabad",
                },
            )

            self.assertEqual(res.status_code, 200, res.text)
            data = res.json()
            final_resp = data.get("final_response", {})

            summary = final_resp.get("summary", "")
            recommendation = final_resp.get("recommendation", "")

            # 1. Must contain both requested items
            self.assertIn("Westbound", summary)
            self.assertIn("km/h", summary)
            self.assertIn("Bottleneck corridor: Westbound", summary)
            self.assertIn("Average speed:", summary)

            # 2. Recommendation must be empty
            self.assertEqual(recommendation, "")

            # 3. Scope classification must contain both
            self.assertEqual(final_resp.get("requested_scope"), ["bottleneck_corridor", "average_speed"])

    # -------------------------------------------------------------------------
    # Test D: "Analyze traffic congestion."
    # -------------------------------------------------------------------------
    def test_d_broad_analysis_response_preserved(self):
        """
        User asks: 'Analyze traffic congestion in Narayanguda.'
        Expected behavior:
          - Broader traffic analysis remains possible because user explicitly requested analysis.
          - Summary provides cross-domain / operational overview.
          - Actionable recommendations are populated.
        """
        with patch("backend.supervisor.main.dispatch_agent") as mock_dispatch:
            mock_dispatch.return_value = self.mock_traffic_evidence

            res = self.client.post(
                "/agents/planner/execute",
                json={
                    "query": "Analyze traffic congestion in Narayanguda.",
                    "location": "Narayanguda, Hyderabad",
                },
            )

            self.assertEqual(res.status_code, 200, res.text)
            data = res.json()
            final_resp = data.get("final_response", {})

            summary = final_resp.get("summary", "")
            recommendation = final_resp.get("recommendation", "")

            # 1. Summary provides broader analysis
            self.assertTrue(len(summary) > 40, f"Expected comprehensive analysis, got: {summary}")
            self.assertIn("Narayanguda", summary)

            # 2. Recommendation is populated
            self.assertTrue(len(recommendation) > 20, f"Expected populated recommendation, got: {recommendation}")

            # 3. Scope classification
            scope = final_resp.get("response_scope", {})
            self.assertEqual(scope.get("detail_level"), "analysis")
            self.assertIn("congestion", scope.get("fields", []))
            self.assertIn("recommendations", scope.get("fields", []))

    # -------------------------------------------------------------------------
    # Test E: Internal Specialist Evidence Retention & Non-Degradation
    # -------------------------------------------------------------------------
    def test_e_internal_specialist_evidence_retained(self):
        """
        Verifies that narrowing the final response does NOT discard internal specialist evidence:
          - collected_results retains the full Traffic Agent response.
          - cross_analysis retains key findings, diagnosed bottlenecks, and candidate interventions.
          - evidence list retains atomic evidence items.
          - Planner reasoning structure is fully preserved.
        """
        with patch("backend.supervisor.main.dispatch_agent") as mock_dispatch:
            mock_dispatch.return_value = self.mock_traffic_evidence

            res = self.client.post(
                "/agents/planner/execute",
                json={
                    "query": "What is the bottleneck corridor?",
                    "location": "Narayanguda, Hyderabad",
                },
            )

            self.assertEqual(res.status_code, 200)
            data = res.json()

            # 1. Full collected_results is intact
            collected = data.get("collected_results", {})
            self.assertIn("traffic", collected)
            trf = collected["traffic"]
            self.assertEqual(len(trf.get("corridors", [])), 4)
            self.assertEqual(trf.get("metrics", {}).get("average_speed_kmh"), 24.5)
            self.assertEqual(trf.get("metrics", {}).get("congestion_index"), 0.51)
            self.assertEqual(len(trf.get("candidate_interventions", [])), 1)

            # 2. Internal diagnosed bottlenecks and key findings are retained
            final_resp = data.get("final_response", {})
            self.assertTrue(len(final_resp.get("diagnosed_bottlenecks", [])) > 0)
            self.assertTrue(len(final_resp.get("key_findings", [])) > 0)

            # 3. Planner feedback insights retained
            insights = data.get("planner_feedback", {}).get("insights", {})
            self.assertIsNotNone(insights.get("cross_analysis"))

    # -------------------------------------------------------------------------
    # Test F: Dynamic Extraction Without Hardcoding (Eastbound vs Northbound)
    # -------------------------------------------------------------------------
    def test_f_dynamic_corridor_extraction_no_hardcoding(self):
        """
        Verifies that corridor answers are dynamically extracted from Traffic Agent telemetry:
          - If evidence specifies Eastbound as bottleneck -> returns Eastbound
          - If evidence specifies Northbound as bottleneck -> returns Northbound
        """
        # Scenario 1: Eastbound bottleneck
        east_evidence = dict(self.mock_traffic_evidence)
        east_evidence["bottlenecks"] = [
            {"corridor": "Eastbound", "reason": "Lowest observed-speed corridor (14.2 km/h)"}
        ]
        east_evidence["corridors"] = [
            {"name": "Eastbound", "avg_speed": 14.2, "status": "CRITICAL"},
            {"name": "Westbound", "avg_speed": 45.0, "status": "SMOOTH"},
        ]

        with patch("backend.supervisor.main.dispatch_agent") as mock_dispatch:
            mock_dispatch.return_value = east_evidence

            res = self.client.post(
                "/agents/planner/execute",
                json={"query": "What is the bottleneck corridor?", "location": "Narayanguda, Hyderabad"},
            )
            data = res.json()
            summary = data.get("final_response", {}).get("summary", "")
            self.assertEqual(summary.strip(), "Bottleneck corridor: Eastbound.")
            self.assertNotIn("Westbound", summary)

        # Scenario 2: Northbound bottleneck
        north_evidence = dict(self.mock_traffic_evidence)
        north_evidence["bottlenecks"] = [
            {"corridor": "Northbound", "reason": "Lowest observed-speed corridor (11.0 km/h)"}
        ]
        north_evidence["corridors"] = [
            {"name": "Northbound", "avg_speed": 11.0, "status": "CRITICAL"},
            {"name": "Westbound", "avg_speed": 45.0, "status": "SMOOTH"},
        ]

        with patch("backend.supervisor.main.dispatch_agent") as mock_dispatch:
            mock_dispatch.return_value = north_evidence

            res = self.client.post(
                "/agents/planner/execute",
                json={"query": "What is the bottleneck corridor?", "location": "Narayanguda, Hyderabad"},
            )
            data = res.json()
            summary = data.get("final_response", {}).get("summary", "")
            self.assertEqual(summary.strip(), "Bottleneck corridor: Northbound.")
            self.assertNotIn("Westbound", summary)

    # -------------------------------------------------------------------------
    # Test G: "Why is Narayanguda congested?" (Causes scope)
    # -------------------------------------------------------------------------
    def test_g_causes_scoped_response(self):
        """
        User asks: 'Why is Narayanguda congested?'
        Expected behavior:
          - Returns the relevant cause/evidence from the bottleneck analysis.
          - Does not dump the entire traffic dataset.
          - Recommendation field is empty ("").
        """
        with patch("backend.supervisor.main.dispatch_agent") as mock_dispatch:
            mock_dispatch.return_value = self.mock_traffic_evidence

            res = self.client.post(
                "/agents/planner/execute",
                json={
                    "query": "Why is Narayanguda congested?",
                    "location": "Narayanguda, Hyderabad",
                },
            )

            self.assertEqual(res.status_code, 200)
            data = res.json()
            final_resp = data.get("final_response", {})

            summary = final_resp.get("summary", "")
            recommendation = final_resp.get("recommendation", "")

            # 1. Focuses on cause
            self.assertIn("Congestion cause:", summary)
            self.assertIn("Lowest observed-speed corridor", summary)

            # 2. Recommendation is empty
            self.assertEqual(recommendation, "")

            # 3. Scope classification
            self.assertEqual(final_resp.get("requested_scope"), ["causes"])

    # -------------------------------------------------------------------------
    # Test H: Specialist Evidence Not Dumped (Section 6 Important Test)
    # -------------------------------------------------------------------------
    def test_specialist_evidence_not_dumped_into_final_response(self):
        """
        Section 6 verification: Proves that specialist evidence is NOT dumped into the final response.
        Given specialist evidence containing:
          - bottleneck_corridor: 'Corridor A'
          - average_speed: 18.4
          - congestion: 0.72
          - waiting_time: 1432
          - throughput: 892

        When user requests: 'What is the bottleneck corridor?'
        Then:
          - final response contains: 'Corridor A'
          - final response must NOT unnecessarily contain: '18.4', '0.72', '1432', '892'
          - specialist evidence remains available internally in collected_results
        """
        specialist_evidence = {
            "source": {"type": "simulation", "engine": "SUMO"},
            "location": "Narayanguda, Hyderabad",
            "bottleneck_corridor": "Corridor A",
            "average_speed": 18.4,
            "congestion": 0.72,
            "waiting_time": 1432,
            "throughput": 892,
            "average_speed_kmh": 18.4,
            "congestion_index": 0.72,
            "average_waiting_time_sec": 1432,
            "bottlenecks": [{"corridor": "Corridor A", "reason": "Severe corridor delay"}],
        }

        with patch("backend.supervisor.main.dispatch_agent") as mock_dispatch:
            mock_dispatch.return_value = specialist_evidence

            res = self.client.post(
                "/agents/planner/execute",
                json={
                    "query": "What is the bottleneck corridor?",
                    "location": "Narayanguda, Hyderabad",
                },
            )

            self.assertEqual(res.status_code, 200, res.text)
            data = res.json()
            final_resp = data.get("final_response", {})
            summary = final_resp.get("summary", "")

            # 1. Must contain the requested corridor
            self.assertIn("Corridor A", summary)

            # 2. Must NOT unnecessarily contain specialist metric values
            self.assertNotIn("18.4", summary)
            self.assertNotIn("0.72", summary)
            self.assertNotIn("1432", summary)
            self.assertNotIn("892", summary)

            # 3. Recommendation must be empty
            self.assertEqual(final_resp.get("recommendation", ""), "")

            # 4. Response scope must be minimal with bottleneck_corridor
            scope = final_resp.get("response_scope", {})
            self.assertEqual(scope.get("fields"), ["bottleneck_corridor"])
            self.assertEqual(scope.get("detail_level"), "minimal")

            # 5. Specialist evidence must remain available internally
            collected = data.get("collected_results", {}).get("traffic", {})
            self.assertEqual(collected.get("bottleneck_corridor"), "Corridor A")
            self.assertEqual(collected.get("average_speed"), 18.4)
            self.assertEqual(collected.get("congestion"), 0.72)
            self.assertEqual(collected.get("waiting_time"), 1432)
            self.assertEqual(collected.get("throughput"), 892)


if __name__ == "__main__":
    unittest.main()

