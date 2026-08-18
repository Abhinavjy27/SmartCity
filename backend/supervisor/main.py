from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Path, Query, status
from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class Domain(str, Enum):
    TRAFFIC = "traffic"
    FLOOD = "flood"
    ENERGY = "energy"
    WEATHER = "weather"


class PlanningStatus(str, Enum):
    RECEIVED = "RECEIVED"
    PLANNING = "PLANNING"
    ORCHESTRATING = "ORCHESTRATING"
    RUNNING_MODELS = "RUNNING_MODELS"
    VERIFYING = "VERIFYING"
    RECOMMENDING = "RECOMMENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AlertStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    DISMISSED = "DISMISSED"
    RESOLVED = "RESOLVED"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RecommendationStatus(str, Enum):
    GENERATED = "GENERATED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"
    IMPLEMENTED = "IMPLEMENTED"
    VERIFIED = "VERIFIED"


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    correlation_id: str
    timestamp: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class PlannerIdentity(BaseModel):
    planner_id: str = Field(..., description="Planner/user identifier")
    department: str = Field(..., description="Owning department")
    role: str = Field(..., description="Role used for policy and approval checks")


class Constraint(BaseModel):
    name: str
    value: Any
    unit: Optional[str] = None


class PlanningRequestCreate(BaseModel):
    objective: str = Field(..., description="Planner objective in natural language")
    location: str = Field(..., description="Primary location/corridor/zone/ward")
    time_horizon: str = Field(..., description="Requested temporal horizon, e.g. peak-hour, 24h")
    planner: PlannerIdentity
    constraints: List[Constraint] = Field(default_factory=list)
    requested_domains: List[Domain] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)


class PlanningRequestAccepted(BaseModel):
    request_id: str
    status: PlanningStatus
    created_at: str
    correlation_id: str


class PlanningRequestDetail(BaseModel):
    request_id: str
    status: PlanningStatus
    objective: str
    location: str
    requested_domains: List[Domain]
    orchestrator_task_id: Optional[str] = None
    recommendation_id: Optional[str] = None
    created_at: str
    updated_at: str


class OrchestratorExecuteRequest(BaseModel):
    request_id: str
    workflow: str = Field(..., description="Workflow name, e.g. monitor-detect-understand")
    steps: List[str] = Field(default_factory=list, description="Optional explicit execution steps")
    priority: int = Field(default=3, ge=1, le=5)


class OrchestratorExecuteResponse(BaseModel):
    task_id: str
    request_id: str
    status: TaskStatus
    assigned_capabilities: List[str]
    created_at: str


class OrchestratorTaskDetail(BaseModel):
    task_id: str
    request_id: str
    status: TaskStatus
    current_step: str
    completed_steps: List[str]
    pending_steps: List[str]
    started_at: str
    updated_at: str


class PlannerPlanRequest(BaseModel):
    request_id: str
    objective: str
    location: str
    domains: List[Domain]
    constraints: List[Constraint] = Field(default_factory=list)


class ScenarioDefinition(BaseModel):
    scenario_id: str
    label: str
    assumptions: List[str]


class PlannerPlanResponse(BaseModel):
    request_id: str
    objective: str
    likely_causes: List[str]
    interventions: List[str]
    required_data: List[str]
    scenarios: List[ScenarioDefinition]
    planner_confidence: float = Field(..., ge=0, le=1)


class KnowledgeSearchRequest(BaseModel):
    request_id: str
    query: str
    filters: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeDocument(BaseModel):
    doc_id: str
    title: str
    source: str
    excerpt: str
    relevance_score: float = Field(..., ge=0, le=1)


class KnowledgeSearchResponse(BaseModel):
    request_id: str
    results: List[KnowledgeDocument]


class DataDiscoveryRequest(BaseModel):
    request_id: str
    domains: List[Domain]
    location: str
    needed_signals: List[str]


class DatasetDescriptor(BaseModel):
    dataset_id: str
    domain: Domain
    source: str
    freshness_minutes: int
    schema_ref: str


class DataDiscoveryResponse(BaseModel):
    request_id: str
    datasets: List[DatasetDescriptor]


class DataRetrievalRequest(BaseModel):
    request_id: str
    dataset_ids: List[str]
    time_range: Dict[str, str] = Field(default_factory=dict)


class DataRetrievalResponse(BaseModel):
    request_id: str
    records_uri: str
    record_count: int
    fetched_at: str


class ModelEvaluationRequest(BaseModel):
    request_id: str
    location: str
    scenario: str
    inputs: Dict[str, Any]


class ModelEvaluationResponse(BaseModel):
    request_id: str
    domain: Domain
    model_id: str
    model_version: str
    status: TaskStatus
    outputs: Dict[str, Any]
    confidence: float = Field(..., ge=0, le=1)


class MonitoringStatusResponse(BaseModel):
    generated_at: str
    domains: Dict[str, str] = Field(..., description="Map of domain name to component status")
    active_alerts: int
    unhealthy_components: List[str]


class MonitoringEvent(BaseModel):
    event_id: str
    timestamp: str
    domain: Domain
    severity: Severity
    type: str
    summary: str


class MonitoringEventsResponse(BaseModel):
    events: List[MonitoringEvent]


class Alert(BaseModel):
    alert_id: str
    status: AlertStatus
    severity: Severity
    domain: Domain
    location: str
    title: str
    message: str
    created_at: str
    updated_at: str


class AlertActionRequest(BaseModel):
    actor_id: str
    reason: Optional[str] = None


class AlertActionResponse(BaseModel):
    alert_id: str
    status: AlertStatus
    acted_by: str
    acted_at: str


class SimulationCreateRequest(BaseModel):
    request_id: str
    name: str
    location: str
    scenarios: List[str]
    domains: List[Domain]


class SimulationCreateResponse(BaseModel):
    simulation_id: str
    status: TaskStatus
    queued_at: str


class SimulationStatusResponse(BaseModel):
    simulation_id: str
    status: TaskStatus
    progress_pct: int = Field(..., ge=0, le=100)
    started_at: Optional[str] = None
    updated_at: str


class SimulationResultResponse(BaseModel):
    simulation_id: str
    status: TaskStatus
    comparison_summary: Dict[str, Any]
    ranked_scenarios: List[Dict[str, Any]]
    generated_at: str


class VerificationRequest(BaseModel):
    request_id: str
    recommendation_id: str
    checks: List[str]


class VerificationResponse(BaseModel):
    request_id: str
    recommendation_id: str
    verification_status: str
    passed_checks: List[str]
    failed_checks: List[str]


class FailSafeCheckRequest(BaseModel):
    request_id: str
    task_id: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class FailSafeCheckResponse(BaseModel):
    request_id: str
    safe_to_proceed: bool
    guardrail_results: Dict[str, str]


class Recommendation(BaseModel):
    recommendation_id: str
    request_id: str
    status: RecommendationStatus
    objective: str
    location: str
    summary: str
    alternatives: List[str]
    expected_impacts: Dict[str, Any]
    confidence: float = Field(..., ge=0, le=1)
    created_at: str
    updated_at: str


class RecommendationDecisionRequest(BaseModel):
    actor_id: str
    reason: Optional[str] = None


class RecommendationModifyRequest(BaseModel):
    actor_id: str
    modifications: Dict[str, Any]
    reason: str


class RecommendationDecisionResponse(BaseModel):
    recommendation_id: str
    status: RecommendationStatus
    updated_at: str


class DigitalTwinStateResponse(BaseModel):
    generated_at: str
    locations: List[Dict[str, Any]]


class DigitalTwinLocationStateResponse(BaseModel):
    location: str
    generated_at: str
    state: Dict[str, Any]


def not_found(code: str, message: str, details: Dict[str, Any]) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=ErrorResponse(
            error=ErrorDetail(
                code=code,
                message=message,
                details=details,
                correlation_id=make_id("corr"),
                timestamp=utc_now_iso(),
            )
        ).model_dump(),
    )


app = FastAPI(
    title="SUPADSP Unified API Contract",
    version="1.0.0-contract",
    description=(
        "Contract-first API surface for Smart City planning workflows. "
        "This OpenAPI defines integration boundaries between frontend, orchestrator, planner, "
        "domain models (traffic/flood/energy/weather), and specialist internal agents."
    ),
)


@app.exception_handler(HTTPException)
async def contract_http_exception_handler(request, exc: HTTPException):
    """Return contract error envelopes as the response body (no FastAPI 'detail' wrapper)."""
    from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
    from fastapi.responses import JSONResponse

    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail, headers=exc.headers)

    return await default_http_exception_handler(request, exc)

planning_requests: Dict[str, PlanningRequestDetail] = {}
orchestrator_tasks: Dict[str, OrchestratorTaskDetail] = {}
alerts_store: Dict[str, Alert] = {}
simulations_store: Dict[str, SimulationStatusResponse] = {}
recommendations_store: Dict[str, Recommendation] = {}


@app.get("/health", tags=["System"], summary="Contract service health")
def health() -> Dict[str, str]:
    return {"service": "supervisor-contract", "status": "ONLINE", "timestamp": utc_now_iso()}


@app.post(
    "/planning/requests",
    tags=["Public API - Planning"],
    response_model=PlanningRequestAccepted,
    summary="Submit planning request",
)
def create_planning_request(payload: PlanningRequestCreate) -> PlanningRequestAccepted:
    request_id = make_id("planreq")
    created_at = utc_now_iso()
    planning_requests[request_id] = PlanningRequestDetail(
        request_id=request_id,
        status=PlanningStatus.RECEIVED,
        objective=payload.objective,
        location=payload.location,
        requested_domains=payload.requested_domains,
        created_at=created_at,
        updated_at=created_at,
    )
    return PlanningRequestAccepted(
        request_id=request_id,
        status=PlanningStatus.RECEIVED,
        created_at=created_at,
        correlation_id=make_id("corr"),
    )


@app.get(
    "/planning/requests/{request_id}",
    tags=["Public API - Planning"],
    response_model=PlanningRequestDetail,
    responses={404: {"model": ErrorResponse}},
    summary="Get planning request status",
)
def get_planning_request(request_id: str = Path(..., min_length=8)) -> PlanningRequestDetail:
    detail = planning_requests.get(request_id)
    if detail is None:
        raise not_found("PLANNING_REQUEST_NOT_FOUND", "Planning request not found", {"request_id": request_id})
    return detail


@app.post(
    "/agents/orchestrator/execute",
    tags=["Internal API - Orchestrator"],
    response_model=OrchestratorExecuteResponse,
    summary="Execute orchestrator workflow",
)
def execute_orchestrator(payload: OrchestratorExecuteRequest) -> OrchestratorExecuteResponse:
    task_id = make_id("orctask")
    created_at = utc_now_iso()
    completed_steps: List[str] = []
    pending_steps = payload.steps if payload.steps else ["monitor", "detect", "understand", "predict", "simulate", "verify", "recommend"]
    orchestrator_tasks[task_id] = OrchestratorTaskDetail(
        task_id=task_id,
        request_id=payload.request_id,
        status=TaskStatus.QUEUED,
        current_step=pending_steps[0],
        completed_steps=completed_steps,
        pending_steps=pending_steps,
        started_at=created_at,
        updated_at=created_at,
    )
    return OrchestratorExecuteResponse(
        task_id=task_id,
        request_id=payload.request_id,
        status=TaskStatus.QUEUED,
        assigned_capabilities=["planner_plan", "data_discovery", "model_evaluation", "verification"],
        created_at=created_at,
    )


@app.get(
    "/agents/orchestrator/tasks/{task_id}",
    tags=["Internal API - Orchestrator"],
    response_model=OrchestratorTaskDetail,
    responses={404: {"model": ErrorResponse}},
    summary="Get orchestrator task status",
)
def get_orchestrator_task(task_id: str = Path(..., min_length=8)) -> OrchestratorTaskDetail:
    detail = orchestrator_tasks.get(task_id)
    if detail is None:
        raise not_found("ORCHESTRATOR_TASK_NOT_FOUND", "Orchestrator task not found", {"task_id": task_id})
    return detail


@app.post(
    "/agents/planner/plan",
    tags=["Internal API - Planner"],
    response_model=PlannerPlanResponse,
    summary="Generate planning strategy",
)
def planner_plan(payload: PlannerPlanRequest) -> PlannerPlanResponse:
    return PlannerPlanResponse(
        request_id=payload.request_id,
        objective=payload.objective,
        likely_causes=[
            "peak-hour demand concentration",
            "intersection bottlenecks",
            "signal-cycle imbalance",
            "weather-induced throughput drop",
        ],
        interventions=[
            "adaptive signal optimization",
            "dynamic rerouting advisories",
            "lane-use adjustment",
            "traffic personnel deployment",
        ],
        required_data=[
            "traffic volumes",
            "signal configuration",
            "weather forecast",
            "historical incident data",
        ],
        scenarios=[
            ScenarioDefinition(
                scenario_id=make_id("scenario"),
                label="baseline",
                assumptions=["current timings", "current demand"],
            ),
            ScenarioDefinition(
                scenario_id=make_id("scenario"),
                label="signal-optimization",
                assumptions=["adaptive cycles enabled"],
            ),
            ScenarioDefinition(
                scenario_id=make_id("scenario"),
                label="combined-strategy",
                assumptions=["signals+routing+manual control"],
            ),
        ],
        planner_confidence=0.91,
    )


@app.post(
    "/agents/knowledge/search",
    tags=["Internal API - Knowledge"],
    response_model=KnowledgeSearchResponse,
    summary="Search policy and historical knowledge",
)
def knowledge_search(payload: KnowledgeSearchRequest) -> KnowledgeSearchResponse:
    return KnowledgeSearchResponse(
        request_id=payload.request_id,
        results=[
            KnowledgeDocument(
                doc_id=make_id("doc"),
                title="Hyderabad peak-hour congestion mitigation guideline",
                source="policy-registry",
                excerpt="Use signal optimization before irreversible lane modifications.",
                relevance_score=0.93,
            )
        ],
    )


@app.post(
    "/agents/data-discovery/discover",
    tags=["Internal API - Data"],
    response_model=DataDiscoveryResponse,
    summary="Discover datasets for planning task",
)
def data_discovery(payload: DataDiscoveryRequest) -> DataDiscoveryResponse:
    return DataDiscoveryResponse(
        request_id=payload.request_id,
        datasets=[
            DatasetDescriptor(
                dataset_id=make_id("dataset"),
                domain=domain,
                source="timescaledb",
                freshness_minutes=15,
                schema_ref=f"{domain.value}.observations.v1",
            )
            for domain in payload.domains
        ],
    )


@app.post(
    "/agents/data-retrieval/retrieve",
    tags=["Internal API - Data"],
    response_model=DataRetrievalResponse,
    summary="Retrieve data payload for execution graph",
)
def data_retrieval(payload: DataRetrievalRequest) -> DataRetrievalResponse:
    return DataRetrievalResponse(
        request_id=payload.request_id,
        records_uri=f"s3://supadsp-data/{payload.request_id}/records.parquet",
        record_count=max(1, len(payload.dataset_ids) * 100),
        fetched_at=utc_now_iso(),
    )


def evaluate_domain(domain: Domain, payload: ModelEvaluationRequest) -> ModelEvaluationResponse:
    return ModelEvaluationResponse(
        request_id=payload.request_id,
        domain=domain,
        model_id=f"{domain.value}_model",
        model_version="v1.0.0",
        status=TaskStatus.COMPLETED,
        outputs={
            "scenario": payload.scenario,
            "location": payload.location,
            "kpi_delta": {"congestion_pct": -12.4, "risk_score": -0.21},
        },
        confidence=0.88,
    )


@app.post(
    "/models/traffic/analyze",
    tags=["Internal API - Domain Models"],
    response_model=ModelEvaluationResponse,
    summary="Run traffic model evaluation",
)
def traffic_model(payload: ModelEvaluationRequest) -> ModelEvaluationResponse:
    return evaluate_domain(Domain.TRAFFIC, payload)


@app.post(
    "/models/flood/analyze",
    tags=["Internal API - Domain Models"],
    response_model=ModelEvaluationResponse,
    summary="Run flood model evaluation",
)
def flood_model(payload: ModelEvaluationRequest) -> ModelEvaluationResponse:
    return evaluate_domain(Domain.FLOOD, payload)


@app.post(
    "/models/energy/analyze",
    tags=["Internal API - Domain Models"],
    response_model=ModelEvaluationResponse,
    summary="Run energy model evaluation",
)
def energy_model(payload: ModelEvaluationRequest) -> ModelEvaluationResponse:
    return evaluate_domain(Domain.ENERGY, payload)


@app.post(
    "/models/weather/analyze",
    tags=["Internal API - Domain Models"],
    response_model=ModelEvaluationResponse,
    summary="Run weather model evaluation",
)
def weather_model(payload: ModelEvaluationRequest) -> ModelEvaluationResponse:
    return evaluate_domain(Domain.WEATHER, payload)


@app.get(
    "/monitoring/status",
    tags=["Public API - Monitoring"],
    response_model=MonitoringStatusResponse,
    summary="Get platform monitoring status",
)
def monitoring_status() -> MonitoringStatusResponse:
    return MonitoringStatusResponse(
        generated_at=utc_now_iso(),
        domains={
            Domain.TRAFFIC: "ONLINE",
            Domain.FLOOD: "ONLINE",
            Domain.ENERGY: "ONLINE",
            Domain.WEATHER: "ONLINE",
        },
        active_alerts=len([a for a in alerts_store.values() if a.status == AlertStatus.ACTIVE]),
        unhealthy_components=[],
    )


@app.get(
    "/monitoring/events",
    tags=["Public API - Monitoring"],
    response_model=MonitoringEventsResponse,
    summary="Get recent monitoring events",
)
def monitoring_events(limit: int = Query(20, ge=1, le=200)) -> MonitoringEventsResponse:
    events = [
        MonitoringEvent(
            event_id=make_id("evt"),
            timestamp=utc_now_iso(),
            domain=Domain.WEATHER,
            severity=Severity.HIGH,
            type="RAINFALL_FORECAST",
            summary="Heavy rainfall predicted in 2 hours for Narayanguda corridor.",
        ),
        MonitoringEvent(
            event_id=make_id("evt"),
            timestamp=utc_now_iso(),
            domain=Domain.TRAFFIC,
            severity=Severity.MEDIUM,
            type="CONGESTION_SPIKE",
            summary="Congestion index crossed 70 in Narayanguda arterial segment.",
        ),
    ]
    return MonitoringEventsResponse(events=events[:limit])


@app.get(
    "/alerts",
    tags=["Public API - Alerts"],
    response_model=List[Alert],
    summary="List alerts",
)
def list_alerts(status_filter: Optional[AlertStatus] = Query(default=None)) -> List[Alert]:
    data = list(alerts_store.values())
    if status_filter is not None:
        data = [item for item in data if item.status == status_filter]
    return data


@app.get(
    "/alerts/{alert_id}",
    tags=["Public API - Alerts"],
    response_model=Alert,
    responses={404: {"model": ErrorResponse}},
    summary="Get alert detail",
)
def get_alert(alert_id: str) -> Alert:
    alert = alerts_store.get(alert_id)
    if alert is None:
        raise not_found("ALERT_NOT_FOUND", "Alert not found", {"alert_id": alert_id})
    return alert


@app.post(
    "/alerts/{alert_id}/acknowledge",
    tags=["Public API - Alerts"],
    response_model=AlertActionResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Acknowledge alert",
)
def acknowledge_alert(alert_id: str, payload: AlertActionRequest) -> AlertActionResponse:
    alert = alerts_store.get(alert_id)
    if alert is None:
        raise not_found("ALERT_NOT_FOUND", "Alert not found", {"alert_id": alert_id})
    alert.status = AlertStatus.ACKNOWLEDGED
    alert.updated_at = utc_now_iso()
    alerts_store[alert_id] = alert
    return AlertActionResponse(alert_id=alert_id, status=alert.status, acted_by=payload.actor_id, acted_at=alert.updated_at)


@app.post(
    "/alerts/{alert_id}/dismiss",
    tags=["Public API - Alerts"],
    response_model=AlertActionResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Dismiss alert",
)
def dismiss_alert(alert_id: str, payload: AlertActionRequest) -> AlertActionResponse:
    alert = alerts_store.get(alert_id)
    if alert is None:
        raise not_found("ALERT_NOT_FOUND", "Alert not found", {"alert_id": alert_id})
    alert.status = AlertStatus.DISMISSED
    alert.updated_at = utc_now_iso()
    alerts_store[alert_id] = alert
    return AlertActionResponse(alert_id=alert_id, status=alert.status, acted_by=payload.actor_id, acted_at=alert.updated_at)


@app.post(
    "/simulations",
    tags=["Public API - Simulations"],
    response_model=SimulationCreateResponse,
    summary="Create simulation run",
)
def create_simulation(payload: SimulationCreateRequest) -> SimulationCreateResponse:
    simulation_id = make_id("sim")
    queued_at = utc_now_iso()
    simulations_store[simulation_id] = SimulationStatusResponse(
        simulation_id=simulation_id,
        status=TaskStatus.QUEUED,
        progress_pct=0,
        started_at=None,
        updated_at=queued_at,
    )
    return SimulationCreateResponse(simulation_id=simulation_id, status=TaskStatus.QUEUED, queued_at=queued_at)


@app.get(
    "/simulations/{simulation_id}",
    tags=["Public API - Simulations"],
    response_model=SimulationStatusResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get simulation status",
)
def get_simulation(simulation_id: str) -> SimulationStatusResponse:
    simulation = simulations_store.get(simulation_id)
    if simulation is None:
        raise not_found("SIMULATION_NOT_FOUND", "Simulation not found", {"simulation_id": simulation_id})
    return simulation


@app.get(
    "/simulations/{simulation_id}/results",
    tags=["Public API - Simulations"],
    response_model=SimulationResultResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get simulation result",
)
def get_simulation_results(simulation_id: str) -> SimulationResultResponse:
    simulation = simulations_store.get(simulation_id)
    if simulation is None:
        raise not_found("SIMULATION_NOT_FOUND", "Simulation not found", {"simulation_id": simulation_id})
    return SimulationResultResponse(
        simulation_id=simulation_id,
        status=TaskStatus.COMPLETED,
        comparison_summary={
            "best_scenario": "combined-strategy",
            "traffic_delay_reduction_pct": 21.4,
            "flood_risk_reduction_pct": 14.8,
        },
        ranked_scenarios=[
            {"name": "combined-strategy", "rank": 1, "score": 0.91},
            {"name": "signal-optimization", "rank": 2, "score": 0.82},
            {"name": "baseline", "rank": 3, "score": 0.36},
        ],
        generated_at=utc_now_iso(),
    )


@app.post(
    "/agents/verification/verify",
    tags=["Internal API - Verification"],
    response_model=VerificationResponse,
    summary="Run verification checks",
)
def verify_recommendation(payload: VerificationRequest) -> VerificationResponse:
    return VerificationResponse(
        request_id=payload.request_id,
        recommendation_id=payload.recommendation_id,
        verification_status="PASSED",
        passed_checks=payload.checks,
        failed_checks=[],
    )


@app.post(
    "/agents/fail-safe/check",
    tags=["Internal API - Fail-Safe"],
    response_model=FailSafeCheckResponse,
    summary="Run fail-safe guardrail checks",
)
def fail_safe_check(payload: FailSafeCheckRequest) -> FailSafeCheckResponse:
    return FailSafeCheckResponse(
        request_id=payload.request_id,
        safe_to_proceed=True,
        guardrail_results={
            "safety_policy": "PASS",
            "budget_limit": "PASS",
            "critical_service_impact": "PASS",
        },
    )


@app.get(
    "/recommendations/{recommendation_id}",
    tags=["Public API - Recommendations"],
    response_model=Recommendation,
    responses={404: {"model": ErrorResponse}},
    summary="Get recommendation detail",
)
def get_recommendation(recommendation_id: str) -> Recommendation:
    recommendation = recommendations_store.get(recommendation_id)
    if recommendation is None:
        raise not_found(
            "RECOMMENDATION_NOT_FOUND",
            "Recommendation not found",
            {"recommendation_id": recommendation_id},
        )
    return recommendation


def ensure_recommendation(recommendation_id: str) -> Recommendation:
    recommendation = recommendations_store.get(recommendation_id)
    if recommendation is None:
        recommendation = Recommendation(
            recommendation_id=recommendation_id,
            request_id=make_id("planreq"),
            status=RecommendationStatus.GENERATED,
            objective="Reduce peak-hour congestion",
            location="Narayanguda",
            summary="Combined signal optimization and dynamic rerouting package.",
            alternatives=["signal-only", "manual-control-only"],
            expected_impacts={"traffic_delay_reduction_pct": 18.0, "flood_risk_delta_pct": -6.0},
            confidence=0.9,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
    recommendations_store[recommendation_id] = recommendation
    return recommendation


@app.post(
    "/recommendations/{recommendation_id}/approve",
    tags=["Public API - Recommendations"],
    response_model=RecommendationDecisionResponse,
    summary="Approve recommendation",
)
def approve_recommendation(recommendation_id: str, payload: RecommendationDecisionRequest) -> RecommendationDecisionResponse:
    recommendation = ensure_recommendation(recommendation_id)
    recommendation.status = RecommendationStatus.APPROVED
    recommendation.updated_at = utc_now_iso()
    recommendations_store[recommendation_id] = recommendation
    return RecommendationDecisionResponse(
        recommendation_id=recommendation_id,
        status=recommendation.status,
        updated_at=recommendation.updated_at,
    )


@app.post(
    "/recommendations/{recommendation_id}/reject",
    tags=["Public API - Recommendations"],
    response_model=RecommendationDecisionResponse,
    summary="Reject recommendation",
)
def reject_recommendation(recommendation_id: str, payload: RecommendationDecisionRequest) -> RecommendationDecisionResponse:
    recommendation = ensure_recommendation(recommendation_id)
    recommendation.status = RecommendationStatus.REJECTED
    recommendation.updated_at = utc_now_iso()
    recommendations_store[recommendation_id] = recommendation
    return RecommendationDecisionResponse(
        recommendation_id=recommendation_id,
        status=recommendation.status,
        updated_at=recommendation.updated_at,
    )


@app.post(
    "/recommendations/{recommendation_id}/modify",
    tags=["Public API - Recommendations"],
    response_model=RecommendationDecisionResponse,
    summary="Modify recommendation",
)
def modify_recommendation(recommendation_id: str, payload: RecommendationModifyRequest) -> RecommendationDecisionResponse:
    recommendation = ensure_recommendation(recommendation_id)
    recommendation.status = RecommendationStatus.MODIFIED
    recommendation.updated_at = utc_now_iso()
    recommendations_store[recommendation_id] = recommendation
    return RecommendationDecisionResponse(
        recommendation_id=recommendation_id,
        status=recommendation.status,
        updated_at=recommendation.updated_at,
    )


@app.get(
    "/digital-twin/state",
    tags=["Public API - Digital Twin"],
    response_model=DigitalTwinStateResponse,
    summary="Get city-wide digital twin state",
)
def digital_twin_state() -> DigitalTwinStateResponse:
    return DigitalTwinStateResponse(
        generated_at=utc_now_iso(),
        locations=[
            {
                "location": "Narayanguda",
                "traffic_index": 0.74,
                "flood_risk": 0.39,
                "energy_load": 0.67,
                "weather_severity": "HIGH_RAIN_PROBABILITY",
            }
        ],
    )


@app.get(
    "/digital-twin/state/{location}",
    tags=["Public API - Digital Twin"],
    response_model=DigitalTwinLocationStateResponse,
    summary="Get location digital twin state",
)
def digital_twin_location_state(location: str) -> DigitalTwinLocationStateResponse:
    return DigitalTwinLocationStateResponse(
        location=location,
        generated_at=utc_now_iso(),
        state={
            "traffic": {"congestion_index": 71.8, "average_speed_kmh": 21.2},
            "flood": {"risk_score": 0.42, "rainfall_forecast_mm": 38.5},
            "energy": {"load_pct": 79.1},
            "weather": {"rain_probability": 0.83, "wind_speed_kmh": 19.4},
        },
    )
