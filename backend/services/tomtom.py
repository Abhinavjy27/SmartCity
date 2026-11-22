"""
TomTom Traffic API Service
===========================
Async httpx client wrapping TomTom Flow, Incidents v5, and Tile APIs.

Key design decisions:
- API key is NEVER sent to the browser — all tile requests go through the
  backend proxy at /api/tiles/{layer}/{z}/{x}/{y}.
- Tenacity-based retry with exponential backoff.
- In-memory TTL cache (60s flow, 120s incidents, 3600s tiles).
- TRAFFIC_MODE env var: "live" (default) or "demo" (returns simulated data
  tagged with source="DEMO_SIMULATED"). Live failures return an explicit
  error, never a silent mock.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

logger = logging.getLogger("tomtom")

TOMTOM_API_KEY: str = os.getenv("TOMTOM_API_KEY", "")
TRAFFIC_MODE: str = os.getenv("TRAFFIC_MODE", "live").lower()

def _get_api_key() -> str:
    global TOMTOM_API_KEY
    if not TOMTOM_API_KEY or TOMTOM_API_KEY == "REPLACE_WITH_YOUR_TOMTOM_KEY":
        load_dotenv(dotenv_path=_ENV_PATH, override=True)
        TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY", "")
    return TOMTOM_API_KEY

# TomTom base URLs (verified from docs.developer.tomtom.com 2024)
TOMTOM_FLOW_BASE = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
TOMTOM_INCIDENTS_BASE = "https://api.tomtom.com/traffic/services/5/incidentDetails"
TOMTOM_MAP_TILE_BASE = "https://api.tomtom.com/map/1/tile/basic/main"
# Raster PNG traffic overlay tiles (colour coded, already working)
TOMTOM_TRAFFIC_FLOW_TILE_BASE = "https://api.tomtom.com/traffic/map/4/tile/flow/relative"
# Vector PBF traffic flow tiles – source-layer "Traffic flow", property "traffic_level" (0-1)
# URL format: /traffic/map/4/tile/flow/relative/{z}/{x}/{y}.pbf
TOMTOM_TRAFFIC_FLOW_VECTOR_TILE_BASE = "https://api.tomtom.com/traffic/map/4/tile/flow/relative"

# Hyderabad bounding box [minLon, minLat, maxLon, maxLat]
HYD_BBOX = (78.30, 17.28, 78.62, 17.55)

# Free-flow speed baseline fallback (km/h) if TomTom doesn't return it
DEFAULT_FREE_FLOW_SPEED = 60.0

# Corridors config
_CORRIDORS_FILE = Path(__file__).parent.parent / "config" / "corridors.json"

# ---------------------------------------------------------------------------
# In-Memory TTL Cache
# ---------------------------------------------------------------------------

class _CacheEntry:
    __slots__ = ("value", "expires_at")
    def __init__(self, value: Any, ttl: float):
        self.value = value
        self.expires_at = time.monotonic() + ttl

class _TTLCache:
    def __init__(self):
        self._store: Dict[str, _CacheEntry] = {}
        self._request_count: int = 0

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry and time.monotonic() < entry.expires_at:
            return entry.value
        return None

    def set(self, key: str, value: Any, ttl: float):
        self._store[key] = _CacheEntry(value, ttl)
        self._request_count += 1

    def increment_request_count(self):
        self._request_count += 1

    @property
    def request_count(self) -> int:
        return self._request_count

_cache = _TTLCache()

# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class FlowSegmentData(BaseModel):
    corridor_id: str
    corridor_name: str
    current_speed: float = Field(..., description="km/h")
    free_flow_speed: float = Field(..., description="km/h")
    current_travel_time: int = Field(..., description="seconds")
    free_flow_travel_time: int = Field(..., description="seconds")
    congestion_ratio: float = Field(..., description="0=free flow, 1=full stop")
    road_closure: bool
    confidence: float
    delay_seconds: int
    status: str  # "free" | "moderate" | "congested" | "severe"
    source: str = "TOMTOM_LIVE"


class TrafficOverviewKPI(BaseModel):
    avg_speed_kmh: float
    congested_corridors: int
    active_incidents: int
    travel_time_index: float
    source: str = "TOMTOM_LIVE"
    as_of: str


class IncidentFeature(BaseModel):
    type: str = "Feature"
    geometry: Dict[str, Any]
    properties: Dict[str, Any]


class IncidentsGeoJSON(BaseModel):
    type: str = "FeatureCollection"
    features: List[IncidentFeature]
    source: str = "TOMTOM_LIVE"
    as_of: str


class CorridorData(BaseModel):
    id: str
    name: str
    speed: float  # km/h
    time: str     # formatted e.g. "16 min"
    status: str   # Free Flow | Moderate | Congested | Severe
    delay_seconds: int
    congestion_ratio: float
    source: str = "TOMTOM_LIVE"


class CorridorsResponse(BaseModel):
    corridors: List[CorridorData]
    city_congestion_index: float
    trend_history: List[Dict[str, Any]]
    source: str = "TOMTOM_LIVE"
    as_of: str


class TrendPoint(BaseModel):
    time: str
    speed: float
    volume: Optional[float] = None


class TrendResponse(BaseModel):
    data: List[TrendPoint]
    source: str = "TOMTOM_LIVE"
    as_of: str


class IntersectionData(BaseModel):
    name: str
    delay: str   # e.g. "142 sec"
    los: str     # Level of Service A-F
    status: str


class IntersectionsResponse(BaseModel):
    intersections: List[IntersectionData]
    source: str = "TOMTOM_LIVE"
    as_of: str


class UsageResponse(BaseModel):
    total_api_requests: int
    mode: str


# ---------------------------------------------------------------------------
# Trend History Store (in-memory ring buffer, ~24 hours at 60s interval)
# ---------------------------------------------------------------------------

_trend_history: List[Dict[str, Any]] = []
_MAX_TREND_POINTS = 1440  # 24h at 60s


def _record_trend_point(avg_speed: float):
    """Append a trend point. Called on every corridor poll."""
    now_h = datetime.now(timezone.utc)
    hour = now_h.hour
    minute = now_h.minute
    label = f"{hour % 12 or 12}:{minute:02d} {'AM' if hour < 12 else 'PM'}"
    _trend_history.append({"time": label, "speed": round(avg_speed, 1), "volume": None})
    if len(_trend_history) > _MAX_TREND_POINTS:
        _trend_history.pop(0)


# ---------------------------------------------------------------------------
# HTTP Client helpers
# ---------------------------------------------------------------------------

_RETRYABLE_EXCEPTIONS = (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)

_shared_client: Optional[httpx.AsyncClient] = None

def _get_shared_client() -> httpx.AsyncClient:
    global _shared_client
    try:
        cur_loop = asyncio.get_running_loop()
    except RuntimeError:
        cur_loop = None

    needs_new = False
    if _shared_client is None or _shared_client.is_closed:
        needs_new = True
    elif getattr(_shared_client, "_owner_loop", None) != cur_loop:
        needs_new = True
    elif getattr(_shared_client, "_owner_loop", None) is not None and getattr(_shared_client, "_owner_loop").is_closed():
        needs_new = True

    if needs_new:
        _shared_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=3.0, read=5.0, write=5.0, pool=10.0),
            limits=httpx.Limits(max_keepalive_connections=50, max_connections=100, keepalive_expiry=120.0),
        )
        _shared_client._owner_loop = cur_loop
    return _shared_client

class _ClientContext:
    async def __aenter__(self) -> httpx.AsyncClient:
        return _get_shared_client()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

def _make_client():
    return _ClientContext()


@retry(
    retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
    wait=wait_exponential(multiplier=0.2, min=0.2, max=1.0),
    stop=stop_after_attempt(2),
    reraise=True,
)
async def _get(client: httpx.AsyncClient, url: str, params: Dict) -> Dict:
    _cache.increment_request_count()
    resp = await client.get(url, params=params)
    if resp.status_code == 401:
        raise RuntimeError("TomTom API returned 401 Unauthorized — check TOMTOM_API_KEY in .env")
    if resp.status_code == 403:
        raise RuntimeError("TomTom API returned 403 Forbidden — check TOMTOM_API_KEY")
    if resp.status_code == 429:
        raise RuntimeError("TomTom API rate limit exceeded (429) — slow down requests")
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Helper: speed → status
# ---------------------------------------------------------------------------

def _speed_to_status(speed: float, free_flow: float) -> str:
    if free_flow <= 0:
        free_flow = DEFAULT_FREE_FLOW_SPEED
    ratio = speed / free_flow
    if ratio >= 0.85:
        return "Free Flow"
    if ratio >= 0.55:
        return "Moderate"
    if ratio >= 0.30:
        return "Congested"
    return "Severe"


def _speed_to_geojson_status(speed: float) -> str:
    if speed >= 50:
        return "free"
    if speed >= 30:
        return "moderate"
    if speed >= 15:
        return "congested"
    return "severe"


def _los_from_delay(delay_sec: int) -> str:
    """Approximate Highway Capacity Manual Level of Service from intersection delay."""
    if delay_sec <= 10:
        return "A"
    if delay_sec <= 20:
        return "B"
    if delay_sec <= 35:
        return "C"
    if delay_sec <= 55:
        return "D"
    if delay_sec <= 80:
        return "E"
    return "F"


def _los_to_status(los: str) -> str:
    return {"A": "Good", "B": "Good", "C": "Good", "D": "Moderate", "E": "High Delay", "F": "High Delay"}.get(los, "Moderate")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Load corridors config
# ---------------------------------------------------------------------------

def _load_corridors() -> List[Dict]:
    try:
        with open(_CORRIDORS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Could not load corridors.json: %s", exc)
        return []


# ---------------------------------------------------------------------------
# DEMO DATA (TRAFFIC_MODE=demo)
# ---------------------------------------------------------------------------

def _demo_flow(corridor_id: str, corridor_name: str) -> FlowSegmentData:
    import random
    spd = random.uniform(12, 65)
    ff = 60.0
    return FlowSegmentData(
        corridor_id=corridor_id,
        corridor_name=corridor_name,
        current_speed=round(spd, 1),
        free_flow_speed=ff,
        current_travel_time=int(1000 / max(spd, 1)),
        free_flow_travel_time=int(1000 / ff),
        congestion_ratio=round(1 - spd / ff, 3),
        road_closure=False,
        confidence=0.7,
        delay_seconds=int(max(0, (1000 / max(spd, 1)) - (1000 / ff))),
        status=_speed_to_status(spd, ff),
        source="DEMO_SIMULATED",
    )


def _demo_overview() -> TrafficOverviewKPI:
    import random
    return TrafficOverviewKPI(
        avg_speed_kmh=round(random.uniform(12, 30), 1),
        congested_corridors=random.randint(5, 15),
        active_incidents=random.randint(8, 30),
        travel_time_index=round(random.uniform(1.3, 2.1), 2),
        source="DEMO_SIMULATED",
        as_of=_utc_now(),
    )


def _demo_incidents() -> IncidentsGeoJSON:
    demo_features = [
        IncidentFeature(
            geometry={"type": "Point", "coordinates": [78.3810, 17.4504]},
            properties={
                "type": "Accident", "location": "Outer Ring Road",
                "detail": "Near Gachibowli Flyover", "severity": "High Impact",
                "time": "10:05 AM", "color": "#E5483F",
                "category": "accident", "from": "Gachibowli", "to": "HiTech City",
                "delay_seconds": 480, "length_m": 350,
            },
        ),
        IncidentFeature(
            geometry={"type": "Point", "coordinates": [78.3912, 17.4480]},
            properties={
                "type": "Lane Blockage", "location": "HiTech City Main Road",
                "detail": "Near Cyber Towers", "severity": "Medium Impact",
                "time": "10:12 AM", "color": "#F4A62A",
                "category": "lane_restriction", "from": "Madhapur", "to": "Cyber Towers",
                "delay_seconds": 240, "length_m": 200,
            },
        ),
    ]
    return IncidentsGeoJSON(features=demo_features, source="DEMO_SIMULATED", as_of=_utc_now())


# ---------------------------------------------------------------------------
# LIVE TomTom API Calls
# ---------------------------------------------------------------------------

async def fetch_flow_segment(
    point: Tuple[float, float],
    corridor_id: str,
    corridor_name: str,
) -> FlowSegmentData:
    """
    Fetch TomTom Flow Segment Data for a lat/lng point.
    point = (longitude, latitude)
    """
    if TRAFFIC_MODE == "demo":
        return _demo_flow(corridor_id, corridor_name)

    cache_key = f"flow:{corridor_id}"
    cached = _cache.get(cache_key)
    if cached:
        return cached

    lng, lat = point
    params = {
        "point": f"{lat},{lng}",
        "unit": "KMPH",
        "openLr": "false",
        "key": _get_api_key(),
    }

    async with _make_client() as client:
        data = await _get(client, TOMTOM_FLOW_BASE, params)

    seg = data.get("flowSegmentData", {})
    current_speed = float(seg.get("currentSpeed", 0))
    free_flow_speed = float(seg.get("freeFlowSpeed", DEFAULT_FREE_FLOW_SPEED))
    current_tt = int(seg.get("currentTravelTime", 0))
    free_flow_tt = int(seg.get("freeFlowTravelTime", 0))
    confidence = float(seg.get("confidence", 1.0))
    road_closure = bool(seg.get("roadClosure", False))

    if free_flow_speed <= 0:
        free_flow_speed = DEFAULT_FREE_FLOW_SPEED
    congestion_ratio = max(0.0, min(1.0, 1.0 - current_speed / free_flow_speed))
    delay_seconds = max(0, current_tt - free_flow_tt)
    status = _speed_to_status(current_speed, free_flow_speed)

    result = FlowSegmentData(
        corridor_id=corridor_id,
        corridor_name=corridor_name,
        current_speed=round(current_speed, 1),
        free_flow_speed=round(free_flow_speed, 1),
        current_travel_time=current_tt,
        free_flow_travel_time=free_flow_tt,
        congestion_ratio=round(congestion_ratio, 3),
        road_closure=road_closure,
        confidence=confidence,
        delay_seconds=delay_seconds,
        status=status,
        source="TOMTOM_LIVE",
    )
    _cache.set(cache_key, result, ttl=60.0)
    return result


_corridor_flows_lock = asyncio.Lock()

async def fetch_all_corridor_flows() -> List[FlowSegmentData]:
    """Poll all configured corridors and return flow data."""
    batch_cached = _cache.get("batch:all_corridor_flows")
    if batch_cached is not None:
        return batch_cached

    async with _corridor_flows_lock:
        batch_cached = _cache.get("batch:all_corridor_flows")
        if batch_cached is not None:
            return batch_cached

        corridors = _load_corridors()

        async def _fetch_one(c: Dict) -> Optional[FlowSegmentData]:
            try:
                return await fetch_flow_segment(
                    point=(c["point"][0], c["point"][1]),
                    corridor_id=c["id"],
                    corridor_name=c["name"],
                )
            except Exception as exc:
                logger.warning("Flow fetch failed for %s: %s", c["id"], exc)
                return None

        tasks = [_fetch_one(c) for c in corridors]
        fetched = await asyncio.gather(*tasks)
        results = [r for r in fetched if r is not None]
        if results:
            _cache.set("batch:all_corridor_flows", results, ttl=60.0)
        return results


_incidents_lock = asyncio.Lock()

async def fetch_incidents() -> IncidentsGeoJSON:
    """Fetch TomTom Traffic Incidents v5 for Hyderabad bbox."""
    if TRAFFIC_MODE == "demo":
        return _demo_incidents()

    cache_key = "incidents:hyderabad"
    cached = _cache.get(cache_key)
    if cached:
        return cached

    async with _incidents_lock:
        cached = _cache.get(cache_key)
        if cached:
            return cached

        min_lon, min_lat, max_lon, max_lat = HYD_BBOX
        bbox_str = f"{min_lat},{min_lon},{max_lat},{max_lon}"

        params = {
            "bbox": bbox_str,
            "fields": "{incidents{type,geometry{type,coordinates},properties{id,iconCategory,magnitudeOfDelay,events{description,code,iconCategory},startTime,endTime,from,to,length,delay,roadNumbers,timeValidity}}}",
            "language": "en-GB",
            "categoryFilter": "0,1,2,3,4,5,6,7,8,9,10,11,14",
            "timeValidityFilter": "present",
            "key": _get_api_key(),
        }

    try:
        async with _make_client() as client:
            data = await _get(client, TOMTOM_INCIDENTS_BASE, params)
    except Exception as exc:
        logger.error("TomTom incidents fetch failed: %s", exc)
        raise

    features: List[IncidentFeature] = []
    raw_incidents = data.get("incidents", [])

    _CATEGORY_MAP = {
        0: ("Unknown", "#8F9295", "Low Impact"),
        1: ("Accident", "#E5483F", "High Impact"),
        2: ("Fog", "#8F9295", "Low Impact"),
        3: ("Dangerous Conditions", "#F4A62A", "Medium Impact"),
        4: ("Rain", "#6C8FC5", "Low Impact"),
        5: ("Ice", "#6C8FC5", "Medium Impact"),
        6: ("Jam", "#E5483F", "High Impact"),
        7: ("Lane Blockage", "#F4A62A", "Medium Impact"),
        8: ("Road Work", "#F4A62A", "Medium Impact"),
        9: ("Wind", "#8F9295", "Low Impact"),
        10: ("Flooding", "#6C8FC5", "Medium Impact"),
        11: ("Detour", "#F4A62A", "Low Impact"),
        14: ("Vehicle Breakdown", "#2F8F72", "Low Impact"),
    }

    now_str = datetime.now(timezone.utc).strftime("%I:%M %p")

    for inc in raw_incidents:
        geom = inc.get("geometry", {})
        props = inc.get("properties", {})

        icon_cat = props.get("iconCategory", 0)
        inc_type, color, severity = _CATEGORY_MAP.get(icon_cat, ("Incident", "#8F9295", "Low Impact"))

        # magnitude (0-4: unknown, minor, moderate, major, extremely_major)
        mag = props.get("magnitudeOfDelay", 0)
        if mag >= 3:
            severity = "High Impact"
            color = "#E5483F"
        elif mag == 2:
            severity = "Medium Impact"
            color = "#F4A62A"
        elif mag <= 1:
            severity = "Low Impact"
            color = "#2F8F72"

        from_loc = props.get("from", "Unknown")
        to_loc = props.get("to", "")
        detail = f"Near {to_loc}" if to_loc else from_loc

        features.append(IncidentFeature(
            geometry=geom,
            properties={
                "type": inc_type,
                "location": from_loc,
                "detail": detail,
                "severity": severity,
                "color": color,
                "time": now_str,
                "category": inc_type.lower().replace(" ", "_"),
                "from": from_loc,
                "to": to_loc,
                "delay_seconds": props.get("delay", 0),
                "length_m": props.get("length", 0),
                "start_time": props.get("startTime"),
                "end_time": props.get("endTime"),
                "magnitude": mag,
            }
        ))

    result = IncidentsGeoJSON(features=features, source="TOMTOM_LIVE", as_of=_utc_now())
    _cache.set(cache_key, result, ttl=120.0)
    return result


async def fetch_traffic_overview() -> TrafficOverviewKPI:
    """
    Compute city-level KPIs from corridor flows + incident count.
    """
    if TRAFFIC_MODE == "demo":
        return _demo_overview()

    cache_key = "overview:hyderabad"
    cached = _cache.get(cache_key)
    if cached:
        return cached

    import asyncio
    flows_task = asyncio.create_task(fetch_all_corridor_flows())
    incidents_task = asyncio.create_task(fetch_incidents())
    flows, incidents = await asyncio.gather(flows_task, incidents_task)

    if not flows:
        raise RuntimeError("No flow data available from TomTom — cannot compute overview KPIs")

    speeds = [f.current_speed for f in flows]
    avg_speed = sum(speeds) / len(speeds)
    congested = sum(1 for f in flows if f.status in ("Congested", "Severe"))
    active_incidents = len(incidents.features)

    # Travel Time Index = weighted avg of congestion ratios + 1 (baseline = 1.0)
    tti = 1.0 + sum(f.congestion_ratio for f in flows) / len(flows)

    result = TrafficOverviewKPI(
        avg_speed_kmh=round(avg_speed, 1),
        congested_corridors=congested,
        active_incidents=active_incidents,
        travel_time_index=round(tti, 2),
        source="TOMTOM_LIVE",
        as_of=_utc_now(),
    )
    _cache.set(cache_key, result, ttl=60.0)
    return result


async def fetch_corridors() -> CorridorsResponse:
    """
    Return per-corridor speeds, travel times, and statuses for the Traffic page table.
    """
    if TRAFFIC_MODE == "demo":
        import random
        corridors_cfg = _load_corridors()
        demo_corridors = []
        for c in corridors_cfg:
            spd = random.uniform(10, 70)
            ff = 60.0
            ratio = max(0, 1 - spd / ff)
            status = _speed_to_status(spd, ff)
            typical = c.get("typical_travel_min", 15)
            travel_min = int(typical * (1 + ratio))
            demo_corridors.append(CorridorData(
                id=c["id"], name=c["name"],
                speed=round(spd, 1),
                time=f"{travel_min} min",
                status=status,
                delay_seconds=int(ratio * typical * 60),
                congestion_ratio=round(ratio, 3),
                source="DEMO_SIMULATED",
            ))
        avg = sum(d.speed for d in demo_corridors) / max(len(demo_corridors), 1)
        _record_trend_point(avg)
        return CorridorsResponse(
            corridors=demo_corridors,
            city_congestion_index=round((1 - avg / 60.0) * 100, 1),
            trend_history=list(_trend_history[-48:]),
            source="DEMO_SIMULATED",
            as_of=_utc_now(),
        )

    cache_key = "corridors:hyderabad"
    cached = _cache.get(cache_key)
    if cached:
        return cached

    corridors_cfg = _load_corridors()
    flows = await fetch_all_corridor_flows()

    flow_by_id = {f.corridor_id: f for f in flows}
    result_corridors: List[CorridorData] = []

    for c in corridors_cfg:
        cid = c["id"]
        flow = flow_by_id.get(cid)
        typical_min = c.get("typical_travel_min", 15)

        if flow:
            spd = flow.current_speed
            ratio = flow.congestion_ratio
            delay_s = flow.delay_seconds
            status = flow.status
            travel_min = int(typical_min * (1 + ratio))
        else:
            # Could not get live data for this corridor — skip it cleanly
            continue

        result_corridors.append(CorridorData(
            id=cid,
            name=c["name"],
            speed=round(spd, 1),
            time=f"{travel_min} min",
            status=status,
            delay_seconds=delay_s,
            congestion_ratio=round(ratio, 3),
            source="TOMTOM_LIVE",
        ))

    if not result_corridors:
        raise RuntimeError("No corridor data available — TomTom API may be unavailable")

    avg_speed = sum(c.speed for c in result_corridors) / len(result_corridors)
    city_ci = round((1 - avg_speed / DEFAULT_FREE_FLOW_SPEED) * 100, 1)
    city_ci = max(0.0, min(100.0, city_ci))

    _record_trend_point(avg_speed)

    resp = CorridorsResponse(
        corridors=result_corridors,
        city_congestion_index=city_ci,
        trend_history=list(_trend_history[-48:]),
        source="TOMTOM_LIVE",
        as_of=_utc_now(),
    )
    _cache.set(cache_key, resp, ttl=60.0)
    return resp


async def fetch_trend() -> TrendResponse:
    """
    Return 24 hourly trend data points. Uses stored history if available,
    otherwise generates from current flows.
    """
    if _trend_history:
        # Return last 24 unique-ish points (sample evenly if more)
        hist = _trend_history[-24:] if len(_trend_history) >= 24 else _trend_history
        points = [TrendPoint(time=p["time"], speed=p["speed"], volume=p["volume"]) for p in hist]
        src = _trend_history[-1].get("source", "TOMTOM_LIVE") if _trend_history else "TOMTOM_LIVE"
        return TrendResponse(data=points, source="TOMTOM_LIVE", as_of=_utc_now())

    # No history yet — seed with current overview + time labels
    flows = await fetch_all_corridor_flows()
    avg = sum(f.current_speed for f in flows) / max(len(flows), 1) if flows else 20.0
    _record_trend_point(avg)

    now_h = datetime.now(timezone.utc).hour
    points = []
    for i in range(24):
        h = (now_h - 23 + i) % 24
        label = f"{h % 12 or 12} {'AM' if h < 12 else 'PM'}"
        points.append(TrendPoint(time=label, speed=round(avg, 1), volume=None))

    return TrendResponse(data=points, source="TOMTOM_LIVE", as_of=_utc_now())


async def fetch_intersections() -> IntersectionsResponse:
    """
    Derive intersection-level data from corridor flows.
    Maps the 5 key Hyderabad intersections to nearby corridor points.
    """
    INTERSECTION_CORRIDOR_MAP = [
        ("Gachibowli Junction", "gachibowli"),
        ("HiTech City Junction", "hitec-city"),
        ("KPHB Junction", "kukatpally"),
        ("Jubilee Hills Checkpost", "jubilee-hills"),
        ("Ameerpet Junction", "ameerpet"),
    ]

    if TRAFFIC_MODE == "demo":
        import random
        results = []
        for name, _ in INTERSECTION_CORRIDOR_MAP:
            delay = random.randint(20, 160)
            los = _los_from_delay(delay)
            results.append(IntersectionData(
                name=name, delay=f"{delay} sec", los=los, status=_los_to_status(los)
            ))
        return IntersectionsResponse(intersections=results, source="DEMO_SIMULATED", as_of=_utc_now())

    cache_key = "intersections:hyderabad"
    cached = _cache.get(cache_key)
    if cached:
        return cached

    flows = await fetch_all_corridor_flows()
    flow_by_id = {f.corridor_id: f for f in flows}

    results: List[IntersectionData] = []
    for name, corridor_id in INTERSECTION_CORRIDOR_MAP:
        flow = flow_by_id.get(corridor_id)
        if flow:
            # Intersection delay ≈ corridor delay / 2 (intersection is a sub-segment)
            delay_sec = max(10, flow.delay_seconds // 2)
        else:
            delay_sec = 30  # neutral fallback if not polled
        los = _los_from_delay(delay_sec)
        results.append(IntersectionData(
            name=name,
            delay=f"{delay_sec} sec",
            los=los,
            status=_los_to_status(los),
        ))

    resp = IntersectionsResponse(intersections=results, source="TOMTOM_LIVE", as_of=_utc_now())
    _cache.set(cache_key, resp, ttl=60.0)
    return resp


async def fetch_flows_geojson() -> Dict[str, Any]:
    """
    Return corridor flow data as a GeoJSON FeatureCollection,
    shaped identically to REAL_TRAFFIC_FLOWS in hyderabadGeoData.js.
    The map component reads this source.
    """
    from backend.services.map.hyderabad_geo import get_corridor_geometry

    if TRAFFIC_MODE == "demo":
        import random
        corridors_cfg = _load_corridors()
        features = []
        for c in corridors_cfg:
            spd = random.uniform(10, 70)
            ff = 60.0
            ratio = round(1 - spd / ff, 3)
            status = _speed_to_geojson_status(spd)
            geom = get_corridor_geometry(c["id"])
            if geom is None:
                continue
            features.append({
                "type": "Feature",
                "properties": {
                    "id": c["id"],
                    "road": c["name"],
                    "corridor": c["name"],
                    "speed": round(spd, 1),
                    "freeFlowSpeed": ff,
                    "congestion_ratio": ratio,
                    "status": status,
                    "statusLabel": _speed_to_status(spd, ff),
                    "color": _status_to_color(status),
                    "source": "DEMO_SIMULATED",
                },
                "geometry": geom,
            })
        return {"type": "FeatureCollection", "features": features, "source": "DEMO_SIMULATED"}

    cache_key = "flows:geojson"
    cached = _cache.get(cache_key)
    if cached:
        return cached

    flows = await fetch_all_corridor_flows()
    features = []
    for flow in flows:
        geom = get_corridor_geometry(flow.corridor_id)
        if geom is None:
            continue
        status_code = _speed_to_geojson_status(flow.current_speed)
        features.append({
            "type": "Feature",
            "properties": {
                "id": flow.corridor_id,
                "road": flow.corridor_name,
                "corridor": flow.corridor_name,
                "speed": flow.current_speed,
                "freeFlowSpeed": flow.free_flow_speed,
                "congestion_ratio": flow.congestion_ratio,
                "status": status_code,
                "statusLabel": flow.status,
                "color": _status_to_color(status_code),
                "roadClosure": flow.road_closure,
                "confidence": flow.confidence,
                "source": "TOMTOM_LIVE",
            },
            "geometry": geom,
        })

    result = {"type": "FeatureCollection", "features": features, "source": "TOMTOM_LIVE"}
    _cache.set(cache_key, result, ttl=60.0)
    return result


def _status_to_color(status: str) -> str:
    return {
        "free": "#2F8F72",
        "moderate": "#EAB308",
        "congested": "#EF4444",
        "severe": "#8B0000",
    }.get(status, "#8F9295")


async def proxy_tile(layer: str, z: int, x: int, y: int) -> bytes:
    """
    Proxy TomTom map/traffic tiles so the API key never reaches the browser.
    layer: "basic" = base map tiles, "flow" = traffic flow tiles
    """
    cache_key = f"tile:{layer}:{z}:{x}:{y}"
    cached = _cache.get(cache_key)
    if cached:
        return cached

    if layer == "basic":
        url = f"{TOMTOM_MAP_TILE_BASE}/{z}/{x}/{y}.png"
    elif layer == "flow":
        url = f"{TOMTOM_TRAFFIC_FLOW_TILE_BASE}/{z}/{x}/{y}.png"
    else:
        raise ValueError(f"Unknown tile layer: {layer}")

    params = {"key": _get_api_key()}

    async with _make_client() as client:
        _cache.increment_request_count()
        resp = await client.get(url, params=params)
        if resp.status_code == 401:
            raise RuntimeError("TomTom tile API: 401 Unauthorized — check TOMTOM_API_KEY in .env")
        if resp.status_code == 403:
            raise RuntimeError("TomTom tile API: 403 Forbidden")
        if resp.status_code == 429:
            raise RuntimeError("TomTom tile API: 429 Too Many Requests")
        resp.raise_for_status()
        tile_bytes = resp.content

    ttl = 86400.0 if layer == "basic" else 120.0
    _cache.set(cache_key, tile_bytes, ttl=ttl)
    return tile_bytes


def get_usage() -> UsageResponse:
    return UsageResponse(
        total_api_requests=_cache.request_count,
        mode=TRAFFIC_MODE,
    )


async def proxy_vector_tile(z: int, x: int, y: int) -> bytes:
    """
    Proxy a TomTom Traffic Flow *vector* tile (.pbf) so the API key never
    reaches the browser.

    Endpoint used (TomTom Traffic API v4, relative flow):
        https://api.tomtom.com/traffic/map/4/tile/flow/relative/{z}/{x}/{y}.pbf

    The .pbf features are in source-layer "Traffic flow" and carry the
    property  traffic_level : float  (0.0 = standstill, 1.0 = free flow).

    TTL = 60 s  (tiles update on each TomTom CDN refresh cycle).
    """
    cache_key = f"vtile:flow:{z}:{x}:{y}"
    cached = _cache.get(cache_key)
    if cached:
        return cached

    url = f"{TOMTOM_TRAFFIC_FLOW_VECTOR_TILE_BASE}/{z}/{x}/{y}.pbf"
    params = {"key": _get_api_key()}

    async with _make_client() as client:
        _cache.increment_request_count()
        resp = await client.get(url, params=params)
        if resp.status_code == 401:
            raise RuntimeError("TomTom vector tile API: 401 Unauthorized — check TOMTOM_API_KEY in .env")
        if resp.status_code == 403:
            raise RuntimeError("TomTom vector tile API: 403 Forbidden")
        if resp.status_code == 429:
            raise RuntimeError("TomTom vector tile API: 429 Too Many Requests — rate limit hit")
        if resp.status_code >= 500:
            raise RuntimeError(f"TomTom vector tile API: {resp.status_code} upstream error")
        resp.raise_for_status()
        tile_bytes = resp.content

    # Cache for 60 s — matches TomTom CDN refresh interval
    _cache.set(cache_key, tile_bytes, ttl=60.0)
    return tile_bytes
