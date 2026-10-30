"""
Traffic API Router — /api/traffic/*
=====================================
All TomTom data is fetched server-side; the API key never reaches the browser.

Endpoints:
  GET /api/traffic/overview      → KPI cards (avg speed, volume, TTI, queue, etc.)
  GET /api/traffic/incidents     → Active incidents GeoJSON
  GET /api/traffic/corridors     → Per-corridor speed, travel time, status
  GET /api/traffic/trend         → 24-point hourly trend (speed + volume)
  GET /api/traffic/intersections → Intersection-level LOS table
  GET /api/traffic/flows/geojson → GeoJSON FeatureCollection for the map layer
  GET /api/traffic/usage         → API request counter + mode
  GET /api/tiles/{layer}/{z}/{x}/{y} → Proxied TomTom map/flow tiles
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Path as FPath
from fastapi.responses import Response
from pydantic import BaseModel

from backend.services.congestion_service import congestion_service
from backend.services.tomtom import (
    UsageResponse,
    CorridorsResponse,
    IncidentsGeoJSON,
    IntersectionsResponse,
    TrafficOverviewKPI,
    TrendResponse,
    fetch_corridors,
    fetch_incidents,
    fetch_intersections,
    fetch_traffic_overview,
    fetch_trend,
    fetch_flows_geojson,
    get_usage,
    proxy_tile,
    proxy_vector_tile,
    TRAFFIC_MODE,
)

logger = logging.getLogger("traffic_router")


class CongestionIndexResponse(BaseModel):
    value_pct: Optional[float] = None
    delta_pp: Optional[float] = None
    baseline_available: bool = False
    valid_points: int = 0
    total_points: int = 0
    level: Optional[str] = None
    updated_at: Optional[str] = None
    status: str = "unavailable"


class CongestionHistoryPoint(BaseModel):
    t: str
    value_pct: float


router = APIRouter()

# ---------------------------------------------------------------------------
# Traffic Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/api/traffic/congestion-index",
    response_model=CongestionIndexResponse,
    tags=["Traffic - TomTom"],
    summary="Live Network Congestion Index across 21 Hyderabad junctions",
)
def get_congestion_index() -> CongestionIndexResponse:
    """
    Serve from in-memory cache and DB. Never calls TomTom on GET.
    """
    return CongestionIndexResponse(**congestion_service.get_current_metrics())


@router.get(
    "/api/traffic/congestion-index/history",
    response_model=List[CongestionHistoryPoint],
    tags=["Traffic - TomTom"],
    summary="Stored real snapshot history for Network Congestion Index",
)
def get_congestion_index_history(hours: int = Query(24, ge=1, le=336)) -> List[CongestionHistoryPoint]:
    return [CongestionHistoryPoint(**pt) for pt in congestion_service.get_history(hours=hours)]


@router.get(
    "/api/traffic/overview",

    response_model=TrafficOverviewKPI,
    tags=["Traffic - TomTom"],
    summary="City-wide traffic KPIs (avg speed, TTI, incidents, queue length)",
)
async def get_traffic_overview() -> TrafficOverviewKPI:
    try:
        return await fetch_traffic_overview()
    except RuntimeError as exc:
        logger.error("Overview fetch failed: %s", exc)
        raise HTTPException(status_code=503, detail={"error": str(exc), "mode": TRAFFIC_MODE})
    except Exception as exc:
        logger.exception("Unexpected error in overview")
        raise HTTPException(status_code=500, detail={"error": "Internal error fetching traffic overview"})


@router.get(
    "/api/traffic/incidents",
    response_model=IncidentsGeoJSON,
    tags=["Traffic - TomTom"],
    summary="Active traffic incidents as GeoJSON (Hyderabad bbox)",
)
async def get_traffic_incidents() -> IncidentsGeoJSON:
    try:
        return await fetch_incidents()
    except RuntimeError as exc:
        logger.error("Incidents fetch failed: %s", exc)
        raise HTTPException(status_code=503, detail={"error": str(exc), "mode": TRAFFIC_MODE})
    except Exception as exc:
        logger.exception("Unexpected error in incidents")
        raise HTTPException(status_code=500, detail={"error": "Internal error fetching incidents"})


@router.get(
    "/api/traffic/corridors",
    response_model=CorridorsResponse,
    tags=["Traffic - TomTom"],
    summary="Per-corridor speed, travel time, and status for all Hyderabad key corridors",
)
async def get_corridors() -> CorridorsResponse:
    try:
        return await fetch_corridors()
    except RuntimeError as exc:
        logger.error("Corridors fetch failed: %s", exc)
        raise HTTPException(status_code=503, detail={"error": str(exc), "mode": TRAFFIC_MODE})
    except Exception as exc:
        logger.exception("Unexpected error in corridors")
        raise HTTPException(status_code=500, detail={"error": "Internal error fetching corridors"})


@router.get(
    "/api/traffic/trend",
    response_model=TrendResponse,
    tags=["Traffic - TomTom"],
    summary="24-point hourly traffic trend (speed + volume)",
)
async def get_traffic_trend() -> TrendResponse:
    try:
        return await fetch_trend()
    except Exception as exc:
        logger.exception("Unexpected error in trend")
        raise HTTPException(status_code=500, detail={"error": "Internal error fetching trend"})


@router.get(
    "/api/traffic/intersections",
    response_model=IntersectionsResponse,
    tags=["Traffic - TomTom"],
    summary="Key intersection delays and Level-of-Service (LOS)",
)
async def get_intersections() -> IntersectionsResponse:
    try:
        return await fetch_intersections()
    except Exception as exc:
        logger.exception("Unexpected error in intersections")
        raise HTTPException(status_code=500, detail={"error": "Internal error fetching intersections"})


@router.get(
    "/api/traffic/flows/geojson",
    tags=["Traffic - TomTom"],
    summary="Traffic flow corridors as GeoJSON FeatureCollection for map rendering",
)
async def get_flows_geojson() -> Dict[str, Any]:
    try:
        return await fetch_flows_geojson()
    except Exception as exc:
        logger.exception("Unexpected error in flows geojson")
        raise HTTPException(status_code=500, detail={"error": "Internal error fetching flow GeoJSON"})


@router.get(
    "/api/traffic/usage",
    response_model=UsageResponse,
    tags=["Traffic - TomTom"],
    summary="TomTom API request counter and mode",
)
def get_traffic_usage() -> UsageResponse:
    return get_usage()


# ---------------------------------------------------------------------------
# Tile Proxy Endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/api/tiles/{layer}/{z}/{x}/{y}",
    tags=["Traffic - TomTom Tiles"],
    summary="Proxy TomTom map and traffic-flow tiles (API key stays server-side)",
)
async def tile_proxy(
    layer: str = FPath(..., description="'basic' for base map, 'flow' for traffic flow overlay"),
    z: int = FPath(..., ge=0, le=22),
    x: int = FPath(..., ge=0),
    y: int = FPath(..., ge=0),
) -> Response:
    if layer not in ("basic", "flow"):
        raise HTTPException(status_code=400, detail="layer must be 'basic' or 'flow'")
    try:
        tile_bytes = await proxy_tile(layer, z, x, y)
        return Response(
            content=tile_bytes,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=86400, immutable" if layer == "basic" else "public, max-age=60",
                "Access-Control-Allow-Origin": "*",
            },
        )
    except RuntimeError as exc:
        logger.error("Tile proxy error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected tile proxy error")
        raise HTTPException(status_code=500, detail="Tile proxy error")


# ---------------------------------------------------------------------------
# Vector Tile Proxy Endpoint  (.pbf — real road network, every road coloured)
# ---------------------------------------------------------------------------

@router.get(
    "/api/traffic/tiles/flow/{z}/{x}/{y}",
    tags=["Traffic - TomTom Tiles"],
    summary=(
        "Proxy TomTom Traffic Flow VECTOR tiles (.pbf). "
        "source-layer='Traffic flow', property traffic_level 0-1 (relative to free-flow). "
        "API key stays server-side. TTL=60s."
    ),
)
async def vector_tile_proxy(
    z: int = FPath(..., ge=0, le=22),
    x: int = FPath(..., ge=0),
    y: int = FPath(..., ge=0),
) -> Response:
    try:
        tile_bytes = await proxy_vector_tile(z, x, y)
        return Response(
            content=tile_bytes,
            media_type="application/x-protobuf",
            headers={
                # 60 s CDN-cacheable — tiles refresh on TomTom's CDN every ~60 s
                "Cache-Control": "public, max-age=60",
                "Access-Control-Allow-Origin": "*",
                # Note: TomTom returns raw protobuf, NOT gzip — no Content-Encoding header
            },
        )
    except RuntimeError as exc:
        logger.error("Vector tile proxy error: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={"error": str(exc), "mode": TRAFFIC_MODE},
        )
    except Exception as exc:
        logger.exception("Unexpected vector tile proxy error")
        raise HTTPException(status_code=500, detail="Vector tile proxy error")
