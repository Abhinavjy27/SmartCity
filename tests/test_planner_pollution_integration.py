"""
Step 5.8 Integration Tests: Pollution Agent -> LLM Planner Integration.
Verifies:
A. Pollution capability can be selected.
B. Planner generates a valid Pollution request.
C. Planner dispatches to Pollution Agent through the existing transport layer.
D. Valid Pollution response becomes Planner evidence.
E. city_avg_aqi is validated.
F. pm25 is validated.
G. pm10 is validated.
H. Pollution 404/no-data is handled gracefully.
I. Pollution timeout is handled gracefully.
J. Malformed Pollution response is handled gracefully.
K. Pollution interventions remain evidence and are NOT automatically sent to Simulation.
L. A multi-agent Traffic + Pollution request can collect both evidence sets.
M. Response scoping still works with Pollution evidence (no metric dumps).
N. Existing Traffic behavior remains unchanged.
O. Existing response-scope tests remain unchanged.
"""

import os
import pytest
from typing import Any, Dict

from backend.agents.planner_agent.llm_client import MockLLMProvider
from backend.agents.planner_agent.planner import PlannerAgent
from backend.agents.planner_agent.contracts import SPECIALIST_AGENT_CONTRACTS
from backend.supervisor.agent_client import dispatch_agent, AGENT_REGISTRY


class TestPlannerPollutionIntegration:
    """Test suite verifying end-to-end integration between LLM Planner and Pollution Agent."""

    def setup_method(self):
        self.original_provider = os.environ.get("LLM_PROVIDER")
        os.environ["LLM_PROVIDER"] = "mock"
        self.mock_provider = MockLLMProvider()
        self.planner = PlannerAgent(llm_provider=self.mock_provider)

    def teardown_method(self):
        if self.original_provider is not None:
            os.environ["LLM_PROVIDER"] = self.original_provider
        else:
            os.environ.pop("LLM_PROVIDER", None)

    def test_case_a_pollution_capability_selected(self):
        """A. Pollution capability can be selected when relevant, and not when irrelevant."""
        # Relevant pollution queries
        plan_pol_1 = self.planner.plan_autonomous("Analyze air pollution in Hyderabad.")
        assert "pollution" in plan_pol_1.required_capabilities

        plan_pol_2 = self.planner.plan_autonomous("What is the PM2.5 level in Narayanguda?")
        assert "pollution" in plan_pol_2.required_capabilities

        plan_pol_3 = self.planner.plan_autonomous("Find the pollution risk in Narayanguda.")
        assert "pollution" in plan_pol_3.required_capabilities

        # Pure traffic + weather query should NOT select pollution
        plan_traffic_weather = self.planner.plan_autonomous("Find the risk of heavy traffic due to rainfall in Narayanguda.")
        assert "traffic" in plan_traffic_weather.required_capabilities
        assert "weather" in plan_traffic_weather.required_capabilities
        assert "pollution" not in plan_traffic_weather.required_capabilities

    def test_case_b_planner_generates_valid_pollution_request(self):
        """B. Planner generates a valid Pollution request conforming to contract."""
        query = "Analyze pollution risk in Narayanguda."
        plan = self.planner.plan_autonomous(query)
        pol_req = next(r for r in plan.agent_requests if r.agent == "pollution")

        assert "location" in pol_req.request
        assert "Narayanguda" in pol_req.request["location"]

        # Ensure context builder populates required fields
        context = self.planner.build_agent_request_context(
            capability="pollution",
            objective="Analyze pollution risk in Narayanguda.",
            location="Narayanguda, Hyderabad",
        )
        assert context.is_complete
        assert context.target_endpoint == "/api/v1/pollution/analyze"
        assert context.method == "POST"
        assert context.payload["location"] == "Narayanguda, Hyderabad"
        assert "objective" in context.payload

    def test_case_c_planner_dispatches_through_transport_layer(self):
        """C. Planner dispatches to Pollution Agent through the existing transport layer."""
        assert "pollution" in AGENT_REGISTRY
        assert AGENT_REGISTRY["pollution"]["endpoint"] == "/api/v1/pollution/analyze"
        assert AGENT_REGISTRY["pollution"]["method"] == "POST"

        res = dispatch_agent("pollution", {
            "location": "Narayanguda, Hyderabad",
            "objective": "Check current air pollution",
        })
        assert isinstance(res, dict)
        assert "city_avg_aqi" in res
        assert "pm25" in res
        assert "pm10" in res
        assert isinstance(res["city_avg_aqi"], (int, float))
        assert isinstance(res["pm25"], (int, float))
        assert isinstance(res["pm10"], (int, float))

    def test_case_d_valid_pollution_response_becomes_evidence(self):
        """D. Valid Pollution response becomes Planner evidence."""
        sample_pollution = {
            "city_avg_aqi": 136,
            "pm25": 78.5,
            "pm10": 115.9,
            "stations": ["Sanathnagar", "Zoo Park"],
            "suggested_interventions": [
                {
                    "action_type": "GREEN_INFRASTRUCTURE",
                    "description": "Vegetative barriers along corridors.",
                    "expected_impact_pct": 12.0,
                    "feasibility_score": 8.5,
                }
            ],
        }
        evidence_items = self.planner.extract_evidence("pollution", sample_pollution, "Hyderabad")
        assert len(evidence_items) >= 3

        metrics_found = {e.metric for e in evidence_items}
        assert "city_avg_aqi" in metrics_found
        assert "pm25" in metrics_found
        assert "pm10" in metrics_found

        eval_res = self.planner.evaluate_and_replan(
            objective="Analyze air pollution in Hyderabad",
            plan=["pollution"],
            collected_results={"pollution": sample_pollution},
            location="Hyderabad",
        )
        assert eval_res.decision == "finalize"
        assert any(e.source == "pollution" for e in eval_res.evidence)

    def test_case_e_city_avg_aqi_validated(self):
        """E. city_avg_aqi is validated."""
        bad_payload = {"pm25": 20.8, "pm10": 31.7}
        with pytest.raises(ValueError, match="city_avg_aqi"):
            self.planner.validate_agent_output("pollution", bad_payload)

        bad_type = {"city_avg_aqi": "one hundred", "pm25": 20.8, "pm10": 31.7}
        with pytest.raises(ValueError, match="numeric"):
            self.planner.validate_agent_output("pollution", bad_type)

    def test_case_f_pm25_validated(self):
        """F. pm25 is validated."""
        bad_payload = {"city_avg_aqi": 100, "pm10": 31.7}
        with pytest.raises(ValueError, match="pm25"):
            self.planner.validate_agent_output("pollution", bad_payload)

        bad_type = {"city_avg_aqi": 100, "pm25": "high", "pm10": 31.7}
        with pytest.raises(ValueError, match="numeric"):
            self.planner.validate_agent_output("pollution", bad_type)

    def test_case_g_pm10_validated(self):
        """G. pm10 is validated."""
        bad_payload = {"city_avg_aqi": 100, "pm25": 20.8}
        with pytest.raises(ValueError, match="pm10"):
            self.planner.validate_agent_output("pollution", bad_payload)

        bad_type = {"city_avg_aqi": 100, "pm25": 20.8, "pm10": None}
        with pytest.raises(ValueError, match="pm10"):
            self.planner.validate_agent_output("pollution", bad_type)

    def test_case_h_pollution_404_no_data_handled_gracefully(self):
        """H. Pollution 404/no-data is handled gracefully without crashing."""
        unavailable_payload = {
            "agent": "pollution",
            "status": "unavailable",
            "error": "No pollution data found for this location.",
        }
        # Validate returns handled failure payload
        val = self.planner.validate_agent_output("pollution", unavailable_payload)
        assert val["status"] == "unavailable"

        # Evaluate and replan does not crash and records failure
        eval_res = self.planner.evaluate_and_replan(
            objective="Analyze pollution in NonExistentCity",
            plan=["pollution"],
            collected_results={"pollution": unavailable_payload},
            location="NonExistentCity",
        )
        assert eval_res.decision == "finalize"
        # No fake pollution metrics should be fabricated in evidence
        assert not any(e.source == "pollution" for e in eval_res.evidence)

    def test_case_i_pollution_timeout_handled_gracefully(self):
        """I. Pollution timeout is handled gracefully."""
        eval_res = self.planner.evaluate_and_replan(
            objective="Analyze air pollution in Hyderabad",
            plan=["pollution"],
            collected_results={},
            failures={"pollution": "Agent 'pollution_agent' timed out after 5.0s"},
            location="Hyderabad",
        )
        assert eval_res.decision == "finalize"
        assert not any(e.source == "pollution" for e in eval_res.evidence)

    def test_case_j_malformed_pollution_response_handled_gracefully(self):
        """J. Malformed Pollution response is handled gracefully without crashing."""
        malformed = {"corrupted": True, "data": 42}
        eval_res = self.planner.evaluate_and_replan(
            objective="Analyze air pollution",
            plan=["pollution"],
            collected_results={"pollution": malformed},
            location="Hyderabad",
        )
        assert eval_res.decision == "finalize"
        assert not any(e.source == "pollution" for e in eval_res.evidence)

    def test_case_k_pollution_interventions_not_sent_to_simulation(self):
        """K. Pollution interventions remain evidence and are NOT automatically sent to Simulation."""
        pollution_with_interventions = {
            "city_avg_aqi": 180,
            "pm25": 95.0,
            "pm10": 140.0,
            "stations": ["Sanathnagar"],
            "suggested_interventions": [
                {
                    "action_type": "SMART_TRAFFIC_LIGHTS",
                    "description": "Adjust signal phases to minimize idling emissions.",
                    "expected_impact_pct": 15.0,
                    "feasibility_score": 7.0,
                },
                {
                    "action_type": "GREEN_INFRASTRUCTURE",
                    "description": "Deploy urban tree canopy.",
                    "expected_impact_pct": 10.0,
                    "feasibility_score": 9.0,
                },
            ],
        }

        eval_res = self.planner.evaluate_and_replan(
            objective="Analyze pollution and suggest interventions in Narayanguda.",
            plan=["pollution"],
            collected_results={"pollution": pollution_with_interventions},
            location="Narayanguda, Hyderabad",
        )

        # Must finalize and NOT trigger a SUMO simulation
        assert eval_res.next_action != "run_simulation"
        assert eval_res.decision == "finalize"
        assert not any(r.agent == "simulation" for r in eval_res.next_cycle_calls)

    def test_case_l_multi_agent_traffic_and_pollution_request(self):
        """L. A multi-agent Traffic + Pollution request can collect both evidence sets."""
        query = "Analyze the relationship between traffic congestion and air pollution in Narayanguda."
        plan = self.planner.plan_autonomous(query)
        caps = plan.required_capabilities
        assert "traffic" in caps
        assert "pollution" in caps

        trf_data = {
            "congestion_index": 0.45,
            "average_speed_kmh": 22.5,
            "average_delay_sec": 38.0,
            "total_vehicles": 250,
            "throughput": 180,
            "corridors": [{"name": "Westbound", "avg_speed": 18.0, "status": "HEAVY"}],
        }
        pol_data = {
            "city_avg_aqi": 125,
            "pm25": 55.4,
            "pm10": 85.0,
            "stations": ["Narayanguda Station"],
            "suggested_interventions": [],
        }

        eval_res = self.planner.evaluate_and_replan(
            objective=query,
            plan=caps,
            collected_results={"traffic": trf_data, "pollution": pol_data},
            location="Narayanguda, Hyderabad",
        )
        assert eval_res.decision == "finalize"
        sources = {e.source for e in eval_res.evidence}
        assert "traffic" in sources
        assert "pollution" in sources
        assert eval_res.cross_analysis is not None
        assert any("Air quality" in f for f in eval_res.cross_analysis.key_findings)

    def test_case_m_response_scoping_with_pollution_evidence(self):
        """M. Response scoping still works with Pollution evidence (no metric dumps)."""
        specialist_pollution = {
            "city_avg_aqi": 64,
            "pm25": 20.8,
            "pm10": 31.7,
            "stations": ["Sanathnagar", "Zoo Park"],
            "suggested_interventions": [
                {
                    "action_type": "GREEN_INFRASTRUCTURE",
                    "description": "Vegetative canopy buffer.",
                    "expected_impact_pct": 5.0,
                    "feasibility_score": 9.0,
                }
            ],
        }

        query = "What is the PM2.5 level in Narayanguda?"
        eval_res = self.planner.evaluate_and_replan(
            objective=query,
            plan=["pollution"],
            collected_results={"pollution": specialist_pollution},
            location="Narayanguda, Hyderabad",
        )

        assert eval_res.response_scope is not None
        assert eval_res.response_scope.fields == ["pm25"]
        assert eval_res.response_scope.detail_level == "minimal"

        summary = eval_res.final_reasoning.summary if eval_res.final_reasoning else ""
        assert "20.8" in summary
        assert "PM2.5" in summary

        # Must NOT dump unrequested metrics or interventions
        assert "64" not in summary
        assert "31.7" not in summary
        assert "Sanathnagar" not in summary
        assert "GREEN_INFRASTRUCTURE" not in summary

        # Recommendation must be empty since not requested
        rec = eval_res.final_reasoning.recommendation if eval_res.final_reasoning else ""
        assert rec == ""
        assert eval_res.final_recommendation == ""

        # Internal evidence remains complete
        assert any(e.metric == "city_avg_aqi" and e.value == 64 for e in eval_res.evidence)
        assert any(e.metric == "pm10" and e.value == 31.7 for e in eval_res.evidence)
