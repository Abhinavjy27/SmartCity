"""
Comprehensive Verification Test Suite for Autonomous LLM Planner.
Covers:
  - 11 Acceptance Scenarios (Natural Language, Semantic Understanding, Dynamic Boundaries)
  - Generic LLM Provider Configuration (Groq, OpenAI, Anthropic, Gemini, Mock)
"""

import os
import unittest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from backend.supervisor.main import app
from backend.agents.planner_agent.llm_client import (
    BaseLLMProvider,
    MockLLMProvider,
    GroqLLMProvider,
    OpenAILLMProvider,
    AnthropicLLMProvider,
    GeminiLLMProvider,
    LLMConfigurationError,
    LLMExecutionError,
    get_llm_provider,
)
from backend.agents.planner_agent.planner import PlannerAgent, get_planner_agent


class TestAutonomousLLMPlanner(unittest.TestCase):
    """Test suite covering all 11 acceptance scenarios."""

    def setUp(self):
        os.environ["LLM_PROVIDER"] = "mock"
        self.mock_provider = MockLLMProvider()
        self.planner = PlannerAgent(llm_provider=self.mock_provider)
        self.client = TestClient(app)

    def tearDown(self):
        os.environ.pop("LLM_PROVIDER", None)

    def test_scenario_1_narayanguda_traffic_only_natural_language(self):
        """Natural-language traffic statement selects only traffic agent without simulation."""
        decision = self.planner.plan_autonomous("Traffic is very high at Narayanguda.")
        self.assertTrue(decision.relevant)
        agents = [c.agent for c in decision.selected_agents]
        self.assertIn("traffic", agents)
        self.assertNotIn("simulation", agents)
        self.assertNotIn("weather", agents)

    def test_scenario_2_investigate_why_dynamic_resolution(self):
        """'Traffic is very high and I want to know why' dynamically invokes weather."""
        decision = self.planner.plan_autonomous("Traffic is very high at Narayanguda and I want to know why.")
        self.assertTrue(decision.relevant)
        agents = [c.agent for c in decision.selected_agents]
        self.assertIn("traffic", agents)
        self.assertIn("weather", agents)

    def test_scenario_3_reduction_intervention_triggers_simulation(self):
        """Intervention question dynamically indicates simulation necessity."""
        decision = self.planner.plan_autonomous("How can we reduce traffic congestion at Narayanguda?")
        self.assertTrue(decision.relevant)
        agents = [c.agent for c in decision.selected_agents]
        self.assertIn("traffic", agents)

    def test_scenario_4_weather_only_inquiry(self):
        """Weather-only question selects only weather agent."""
        decision = self.planner.plan_autonomous("Is it raining in Hyderabad today?")
        self.assertTrue(decision.relevant)
        agents = [c.agent for c in decision.selected_agents]
        self.assertIn("weather", agents)
        self.assertNotIn("traffic", agents)
        self.assertNotIn("simulation", agents)

    def test_scenario_5_pollution_inquiry(self):
        """Air quality query dynamically selects pollution agent."""
        decision = self.planner.plan_autonomous("What is the air quality and PM2.5 level in Nacharam?")
        self.assertTrue(decision.relevant)
        agents = [c.agent for c in decision.selected_agents]
        self.assertIn("pollution", agents)
        self.assertNotIn("traffic", agents)

    def test_scenario_6_simulation_sumo_boundary_execution(self):
        """SUMO simulation boundary receives validated payload and produces metrics."""
        ctx = self.planner.build_agent_request_context(
            capability="simulation",
            objective="Simulate signal timing optimization",
            location="Narayanguda",
            existing_results={
                "traffic": {
                    "corridors": [{"name": "Narayanguda Main", "status": "HEAVY"}]
                }
            },
        )
        self.assertTrue(ctx.is_complete)
        self.assertEqual(ctx.payload["target_location"], "Narayanguda")
        self.assertTrue(ctx.payload["signal_optimization"])

    def test_scenario_7_missing_information_no_fabrication(self):
        """Missing required field is flagged without fabricating defaults."""
        ctx = self.planner.build_agent_request_context(
            capability="traffic",
            objective="Monitor congestion",
            location="",  # No location provided
        )
        self.assertFalse(ctx.is_complete)
        self.assertIn("location", ctx.missing_fields)

    def test_scenario_8_malformed_specialist_output(self):
        """Corrupted specialist output is rejected by defensive validation."""
        with self.assertRaises(ValueError):
            self.planner.validate_agent_output("traffic", {"unknown_key": 123})

    def test_scenario_9_llm_invalid_json_handling(self):
        """Invalid JSON from LLM raises clean error without crashing."""
        mock_bad = MagicMock(spec=BaseLLMProvider)
        mock_bad.generate_json.side_effect = LLMExecutionError("Malformed JSON response")
        bad_planner = PlannerAgent(llm_provider=mock_bad)
        with self.assertRaises(LLMExecutionError):
            bad_planner.plan_autonomous("Traffic jam at Begumpet")

    def test_scenario_10_no_llm_api_key_handling(self):
        """Missing API key raises LLMConfigurationError with clean message."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "groq", "LLM_API_KEY": ""}):
            with self.assertRaises(LLMConfigurationError):
                get_llm_provider()

    def test_scenario_11_different_phrasings_semantic_understanding(self):
        """Semantic phrasing variations all resolve correctly."""
        phrasings = [
            "Vehicles are stuck for kilometers on the flyover",
            "Severe bottleneck near the tech corridor",
            "Commute travel time is excessively delayed",
        ]
        for p in phrasings:
            dec = self.planner.plan_autonomous(p)
            self.assertTrue(dec.relevant, f"Failed for phrasing: {p}")
            self.assertIn("traffic", [c.agent for c in dec.selected_agents])


class TestGenericLLMProviderConfiguration(unittest.TestCase):
    """Test generic configuration across providers."""

    def test_groq_receives_generic_llm_api_key(self):
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "groq",
            "LLM_MODEL": "llama-3.3-70b-versatile",
            "LLM_API_KEY": "test-generic-key-groq",
        }):
            provider = get_llm_provider()
            self.assertIsInstance(provider, GroqLLMProvider)
            self.assertEqual(provider.api_key, "test-generic-key-groq")
            self.assertEqual(provider.model, "llama-3.3-70b-versatile")

    def test_openai_receives_generic_llm_api_key(self):
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "openai",
            "LLM_MODEL": "gpt-4o",
            "LLM_API_KEY": "test-generic-key-openai",
        }):
            provider = get_llm_provider()
            self.assertIsInstance(provider, OpenAILLMProvider)
            self.assertEqual(provider.api_key, "test-generic-key-openai")
            self.assertEqual(provider.model, "gpt-4o")

    def test_anthropic_receives_generic_llm_api_key(self):
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "anthropic",
            "LLM_MODEL": "claude-3-5-sonnet",
            "LLM_API_KEY": "test-generic-key-anthropic",
        }):
            provider = get_llm_provider()
            self.assertIsInstance(provider, AnthropicLLMProvider)
            self.assertEqual(provider.api_key, "test-generic-key-anthropic")
            self.assertEqual(provider.model, "claude-3-5-sonnet")

    def test_gemini_receives_generic_llm_api_key(self):
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "gemini",
            "LLM_MODEL": "gemini-1.5-pro",
            "LLM_API_KEY": "test-generic-key-gemini",
        }):
            provider = get_llm_provider()
            self.assertIsInstance(provider, GeminiLLMProvider)
            self.assertEqual(provider.api_key, "test-generic-key-gemini")
            self.assertEqual(provider.model, "gemini-1.5-pro")

    def test_mock_llm_provider_works(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "mock"}):
            provider = get_llm_provider()
            self.assertIsInstance(provider, MockLLMProvider)

    def test_llm_model_is_configurable(self):
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "groq",
            "LLM_MODEL": "custom-model-id",
            "LLM_API_KEY": "valid-key",
        }):
            provider = get_llm_provider()
            self.assertEqual(provider.model, "custom-model-id")

    def test_missing_llm_api_key_raises_configuration_error(self):
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "groq",
            "LLM_API_KEY": "",
        }, clear=True):
            with self.assertRaises(LLMConfigurationError):
                get_llm_provider()

    def test_invalid_llm_provider_raises_configuration_error(self):
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "unsupported_llm_corp",
            "LLM_API_KEY": "valid-key",
        }):
            with self.assertRaises(LLMConfigurationError):
                get_llm_provider()

    def test_no_automatic_fallback_on_provider_failure(self):
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "groq",
            "LLM_API_KEY": "test-key",
            "LLM_MODEL": "test-model",
        }):
            provider = get_llm_provider()
            with patch.object(provider, "generate_json", side_effect=LLMExecutionError("Service unavailable")):
                planner = PlannerAgent(llm_provider=provider)
                with self.assertRaises(LLMExecutionError):
                    planner.plan_autonomous("Traffic is high")


class TestCycleBasedPlannerAcceptance(unittest.TestCase):
    """
    Verification suite for the redesigned cycle-based LLM Planner architecture.
    Tests TEST A through TEST F as specified in the architectural requirements.
    """

    def setUp(self):
        os.environ["LLM_PROVIDER"] = "mock"
        self.mock_provider = MockLLMProvider()
        self.planner = PlannerAgent(llm_provider=self.mock_provider)
        self.client = TestClient(app)

    def tearDown(self):
        os.environ.pop("LLM_PROVIDER", None)

    def test_test_a_traffic_only(self):
        """
        TEST A: 'Traffic is very high at Narayanguda.'
        Expected: traffic selected; next_action is collect_evidence.
        """
        # 1. Unit test via PlannerAgent
        decision = self.planner.plan_autonomous("Traffic is very high at Narayanguda.")
        self.assertTrue(decision.relevant)
        self.assertIn("traffic", decision.required_capabilities)
        self.assertNotIn("weather", decision.required_capabilities)
        self.assertNotIn("pollution", decision.required_capabilities)
        self.assertNotIn("simulation", decision.required_capabilities)
        self.assertEqual(decision.next_action, "collect_evidence")
        self.assertEqual(len(decision.agent_requests), 1)
        self.assertEqual(decision.agent_requests[0].agent, "traffic")
        self.assertIn("location", decision.agent_requests[0].request)

        # 2. HTTP Endpoint test via /agents/planner/plan
        res = self.client.post("/agents/planner/plan", json={
            "request_id": "TEST-A-001",
            "objective": "Traffic is very high at Narayanguda.",
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["required_capabilities"], ["traffic"])
        self.assertEqual(data["next_action"], "collect_evidence")
        self.assertNotIn("scenarios", data)
        self.assertNotIn("likely_causes", data)

    def test_test_b_weather_only_no_traffic_leakage(self):
        """
        TEST B: 'What are the current weather conditions at Narayanguda?'
        Expected: weather selected; NO unrelated traffic information, causes, or scenarios.
        """
        # 1. Unit test via PlannerAgent
        decision = self.planner.plan_autonomous("What are the current weather conditions at Narayanguda?")
        self.assertTrue(decision.relevant)
        self.assertIn("weather", decision.required_capabilities)
        self.assertNotIn("traffic", decision.required_capabilities)
        self.assertNotIn("simulation", decision.required_capabilities)
        self.assertEqual(decision.next_action, "collect_evidence")
        self.assertEqual(decision.agent_requests[0].agent, "weather")

        # 2. HTTP Endpoint test via /agents/planner/plan
        res = self.client.post("/agents/planner/plan", json={
            "request_id": "TEST-B-002",
            "objective": "What are the current weather conditions at Narayanguda?",
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["required_capabilities"], ["weather"])
        self.assertEqual(data["next_action"], "collect_evidence")
        # Ensure no traffic-specific defaults leak into weather responses
        self.assertNotIn("scenarios", data)
        self.assertNotIn("likely_causes", data)
        self.assertNotIn("required_data", data)
        for req in data["agent_requests"]:
            self.assertEqual(req["agent"], "weather")

    def test_test_c_pollution_only_no_traffic_scenarios(self):
        """
        TEST C: 'What is the current pollution level at Narayanguda?'
        Expected: pollution selected; NO unrelated traffic scenarios.
        """
        # 1. Unit test via PlannerAgent
        decision = self.planner.plan_autonomous("What is the current pollution level at Narayanguda?")
        self.assertTrue(decision.relevant)
        self.assertIn("pollution", decision.required_capabilities)
        self.assertNotIn("traffic", decision.required_capabilities)
        self.assertNotIn("simulation", decision.required_capabilities)
        self.assertEqual(decision.next_action, "collect_evidence")

        # 2. HTTP Endpoint test via /agents/planner/plan
        res = self.client.post("/agents/planner/plan", json={
            "request_id": "TEST-C-003",
            "objective": "What is the current pollution level at Narayanguda?",
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["required_capabilities"], ["pollution"])
        self.assertEqual(data["next_action"], "collect_evidence")
        self.assertNotIn("scenarios", data)

    def test_test_d_reduction_traffic_first_then_simulation(self):
        """
        TEST D: 'How can we reduce traffic congestion at Narayanguda?'
        Expected: traffic is considered first (baseline). Planner can subsequently decide
        whether simulation is required in the evaluation cycle.
        """
        # Cycle 1: Initial planning considers traffic first
        decision = self.planner.plan_autonomous("How can we reduce traffic congestion at Narayanguda?")
        self.assertTrue(decision.relevant)
        self.assertIn("traffic", decision.required_capabilities)
        self.assertEqual(decision.next_action, "collect_evidence")

        # Cycle 2: Feedback provides baseline traffic evidence -> Planner decides simulation is required
        res_fb = self.client.post("/agents/planner/feedback", json={
            "request_id": "TEST-D-004",
            "objective": "How can we reduce traffic congestion at Narayanguda?",
            "location": "Narayanguda",
            "agent": "traffic",
            "result": {
                "source": "SUMO",
                "scenario": "baseline",
                "metrics": {
                    "active_vehicles": 412,
                    "average_speed_kmh": 16.5,
                    "average_delay_sec": 52.1,
                    "congestion_index": 78.4
                }
            }
        })
        self.assertEqual(res_fb.status_code, 200)
        fb_data = res_fb.json()
        self.assertEqual(fb_data["decision"], "run_simulation")
        self.assertEqual(fb_data["next_action"], "run_simulation")
        self.assertIn("simulation", fb_data["required_capabilities"])

    def test_test_e_interventions_planning_simulation_relevant(self):
        """
        TEST E: 'How can we reduce traffic congestion using different interventions?'
        Expected: Planner can decide that simulation/intervention testing across scenarios is relevant.
        """
        decision = self.planner.plan_autonomous("How can we reduce traffic congestion using different interventions?")
        self.assertTrue(decision.relevant)
        self.assertIn("simulation", decision.required_capabilities)
        self.assertEqual(decision.next_action, "run_simulation")
        self.assertIsNotNone(decision.scenarios)
        self.assertTrue(len(decision.scenarios) >= 2)

    def test_test_f_feedback_traffic_result_dynamic_evaluation(self):
        """
        TEST F: Provide a Traffic Agent result through feedback.
        Expected: Planner evaluates the result and produces a next action dynamically.
        """
        res = self.client.post("/agents/planner/feedback", json={
            "request_id": "TEST-F-005",
            "objective": "Check current traffic status at Narayanguda",
            "location": "Narayanguda",
            "agent": "traffic",
            "result": {
                "source": "SUMO",
                "scenario": "baseline",
                "metrics": {
                    "active_vehicles": 342,
                    "average_speed_kmh": 24.7,
                    "average_delay_sec": 38.2,
                    "congestion_index": 0.61
                }
            }
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("decision", data)
        self.assertIn("next_action", data)
        self.assertEqual(data["next_action"], "finalize")
        self.assertEqual(data["status"], "SUCCESS")
        self.assertIn("analysis", data["insights"])

