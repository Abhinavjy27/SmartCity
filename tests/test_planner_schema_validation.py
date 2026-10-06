"""
Regression test suite for Planner schema validation, next_action normalization,
and Groq openai/gpt-oss-120b response robustness.

Verifies:
1. valid next_action string preserved
2. next_action=null handled safely without Pydantic validation failure
3. immediate-answer request (agent_requests=[]) falls back to "finalize"
4. specialist-agent request falls back to "collect_evidence"
5. multi-agent request falls back to "collect_evidence", simulation to "run_simulation"
6. malformed LLM output handling & LLMJsonParsingError hierarchy
7. Groq openai/gpt-oss-120b response payloads parsed correctly
8. LLMEvaluationDecision next_action=null fallback
9. LLMFinalReasoning next_action=null fallback
10. plan_autonomous safeguard transitions to finalize if no valid agents remain
"""

import unittest
from unittest.mock import MagicMock

from backend.agents.planner_agent.schema import (
    LLMPlanDecision,
    LLMEvaluationDecision,
    LLMFinalReasoning,
    AgentRequest,
)
from backend.agents.planner_agent.llm_client import (
    BaseLLMProvider,
    LLMError,
    LLMProviderError,
    LLMJsonParsingError,
    MockLLMProvider,
)
from backend.agents.planner_agent.planner import PlannerAgent


class TestPlannerSchemaValidation(unittest.TestCase):
    """Unit and regression tests for LLMPlanDecision and next_action handling."""

    def test_1_valid_next_action_string_preserved(self):
        """Valid next_action strings are preserved exactly as provided."""
        for action in ("collect_evidence", "run_simulation", "finalize", "abort"):
            payload = {
                "relevant": True,
                "objective": "Test objective",
                "required_capabilities": ["traffic"],
                "agent_requests": [{"agent": "traffic", "request": {"location": "Narayanguda"}}],
                "next_action": action,
            }
            decision = LLMPlanDecision.model_validate(payload)
            self.assertEqual(decision.next_action, action)
            self.assertTrue(decision.relevant)

    def test_2_next_action_null_handled_safely(self):
        """next_action=null does NOT raise Pydantic validation error."""
        payload = {
            "relevant": True,
            "objective": "Test objective",
            "required_capabilities": ["traffic"],
            "agent_requests": [{"agent": "traffic", "request": {"location": "Narayanguda"}}],
            "next_action": None,
        }
        # Must not raise ValidationError
        decision = LLMPlanDecision.model_validate(payload)
        self.assertEqual(decision.next_action, "collect_evidence")

    def test_3_immediate_answer_request_fallback_to_finalize(self):
        """Immediate answer / out-of-scope with no agents and next_action=null falls back to finalize."""
        # A: relevant=False out-of-scope query
        payload_oos = {
            "relevant": False,
            "objective": "What is the capital of France?",
            "identified_problem": None,
            "objective_understanding": None,
            "required_capabilities": [],
            "agent_requests": [],
            "next_action": None,
            "response": "Out of scope for Smart City system.",
        }
        dec_oos = LLMPlanDecision.model_validate(payload_oos)
        self.assertFalse(dec_oos.relevant)
        self.assertEqual(dec_oos.next_action, "finalize")

        # B: relevant=True clarifying / immediate answer query with no agent calls
        payload_immediate = {
            "relevant": True,
            "objective": "What is the current pollution?",
            "identified_problem": "User did not specify a location",
            "required_capabilities": [],
            "agent_requests": [],
            "next_action": None,
            "response": "Please specify the location for pollution data.",
        }
        dec_imm = LLMPlanDecision.model_validate(payload_immediate)
        self.assertTrue(dec_imm.relevant)
        self.assertEqual(dec_imm.next_action, "finalize")

    def test_4_specialist_agent_request_fallback_to_collect_evidence(self):
        """Single specialist agent with next_action=null falls back to collect_evidence."""
        for spec in ("traffic", "pollution", "weather", "energy"):
            payload = {
                "relevant": True,
                "objective": f"Check {spec}",
                "agent_requests": [{"agent": spec, "request": {"location": "Narayanguda"}}],
                "next_action": None,
            }
            dec = LLMPlanDecision.model_validate(payload)
            self.assertEqual(dec.next_action, "collect_evidence")
            self.assertIn(spec, dec.required_capabilities)

    def test_5_multi_agent_and_simulation_requests(self):
        """Multi-agent requests fall back to collect_evidence, while simulation falls back to run_simulation."""
        # Multi-agent
        multi_payload = {
            "relevant": True,
            "objective": "Correlate traffic and pollution",
            "agent_requests": [
                {"agent": "traffic", "request": {"location": "Narayanguda"}},
                {"agent": "pollution", "request": {"location": "Narayanguda", "data_mode": "current"}},
            ],
            "next_action": None,
        }
        dec_multi = LLMPlanDecision.model_validate(multi_payload)
        self.assertEqual(dec_multi.next_action, "collect_evidence")
        self.assertEqual(dec_multi.required_capabilities, ["traffic", "pollution"])

        # Simulation
        sim_payload = {
            "relevant": True,
            "objective": "Run simulation test",
            "agent_requests": [
                {"agent": "simulation", "request": {"scenario_name": "synthetic_normal"}},
            ],
            "next_action": None,
        }
        dec_sim = LLMPlanDecision.model_validate(sim_payload)
        self.assertEqual(dec_sim.next_action, "run_simulation")

    def test_6_malformed_llm_output_and_error_hierarchy(self):
        """Malformed LLM output raises LLMJsonParsingError which is a subclass of LLMProviderError."""
        self.assertTrue(issubclass(LLMJsonParsingError, LLMProviderError))
        self.assertTrue(issubclass(LLMJsonParsingError, LLMError))

        # Test planner handles provider parsing error gracefully
        class FailingLLMProvider(BaseLLMProvider):
            @property
            def provider_name(self):
                return "failing"

            def generate_json(self, system_prompt, user_prompt, **kwargs):
                raise LLMJsonParsingError("Unparseable JSON from model")

        planner = PlannerAgent(llm_provider=FailingLLMProvider())
        with self.assertRaises(LLMJsonParsingError):
            planner.plan_autonomous(objective="Test failure")

    def test_7_groq_gpt_oss_120b_real_payload_parsing(self):
        """Simulated exact outputs captured from Groq openai/gpt-oss-120b parse cleanly."""
        # Exact raw payload observed from openai/gpt-oss-120b for "What is the capital of France?"
        groq_oos_payload = {
            "relevant": False,
            "objective": "What is the capital of France?",
            "identified_problem": None,
            "objective_understanding": None,
            "required_capabilities": [],
            "agent_requests": [],
            "next_action": None,
            "confidence": None,
            "response": None,
        }
        dec_oos = LLMPlanDecision.model_validate(groq_oos_payload)
        self.assertFalse(dec_oos.relevant)
        self.assertEqual(dec_oos.next_action, "finalize")

        # Exact raw payload observed from openai/gpt-oss-120b for cross-domain traffic+pollution
        groq_multi_payload = {
            "relevant": True,
            "objective": "Assess impact of traffic congestion in Narayanguda on current air pollution",
            "identified_problem": "Potential link between traffic congestion and elevated air pollution levels",
            "objective_understanding": "User wants to understand how traffic affects pollution",
            "required_capabilities": ["traffic", "pollution"],
            "agent_requests": [
                {
                    "agent": "traffic",
                    "request": {"location": "Narayanguda, Hyderabad", "purpose": "baseline_traffic_analysis"},
                    "reason": "Obtain current traffic metrics",
                },
                {
                    "agent": "pollution",
                    "request": {"location": "Narayanguda, Hyderabad", "data_mode": "current"},
                    "reason": "Retrieve real-time AQI",
                },
            ],
            "next_action": "collect_evidence",
            "confidence": None,
            "response": None,
        }
        dec_multi = LLMPlanDecision.model_validate(groq_multi_payload)
        self.assertTrue(dec_multi.relevant)
        self.assertEqual(dec_multi.next_action, "collect_evidence")
        self.assertEqual(len(dec_multi.agent_requests), 2)

    def test_8_evaluation_decision_null_next_action(self):
        """LLMEvaluationDecision with next_action=null defaults to decision."""
        eval_payload = {
            "evidence_sufficient": True,
            "decision": "finalize",
            "next_action": None,
            "analysis": "Telemetry is sufficient to answer the objective.",
            "required_capabilities": [],
            "agent_requests": [],
        }
        dec_eval = LLMEvaluationDecision.model_validate(eval_payload)
        self.assertEqual(dec_eval.decision, "finalize")
        self.assertEqual(dec_eval.next_action, "finalize")

        eval_sim_payload = {
            "evidence_sufficient": False,
            "decision": "run_simulation",
            "next_action": None,
            "analysis": "Intervention needs SUMO verification.",
            "agent_requests": [{"agent": "simulation", "request": {"scenario": "synthetic_normal"}}],
        }
        dec_sim_eval = LLMEvaluationDecision.model_validate(eval_sim_payload)
        self.assertEqual(dec_sim_eval.decision, "run_simulation")
        self.assertEqual(dec_sim_eval.next_action, "run_simulation")

    def test_9_final_reasoning_null_next_action(self):
        """LLMFinalReasoning with next_action=null defaults to operational_implementation."""
        final_payload = {
            "summary": "Synthesized cross-domain overview.",
            "evidence_used": ["speed: 15.2 km/h"],
            "cross_domain_relationships": "Traffic congestion increases localized PM2.5.",
            "causation_likelihood": "PLAUSIBLE",
            "uncertainty_and_limitations": "Sensor coverage limited to corridor.",
            "recommendation": "Adjust traffic signal green time by +10s.",
            "next_action": None,
        }
        final_dec = LLMFinalReasoning.model_validate(final_payload)
        self.assertEqual(final_dec.next_action, "operational_implementation")

    def test_10_plan_autonomous_safeguard_fallback_on_unallowed_agent(self):
        """If all requested agents are unallowed and stripped, next_action transitions to finalize."""
        class MockUnallowedAgentProvider(BaseLLMProvider):
            @property
            def provider_name(self):
                return "mock_unallowed"

            def generate_json(self, system_prompt, user_prompt, **kwargs):
                return {
                    "relevant": True,
                    "objective": "Test unallowed agent",
                    "required_capabilities": ["unallowed_domain"],
                    "agent_requests": [
                        {"agent": "unallowed_domain", "request": {}, "reason": "invalid"}
                    ],
                    "next_action": "collect_evidence",
                }

        planner = PlannerAgent(llm_provider=MockUnallowedAgentProvider())
        decision = planner.plan_autonomous("Test query")
        self.assertEqual(decision.agent_requests, [])
        self.assertEqual(decision.required_capabilities, [])
        self.assertEqual(decision.next_action, "finalize")


if __name__ == "__main__":
    unittest.main()
