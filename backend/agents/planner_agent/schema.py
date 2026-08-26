"""
Pydantic schemas for Planner Agent output validation.
Enforces strict structured JSON format for relevant plans, gatekeeping rejections, and evaluation/re-planning loops.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, model_validator


class PlannerResponse(BaseModel):
    """
    Structured output schema for the Planner Agent's initial plan generation and gatekeeping.
    """
    relevant: bool = Field(
        ...,
        description="Whether the user query is relevant to the Smart City traffic optimization domain."
    )
    domain: Optional[Literal["traffic"]] = Field(
        default=None,
        description="Domain of the query. Currently only 'traffic' is supported. Null if irrelevant."
    )
    objective: Optional[str] = Field(
        default=None,
        description="Concise, extracted planner objective in natural language. Null if irrelevant."
    )
    plan: List[str] = Field(
        default_factory=list,
        description="Ordered list of execution steps for the orchestrator and domain agents. Empty if irrelevant."
    )
    response: Optional[str] = Field(
        default=None,
        description="User-facing explanation message when the query is rejected or out of scope."
    )

    @model_validator(mode="after")
    def validate_gatekeeping_consistency(self) -> PlannerResponse:
        """
        Validate logical consistency between relevant flag and associated fields.
        """
        if self.relevant:
            if not self.domain:
                self.domain = "traffic"
            if not self.objective or not self.objective.strip():
                raise ValueError("Relevant query must specify an 'objective'.")
            if not self.plan or len(self.plan) == 0:
                raise ValueError("Relevant query must contain at least one step in 'plan'.")
            self.response = None
        else:
            self.domain = None
            self.objective = None
            self.plan = []
            if not self.response or not self.response.strip():
                self.response = "This question is outside the scope of the Smart City system."
        return self


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
