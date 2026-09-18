"""
Substation Registry and Spatial Mapping for Hyderabad Urban Power Grid (TSSPDCL / TSTRANSCO).
Provides base metadata, transformer capacity ratings, coordinates, and zone groupings.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Any


SUBSTATIONS_DB: List[Dict[str, Any]] = [
    {
        "id": "SUB_01",
        "name": "Madhapur 220kV",
        "voltage_kv": 220,
        "capacity_mw": 480.0,
        "base_load_pct": 82.5,
        "zone": "HITECH City",
        "latitude": 17.4483,
        "longitude": 78.3915,
        "feeder_lines": 8,
        "keywords": ["madhapur", "cyber towers", "inorbit", "durgam cheruvu", "mindspace"]
    },
    {
        "id": "SUB_02",
        "name": "Gachibowli 132kV",
        "voltage_kv": 132,
        "capacity_mw": 260.0,
        "base_load_pct": 74.0,
        "zone": "Gachibowli",
        "latitude": 17.4401,
        "longitude": 78.3489,
        "feeder_lines": 6,
        "keywords": ["gachibowli", "flyover", "stadium", "wipro junction", "outer ring road"]
    },
    {
        "id": "SUB_03",
        "name": "Kondapur 132kV",
        "voltage_kv": 132,
        "capacity_mw": 220.0,
        "base_load_pct": 68.5,
        "zone": "HITECH City",
        "latitude": 17.4682,
        "longitude": 78.3578,
        "feeder_lines": 6,
        "keywords": ["kondapur", "botanical garden", "kothaguda", "hafeezpet"]
    },
    {
        "id": "SUB_04",
        "name": "Narayanguda 132kV",
        "voltage_kv": 132,
        "capacity_mw": 240.0,
        "base_load_pct": 76.5,
        "zone": "Central Hyderabad",
        "latitude": 17.3984,
        "longitude": 78.4905,
        "feeder_lines": 6,
        "keywords": ["narayanguda", "himayatnagar", "barkatpura", "hyderguda", "king koti", "kachiguda"]
    },
    {
        "id": "SUB_05",
        "name": "Tarnaka 132kV",
        "voltage_kv": 132,
        "capacity_mw": 200.0,
        "base_load_pct": 72.0,
        "zone": "Secunderabad",
        "latitude": 17.4289,
        "longitude": 78.5324,
        "feeder_lines": 5,
        "keywords": ["tarnaka", "osmania university", "ou", "habsiguda", "moula ali"]
    },
    {
        "id": "SUB_06",
        "name": "Financial District 220kV",
        "voltage_kv": 220,
        "capacity_mw": 500.0,
        "base_load_pct": 84.0,
        "zone": "Gachibowli",
        "latitude": 17.4156,
        "longitude": 78.3392,
        "feeder_lines": 10,
        "keywords": ["financial district", "nankramguda", "waverock", "us consulate", "isb", "kokapet"]
    },
    {
        "id": "SUB_07",
        "name": "Secunderabad Paradise 220kV",
        "voltage_kv": 220,
        "capacity_mw": 450.0,
        "base_load_pct": 79.5,
        "zone": "Secunderabad",
        "latitude": 17.4411,
        "longitude": 78.4983,
        "feeder_lines": 8,
        "keywords": ["secunderabad", "paradise", "patny", "marredpally", "bowenpally", "jubilee bus station", "jbs"]
    },
    {
        "id": "SUB_08",
        "name": "Kukatpally 220kV",
        "voltage_kv": 220,
        "capacity_mw": 420.0,
        "base_load_pct": 77.0,
        "zone": "Kukatpally",
        "latitude": 17.4849,
        "longitude": 78.4138,
        "feeder_lines": 8,
        "keywords": ["kukatpally", "kphb", "y junction", "jntu", "forum mall"]
    },
    {
        "id": "SUB_09",
        "name": "Charminar 132kV",
        "voltage_kv": 132,
        "capacity_mw": 280.0,
        "base_load_pct": 71.5,
        "zone": "Old City",
        "latitude": 17.3616,
        "longitude": 78.4747,
        "feeder_lines": 6,
        "keywords": ["charminar", "old city", "madina", "laad bazaar", "falaknuma", "nayapul", "moazzam jahi"]
    },
    {
        "id": "SUB_10",
        "name": "LB Nagar 132kV",
        "voltage_kv": 132,
        "capacity_mw": 300.0,
        "base_load_pct": 66.0,
        "zone": "LB Nagar",
        "latitude": 17.3457,
        "longitude": 78.5522,
        "feeder_lines": 6,
        "keywords": ["lb nagar", "ring road", "dilsukhnagar", "kothapet", "vanasthalipuram", "hayathnagar"]
    },
    {
        "id": "SUB_11",
        "name": "Sanathnagar 132kV",
        "voltage_kv": 132,
        "capacity_mw": 260.0,
        "base_load_pct": 80.0,
        "zone": "Industrial North",
        "latitude": 17.4583,
        "longitude": 78.4417,
        "feeder_lines": 6,
        "keywords": ["sanathnagar", "erragadda", "fateh nagar", "bharat nagar", "moosapet", "industrial estate"]
    },
    {
        "id": "SUB_12",
        "name": "Nacharam TSIIC 132kV",
        "voltage_kv": 132,
        "capacity_mw": 250.0,
        "base_load_pct": 81.0,
        "zone": "Industrial East",
        "latitude": 17.4241,
        "longitude": 78.5672,
        "feeder_lines": 6,
        "keywords": ["nacharam", "tsiic", "mallapur", "industrial area", "ida nacharam", "uppal"]
    },
    {
        "id": "SUB_13",
        "name": "Begumpet 132kV",
        "voltage_kv": 132,
        "capacity_mw": 280.0,
        "base_load_pct": 75.5,
        "zone": "Central Hyderabad",
        "latitude": 17.4448,
        "longitude": 78.4682,
        "feeder_lines": 6,
        "keywords": ["begumpet", "airport flyover", "prakash nagar", "rasoolpura", "somajiguda", "panjagutta"]
    },
    {
        "id": "SUB_14",
        "name": "Jubilee Hills 132kV",
        "voltage_kv": 132,
        "capacity_mw": 260.0,
        "base_load_pct": 71.0,
        "zone": "Central Hyderabad",
        "latitude": 17.4319,
        "longitude": 78.4073,
        "feeder_lines": 6,
        "keywords": ["jubilee hills", "banjara hills", "road no 36", "road no 45", "checkpost", "filmnagar"]
    },
    {
        "id": "SUB_15",
        "name": "Miyapur 132kV",
        "voltage_kv": 132,
        "capacity_mw": 240.0,
        "base_load_pct": 67.0,
        "zone": "Kukatpally",
        "latitude": 17.4968,
        "longitude": 78.3614,
        "feeder_lines": 6,
        "keywords": ["miyapur", "allwyn", "chandanagar", "metro depot", "bachupally"]
    }
]


ZONE_METRICS_CONFIG: Dict[str, Dict[str, Any]] = {
    "HITECH City": {"color": "#00f0ff", "nominal_mwh": 342, "peak_base": 89},
    "Gachibowli": {"color": "#8b5cf6", "nominal_mwh": 285, "peak_base": 82},
    "Secunderabad": {"color": "#f43f5e", "nominal_mwh": 428, "peak_base": 91},
    "Kukatpally": {"color": "#f59e0b", "nominal_mwh": 312, "peak_base": 78},
    "Old City": {"color": "#10b981", "nominal_mwh": 256, "peak_base": 72},
    "LB Nagar": {"color": "#3b82f6", "nominal_mwh": 198, "peak_base": 65},
    "Central Hyderabad": {"color": "#ec4899", "nominal_mwh": 380, "peak_base": 84},
    "Industrial North": {"color": "#e11d48", "nominal_mwh": 320, "peak_base": 86},
    "Industrial East": {"color": "#f97316", "nominal_mwh": 290, "peak_base": 85},
}


def match_substations_by_location(location_query: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Filter and rank substations matching the location string.
    If no specific match or generic 'Hyderabad' is provided, returns all substations.
    """
    if not location_query or not location_query.strip():
        return SUBSTATIONS_DB.copy()

    normalized = location_query.lower().strip()
    
    # Generic whole-city matchers
    if normalized in ["hyderabad", "hyderabad central", "ghmc", "telangana", "city wide", "metro"]:
        return SUBSTATIONS_DB.copy()

    matched = []
    # 1. Exact or keyword match
    for sub in SUBSTATIONS_DB:
        sub_name_lower = sub["name"].lower()
        sub_zone_lower = sub["zone"].lower()
        
        # Direct name/zone match
        if normalized in sub_name_lower or sub_name_lower in normalized:
            matched.append(sub)
            continue
        if normalized in sub_zone_lower or sub_zone_lower in normalized:
            matched.append(sub)
            continue
            
        # Keyword token search
        tokens = re.findall(r"\w+", normalized)
        for kw in sub.get("keywords", []):
            if any(token in kw or kw in token for token in tokens if len(token) > 2):
                matched.append(sub)
                break

    # If no specific match was found, return all substations to preserve resilience
    if not matched:
        return SUBSTATIONS_DB.copy()

    return matched
