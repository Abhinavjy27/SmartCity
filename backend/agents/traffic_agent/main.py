"""
SUPADSP Specialist Agent — Traffic Intelligence (Eclipse SUMO Microsimulation Boundary).
Executes reproducible synthetic traffic demand simulations on the Narayanguda road network
and returns structured evidence metrics to the LLM Planner without Orchestrator mediation.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, FastAPI, HTTPException, Query, status

from backend.agents.traffic_agent.schemas import (
    SignalOptimizationRequest,
    SignalOptimizationResponse,
    TrafficAnalyzeRequest,
    TrafficEvidenceResponse,
)
from backend.agents.traffic_agent.service import TrafficService, get_traffic_service
from backend.agents.traffic_agent.sumo_runner import SumoExecutionError

app = FastAPI(
    title="SUPADSP Traffic Agent (Eclipse SUMO)",
    version="2.0.0",
    description="Specialist Simulation Agent running Eclipse SUMO 1.27.1 on Narayanguda, Hyderabad.",
)
router = APIRouter()


@app.get("/health")
def health():
    svc = get_traffic_service()
    return {
        "agent": "Traffic Agent",
        "status": "ONLINE",
        "sumo_available": True,
        "sumo_version": "1.27.1",
        "network": "narayanguda_network.net.xml",
        "supported_scenarios": svc.get_supported_scenarios(),
    }


@router.get(
    "/api/v1/traffic/kpis",
    summary="Get baseline traffic KPIs from Eclipse SUMO simulation",
    response_model=TrafficEvidenceResponse,
)
def get_traffic_kpis(
    location: str = Query("Narayanguda, Hyderabad", description="Target locality"),
    scenario: str = Query("synthetic_normal", description="Synthetic demand scenario name"),
    duration_seconds: int = Query(120, description="Simulation duration in seconds"),
    seed: int = Query(42, description="Random seed for deterministic demand generation"),
    purpose: Optional[str] = Query("baseline_traffic_analysis", description="Planner objective context"),
    force_fresh: bool = Query(False, description="Bypass cache and execute simulation afresh"),
) -> Dict[str, Any]:
    svc = get_traffic_service()
    try:
        evidence = svc.run_baseline_simulation(
            location=location,
            scenario=scenario,
            duration_seconds=duration_seconds,
            seed=seed,
            purpose=purpose or "baseline_traffic_analysis",
            force_fresh=force_fresh,
        )
        return evidence.model_dump()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_SCENARIO", "message": str(exc)},
        )
    except SumoExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "SUMO_SIMULATION_ERROR", "message": str(exc), "details": exc.details},
        )


@router.post(
    "/api/v1/traffic/analyze",
    summary="Analyze traffic for a scenario via Eclipse SUMO baseline simulation",
    response_model=TrafficEvidenceResponse,
)
def analyze_traffic(req: Optional[TrafficAnalyzeRequest] = None) -> Dict[str, Any]:
    svc = get_traffic_service()
    req = req or TrafficAnalyzeRequest()
    try:
        evidence = svc.run_baseline_simulation(
            location=req.location or "Narayanguda, Hyderabad",
            scenario=req.scenario or "synthetic_normal",
            duration_seconds=req.duration_seconds or 120,
            seed=req.seed if req.seed is not None else 42,
            purpose=req.purpose or "baseline_traffic_analysis",
            force_fresh=req.force_fresh or False,
        )
        return evidence.model_dump()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_SCENARIO", "message": str(exc)},
        )
    except SumoExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "SUMO_SIMULATION_ERROR", "message": str(exc), "details": exc.details},
        )


@router.post(
    "/api/v1/traffic/optimize-signal",
    summary="Generate and validate signal optimization candidate parameters",
    response_model=SignalOptimizationResponse,
)
def optimize_signal(req: Optional[SignalOptimizationRequest] = None) -> Dict[str, Any]:
    svc = get_traffic_service()
    req = req or SignalOptimizationRequest()
    try:
        resp = svc.validate_signal_timing(
            intersection_id=req.intersection_id,
            target_corridor=req.target_corridor,
            green_adjustment=req.green_time_adjustment_sec if req.green_time_adjustment_sec is not None else 15.0,
            cycle_sec=req.current_cycle_sec if req.current_cycle_sec is not None else 120,
        )
        return resp.model_dump()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_SIGNAL_PARAMETERS", "message": str(exc)},
        )


app.include_router(router)
