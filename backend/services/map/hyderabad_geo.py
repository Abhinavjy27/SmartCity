"""
hyderabad_geo.py
================
Provides GeoJSON LineString geometries for Hyderabad traffic corridors,
indexed by corridor ID (matching corridors.json).

These geometries are used in fetch_flows_geojson() to attach real road
coordinates to TomTom flow data, matching the shape of REAL_TRAFFIC_FLOWS
in the frontend's hyderabadGeoData.js.
"""

from __future__ import annotations
from typing import Any, Dict, Optional

# Map from corridor_id → GeoJSON geometry object
# Coordinates are in [longitude, latitude] WGS84 order (GeoJSON standard).
# Points are sourced from the frontend's hyderabadGeoData.js to ensure
# identical map rendering when TomTom data replaces static data.

_CORRIDOR_GEOMETRIES: Dict[str, Dict[str, Any]] = {
    "hitec-city": {
        "type": "LineString",
        "coordinates": [
            [78.3780, 17.4510],
            [78.3810, 17.4504],
            [78.3850, 17.4490],
            [78.3890, 17.4480],
            [78.3920, 17.4470],
        ],
    },
    "gachibowli": {
        "type": "LineString",
        "coordinates": [
            [78.3300, 17.4200],
            [78.3380, 17.4300],
            [78.3450, 17.4380],
            [78.3496, 17.4428],
            [78.3600, 17.4490],
            [78.3700, 17.4500],
            [78.3810, 17.4504],
        ],
    },
    "madhapur": {
        "type": "LineString",
        "coordinates": [
            [78.3912, 17.4480],
            [78.3980, 17.4450],
            [78.4071, 17.4312],
        ],
    },
    "jubilee-hills": {
        "type": "LineString",
        "coordinates": [
            [78.4010, 17.4340],
            [78.4071, 17.4312],
            [78.4150, 17.4280],
            [78.4200, 17.4250],
        ],
    },
    "banjara-hills": {
        "type": "LineString",
        "coordinates": [
            [78.4300, 17.4200],
            [78.4350, 17.4185],
            [78.4412, 17.4168],
            [78.4480, 17.4150],
        ],
    },
    "secunderabad": {
        "type": "LineString",
        "coordinates": [
            [78.4680, 17.4440],
            [78.4750, 17.4420],
            [78.4900, 17.4415],
            [78.5020, 17.4415],
        ],
    },
    "ameerpet": {
        "type": "LineString",
        "coordinates": [
            [78.4380, 17.4340],
            [78.4430, 17.4360],
            [78.4513, 17.4375],
            [78.4580, 17.4390],
        ],
    },
    "lb-nagar": {
        "type": "LineString",
        "coordinates": [
            [78.5000, 17.3700],
            [78.5200, 17.3600],
            [78.5380, 17.3530],
            [78.5520, 17.3480],
        ],
    },
    "uppal": {
        "type": "LineString",
        "coordinates": [
            [78.5200, 17.4100],
            [78.5380, 17.4060],
            [78.5520, 17.4030],
            [78.5620, 17.4020],
        ],
    },
    "kukatpally": {
        "type": "LineString",
        "coordinates": [
            [78.3850, 17.4710],
            [78.3900, 17.4760],
            [78.3960, 17.4800],
            [78.4020, 17.4840],
        ],
    },
    "charminar": {
        "type": "LineString",
        "coordinates": [
            [78.4600, 17.3700],
            [78.4680, 17.3660],
            [78.4747, 17.3616],
        ],
    },
    "begumpet": {
        "type": "LineString",
        "coordinates": [
            [78.4520, 17.4460],
            [78.4580, 17.4450],
            [78.4650, 17.4445],
            [78.4680, 17.4440],
        ],
    },
    "orr-gachibowli": {
        "type": "LineString",
        "coordinates": [
            [78.3200, 17.4050],
            [78.3250, 17.4100],
            [78.3298, 17.4182],
            [78.3350, 17.4250],
        ],
    },
}


def get_corridor_geometry(corridor_id: str) -> Optional[Dict[str, Any]]:
    """Return the GeoJSON geometry for a corridor by ID, or None if not found."""
    return _CORRIDOR_GEOMETRIES.get(corridor_id)


def get_all_geometries() -> Dict[str, Dict[str, Any]]:
    return dict(_CORRIDOR_GEOMETRIES)
