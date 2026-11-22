"""
SUPADSP Specialist Agent — Traffic Intelligence (Live TomTom Telemetry).
Fulfills all real-world traffic monitoring, condition queries, and bottleneck detection
using the TomTom Traffic API. SUMO simulation is strictly restricted to the Simulation Agent.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, FastAPI, HTTPException, Query, status

from backend.agents.traffic_agent.location_resolver import LocationResolver
from backend.agents.traffic_agent.network_manager import get_network_manager
from backend.agents.traffic_agent.schemas import (
    TrafficAnalyzeRequest,
    TrafficEvidenceResponse,
)
from backend.agents.traffic_agent.service import get_traffic_service

app = FastAPI(
    title="SUPADSP Traffic Agent (Live TomTom Telemetry)",
    version="2.0.0",
    description="Specialist Traffic Agent providing real-time TomTom Traffic Flow and Incidents intelligence for Hyderabad.",
)
router = APIRouter()


@app.get("/health")
def health():
    svc = get_traffic_service()
    return {
        "agent": "Traffic Agent",
        "status": "ONLINE",
        "data_source": "TomTom Traffic API",
        "traffic_mode": "live",
        "supported_localities": LocationResolver.get_supported_localities(),
        "supported_scenarios": svc.get_supported_scenarios(),
    }


@router.get(
    "/api/v1/traffic/kpis",
    summary="Get real-time live traffic KPIs from TomTom Traffic API",
    response_model=TrafficEvidenceResponse,
)
def get_traffic_kpis(
    location: Optional[str] = Query(None, description="Target locality"),
    query_text: Optional[str] = Query(None, description="Natural language user query for locality resolution"),
    scenario: str = Query("live_observed", description="Telemetry mode or scenario context"),
    duration_seconds: int = Query(120, description="Reference duration in seconds"),
    seed: Optional[int] = Query(None, description="Optional seed reference"),
    purpose: Optional[str] = Query("live_traffic_monitoring", description="Planner objective context"),
    force_fresh: bool = Query(False, description="Bypass cache and query TomTom API freshly"),
) -> Dict[str, Any]:
    svc = get_traffic_service()
    try:
        evidence = svc.get_traffic_kpis(
            location=location,
            query_text=query_text,
            scenario=scenario,
            duration_seconds=duration_seconds,
            seed=seed,
            purpose=purpose or "live_traffic_monitoring",
            force_fresh=force_fresh,
        )
        return evidence.model_dump()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "TRAFFIC_AGENT_ERROR", "message": str(exc)},
        )


@router.post(
    "/api/v1/traffic/analyze",
    summary="Analyze live traffic for a locality via TomTom Traffic API",
    response_model=TrafficEvidenceResponse,
)
def analyze_traffic(req: Optional[TrafficAnalyzeRequest] = None) -> Dict[str, Any]:
    svc = get_traffic_service()
    req = req or TrafficAnalyzeRequest()
    try:
        evidence = svc.analyze_traffic(req)
        return evidence.model_dump()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "TRAFFIC_AGENT_ERROR", "message": str(exc)},
        )


@router.get(
    "/api/v1/traffic/networks",
    summary="List available authentic OpenStreetMap SUMO road networks",
)
def list_networks() -> List[Dict[str, Any]]:
    nm = get_network_manager()
    return nm.list_available_networks()


app.include_router(router)
