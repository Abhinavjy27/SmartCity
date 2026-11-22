from __future__ import annotations

import copy
import logging
import os
import re
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Path, Query, status
from pydantic import BaseModel, Field, model_validator

from backend.agents.planner_agent.llm_client import LLMConfigurationError, LLMProviderError
from backend.agents.planner_agent.planner import PlannerAgent, get_planner_agent
from backend.agents.planner_agent.schema import AgentRequest, ScenarioDefinition
from backend.config import (
    DEFAULT_PRODUCTION_EVALUATION_DURATION_SECONDS,
    CI_SMOKE_EVALUATION_DURATION_SECONDS,
    HISTORICAL_EVALUATION_DURATION_SECONDS,
)
from backend.supervisor.agent_client import dispatch_agent

logger = logging.getLogger("supervisor")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


INVALID_LOCATION_TOKENS = {
    "", "unknown", "none", "null", "undefined", "n/a", "na",
    "not specified", "unspecified", "any", "city", "location", "here",
    "default", "somewhere", "nil", "?",
}

KNOWN_HYDERABAD_LOCALITIES = [
    "narayanguda", "hyderguda", "begumpet", "gachibowli", "hitec city",
    "hitech city", "jubilee hills", "banjara hills", "secunderabad", "charminar",
    "sanathnagar", "nacharam", "bollaram", "patancheru", "tarnaka", "somajiguda",
    "kompally", "malakpet", "kukatpally", "madhapur", "miyapur", "ameerpet",
    "kondapur", "dilsukhnagar", "lb nagar", "shamshabad", "alwal", "uppal",
    "lingampally", "mehdipatnam", "koti", "santosh nagar", "santhosh nagar",
    "santoshnagar", "amberpet", "abids", "falaknuma", "nampally", "masab tank",
    "tolichowki", "manikonda", "raidurg", "chandanagar", "nizampet", "bowenpally",
    "malkajgiri", "habsiguda", "attapur", "balapur", "hyderabad",
]


CONTEXTUAL_REFERENCE_PATTERNS = [
    r"\bthere\b",
    r"\bsame\s+(?:location|area|corridor|place|spot|zone|intersection|junction)\b",
    r"\bthat\s+(?:corridor|area|location|place|spot|zone|intersection|junction)\b",
    r"\b(?:test|simulate|run)\s+(?:it|that|this)\b",
    r"\b(?:in|at|near|around)\s+(?:that|the\s+same)\s+(?:area|corridor|location|place|spot)\b",
    r"\baround\s+there\b",
    r"\bnear\s+there\b",
]


def has_contextual_reference(text: Optional[str]) -> bool:
    """Detect whether user query contains anaphoric references pointing to previous conversation context."""
    if not text or not isinstance(text, str):
        return False
    lower = text.lower()
    for pat in CONTEXTUAL_REFERENCE_PATTERNS:
        if re.search(pat, lower):
            return True
    return False


def extract_locality_from_history(conversation_history: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    """
    Search conversation history turns in reverse order to find the last resolved locality.
    Inspects:
    1. turn.get("location")
    2. specialist evidence in collected_results / traffic_evidence / pollution_evidence
    3. natural language query content of user turns (e.g., 'What is the traffic in Tarnaka?')
    """
    if not conversation_history:
        return None
    from backend.agents.traffic_agent.location_resolver import LocationResolver

    for turn in reversed(conversation_history):
        if not isinstance(turn, dict):
            continue

        turn_loc = turn.get("location")
        if turn_loc and isinstance(turn_loc, str):
            t_norm = turn_loc.strip().lower()
            if t_norm and t_norm not in INVALID_LOCATION_TOKENS:
                resolved_t = LocationResolver.resolve(explicit_location=turn_loc)
                if resolved_t:
                    return f"{resolved_t.name}, Hyderabad" if "hyderabad" not in resolved_t.name.lower() else resolved_t.name
                return turn_loc.strip()

        for ev_key in [
            "traffic_evidence", "trafficEvidence",
            "pollution_evidence", "pollutionEvidence",
            "simulation_evidence", "simulationEvidence",
        ]:
            ev = turn.get(ev_key)
            if isinstance(ev, dict):
                ev_loc = ev.get("location")
                if ev_loc and isinstance(ev_loc, str) and ev_loc.strip().lower() not in INVALID_LOCATION_TOKENS:
                    resolved_ev = LocationResolver.resolve(explicit_location=ev_loc)
                    if resolved_ev:
                        return f"{resolved_ev.name}, Hyderabad" if "hyderabad" not in resolved_ev.name.lower() else resolved_ev.name

        col = turn.get("collected_results") or turn.get("agent_results") or {}
        if isinstance(col, dict):
            for agent_key in ["traffic", "pollution", "weather", "energy", "simulation"]:
                agent_data = col.get(agent_key)
                if isinstance(agent_data, dict):
                    a_loc = agent_data.get("location")
                    if a_loc and isinstance(a_loc, str) and a_loc.strip().lower() not in INVALID_LOCATION_TOKENS:
                        resolved_a = LocationResolver.resolve(explicit_location=a_loc)
                        if resolved_a:
                            return f"{resolved_a.name}, Hyderabad" if "hyderabad" not in resolved_a.name.lower() else resolved_a.name
                        return a_loc.strip()

        content = turn.get("content") or turn.get("query")
        if content and isinstance(content, str):
            resolved_c = LocationResolver.resolve(query_text=content)
            if resolved_c:
                return f"{resolved_c.name}, Hyderabad" if "hyderabad" not in resolved_c.name.lower() else resolved_c.name

    return None


def sanitize_location(
    location: Optional[str],
    query_text: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    conversation_id: Optional[str] = None,
    default_location: str = "Narayanguda, Hyderabad",
) -> str:
    """
    Sanitize location string following strict precedence hierarchy:
    1. Explicit locality mentioned in current query text (HIGHEST PRECEDENCE - overrides past context).
    2. Explicit caller-provided locality parameter (if not blank/unknown/invalid and not an anaphoric query).
    3. Conversation context:
       - If query contains anaphoric references ('there', 'same location', 'that corridor', 'test it')
         OR if no explicit request parameter was provided:
         look up last resolved locality in conversation session or conversation history.
    4. Default fallback ('Narayanguda, Hyderabad') ONLY when no context exists.
    """
    from backend.agents.traffic_agent.location_resolver import LocationResolver

    # Step 1: Explicit locality mentioned in current query text (HIGHEST PRECEDENCE)
    if query_text and isinstance(query_text, str) and query_text.strip():
        resolved_q = LocationResolver.resolve(query_text=query_text)
        if resolved_q:
            loc_str = f"{resolved_q.name}, Hyderabad" if "hyderabad" not in resolved_q.name.lower() else resolved_q.name
            if conversation_id and conversation_id in _PLANNER_SESSIONS:
                _PLANNER_SESSIONS[conversation_id]["last_locality"] = loc_str
            return loc_str

    # Determine whether current query is anaphoric / context-referencing
    is_anaphoric = has_contextual_reference(query_text)

    # Lookup conversation context from isolated session store or conversation history
    context_loc = None
    if conversation_id and conversation_id in _PLANNER_SESSIONS:
        context_loc = _PLANNER_SESSIONS[conversation_id].get("last_locality")
    if not context_loc:
        context_loc = extract_locality_from_history(conversation_history)

    # If query contains explicit anaphora ('there', 'same location', 'that corridor', 'test it')
    # and we have conversation context, resolve directly to the context!
    if is_anaphoric and context_loc:
        logger.info(
            f"[Locality Resolution] Anaphoric reference in query '{query_text}' resolved to conversation context: {context_loc}"
        )
        return context_loc

    # Step 2: Explicit caller-provided locality parameter
    if location and isinstance(location, str):
        norm = location.strip().lower()
        if norm and norm not in INVALID_LOCATION_TOKENS:
            resolved_loc = LocationResolver.resolve(explicit_location=location)
            if resolved_loc:
                loc_str = f"{resolved_loc.name}, Hyderabad" if "hyderabad" not in resolved_loc.name.lower() else resolved_loc.name
                if conversation_id and conversation_id in _PLANNER_SESSIONS:
                    _PLANNER_SESSIONS[conversation_id]["last_locality"] = loc_str
                return loc_str
            return location.strip()

    # Step 3: Inherit from conversation context for follow-up questions
    if context_loc:
        logger.info(f"[Locality Resolution] Inherited locality from conversation context: {context_loc}")
        return context_loc

    # Step 4: Fallback to default ONLY when no context exists
    return default_location


def validate_agent_locality(
    expected_locality: str,
    agent_res: Any,
    agent_cap: str,
) -> bool:
    """
    Validate that the returned specialist agent response corresponds to the expected locality.
    Prevents silent substitution of another locality.
    """
    if not isinstance(agent_res, dict):
        return True

    from backend.agents.traffic_agent.location_resolver import LocationResolver
    expected_resolved = LocationResolver.resolve(explicit_location=expected_locality)
    if not expected_resolved:
        return True

    # Check various location fields returned by agents
    ret_loc_str = (
        agent_res.get("location")
        or agent_res.get("locality")
        or (agent_res.get("metadata", {}) or {}).get("locality")
        or (agent_res.get("metrics", {}) or {}).get("location")
        or agent_res.get("city")
    )
    if not ret_loc_str or not isinstance(ret_loc_str, str):
        return True

    actual_resolved = LocationResolver.resolve(explicit_location=ret_loc_str)
    if not actual_resolved:
        return True

    if expected_resolved.slug != actual_resolved.slug:
        logger.error(
            f"[Supervisor] Locality validation mismatch for agent '{agent_cap}': "
            f"expected '{expected_resolved.name}' ({expected_resolved.slug}), "
            f"but received '{actual_resolved.name}' ({actual_resolved.slug}). Rejecting substituted locality."
        )
        return False
    return True


class Domain(str, Enum):
    TRAFFIC = "traffic"
    FLOOD = "flood"
    ENERGY = "energy"
    WEATHER = "weather"
    POLLUTION = "pollution"
    SIMULATION = "simulation"


class PlanningStatus(str, Enum):
    RECEIVED = "RECEIVED"
    PLANNING = "PLANNING"
    COORDINATING = "COORDINATING"
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
    recommendation_id: Optional[str] = None
    created_at: str
    updated_at: str


class PlannerPlanRequest(BaseModel):
    request_id: str
    objective: str
    location: Optional[str] = ""
    domains: Optional[List[Domain]] = Field(default_factory=list)
    constraints: List[Constraint] = Field(default_factory=list)


class PlannerPlanResponse(BaseModel):
    request_id: str
    objective: str
    required_capabilities: List[str] = Field(default_factory=list, description="Specialist capabilities required for this cycle")
    agent_requests: List[AgentRequest] = Field(default_factory=list, description="Contract-compliant agent requests generated by LLM")
    next_action: str = Field(default="collect_evidence", description="Dynamic next action: collect_evidence, run_simulation, finalize")
    cycle: int = Field(default=1)
    planner_confidence: Optional[float] = Field(default=None, ge=0, le=1)
    scenarios: Optional[List[ScenarioDefinition]] = Field(default=None, description="Simulation scenarios only when experiment testing is decided")
    likely_causes: Optional[List[str]] = Field(default=None, description="Likely causes when relevant to diagnosed domain")
    interventions: Optional[List[str]] = Field(default=None, description="Candidate interventions if evaluated")
    required_data: Optional[List[str]] = Field(default=None, description="Required telemetry fields")


class PlannerFeedbackRequest(BaseModel):
    request_id: str
    task_id: Optional[str] = None
    objective: str
    location: Optional[str] = ""
    domains: List[Domain] = Field(default_factory=list)
    assigned_capabilities: List[str] = Field(default_factory=list)
    dispatched_agents: List[str] = Field(default_factory=list)
    collected_results: Dict[str, Any] = Field(default_factory=dict)
    failures: Dict[str, Any] = Field(default_factory=dict)
    constraints: List[Constraint] = Field(default_factory=list)
    cycle: int = Field(default=2)
    max_cycles: Optional[int] = Field(default=3, description="Maximum planning and simulation budget")
    agent: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class PlannerFeedbackResponse(BaseModel):
    request_id: str
    task_id: Optional[str] = None
    status: str = "RECEIVED"
    cycle: int = Field(default=2)
    decision: str = Field(default="finalize", description="Planner next decision after evaluating agent results")
    next_action: str = Field(default="finalize", description="Dynamic next action determined by LLM")
    required_capabilities: List[str] = Field(default_factory=list)
    agent_requests: List[AgentRequest] = Field(default_factory=list)
    insights: Dict[str, Any] = Field(default_factory=dict, description="Synthesized insights from collected agent results")
    final_reasoning: Optional[Dict[str, Any]] = Field(default=None, description="Final cross-domain reasoning and recommendations if finalized")
    next_steps: List[str] = Field(default_factory=list)
    evidence_status: Optional[str] = Field(default="EVIDENCE: OBSERVATIONAL")
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    received_results: Dict[str, Any] = Field(default_factory=dict)
    failures: Dict[str, Any] = Field(default_factory=dict)
    scenarios: Optional[List[ScenarioDefinition]] = Field(default=None)
    simulation_context: Optional[Dict[str, Any]] = Field(default=None)


class PlannerExecuteRequest(BaseModel):
    request_id: Optional[str] = None
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None
    objective: Optional[str] = None
    query: Optional[str] = None
    location: Optional[str] = None
    domains: Optional[List[Domain]] = Field(default_factory=list)
    constraints: List[Constraint] = Field(default_factory=list)
    max_cycles: Optional[int] = 3
    conversation_history: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    simulation_history: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    tested_scenarios: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    duration_seconds: Optional[int] = None
    scenario: Optional[str] = None
    seed: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def sync_query_objective(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Synchronize conversation_id and session_id
            cid = data.get("conversation_id")
            sid = data.get("session_id")
            eff_cid = (cid or sid or "").strip()
            if eff_cid:
                data["conversation_id"] = eff_cid
                data["session_id"] = eff_cid

            q = data.get("query")
            obj = data.get("objective")
            if q and not obj:
                data["objective"] = q
            elif obj and not q:
                data["query"] = obj

            eff_query = data.get("objective") or data.get("query")
            data["location"] = sanitize_location(
                location=data.get("location"),
                query_text=eff_query,
                conversation_history=data.get("conversation_history"),
                conversation_id=eff_cid or None,
            )

            # Parse scenario, duration_seconds, seed from text if not provided
            txt = str(data.get("objective") or data.get("query") or "").lower()
            if not data.get("scenario"):
                if "synthetic_peak_westbound" in txt or "peak westbound" in txt or "peak_westbound" in txt:
                    data["scenario"] = "synthetic_peak_westbound"
                elif "synthetic_normal" in txt or "normal traffic" in txt or "normal demand" in txt:
                    data["scenario"] = "synthetic_normal"

            import re
            is_cross_horizon = ("300" in txt and "600" in txt) or ("between 300 and 600" in txt)
            if is_cross_horizon:
                data["duration_seconds"] = None
            elif data.get("duration_seconds") is None:
                dur_match = re.search(r"\b(120|300|600)\s*(?:-|\s)?(?:s|sec|second)?\b", txt)
                if dur_match:
                    data["duration_seconds"] = int(dur_match.group(1))

            if data.get("seed") is None:
                import re
                seed_match = re.search(r"\bseed\s*[:=]?\s*(\d+)\b", txt)
                if seed_match:
                    try:
                        data["seed"] = int(seed_match.group(1))
                    except (ValueError, TypeError):
                        pass
        return data


# Session store for Planner conversations & simulation histories keyed by explicit conversation_id / session_id
_PLANNER_SESSIONS: Dict[str, Dict[str, Any]] = {}



class PlannerExecuteResponse(BaseModel):
    request_id: str
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None
    location: Optional[str] = None
    status: str
    cycle: int = 1
    selected_capabilities: List[str] = Field(default_factory=list)
    dispatched_agents: List[str] = Field(default_factory=list)
    agent_results: Dict[str, Any] = Field(default_factory=dict)
    collected_results: Dict[str, Any] = Field(default_factory=dict)
    failures: Dict[str, Any] = Field(default_factory=dict)
    planner_feedback: Dict[str, Any] = Field(default_factory=dict)
    final_response: Optional[Dict[str, Any]] = None
    evidence_status: Optional[str] = Field(default="EVIDENCE: OBSERVATIONAL")
    confidence: Optional[float] = None
    created_at: str
    runtime: Optional[Dict[str, Any]] = None


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


from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.services.congestion_service import congestion_service
    congestion_service.start_background_task()
    yield
    congestion_service.stop_background_task()


app = FastAPI(
    title="SUPADSP Unified API Contract",
    version="1.0.0-contract",
    description=(
        "Contract-first API surface for Smart City planning workflows. "
        "This OpenAPI defines integration boundaries between frontend, planner, "
        "domain models (traffic/flood/energy/weather/pollution/simulation), and specialist internal agents."
    ),
    lifespan=lifespan,
)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
alerts_store: Dict[str, Alert] = {
    "ALERT_01": Alert(
        alert_id="ALERT_01",
        status=AlertStatus.ACTIVE,
        severity=Severity.CRITICAL,
        domain=Domain.TRAFFIC,
        location="Gachibowli — HITECH City",
        title="Evening Traffic Gridlock at Gachibowli Flyover & Mindspace Corridor",
        message="Severe bottleneck causing 3.4 km vehicle queues during peak evening office rush.",
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    ),
    "ALERT_02": Alert(
        alert_id="ALERT_02",
        status=AlertStatus.ACTIVE,
        severity=Severity.HIGH,
        domain=Domain.WEATHER,
        location="Nacharam Industrial Zone",
        title="Air Quality Deterioration in Nacharam Sector",
        message="Particulate matter PM2.5 levels exceeding threshold (>180 ug/m3). Dispersion inhibited by low wind speeds.",
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    ),
    "ALERT_03": Alert(
        alert_id="ALERT_03",
        status=AlertStatus.ACTIVE,
        severity=Severity.MEDIUM,
        domain=Domain.ENERGY,
        location="Financial District Substation",
        title="High Peak Load Margin on Feeder Grid #4",
        message="Transformer core temperature near 78C due to simultaneous data center and EV charging station draw.",
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    ),
    "ALERT_04": Alert(
        alert_id="ALERT_04",
        status=AlertStatus.ACTIVE,
        severity=Severity.HIGH,
        domain=Domain.FLOOD,
        location="Begumpet Low-lying Ingress",
        title="Urban Flood Risk Alert - Monsoon Inundation",
        message="Stormwater catchment reaching 84% capacity. Sump drainage backflow risk within 45 minutes.",
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    ),
}
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


KNOWN_CAPABILITIES = {
    "traffic",
    "weather",
    "energy",
    "flood",
    "pollution",
    "simulation",
    "data_discovery",
    "data_retrieval",
    "verification",
    "knowledge",
    "planner",
}





@app.post(
    "/agents/planner/plan",
    tags=["Internal API - Planner"],
    response_model=PlannerPlanResponse,
    summary="Generate initial planning cycle",
    response_model_exclude_none=True,
)
def planner_plan(payload: PlannerPlanRequest) -> PlannerPlanResponse:
    try:
        planner_agent = get_planner_agent()
        plan_decision = planner_agent.plan_autonomous(
            objective=payload.objective,
            location=payload.location,
            constraints=payload.constraints,
        )
    except (LLMConfigurationError, LLMProviderError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="LLM_PLANNER_UNAVAILABLE",
                    message=str(exc),
                    details={"request_id": payload.request_id},
                    correlation_id=make_id("corr"),
                    timestamp=utc_now_iso(),
                )
            ).model_dump(),
        )

    if not plan_decision.relevant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="QUERY_OUT_OF_SCOPE",
                    message=plan_decision.response or "This question is outside the scope of the Smart City system.",
                    details={"request_id": payload.request_id},
                    correlation_id=make_id("corr"),
                    timestamp=utc_now_iso(),
                )
            ).model_dump(),
        )

    scenarios = None
    if plan_decision.scenarios:
        scenarios = [
            ScenarioDefinition(
                scenario_id=sc.get("scenario_id", make_id("scenario")),
                label=sc.get("label", "experiment"),
                assumptions=sc.get("assumptions", []),
            )
            for sc in plan_decision.scenarios
        ]

    return PlannerPlanResponse(
        request_id=payload.request_id,
        objective=plan_decision.objective or payload.objective,
        required_capabilities=plan_decision.required_capabilities,
        agent_requests=plan_decision.agent_requests,
        next_action=plan_decision.next_action,
        cycle=1,
        planner_confidence=plan_decision.confidence,
        scenarios=scenarios,
        likely_causes=None,
        interventions=None,
        required_data=None,
    )


@app.post(
    "/agents/planner/feedback",
    tags=["Internal API - Planner"],
    response_model=PlannerFeedbackResponse,
    summary="Submit specialist agent results to planner for feedback & next cycle decision",
    response_model_exclude_none=True,
)
def planner_feedback(payload: PlannerFeedbackRequest) -> PlannerFeedbackResponse:
    # Support both single-agent result and collected_results dictionary
    collected = dict(payload.collected_results or {})
    if payload.agent and payload.result:
        collected[payload.agent] = payload.result

    try:
        planner_agent = get_planner_agent()
        max_cyc = payload.max_cycles if payload.max_cycles is not None else 3
        eval_result = planner_agent.evaluate_and_replan(
            objective=payload.objective,
            plan=payload.assigned_capabilities or list(collected.keys()),
            collected_results=collected,
            failures=payload.failures,
            cycle_num=payload.cycle,
            max_cycles=max_cyc,
            location=payload.location or "Hyderabad",
        )
    except (LLMConfigurationError, LLMProviderError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="LLM_PLANNER_UNAVAILABLE",
                    message=str(exc),
                    details={"request_id": payload.request_id},
                    correlation_id=make_id("corr"),
                    timestamp=utc_now_iso(),
                )
            ).model_dump(),
        )

    insights: Dict[str, Any] = {
        "analysis": eval_result.analysis,
        "goal_achieved": eval_result.goal_achieved,
        "recommendation": eval_result.final_recommendation,
        "revised_plan": eval_result.revised_plan,
        "agent_results": collected,
    }
    if payload.failures:
        insights["agent_failures"] = payload.failures
    if eval_result.cross_analysis:
        insights["cross_analysis"] = eval_result.cross_analysis.model_dump()

    final_reasoning_dict = eval_result.final_reasoning.model_dump() if eval_result.final_reasoning else None
    if final_reasoning_dict is not None and eval_result.cross_analysis:
        final_reasoning_dict["key_findings"] = eval_result.cross_analysis.key_findings
        final_reasoning_dict["diagnosed_bottlenecks"] = eval_result.cross_analysis.diagnosed_bottlenecks

    scenarios = None
    if eval_result.scenarios:
        scenarios = [
            ScenarioDefinition(
                scenario_id=sc.get("scenario_id", make_id("scenario")),
                label=sc.get("label", "experiment"),
                assumptions=sc.get("assumptions", []),
            )
            for sc in eval_result.scenarios
        ]

    status_str = "SUCCESS" if eval_result.goal_achieved else (
        "SIMULATION_REQUIRED" if eval_result.next_action == "run_simulation" else "NEEDS_REPLANNING"
    )

    return PlannerFeedbackResponse(
        request_id=payload.request_id,
        task_id=payload.task_id,
        status=status_str,
        cycle=payload.cycle,
        decision=eval_result.decision,
        next_action=eval_result.next_action,
        required_capabilities=eval_result.next_cycle_caps,
        agent_requests=eval_result.next_cycle_calls,
        insights=insights,
        final_reasoning=final_reasoning_dict,
        next_steps=eval_result.revised_plan if not eval_result.goal_achieved else ["implement_recommendation", "monitor_flow"],
        evidence_status=eval_result.evidence_status,
        confidence=eval_result.confidence,
        received_results=collected,
        failures=payload.failures,
        scenarios=scenarios,
        simulation_context=eval_result.simulation_context,
    )


def resolve_canonical_baseline(
    simulations_history: List[Dict[str, Any]],
    collected_results: Dict[str, Any],
    target_scen: Optional[str],
    target_dur: Optional[int],
    target_seed: Optional[int],
    target_net: Optional[str] = "narayanguda_network.net.xml",
) -> Optional[Dict[str, Any]]:
    """
    Deterministically resolves ONE immutable canonical baseline for an experiment set:
    (scenario, duration_seconds, seed, network).

    NEVER treats an intervention as a baseline.
    NEVER chains interventions (e.g. +10s must never become baseline for +19s;
    +19s must never become baseline for rerouting).
    """
    # 1. Search simulations_history for a TRUE pure baseline simulation (never an intervention)
    for s in simulations_history:
        if not isinstance(s, dict):
            continue
        scen_id = str(s.get("scenario_id") or "").lower()
        has_intervention = bool(
            s.get("intervention_applied")
            or s.get("intervention")
            or scen_id.startswith(("signal_timing", "rerouting", "scen_signal", "scen_reroute", "intervention"))
        )
        is_pure_baseline = scen_id.startswith("baseline") or (not has_intervention and s.get("type") == "simulation")

        if is_pure_baseline:
            s_comp = s.get("comparison", {}) if isinstance(s.get("comparison"), dict) else {}
            s_meta = s.get("metadata", {}) if isinstance(s.get("metadata"), dict) else {}
            s_dur = s.get("duration_seconds") or s_comp.get("baseline_duration_seconds") or s_meta.get("duration_seconds")
            s_scen = s.get("scenario") or s_comp.get("baseline_scenario") or s_meta.get("demand_profile")
            s_sd = s.get("seed") if s.get("seed") is not None else (s_comp.get("baseline_seed") if s_comp.get("baseline_seed") is not None else s_meta.get("random_seed"))
            s_net = s.get("network_name") or s_comp.get("baseline_network") or s_meta.get("network_name")

            if target_dur is not None and s_dur is not None and int(s_dur) == int(target_dur):
                if target_scen is None or not s_scen or str(s_scen).strip().lower() == str(target_scen).strip().lower():
                    if target_seed is None or s_sd is None or int(s_sd) == int(target_seed):
                        if target_net is None or not s_net or str(s_net).strip().lower() == str(target_net).strip().lower():
                            s_m = s.get("metrics") or {}
                            corridor_speeds = {}
                            for c in (s.get("corridors") or []):
                                if isinstance(c, dict) and c.get("avg_speed") is not None:
                                    if c.get("id"):
                                        corridor_speeds[str(c["id"]).lower().strip()] = float(c["avg_speed"])
                                    if c.get("name"):
                                        corridor_speeds[str(c["name"]).lower().strip()] = float(c["avg_speed"])
                            base_id = s.get("scenario_id") or f"baseline:dur{s_dur}s:seed{s_sd}"
                            return {
                                "scenario_id": base_id,
                                "scenario_name": s_scen or target_scen,
                                "scenario": s_scen or target_scen,
                                "seed": s_sd if s_sd is not None else target_seed,
                                "duration_seconds": int(s_dur),
                                "network_name": s_net or target_net,
                                "network": s_net or target_net,
                                "average_speed_kmh": s.get("average_speed_kmh") or s_m.get("average_speed_kmh"),
                                "average_delay_sec": s.get("average_delay_sec") or s_m.get("average_delay_sec"),
                                "average_waiting_time_sec": s.get("average_waiting_time_sec") or s_m.get("average_waiting_time_sec"),
                                "congestion_index": s.get("congestion_index") or s_m.get("congestion_index"),
                                "throughput": s.get("throughput") or s_m.get("throughput", 0),
                                "corridors": s.get("corridors") or [],
                                "corridor_speeds": corridor_speeds,
                                "baseline_reference": {
                                    "scenario_id": base_id,
                                    "scenario": s_scen or target_scen,
                                    "duration_seconds": int(s_dur),
                                    "seed": s_sd if s_sd is not None else target_seed,
                                    "network": s_net or target_net,
                                },
                            }

    # 2. Check collected_results["traffic"] (pre-intervention empirical baseline observation)
    if "traffic" in collected_results:
        trf_data = collected_results["traffic"]
        b_metrics = trf_data.get("metrics") if isinstance(trf_data.get("metrics"), dict) else trf_data
        b_meta = trf_data.get("metadata") if isinstance(trf_data.get("metadata"), dict) else {}
        base_seed = trf_data.get("seed") if trf_data.get("seed") is not None else b_meta.get("random_seed")
        base_duration = trf_data.get("duration_seconds") if trf_data.get("duration_seconds") is not None else b_meta.get("duration_seconds")
        base_scenario = trf_data.get("scenario") or trf_data.get("scenario_name") or b_meta.get("demand_profile")
        base_net = trf_data.get("network_name") or b_meta.get("network_name") or target_net

        if base_duration is not None and target_dur is not None and int(base_duration) == int(target_dur):
            if target_scen is None or not base_scenario or str(base_scenario).strip().lower() == str(target_scen).strip().lower():
                if target_seed is None or base_seed is None or int(base_seed) == int(target_seed):
                    corridor_speeds = {}
                    for c in (trf_data.get("corridors") or []):
                        if isinstance(c, dict) and c.get("avg_speed") is not None:
                            if c.get("id"):
                                corridor_speeds[str(c["id"]).lower().strip()] = float(c["avg_speed"])
                            if c.get("name"):
                                corridor_speeds[str(c["name"]).lower().strip()] = float(c["avg_speed"])

                    base_id = trf_data.get("scenario_id") or f"baseline:dur{base_duration}s:seed{base_seed}"
                    return {
                        "scenario_id": base_id,
                        "scenario_name": base_scenario or target_scen,
                        "scenario": base_scenario or target_scen,
                        "seed": base_seed if base_seed is not None else target_seed,
                        "duration_seconds": int(base_duration),
                        "network_name": base_net,
                        "network": base_net,
                        "average_speed_kmh": trf_data.get("average_speed_kmh") or b_metrics.get("average_speed_kmh"),
                        "average_delay_sec": trf_data.get("average_delay_sec") or b_metrics.get("average_delay_sec"),
                        "average_waiting_time_sec": trf_data.get("average_waiting_time_sec") or b_metrics.get("average_waiting_time_sec"),
                        "congestion_index": trf_data.get("congestion_index") or b_metrics.get("congestion_index"),
                        "throughput": trf_data.get("throughput") or b_metrics.get("throughput", 0),
                        "corridors": trf_data.get("corridors", []),
                        "corridor_speeds": corridor_speeds,
                        "baseline_reference": {
                            "scenario_id": base_id,
                            "scenario": base_scenario or target_scen,
                            "duration_seconds": int(base_duration),
                            "seed": base_seed if base_seed is not None else target_seed,
                            "network": base_net,
                        },
                    }

    # 3. Check if any completed intervention in simulations_history already carries
    # the canonical baseline summary/metrics (NEVER the intervention's own metrics!)
    for s in simulations_history:
        if not isinstance(s, dict):
            continue
        comp = s.get("comparison")
        b_sum = s.get("baseline_metrics") or (comp.get("baseline_summary") if isinstance(comp, dict) else None)
        if isinstance(b_sum, dict) and b_sum.get("average_speed_kmh") is not None:
            s_comp = comp if isinstance(comp, dict) else {}
            s_meta = s.get("metadata", {}) if isinstance(s.get("metadata"), dict) else {}
            s_dur = s_comp.get("baseline_duration_seconds") or s.get("duration_seconds") or s_meta.get("duration_seconds")
            s_scen = s_comp.get("baseline_scenario") or s.get("scenario") or s_meta.get("demand_profile")
            s_sd = s_comp.get("baseline_seed") if s_comp.get("baseline_seed") is not None else s.get("seed")
            s_net = s_comp.get("baseline_network") or s.get("network_name") or s_meta.get("network_name")

            if target_dur is not None and s_dur is not None and int(s_dur) == int(target_dur):
                if target_scen is None or not s_scen or str(s_scen).strip().lower() == str(target_scen).strip().lower():
                    if target_seed is None or s_sd is None or int(s_sd) == int(target_seed):
                        b_ref = s.get("baseline_reference") or s_comp.get("baseline_reference") or {}
                        base_id = b_ref.get("scenario_id") or f"baseline:dur{s_dur}s:seed{s_sd}"
                        return {
                            "scenario_id": base_id,
                            "scenario_name": s_scen or target_scen,
                            "scenario": s_scen or target_scen,
                            "seed": s_sd if s_sd is not None else target_seed,
                            "duration_seconds": int(s_dur),
                            "network_name": s_net or target_net,
                            "network": s_net or target_net,
                            "average_speed_kmh": b_sum.get("average_speed_kmh"),
                            "average_delay_sec": b_sum.get("average_delay_sec"),
                            "average_waiting_time_sec": b_sum.get("average_waiting_time_sec"),
                            "congestion_index": b_sum.get("congestion_index"),
                            "throughput": b_sum.get("throughput", 0),
                            "corridors": s.get("corridors", []),
                            "corridor_speeds": {},
                            "baseline_reference": {
                                "scenario_id": base_id,
                                "scenario": s_scen or target_scen,
                                "duration_seconds": int(s_dur),
                                "seed": s_sd if s_sd is not None else target_seed,
                                "network": s_net or target_net,
                            },
                        }

    return None


def verify_multi_intervention_invariant(tested_scenarios: List[Dict[str, Any]]) -> None:
    """
    Deterministically verifies that all tested interventions in the same experiment set
    (matching scenario, duration, seed, network) share the exact same canonical baseline
    and are never chained to one another.
    """
    by_set: Dict[tuple, List[Dict[str, Any]]] = {}
    for scen in tested_scenarios:
        if not isinstance(scen, dict):
            continue
        if not (scen.get("intervention") or scen.get("intervention_applied")):
            continue
        key = (
            str(scen.get("scenario") or "").strip().lower(),
            scen.get("duration_seconds"),
            scen.get("seed"),
            str(scen.get("network_name") or scen.get("network") or "").strip().lower(),
        )
        by_set.setdefault(key, []).append(scen)

    for exp_key, scens in by_set.items():
        if len(scens) <= 1:
            continue
        first_b_metrics = scens[0].get("baseline_metrics") or (scens[0].get("comparison", {}) or {}).get("baseline_summary")
        first_b_speed = first_b_metrics.get("average_speed_kmh") if isinstance(first_b_metrics, dict) else None
        first_b_delay = first_b_metrics.get("average_delay_sec") if isinstance(first_b_metrics, dict) else None

        for idx, s in enumerate(scens[1:], start=2):
            s_b_metrics = s.get("baseline_metrics") or (s.get("comparison", {}) or {}).get("baseline_summary")
            s_b_speed = s_b_metrics.get("average_speed_kmh") if isinstance(s_b_metrics, dict) else None
            s_b_delay = s_b_metrics.get("average_delay_sec") if isinstance(s_b_metrics, dict) else None

            if first_b_speed is not None and s_b_speed is not None and abs(first_b_speed - s_b_speed) > 1e-4:
                raise ValueError(
                    f"Multi-intervention invariant violated: Intervention #{idx} has baseline speed {s_b_speed} "
                    f"differing from canonical baseline speed {first_b_speed} in experiment set {exp_key}. Baseline chaining detected!"
                )
            if first_b_delay is not None and s_b_delay is not None and abs(first_b_delay - s_b_delay) > 1e-4:
                raise ValueError(
                    f"Multi-intervention invariant violated: Intervention #{idx} has baseline delay {s_b_delay} "
                    f"differing from canonical baseline delay {first_b_delay} in experiment set {exp_key}. Baseline chaining detected!"
                )


@app.post(
    "/agents/planner/execute",
    tags=["Internal API - Planner"],
    response_model=PlannerExecuteResponse,
    summary="Execute autonomous planner pipeline (Plan -> Specialist Dispatch -> Feedback Evaluation)",
)
def planner_execute(payload: PlannerExecuteRequest) -> PlannerExecuteResponse:
    t_start = time.perf_counter()
    req_id = payload.request_id or make_id("planreq")
    conv_id = (payload.conversation_id or payload.session_id or "").strip()
    planner_agent = get_planner_agent()
    stage_latencies: Dict[str, float] = {}
    specialist_calls_record: List[Dict[str, Any]] = []

    # CURRENT REQUEST: Objective must remain faithful to current user instruction without prepending stale history
    effective_objective = (payload.objective or payload.query or "").strip()
    payload.objective = effective_objective
    payload.query = effective_objective

    # Sanitize and inherit location adhering to strict precedence hierarchy:
    # 1. Explicit locality in current query text (overrides all past context)
    # 2. Contextual reference ('there', 'same location', 'that corridor', 'test it') -> resolved from conversation context
    # 3. Explicit request parameter provided by caller
    # 4. Conversation context for genuine follow-ups
    # 5. Default fallback ('Narayanguda, Hyderabad') ONLY when no context exists
    payload.location = sanitize_location(
        location=payload.location,
        query_text=effective_objective,
        conversation_history=payload.conversation_history,
        conversation_id=conv_id or None,
    )

    if conv_id:
        sess = _PLANNER_SESSIONS.setdefault(conv_id, {})
        sess["conversation_id"] = conv_id
        sess["session_id"] = conv_id
        sess["last_locality"] = payload.location

    # Safe request diagnostics logging (Section 4 & Section 1)
    logger.info(
        f"[Planner Diagnostics] REQUEST_ID={req_id} | CONVERSATION_ID={conv_id or 'none'} | "
        f"CURRENT_QUERY='{payload.query or ''}' | CURRENT_OBJECTIVE='{payload.objective or ''}' | "
        f"LOCATION='{payload.location or ''}' | HISTORY_COUNT={len(payload.conversation_history or [])} | "
        f"SIM_HISTORY_COUNT={len(payload.simulation_history or [])} | TESTED_SCENARIOS_COUNT={len(payload.tested_scenarios or [])}"
    )

    # Ingest prior simulation history strictly for analytical follow-up comparisons
    session_id = conv_id
    session_data = _PLANNER_SESSIONS.get(session_id, {}) if session_id else {}

    prior_sims: List[Dict[str, Any]] = []

    if payload.simulation_history:
        prior_sims.extend(payload.simulation_history)

    if not prior_sims and payload.tested_scenarios:
        prior_sims.extend(payload.tested_scenarios)

    if not prior_sims and payload.conversation_history:
        for turn in reversed(payload.conversation_history):
            if isinstance(turn, dict):
                t_sims = turn.get("simulations") or turn.get("simulation_history") or turn.get("tested_scenarios") or turn.get("simulation_evidence")
                if t_sims and isinstance(t_sims, list):
                    prior_sims.extend(t_sims)
                    break
                elif t_sims and isinstance(t_sims, dict):
                    prior_sims.append(t_sims)
                    break
                col_res = turn.get("collected_results")
                if isinstance(col_res, dict):
                    c_sims = col_res.get("simulations") or col_res.get("simulation")
                    if c_sims and isinstance(c_sims, list):
                        prior_sims.extend(c_sims)
                        break
                    elif c_sims and isinstance(c_sims, dict):
                        prior_sims.append(c_sims)
                        break

    is_fresh_conversation = not payload.conversation_history and not payload.simulation_history and not payload.tested_scenarios
    if not prior_sims and session_id and not is_fresh_conversation:
        cached_sims = session_data.get("simulations_history") or session_data.get("simulations") or []
        if cached_sims:
            prior_sims.extend(cached_sims)

    # STRICT SEPARATION: collected_results holds specialist evidence collected strictly for THIS turn.
    # It must start empty. Prior observational traffic/pollution must NEVER be injected into collected_results.
    collected_results: Dict[str, Any] = {}
    simulations_history: List[Dict[str, Any]] = list(prior_sims) if prior_sims else []
    if simulations_history:
        collected_results["simulations"] = simulations_history
        collected_results["simulations_history"] = simulations_history

    # Determine effective duration, scenario, and seed
    obj_lower = effective_objective.lower()
    from backend.agents.planner_agent.scope import request_involves_traffic_optimization_or_simulation
    is_opt_request = request_involves_traffic_optimization_or_simulation(obj_lower)

    import re
    is_cross_horizon = ("300" in obj_lower and "600" in obj_lower) or ("between 300 and 600" in obj_lower)
    req_duration = payload.duration_seconds
    if is_cross_horizon:
        req_duration = None
    elif req_duration is None:
        dur_match = re.search(r"\b(120|300|600)\s*(?:-|\s)?(?:s|sec|second)?\b", obj_lower)
        if dur_match:
            val = int(dur_match.group(1))
            if val == 600:
                req_duration = DEFAULT_PRODUCTION_EVALUATION_DURATION_SECONDS
            elif val == 300:
                req_duration = HISTORICAL_EVALUATION_DURATION_SECONDS
            elif val == 120:
                req_duration = CI_SMOKE_EVALUATION_DURATION_SECONDS
        elif is_opt_request:
            req_duration = DEFAULT_PRODUCTION_EVALUATION_DURATION_SECONDS

    # Determine request seed:
    # 1. If explicit seed was provided (in payload.seed or parsed from objective), preserve it.
    # 2. If follow-up query with prior simulation history, inherit prior simulation seed.
    # 3. Otherwise, generate a fresh randomized seed for this planning request.
    if payload.seed is None:
        prior_seed = None
        for s in prior_sims:
            if isinstance(s, dict) and s.get("seed") is not None:
                prior_seed = s.get("seed")
                break
        if prior_seed is not None:
            payload.seed = prior_seed
        else:
            try:
                import random
                payload.seed = random.randint(1000, 99999)
            except Exception as exc:
                logger.warning(f"Failed to generate random seed: {exc}. Defaulting to 42.")
                payload.seed = 42

    # Stage 1: Autonomous Initial Plan & Agent Selection
    t_stage1_start = time.perf_counter()
    try:
        plan_decision = planner_agent.plan_autonomous(
            objective=effective_objective,
            location=payload.location,
            constraints=payload.constraints,
            simulation_history=simulations_history,
            existing_results=collected_results,
            duration_seconds=req_duration,
            scenario=payload.scenario,
            seed=payload.seed,
            conversation_history=payload.conversation_history,
        )
        stage_latencies["stage_1_ms"] = round((time.perf_counter() - t_stage1_start) * 1000.0, 1)
    except (LLMConfigurationError, LLMProviderError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="LLM_PLANNER_UNAVAILABLE",
                    message=str(exc),
                    details={"request_id": req_id},
                    correlation_id=make_id("corr"),
                    timestamp=utc_now_iso(),
                )
            ).model_dump(),
        )

    if not plan_decision.relevant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="QUERY_OUT_OF_SCOPE",
                    message=plan_decision.response or "This question is outside the scope of the Smart City system.",
                    details={"request_id": req_id},
                    correlation_id=make_id("corr"),
                    timestamp=utc_now_iso(),
                )
            ).model_dump(),
        )

    dispatched_agents: List[str] = []
    failures: Dict[str, Any] = {}
    executed_scenario_ids: set = set()
    max_cycles = min(payload.max_cycles or 3, 3)
    current_cycle = 1
    current_next_action = plan_decision.next_action
    current_agent_requests = plan_decision.agent_requests
    eval_result = None

    while current_cycle <= max_cycles:
        # Step A: Dispatch specialist requests determined by Planner
        if current_next_action in ("collect_evidence", "run_simulation", "request_more_evidence"):
            for call in current_agent_requests:
                agent_cap = call.agent.lower().strip()
                req_payload = dict(call.request or {})

                if agent_cap == "simulation":
                    # Step 1: Parse request
                    # req_payload is already dict(call.request or {})

                    # Step 2: Resolve preliminary experiment/request metadata
                    from backend.agents.traffic_agent.location_resolver import LocationResolver
                    loc_resolved = LocationResolver.resolve(
                        query_text=payload.objective,
                        explicit_location=req_payload.get("location") or payload.location,
                    )
                    prelim_loc = loc_resolved.name if loc_resolved else (req_payload.get("location") or payload.location or "Hyderabad")
                    default_net = f"{loc_resolved.slug}_network.net.xml" if loc_resolved else "hyderabad_network.net.xml"

                    prelim_dur = req_payload.get("duration_seconds") or req_duration or DEFAULT_PRODUCTION_EVALUATION_DURATION_SECONDS
                    prelim_scen = req_payload.get("scenario_name") or req_payload.get("scenario") or payload.scenario or "synthetic_peak_westbound"
                    prelim_seed = req_payload.get("seed") if req_payload.get("seed") is not None else payload.seed
                    prelim_net = req_payload.get("network_name") or req_payload.get("network") or default_net

                    # Step 3: Resolve matching canonical baseline & structured baseline reference
                    canonical_baseline = resolve_canonical_baseline(
                        simulations_history=simulations_history,
                        collected_results=collected_results,
                        target_scen=prelim_scen,
                        target_dur=prelim_dur,
                        target_seed=prelim_seed,
                        target_net=prelim_net,
                    )

                    baseline_ref = req_payload.get("baseline_reference")
                    if not baseline_ref and canonical_baseline:
                        baseline_ref = canonical_baseline.get("baseline_reference")
                    if not baseline_ref and canonical_baseline:
                        base_sd = canonical_baseline.get("seed") if canonical_baseline.get("seed") is not None else prelim_seed
                        base_d = canonical_baseline.get("duration_seconds") or prelim_dur
                        base_sc = canonical_baseline.get("scenario") or canonical_baseline.get("scenario_name") or prelim_scen
                        base_nt = canonical_baseline.get("network") or canonical_baseline.get("network_name") or prelim_net
                        baseline_ref = {
                            "scenario_id": canonical_baseline.get("scenario_id") or f"baseline:dur{base_d}s" + (f":seed{base_sd}" if base_sd is not None else ""),
                            "scenario": base_sc,
                            "duration_seconds": int(base_d),
                            "seed": base_sd,
                            "network": base_nt,
                        }

                    # Baseline reference and metrics must be explicitly attached
                    # and defensively copied so the canonical baseline remains immutable.
                    if canonical_baseline:
                        req_payload["baseline_metrics"] = copy.deepcopy(canonical_baseline)
                    else:
                        req_payload.setdefault("baseline_metrics", None)

                    if baseline_ref:
                        req_payload["baseline_reference"] = copy.deepcopy(baseline_ref)
                    else:
                        req_payload.setdefault("baseline_reference", None)

                    # Step 4: Resolve seed / duration / scenario / network following strict precedence:
                    # explicit request value -> matching baseline_ref -> configured production default (no invented seed)
                    sim_seed = (
                        req_payload.get("seed")
                        if req_payload.get("seed") is not None
                        else (
                            payload.seed
                            if payload.seed is not None
                            else (
                                baseline_ref.get("seed")
                                if (baseline_ref and baseline_ref.get("seed") is not None)
                                else (
                                    canonical_baseline.get("seed")
                                    if (canonical_baseline and canonical_baseline.get("seed") is not None)
                                    else None
                                )
                            )
                        )
                    )

                    sim_dur = (
                        req_payload.get("duration_seconds")
                        or payload.duration_seconds
                        or req_duration
                        or (baseline_ref.get("duration_seconds") if (baseline_ref and baseline_ref.get("duration_seconds")) else None)
                        or (canonical_baseline.get("duration_seconds") if (canonical_baseline and canonical_baseline.get("duration_seconds")) else None)
                        or DEFAULT_PRODUCTION_EVALUATION_DURATION_SECONDS
                    )

                    sim_scen = (
                        req_payload.get("scenario_name")
                        or req_payload.get("scenario")
                        or payload.scenario
                        or (baseline_ref.get("scenario") if (baseline_ref and baseline_ref.get("scenario")) else None)
                        or (canonical_baseline.get("scenario") if (canonical_baseline and canonical_baseline.get("scenario")) else None)
                        or "synthetic_peak_westbound"
                    )

                    sim_net = (
                        req_payload.get("network_name")
                        or req_payload.get("network")
                        or (baseline_ref.get("network") if (baseline_ref and baseline_ref.get("network")) else None)
                        or (canonical_baseline.get("network") if (canonical_baseline and canonical_baseline.get("network")) else None)
                        or default_net
                    )

                    sim_loc = (
                        req_payload.get("location")
                        or prelim_loc
                    )

                    req_payload["duration_seconds"] = sim_dur
                    req_payload["scenario_name"] = sim_scen
                    req_payload["scenario"] = sim_scen
                    req_payload["network_name"] = sim_net
                    req_payload["network"] = sim_net
                    req_payload["location"] = sim_loc
                    if sim_seed is not None:
                        req_payload["seed"] = sim_seed
                    elif "seed" in req_payload and req_payload["seed"] is None:
                        del req_payload["seed"]

                    # Step 5: Build intervention request
                    # Ensure structured intervention is provided for simulation and normalized exactly once
                    from backend.agents.simulation_agent.schemas import normalize_intervention
                    if not req_payload.get("intervention"):
                        if eval_result and eval_result.simulation_context and eval_result.simulation_context.get("intervention"):
                            req_payload["intervention"] = eval_result.simulation_context["intervention"]
                        elif "traffic" in collected_results:
                            trf_data = collected_results["traffic"]
                            cands = trf_data.get("candidate_interventions", [])
                            bn = trf_data.get("bottleneck_corridor") or prelim_loc or "Westbound"
                            if cands:
                                top_c = cands[0]
                                req_payload["intervention"] = {
                                    "type": top_c.get("intervention_type", top_c.get("type", "signal_timing")),
                                    "target": top_c.get("target", bn),
                                    "parameters": top_c.get("parameters", {"green_time_adjustment_sec": 15.0}),
                                }
                            else:
                                req_payload["intervention"] = {
                                    "type": "signal_timing",
                                    "target": bn,
                                    "parameters": {"green_time_adjustment_sec": 15.0},
                                }

                    req_payload["intervention"] = normalize_intervention(
                        req_payload.get("intervention"),
                        default_target=prelim_loc
                    )

                    # If an intervention is being simulated, ensure a paired canonical baseline is executed first
                    has_intervention = bool(req_payload.get("intervention"))
                    if has_intervention and not canonical_baseline:
                        logger.info(f"[Supervisor] No canonical baseline exists for {sim_net} (seed={sim_seed}, dur={sim_dur}s). Executing baseline first.")
                        baseline_req_payload = copy.deepcopy(req_payload)
                        baseline_req_payload["intervention"] = None
                        baseline_req_payload.pop("candidate_intervention", None)
                        baseline_req_payload.pop("signal_optimization", None)
                        baseline_req_payload.pop("intervention_applied", None)
                        baseline_scen_id = f"baseline:dur{int(sim_dur)}s" + (f":seed{sim_seed}" if sim_seed is not None else "")
                        baseline_req_payload["scenario_id"] = baseline_scen_id
                        baseline_req_payload["baseline_metrics"] = None
                        baseline_req_payload["baseline_reference"] = None
                        try:
                            t_base_start = time.perf_counter()
                            baseline_res = dispatch_agent("simulation", baseline_req_payload)
                            executed_scenario_ids.add(baseline_scen_id)
                            simulations_history.append(baseline_res)
                            canonical_baseline = copy.deepcopy(baseline_res)
                            baseline_ref = {
                                "scenario_id": baseline_scen_id,
                                "scenario": sim_scen,
                                "duration_seconds": int(sim_dur),
                                "seed": sim_seed,
                                "network": sim_net,
                            }
                            req_payload["baseline_metrics"] = copy.deepcopy(canonical_baseline)
                            req_payload["baseline_reference"] = copy.deepcopy(baseline_ref)
                            specialist_calls_record.append({
                                "agent": "simulation",
                                "status": "completed",
                                "latency_ms": round((time.perf_counter() - t_base_start) * 1000.0, 1),
                            })
                        except Exception as exc:
                            logger.warning(f"[Supervisor] Failed to auto-execute baseline simulation: {exc}")

                    from backend.agents.simulation_agent.service import SimulationService
                    scen_id = req_payload.get("scenario_id") or SimulationService.generate_scenario_id(
                        req_payload.get("intervention"),
                        seed=sim_seed,
                        duration=sim_dur,
                    )
                    req_payload["scenario_id"] = scen_id

                    # Accidental duplicate scenario detection
                    if scen_id in executed_scenario_ids:
                        logger.info(f"Duplicate scenario '{scen_id}' requested; reusing previous simulation evidence.")
                        cached_sim = next((s for s in simulations_history if s.get("scenario_id") == scen_id), None)
                        if cached_sim:
                            agent_res = dict(cached_sim)
                            agent_res["duplicate_detected"] = True
                        else:
                            agent_res = dispatch_agent(agent_cap, req_payload)
                    else:
                        t_sim_start = time.perf_counter()
                        try:
                            agent_res = dispatch_agent(agent_cap, req_payload)
                            if not validate_agent_locality(sim_loc, agent_res, "simulation"):
                                err_msg = f"Locality mismatch in simulation: expected '{sim_loc}', but received '{agent_res.get('location') if isinstance(agent_res, dict) else 'unknown'}'"
                                logger.error(f"[Supervisor] {err_msg}")
                                failures[agent_cap] = err_msg
                                agent_res = None
                            else:
                                executed_scenario_ids.add(scen_id)
                                simulations_history.append(agent_res)
                                sim_dur = round((time.perf_counter() - t_sim_start) * 1000.0, 1)
                                specialist_calls_record.append({
                                    "agent": agent_cap,
                                    "status": "completed",
                                    "latency_ms": sim_dur,
                                })
                        except Exception as exc:
                            failures[agent_cap] = str(exc)
                            agent_res = None
                            sim_dur = round((time.perf_counter() - t_sim_start) * 1000.0, 1)
                            specialist_calls_record.append({
                                "agent": agent_cap,
                                "status": "failed",
                                "latency_ms": sim_dur,
                            })

                    if agent_res is not None:
                        collected_results["simulations"] = simulations_history
                        collected_results["simulation"] = simulations_history if len(simulations_history) > 1 else agent_res
                        agent_tag = f"{agent_cap}_agent"
                        if agent_tag not in dispatched_agents:
                            dispatched_agents.append(agent_tag)
                else:
                    t_spec_start = time.perf_counter()
                    try:
                        # Propagate resolved locality and context consistently across ALL specialist agents
                        from backend.agents.traffic_agent.location_resolver import LocationResolver
                        loc_res = LocationResolver.resolve(
                            explicit_location=payload.location,
                            query_text=payload.objective,
                        )
                        resolved_loc_str = f"{loc_res.name}, Hyderabad" if loc_res else (payload.location or "Hyderabad")
                        req_payload["location"] = resolved_loc_str
                        if payload.objective and "query_text" not in req_payload:
                            req_payload["query_text"] = payload.objective

                        if agent_cap == "traffic":
                            if req_duration is not None and "duration_seconds" not in req_payload:
                                req_payload["duration_seconds"] = req_duration
                            if payload.scenario and "scenario" not in req_payload:
                                req_payload["scenario"] = payload.scenario
                            if payload.seed is not None and "seed" not in req_payload:
                                req_payload["seed"] = payload.seed
                        agent_res = dispatch_agent(agent_cap, req_payload)

                        # Validate returned locality before combining agent results
                        if not validate_agent_locality(resolved_loc_str, agent_res, agent_cap):
                            err_msg = (
                                f"Locality mismatch: expected evidence for '{resolved_loc_str}', "
                                f"but received data for '{agent_res.get('location') if isinstance(agent_res, dict) else 'unknown'}'."
                            )
                            logger.error(f"[Supervisor] {err_msg}")
                            failures[agent_cap] = err_msg
                        else:
                            collected_results[agent_cap] = agent_res
                            if agent_cap == "traffic" and isinstance(agent_res, dict):
                                actual_sim_seed = agent_res.get("seed") or (agent_res.get("metadata", {}) or {}).get("random_seed")
                                if actual_sim_seed is not None:
                                    payload.seed = actual_sim_seed
                            agent_tag = f"{agent_cap}_agent"
                            if agent_tag not in dispatched_agents:
                                dispatched_agents.append(agent_tag)
                        spec_dur = round((time.perf_counter() - t_spec_start) * 1000.0, 1)
                        spec_rec = {
                            "agent": agent_cap,
                            "status": "completed",
                            "latency_ms": spec_dur,
                        }
                        if isinstance(agent_res, dict):
                            if "data_mode" in agent_res:
                                spec_rec["data_mode"] = agent_res["data_mode"]
                            if "data_source" in agent_res:
                                spec_rec["data_source"] = agent_res["data_source"]
                        specialist_calls_record.append(spec_rec)
                        logger.info(
                            f"[Supervisor] Specialist '{agent_cap}' completed in {spec_dur}ms "
                            f"(mode={spec_rec.get('data_mode', 'standard')}, source={spec_rec.get('data_source', 'standard')})"
                        )
                    except Exception as exc:
                        failures[agent_cap] = str(exc)
                        spec_dur = round((time.perf_counter() - t_spec_start) * 1000.0, 1)
                        specialist_calls_record.append({
                            "agent": agent_cap,
                            "status": "failed",
                            "latency_ms": spec_dur,
                        })

        # Step B: Evaluate collected evidence with LLM Planner
        t_eval_start = time.perf_counter()
        try:
            eval_result = planner_agent.evaluate_and_replan(
                objective=effective_objective,
                plan=plan_decision.required_capabilities,
                collected_results=collected_results,
                failures=failures,
                cycle_num=current_cycle,
                max_cycles=max_cycles,
                location=payload.location or "Hyderabad",
            )
            stage_latencies[f"cycle_{current_cycle}_eval_ms"] = round((time.perf_counter() - t_eval_start) * 1000.0, 1)
        except (LLMConfigurationError, LLMProviderError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        code="LLM_PLANNER_UNAVAILABLE",
                        message=str(exc),
                        details={"request_id": req_id, "cycle": current_cycle},
                        correlation_id=make_id("corr"),
                        timestamp=utc_now_iso(),
                    )
                ).model_dump(),
            )

        # Step C: Check if Planner has finalized or reached terminating state
        if eval_result.decision in ("finalize", "abort") or eval_result.next_action in ("finalize", "abort"):
            break

        # If more cycles requested and within limit, proceed to next cycle
        if current_cycle < max_cycles:
            current_cycle += 1
            current_next_action = eval_result.next_action
            current_agent_requests = eval_result.next_cycle_calls
        else:
            break

    if eval_result.final_reasoning:
        final_reasoning_dict = eval_result.final_reasoning.model_dump()
    else:
        # Fallback if final_reasoning is somehow None
        from backend.agents.planner_agent.planner import PlannerAgent
        fallback_sum = PlannerAgent._build_deterministic_specialist_summary(
            objective=effective_objective,
            collected_results=collected_results,
            location=payload.location,
        )
        final_reasoning_dict = {
            "summary": fallback_sum or eval_result.analysis,
            "recommendation": eval_result.final_recommendation or "",
            "confidence": eval_result.confidence,
            "decision": eval_result.decision,
            "evidence_status": eval_result.evidence_status,
        }

    # Honest evidence_status based on executed simulation history or collected specialist evidence
    from backend.agents.planner_agent.planner import is_analytical_history_followup
    new_sims_this_turn = len(executed_scenario_ids)
    is_sim_followup = is_analytical_history_followup(effective_objective) and len(simulations_history) > 0

    if new_sims_this_turn >= 2 or (is_sim_followup and len(simulations_history) >= 2):
        det_evidence_status = "EVIDENCE: MULTI-SIMULATION EVALUATION"
        rec_basis = "SIMULATION_TESTED_EVIDENCE"
    elif new_sims_this_turn == 1 or (is_sim_followup and len(simulations_history) == 1):
        det_evidence_status = "EVIDENCE: SINGLE SIMULATION RUN"
        rec_basis = "SIMULATION_TESTED_EVIDENCE"
    else:
        # No simulation executed this turn and not an analytical simulation follow-up
        has_pol = "pollution" in collected_results and "pollution" not in failures
        has_trf = "traffic" in collected_results and "traffic" not in failures
        has_wtr = "weather" in collected_results and "weather" not in failures
        has_eng = "energy" in collected_results and "energy" not in failures

        if has_pol and not has_trf:
            det_evidence_status = "EVIDENCE: MODELLED ESTIMATE"
            rec_basis = "MODELLED_ENVIRONMENTAL_ANALYSIS"
        elif has_trf and has_pol:
            det_evidence_status = "EVIDENCE: MULTI-SOURCE (API & MODELLED)"
            rec_basis = "MULTI_DOMAIN_TELEMETRY_AND_MODEL"
        elif has_trf or has_wtr or has_eng:
            det_evidence_status = "EVIDENCE: API-SOURCED TELEMETRY"
            rec_basis = "OBSERVATIONAL_TELEMETRY_ONLY"
        else:
            det_evidence_status = "EVIDENCE: MUNICIPAL ADVISORY & RECOMMENDATION"
            rec_basis = "EXPERT_MUNICIPAL_KNOWLEDGE"

    eval_result.evidence_status = det_evidence_status
    final_reasoning_dict["evidence_status"] = det_evidence_status

    if eval_result.final_reasoning:
        final_reasoning_dict["tested_interventions"] = eval_result.final_reasoning.tested_interventions
        final_reasoning_dict["untested_candidates"] = eval_result.final_reasoning.untested_candidates
        final_reasoning_dict["recommendation_basis"] = rec_basis
    else:
        final_reasoning_dict.setdefault("tested_interventions", [])
        final_reasoning_dict.setdefault("untested_candidates", [])
        final_reasoning_dict["recommendation_basis"] = rec_basis

    if eval_result.cross_analysis:
        final_reasoning_dict["key_findings"] = eval_result.cross_analysis.key_findings
        final_reasoning_dict["diagnosed_bottlenecks"] = eval_result.cross_analysis.diagnosed_bottlenecks
        if eval_result.cross_analysis.simulation_comparison:
            final_reasoning_dict["simulation_comparison"] = eval_result.cross_analysis.simulation_comparison

    # Ensure tested_scenarios and corridor_trade_offs are in final_reasoning_dict
    if simulations_history:
        # Horizon-aware comparison selection based on requested duration
        matching_sims = [
            s for s in simulations_history
            if req_duration is None
            or s.get("duration_seconds") == req_duration
            or (s.get("comparison", {}) if isinstance(s.get("comparison"), dict) else {}).get("intervention_duration_seconds") == req_duration
            or (s.get("metadata", {}) if isinstance(s.get("metadata"), dict) else {}).get("duration_seconds") == req_duration
        ]
        target_sim = matching_sims[-1] if matching_sims else (simulations_history[-1] if simulations_history else {})
        final_reasoning_dict["comparison"] = target_sim.get("comparison")
        final_reasoning_dict["metric_changes"] = target_sim.get("comparison")
        if not final_reasoning_dict.get("simulation_comparison"):
            final_reasoning_dict["simulation_comparison"] = target_sim.get("comparison")

        # PART 6: Structured Active Experiment Context
        from backend.agents.traffic_agent.location_resolver import LocationResolver
        loc_res_final = LocationResolver.resolve(
            query_text=payload.objective,
            explicit_location=payload.location,
        )
        resolved_net = f"{loc_res_final.slug}_network.net.xml" if loc_res_final else "hyderabad_network.net.xml"

        final_reasoning_dict["requested_duration"] = "BOTH" if is_cross_horizon else req_duration
        final_reasoning_dict["requested_scenario"] = payload.scenario or (target_sim.get("scenario") if isinstance(target_sim, dict) else None) or "synthetic_peak_westbound"
        final_reasoning_dict["requested_seed"] = payload.seed or (target_sim.get("seed") if isinstance(target_sim, dict) else None)
        final_reasoning_dict["requested_network"] = (target_sim.get("network_name") if isinstance(target_sim, dict) else None) or resolved_net

        tested_scenarios_list = []
        for s in simulations_history:
            if not isinstance(s, dict):
                continue
            s_comp = s.get("comparison", {}) if isinstance(s.get("comparison"), dict) else {}
            s_meta = s.get("metadata", {}) if isinstance(s.get("metadata"), dict) else {}
            b_ref = s.get("baseline_reference") or s_comp.get("baseline_reference")
            b_metrics = s.get("baseline_metrics") or s_comp.get("baseline_summary")
            int_metrics = s.get("intervention_metrics") or s_comp.get("intervention_summary") or s.get("metrics")
            s_network = s.get("network_name") or s_comp.get("intervention_network") or s_meta.get("network_name") or resolved_net

            tested_scenarios_list.append({
                "scenario_id": s.get("scenario_id"),
                "scenario": s.get("scenario") or s_comp.get("intervention_scenario") or s_meta.get("demand_profile") or "synthetic_peak_westbound",
                "duration_seconds": s.get("duration_seconds") or s_comp.get("intervention_duration_seconds") or s_meta.get("duration_seconds"),
                "seed": s.get("seed") or s_comp.get("intervention_seed") or s_meta.get("random_seed"),
                "network": s_network,
                "network_name": s_network,
                "intervention": s.get("intervention_applied") or s.get("intervention"),
                "baseline_reference": b_ref,
                "baseline_metrics": b_metrics,
                "intervention_metrics": int_metrics,
                "metrics": s.get("metrics") or int_metrics,
                "comparison": s.get("comparison"),
                "corridor_trade_offs": s.get("corridor_trade_offs", []),
                "trade_off_summary": s.get("trade_off_summary"),
                "fair_comparison": s_comp.get("fair_comparison", True),
                "evidence_status": s.get("evidence_status") or det_evidence_status,
            })

        verify_multi_intervention_invariant(tested_scenarios_list)
        final_reasoning_dict["tested_scenarios"] = tested_scenarios_list
    final_reasoning_dict.setdefault("requested_duration", "BOTH" if is_cross_horizon else req_duration)
    final_reasoning_dict.setdefault("requested_scenario", payload.scenario or "synthetic_peak_westbound")
    final_reasoning_dict.setdefault("requested_seed", payload.seed)
    from backend.agents.traffic_agent.location_resolver import LocationResolver
    _lres = LocationResolver.resolve(query_text=payload.objective, explicit_location=payload.location)
    final_reasoning_dict.setdefault("requested_network", f"{_lres.slug}_network.net.xml" if _lres else "hyderabad_network.net.xml")

    agent_results_payload = dict(collected_results)
    if simulations_history:
        agent_results_payload["simulations"] = simulations_history
        agent_results_payload["simulation"] = simulations_history if len(simulations_history) > 1 else simulations_history[0]

    feedback_dict = {
        "decision": eval_result.decision,
        "next_action": eval_result.next_action,
        "evidence_status": det_evidence_status,
        "confidence": eval_result.confidence,
        "insights": {
            "analysis": eval_result.analysis,
            "recommendation": eval_result.final_recommendation,
            "cross_analysis": eval_result.cross_analysis.model_dump() if eval_result.cross_analysis else None,
            "agent_results": agent_results_payload,
        },
        "next_steps": eval_result.revised_plan if not eval_result.goal_achieved else ["implement_recommendation", "monitor_flow"],
    }

    status_str = "COMPLETED" if eval_result.goal_achieved else (
        "SIMULATION_REQUIRED" if eval_result.next_action == "run_simulation" else (
            "ABORTED" if eval_result.decision == "abort" else "NEEDS_REPLANNING"
        )
    )

    # Session store caching for current session_id / conversation_id
    if session_id:
        _PLANNER_SESSIONS[session_id] = {
            "conversation_id": session_id,
            "session_id": session_id,
            "last_locality": payload.location,
            "simulations_history": simulations_history,
            "tested_scenarios": final_reasoning_dict.get("tested_scenarios", []),
            "tested_interventions": final_reasoning_dict.get("tested_interventions", []),
            "untested_candidates": final_reasoning_dict.get("untested_candidates", []),
            "evidence_status": det_evidence_status,
            "last_updated": utc_now_iso(),
        }

    provider_obj = getattr(planner_agent, "llm_provider", None)
    provider_name = getattr(provider_obj, "provider_name", "unknown") if provider_obj else "unknown"
    provider_model = getattr(provider_obj, "model", "unknown") if provider_obj else "unknown"

    total_latency_ms = round((time.perf_counter() - t_start) * 1000.0, 1)
    runtime_metadata = {
        "request_id": req_id,
        "conversation_id": session_id or None,
        "session_id": session_id or None,
        "location": payload.location,
        "llm_provider": provider_name,
        "llm_model": provider_model,
        "llm_calls": 3 if current_cycle == 1 else (3 + (current_cycle - 1) * 2),
        "specialist_calls": specialist_calls_record,
        "simulation_runs": [s.get("scenario_id") for s in simulations_history if isinstance(s, dict) and s.get("scenario_id")],
        "cache_used": False,
        "total_latency_ms": total_latency_ms,
        "stage_latencies_ms": stage_latencies,
    }

    final_reasoning_dict["location"] = payload.location

    return PlannerExecuteResponse(
        request_id=req_id,
        conversation_id=session_id or None,
        session_id=session_id or None,
        location=payload.location,
        status=status_str,
        cycle=current_cycle,
        selected_capabilities=plan_decision.required_capabilities,
        dispatched_agents=dispatched_agents,
        agent_results=agent_results_payload,
        collected_results=collected_results,
        failures=failures,
        planner_feedback=feedback_dict,
        final_response=final_reasoning_dict,
        evidence_status=det_evidence_status,
        confidence=eval_result.confidence,
        created_at=utc_now_iso(),
        runtime=runtime_metadata,
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


# ---------------------------------------------------------------------------
# Specialist Agent APIs (Traffic, Weather, Pollution, Energy, Simulation)
# ---------------------------------------------------------------------------
from backend.agents.traffic_agent.main import router as traffic_router
from backend.agents.weather_agent.main import router as weather_router
from backend.agents.pollution_agent.main import router as pollution_router
from backend.agents.energy_agent.main import router as energy_router
from backend.agents.simulation_agent.main import router as simulation_router

app.include_router(traffic_router, tags=["Specialist Agent - Traffic"])
app.include_router(weather_router, tags=["Specialist Agent - Weather"])
app.include_router(pollution_router, tags=["Specialist Agent - Pollution"])
app.include_router(energy_router, tags=["Specialist Agent - Energy"])
app.include_router(simulation_router, tags=["Specialist Agent - Simulation"])

# ---------------------------------------------------------------------------
# TomTom Traffic Intelligence API (/api/traffic/*, /api/tiles/*)
# ---------------------------------------------------------------------------
from backend.routers.traffic import router as tomtom_traffic_router  # noqa: E402

app.include_router(tomtom_traffic_router, tags=["Traffic - TomTom"])

