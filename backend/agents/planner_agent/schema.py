"""
Pydantic schemas for Planner Agent output validation.
Enforces strict structured JSON format for relevant plans, gatekeeping rejections, and evaluation/re-planning loops.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, model_validator


class PlannerResponse(BaseModel):
    """
    Structured output schema for the Planner Agent conforming to the Task Execution JSON standard.
    """
    task_id: str = Field(
        ...,
        description="Unique ID for the created planning task."
    )
    request_id: str = Field(
        ...,
        description="Unique request identifier."
    )
    status: Literal["QUEUED", "IN_PROGRESS", "COMPLETED", "FAILED", "REJECTED"] = Field(
        default="QUEUED",
        description="Current status of the planning task."
    )
    assigned_capabilities: List[str] = Field(
        default_factory=list,
        description="Capabilities assigned by the planner to address the request."
    )
    dispatched_agents: List[str] = Field(
        default_factory=list,
        description="Specialist agents dispatched to perform the plan steps."
    )
    collected_results: Dict[str, Any] = Field(
        default_factory=dict,
        description="Collected execution results from specialist agents."
    )
    failures: Dict[str, Any] = Field(
        default_factory=dict,
        description="Failures or errors encountered during step execution."
    )
    planner_feedback: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Feedback, reasoning, objective, and domain gatekeeping details from the planner."
    )
    created_at: str = Field(
        ...,
        description="ISO 8601 timestamp string when the task was created."
    )

    @property
    def relevant(self) -> bool:
        if self.planner_feedback and isinstance(self.planner_feedback, dict):
            return self.planner_feedback.get("relevant", self.status != "REJECTED")
        return self.status != "REJECTED"

    @property
    def domain(self) -> Optional[str]:
        if self.planner_feedback and isinstance(self.planner_feedback, dict):
            return self.planner_feedback.get("domain")
        return None

    @property
    def objective(self) -> Optional[str]:
        if self.planner_feedback and isinstance(self.planner_feedback, dict):
            return self.planner_feedback.get("objective")
        return None

    @property
    def plan(self) -> List[str]:
        if self.planner_feedback and isinstance(self.planner_feedback, dict):
            return self.planner_feedback.get("plan", [])
        return []

    @property
    def response(self) -> Optional[str]:
        if self.planner_feedback and isinstance(self.planner_feedback, dict):
            return self.planner_feedback.get("response")
        return None


class PlannerEvaluationResponse(BaseModel):
    """
    Structured output schema for the Planner Agent's result evaluation and re-planning step.
    """
    goal_achieved: bool = Field(
        ...,
        description="Whether the collected specialist agent data and simulation results satisfy the planning objective."
    )
    decision: Literal["PROCEED_TO_RECOMMENDATION", "RE_PLAN", "ABORT"] = Field(
        ...,
        description="Next strategic decision: proceed to final recommendation, trigger re-planning, or abort."
    )
    analysis: str = Field(
        ...,
        description="Strategic analysis explaining how the returned data addresses the bottleneck, delays, or traffic conditions."
    )
    final_recommendation: Optional[str] = Field(
        default=None,
        description="Actionable policy or signal recommendation for municipal planners if goal is achieved."
    )
    revised_plan: List[str] = Field(
        default_factory=list,
        description="Ordered list of revised execution steps if the goal was not achieved and re-planning is required."
    )
    confidence: float = Field(
        default=0.90,
        ge=0.0,
        le=1.0,
        description="Planner confidence score in this evaluation."
    )
