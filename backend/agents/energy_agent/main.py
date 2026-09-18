"""
SUPADSP Specialist Agent — Energy Grid Intelligence
Real-Time FastAPI Specialist Agent for Substation Telemetry, Grid Load Analysis, Peak Shaving, and Cross-Domain Optimization.
Maintains strict contract compliance with SUPADSP Planner, Supervisor, and Frontend views.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, FastAPI, Query

from backend.agents.energy_agent.load_calculator import compute_telemetry_state
from backend.agents.energy_agent.optimizer import execute_peak_shaving, generate_recommendations
from backend.agents.energy_agent.schema import (
    EnergyAnalyzeRequest,
    EnergyAnalyzeResponse,
    GridStatusResponse,
    PeakShavingRequest,
    PeakShavingResponse,
    SubstationData,
    ZoneConsumption,
)
from backend.agents.energy_agent.substations import SUBSTATIONS_DB, match_substations_by_location

app = FastAPI(
    title="SUPADSP Energy Agent",
    version="2.0.0",
    description="Specialist AI Agent for Substation Telemetry, Diurnal Grid Load Monitoring, and Peak Shaving Optimization.",
)
router = APIRouter()


@app.get("/health", tags=["System"], summary="Energy agent health check")
def health() -> Dict[str, str]:
    """Health check endpoint for container orchestrator and supervisor."""
    return {"agent": "Energy Agent", "status": "ONLINE"}


@router.get(
    "/api/v1/energy/grid-status",
    tags=["Grid Telemetry"],
    response_model=GridStatusResponse,
    summary="Get real-time grid status and substation telemetry",
)
def get_grid_status(
    location: Optional[str] = Query(
        default=None,
        description="Location, zone, or substation filter (e.g. 'Narayanguda, Hyderabad', 'Tarnaka, Hyderabad', 'Madhapur')",
    ),
    ambient_temp_c: Optional[float] = Query(
        default=None,
        ge=-20.0,
        le=65.0,
        description="Ambient temperature feed from weather agent (°C)",
    ),
    traffic_occupancy_pct: Optional[float] = Query(
        default=None,
        ge=0.0,
        le=100.0,
        description="Traffic occupancy feed from traffic agent (%)",
    ),
    ev_count: Optional[int] = Query(
        default=None,
        ge=0,
        description="Active EV fleet count estimate",
    ),
) -> Dict[str, Any]:
    """
    Primary contract endpoint.
    Ingests optional location filter and cross-domain weather / traffic context.
    Returns real-time load, capacity, severity, substation telemetry, and recommendations.
    """
    telemetry = compute_telemetry_state(
        location=location,
        ambient_temp_c=ambient_temp_c,
        traffic_occupancy_pct=traffic_occupancy_pct,
        ev_count=ev_count,
    )

    # Generate dynamic recommendations for current grid state
    recs = generate_recommendations(
        substations=telemetry["substations"],
        load_pct=telemetry["load_pct"],
        ambient_temp_c=ambient_temp_c,
        traffic_occupancy_pct=traffic_occupancy_pct,
    )
    telemetry["recommendations"] = recs

    return telemetry


@router.post(
    "/api/v1/energy/analyze",
    tags=["Analysis"],
    response_model=EnergyAnalyzeResponse,
    summary="Analyze energy grid load for scenario or specific location",
)
def analyze_energy(req: Optional[EnergyAnalyzeRequest] = None) -> EnergyAnalyzeResponse:
    """
    Specialist analysis endpoint used by supervisor and frontend model evaluation.
    Computes projected load, stability index, and projected savings.
    """
    target_location = req.location if req and req.location else "Financial District Substation"
    ambient_temp = req.ambient_temp_c if req else None
    traffic_occ = req.traffic_occupancy_pct if req else None
    ev_cnt = req.ev_count if req else None

    telemetry = compute_telemetry_state(
        location=target_location,
        ambient_temp_c=ambient_temp,
        traffic_occupancy_pct=traffic_occ,
        ev_count=ev_cnt,
    )

    recs = generate_recommendations(
        substations=telemetry["substations"],
        load_pct=telemetry["load_pct"],
        ambient_temp_c=ambient_temp,
        traffic_occupancy_pct=traffic_occ,
    )

    current_load = telemetry["current_load_mw"]
    load_pct = telemetry["load_pct"]
    severity = telemetry["severity"]
    projected_savings = round(current_load * 0.15, 1) if current_load > 0 else 6.4
    stability_index = round(max(0.70, min(0.99, 1.0 - (max(0.0, load_pct - 70.0) * 0.01))), 2)

    return EnergyAnalyzeResponse(
        status="COMPLETED",
        domain="energy",
        location=target_location,
        current_load_mw=current_load,
        load_pct=load_pct,
        severity=severity,
        projected_savings_mw=projected_savings,
        grid_stability_index=stability_index,
        confidence=0.95,
        recommendations=recs,
    )


@router.post(
    "/api/v1/energy/peak-shave",
    tags=["Optimization"],
    response_model=PeakShavingResponse,
    summary="Compute peak-shaving dispatch strategy for overloaded zone",
)
def peak_shave(req: Optional[PeakShavingRequest] = None) -> PeakShavingResponse:
    """
    Calculates battery dispatch and demand response actions to shave peak load.
    """
    request_obj = req or PeakShavingRequest()
    return execute_peak_shaving(request_obj)


@router.get(
    "/api/v1/energy/substations",
    tags=["Grid Telemetry"],
    response_model=List[SubstationData],
    summary="Query detailed substation telemetry with optional filters",
)
def get_substations(
    zone: Optional[str] = Query(default=None, description="Filter by zone"),
    status: Optional[str] = Query(default=None, description="Filter by status: CRITICAL, HIGH, NORMAL"),
) -> List[SubstationData]:
    """
    Returns list of monitored substations with optional zone/status filters.
    """
    telemetry = compute_telemetry_state()
    subs: List[SubstationData] = telemetry["substations"]

    if zone:
        subs = [s for s in subs if s.zone.lower() == zone.lower()]
    if status:
        subs = [s for s in subs if s.status.upper() == status.upper()]

    return subs


@router.get(
    "/api/v1/energy/zones",
    tags=["Grid Telemetry"],
    response_model=List[ZoneConsumption],
    summary="Query zone-wise power consumption breakdown",
)
def get_zones() -> List[ZoneConsumption]:
    """
    Returns aggregated zone consumption statistics for Hyderabad.
    """
    telemetry = compute_telemetry_state()
    return telemetry["zone_data"]


# Include router in FastAPI application instance
app.include_router(router)
