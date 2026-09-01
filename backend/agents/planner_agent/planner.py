"""
Core Planner Agent implementation for the SUPADSP Smart City platform.
Receives user natural-language queries, runs gatekeeping checks, extracts objectives, generates structured execution plans,
and performs result evaluation / dynamic re-planning.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.agents.planner_agent.llm_client import LLMClient
from backend.agents.planner_agent.prompts import (
    PLANNER_EVALUATION_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    build_evaluation_prompt,
)
from backend.agents.planner_agent.schema import (
    OrchestratorExecuteRequest,
    OrchestratorExecuteResponse,
    PlannerConstraint,
    PlannerEvaluationResponse,
    PlannerResponse,
)

logger = logging.getLogger("planner_agent")


def _create_fallback_planner_response(
    status: str = "REJECTED",
    response_text: str = "This question is outside the scope of the Smart City system.",
    relevant: bool = False,
    task_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> PlannerResponse:
    now_iso = datetime.now(timezone.utc).isoformat()
    tid = task_id or f"task_{uuid.uuid4().hex[:8]}"
    rid = request_id or f"req_{uuid.uuid4().hex[:8]}"
    return PlannerResponse(
        task_id=tid,
        request_id=rid,
        status=status,
        assigned_capabilities=[],
        dispatched_agents=[],
        collected_results={},
        failures={},
        planner_feedback={
            "relevant": relevant,
            "domain": None,
            "objective": None,
            "plan": [],
            "response": response_text,
        },
        created_at=now_iso,
    )


class PlannerAgent:
    """
    Planner Agent acts as the front gatekeeper, strategic planning brain, and re-planning engine.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    def plan(self, user_query: str) -> PlannerResponse:
        """
        Process a user query and return a validated PlannerResponse.

        Steps:
        1. Validate query input.
        2. Execute LLM call with system prompts and JSON constraint.
        3. Parse and validate JSON into Pydantic PlannerResponse schema.
        4. Return structured response (gatekeeping or execution plan).
        """
        if not user_query or not user_query.strip():
            return _create_fallback_planner_response(
                status="REJECTED",
                response_text="Please provide a valid query or description of the urban traffic situation.",
                relevant=False,
            )

        sanitized_query = user_query.strip()

        try:
            # 1. Call LLM
            raw_json_str = self.llm_client.generate_json_plan(
                system_prompt=PLANNER_SYSTEM_PROMPT,
                user_query=sanitized_query,
            )

            # 2. Parse raw JSON
            parsed_dict = json.loads(raw_json_str)

            # 3. Ensure required task metadata fields exist
            now_iso = datetime.now(timezone.utc).isoformat()
            if "task_id" not in parsed_dict or not parsed_dict["task_id"]:
                parsed_dict["task_id"] = f"task_{uuid.uuid4().hex[:8]}"
            if "request_id" not in parsed_dict or not parsed_dict["request_id"]:
                parsed_dict["request_id"] = f"req_{uuid.uuid4().hex[:8]}"
            if "created_at" not in parsed_dict or not parsed_dict["created_at"]:
                parsed_dict["created_at"] = now_iso

            # Legacy compatibility for flat LLM JSON
            if "planner_feedback" not in parsed_dict and ("relevant" in parsed_dict or "objective" in parsed_dict):
                relevant = parsed_dict.get("relevant", True)
                parsed_dict["planner_feedback"] = {
                    "relevant": relevant,
                    "domain": parsed_dict.get("domain", "traffic" if relevant else None),
                    "objective": parsed_dict.get("objective"),
                    "plan": parsed_dict.get("plan", []),
                    "response": parsed_dict.get("response"),
                }
                if "status" not in parsed_dict:
                    parsed_dict["status"] = "QUEUED" if relevant else "REJECTED"
                if "assigned_capabilities" not in parsed_dict:
                    parsed_dict["assigned_capabilities"] = ["traffic_flow_analysis", "signal_optimization"] if relevant else []
                if "dispatched_agents" not in parsed_dict:
                    parsed_dict["dispatched_agents"] = ["TrafficAgent", "SimulationAgent"] if relevant else []

            # 4. Validate against Pydantic schema
            validated_response = PlannerResponse.model_validate(parsed_dict)
            return validated_response

        except json.JSONDecodeError as exc:
            logger.error(f"Failed to decode LLM response as JSON: {exc}")
            return _create_fallback_planner_response(
                status="FAILED",
                response_text="The system could not parse the planner output. Please try rephrasing your request.",
                relevant=False,
            )
        except Exception as exc:
            logger.error(f"Planner Agent error: {exc}")
            return _create_fallback_planner_response(
                status="FAILED",
                response_text=f"Error generating plan: {str(exc)}",
                relevant=False,
            )

    def evaluate_and_replan(
        self,
        objective: str,
        plan: List[str],
        collected_results: Dict[str, Any],
        failures: Optional[Dict[str, Any]] = None,
    ) -> PlannerEvaluationResponse:
        """
        Evaluate specialist agent telemetry against the original objective.
        Determines whether the goal was achieved, generates a final recommendation, or drafts a revised plan.
        """
        eval_prompt = build_evaluation_prompt(
            objective=objective,
            plan=plan,
            collected_results=collected_results,
            failures=failures or {},
        )

        try:
            raw_json_str = self.llm_client.generate_json_plan(
                system_prompt=PLANNER_EVALUATION_SYSTEM_PROMPT,
                user_query=eval_prompt,
            )
            parsed_dict = json.loads(raw_json_str)
            return PlannerEvaluationResponse.model_validate(parsed_dict)

        except Exception as exc:
            logger.error(f"Evaluation & Re-planning error: {exc}")
            # Resilient fallback if LLM evaluation fails
            has_failures = bool(failures)
            return PlannerEvaluationResponse(
                goal_achieved=not has_failures,
                decision="PROCEED_TO_RECOMMENDATION" if not has_failures else "RE_PLAN",
                analysis=f"Evaluated with collected metrics. Fallback note: {str(exc)}",
                final_recommendation="Implement adaptive signal timing based on real-time traffic sensor telemetry." if not has_failures else None,
                revised_plan=["Retry telemetry retrieval", "Check traffic sensor connectivity"] if has_failures else [],
                confidence=0.85,
            )

    def build_orchestrator_request(
        self,
        user_query: str,
        request_id: Optional[str] = None,
        workflow: str = "monitor-detect-understand",
        priority: int = 3,
        location: Optional[str] = None,
        constraints: Optional[List[PlannerConstraint]] = None,
    ) -> OrchestratorExecuteRequest:
        """
        Convert a user query into a validated OrchestratorExecuteRequest schema payload.
        """
        plan_result = self.plan(user_query)
        req_id = request_id or plan_result.request_id

        steps = plan_result.plan if plan_result.plan else [
            "Collect real-time traffic telemetry and vehicle counts",
            "Run SUMO congestion simulation for target corridor",
            "Generate optimized signal split recommendations",
        ]

        domains = [plan_result.domain] if plan_result.domain else ["traffic"]

        return OrchestratorExecuteRequest(
            request_id=req_id,
            workflow=workflow,
            steps=steps,
            priority=priority,
            objective=plan_result.objective or user_query,
            location=location or "Hyderabad Urban Corridor",
            domains=domains,
            constraints=constraints or [],
        )

    def plan_and_execute(
        self,
        user_query: str,
        request_id: Optional[str] = None,
    ) -> OrchestratorExecuteResponse:
        """
        Full end-to-end flow: Generate execution plan and run via supervisor orchestrator.
        """
        orch_req = self.build_orchestrator_request(user_query, request_id=request_id)
        try:
            from backend.supervisor.main import OrchestratorExecuteRequest as SupervisorOrchReq, execute_orchestrator
            supervisor_payload = SupervisorOrchReq.model_validate(orch_req.model_dump())
            supervisor_res = execute_orchestrator(supervisor_payload)
            return OrchestratorExecuteResponse.model_validate(supervisor_res.model_dump())
        except Exception as exc:
            logger.warning(f"Supervisor orchestrator dispatch error, returning standalone plan: {exc}")
            return self.plan(user_query)


# Default factory function
def get_planner_agent() -> PlannerAgent:
    return PlannerAgent()

