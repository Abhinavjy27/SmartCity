"""
SUPADSP Specialist Agent — Planner Agent API Service
Exposes endpoints for gatekeeping, objective extraction, orchestrator request generation, execution, and feedback evaluation.
"""

from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from backend.agents.planner_agent.planner import PlannerAgent, get_planner_agent
from backend.agents.planner_agent.schema import (
    OrchestratorExecuteRequest,
    OrchestratorExecuteResponse,
    PlannerConstraint,
    PlannerEvaluationResponse,
    PlannerResponse,
)

app = FastAPI(
    title="SUPADSP Planner Agent Service",
    version="2.0.0",
    description="Planner Agent service generating orchestrator execution payloads and evaluating domain telemetry."
)


class QueryRequest(BaseModel):
    query: str = Field(..., description="User query or traffic scenario description")
    request_id: Optional[str] = Field(default=None, description="Optional request ID")
    location: Optional[str] = Field(default="Hyderabad Urban Corridor", description="Target location")
    workflow: Optional[str] = Field(default="monitor-detect-understand", description="Workflow name")
    priority: int = Field(default=3, ge=1, le=5, description="Priority level 1-5")
    constraints: List[PlannerConstraint] = Field(default_factory=list, description="Execution constraints")


class FeedbackPayload(BaseModel):
    request_id: str
    task_id: Optional[str] = None
    objective: str
    assigned_capabilities: List[str] = Field(default_factory=list)
    collected_results: Dict[str, Any] = Field(default_factory=dict)
    failures: Dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
def health():
    return {"agent": "Planner Agent", "status": "ONLINE"}


@app.post(
    "/api/v1/planner/plan",
    response_model=PlannerResponse,
    summary="Process user query and return validated PlannerResponse"
)
def plan_query(req: QueryRequest) -> PlannerResponse:
    planner = get_planner_agent()
    return planner.plan(req.query)


@app.post(
    "/api/v1/planner/build-orchestrator-request",
    response_model=OrchestratorExecuteRequest,
    summary="Format user query into standard OrchestratorExecuteRequest payload"
)
def build_orchestrator_request_endpoint(req: QueryRequest) -> OrchestratorExecuteRequest:
    planner = get_planner_agent()
    return planner.build_orchestrator_request(
        user_query=req.query,
        request_id=req.request_id,
        workflow=req.workflow or "monitor-detect-understand",
        priority=req.priority,
        location=req.location,
        constraints=req.constraints,
    )


@app.post(
    "/api/v1/planner/execute",
    response_model=OrchestratorExecuteResponse,
    summary="Execute plan via supervisor orchestrator"
)
def execute_plan(req: QueryRequest) -> OrchestratorExecuteResponse:
    planner = get_planner_agent()
    return planner.plan_and_execute(req.query, request_id=req.request_id)


@app.post(
    "/api/v1/planner/feedback",
    response_model=PlannerEvaluationResponse,
    summary="Evaluate collected agent telemetry against objective"
)
def feedback(req: FeedbackPayload) -> PlannerEvaluationResponse:
    planner = get_planner_agent()
    return planner.evaluate_and_replan(
        objective=req.objective,
        plan=req.assigned_capabilities,
        collected_results=req.collected_results,
        failures=req.failures,
    )
