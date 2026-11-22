"""
SUPADSP Hyderabad Location Resolver
Resolves natural language queries and explicit location parameters
to canonical Hyderabad localities, geographic coordinates, and bounding boxes.
Strictly validates coordinates within Hyderabad metropolitan bounds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

HYDERABAD_BOUNDS = {
    "min_lat": 17.15,
    "max_lat": 17.65,
    "min_lon": 78.15,
    "max_lon": 78.75,
}

@dataclass
class ResolvedLocation:
    name: str
    slug: str
    lat: float
    lon: float
    bbox: Tuple[float, float, float, float]  # min_lat, min_lon, max_lat, max_lon
    matched_by: str  # 'explicit_arg' | 'query_text' | 'default'

    @property
    def point(self) -> Tuple[float, float]:
        """Returns (lon, lat) tuple as standard GeoJSON / GIS format."""
        return (self.lon, self.lat)

    @property
    def lat_lon_str(self) -> str:
        return f"{self.lat:.4f},{self.lon:.4f}"

    def is_within_hyderabad(self) -> bool:
        return (
            HYDERABAD_BOUNDS["min_lat"] <= self.lat <= HYDERABAD_BOUNDS["max_lat"]
            and HYDERABAD_BOUNDS["min_lon"] <= self.lon <= HYDERABAD_BOUNDS["max_lon"]
        )


CANONICAL_LOCALITIES: Dict[str, Dict] = {
    "narayanguda": {
        "name": "Narayanguda",
        "aliases": ["narayanguda", "narayanaguda", "narayan guda", "hyderguda", "chikkadapally", "barkatpura", "himayat nagar", "himayatnagar"],
        "lat": 17.3978,
        "lon": 78.4907,
        "bbox": (17.3824, 78.4770, 17.4314, 78.5059),
    },
    "tarnaka": {
        "name": "Tarnaka",
        "aliases": ["tarnaka", "tarnaka junction", "tarnaka jn", "ou", "osmania university", "habsiguda", "lalaguda"],
        "lat": 17.4290,
        "lon": 78.5320,
        "bbox": (17.4180, 78.5260, 17.4380, 78.5460),
    },
    "nacharam": {
        "name": "Nacharam",
        "aliases": ["nacharam", "nacharam ida", "nacharam industrial", "mallapur", "nacharam jn", "nacharam road"],
        "lat": 17.4320,
        "lon": 78.5600,
        "bbox": (17.4200, 78.5500, 17.4400, 78.5700),
    },
    "madhapur": {
        "name": "Madhapur",
        "aliases": ["madhapur", "madhapur jn", "durgam cheruvu", "inorbit", "inorbit mall", "kavuri hills", "image hospital"],
        "lat": 17.4480,
        "lon": 78.3912,
        "bbox": (17.4380, 78.3780, 17.4580, 78.4020),
    },
    "gachibowli": {
        "name": "Gachibowli",
        "aliases": ["gachibowli", "gachibowli flyover", "gachibowli junction", "gachibowli jn", "financial district", "wipro circle", "iit hyderabad", "iiit"],
        "lat": 17.4401,
        "lon": 78.3489,
        "bbox": (17.4300, 78.3380, 17.4500, 78.3580),
    },
    "hitec-city": {
        "name": "HITEC City",
        "aliases": ["hitec city", "hitech city", "cyber towers", "cyber city", "mindspace"],
        "lat": 17.4435,
        "lon": 78.3772,
        "bbox": (17.4350, 78.3680, 17.4550, 78.3880),
    },
    "jubilee-hills": {
        "name": "Jubilee Hills",
        "aliases": ["jubilee hills", "jubilee check post", "check post", "road no 36", "road no 45"],
        "lat": 17.4318,
        "lon": 78.4073,
        "bbox": (17.4200, 78.3950, 17.4420, 78.4180),
    },
    "banjara-hills": {
        "name": "Banjara Hills",
        "aliases": ["banjara hills", "road no 1", "road no 12", "taj krishna", "care hospital"],
        "lat": 17.4239,
        "lon": 78.4238,
        "bbox": (17.4120, 78.4100, 17.4350, 78.4350),
    },
    "panjagutta": {
        "name": "Panjagutta",
        "aliases": ["panjagutta", "punjagutta", "nagarjuna circle"],
        "lat": 17.4260,
        "lon": 78.4520,
        "bbox": (17.4180, 78.4420, 17.4350, 78.4600),
    },
    "ameerpet": {
        "name": "Ameerpet",
        "aliases": ["ameerpet", "ameerpet junction", "ameerpet metro", "sr nagar"],
        "lat": 17.4375,
        "lon": 78.4483,
        "bbox": (17.4280, 78.4380, 17.4460, 78.4580),
    },
    "begumpet": {
        "name": "Begumpet",
        "aliases": ["begumpet", "begumpet flyover", "prakash nagar", "rasoolpura"],
        "lat": 17.4440,
        "lon": 78.4676,
        "bbox": (17.4350, 78.4580, 17.4520, 78.4760),
    },
    "secunderabad": {
        "name": "Secunderabad",
        "aliases": ["secunderabad", "secunderabad station", "paradise circle", "clock tower", "patny"],
        "lat": 17.4344,
        "lon": 78.5013,
        "bbox": (17.4250, 78.4900, 17.4450, 78.5120),
    },
    "kukatpally": {
        "name": "Kukatpally",
        "aliases": ["kukatpally", "kphb", "kukatpally y junction", "jntu"],
        "lat": 17.4849,
        "lon": 78.4138,
        "bbox": (17.4720, 78.4000, 17.4960, 78.4250),
    },
    "mehdipatnam": {
        "name": "Mehdipatnam",
        "aliases": ["mehdipatnam", "mehdipatnam junction", "pvnr expressway", "sarojini devi eye hospital"],
        "lat": 17.3950,
        "lon": 78.4400,
        "bbox": (17.3850, 78.4300, 17.4050, 78.4500),
    },
    "charminar": {
        "name": "Charminar",
        "aliases": ["charminar", "old city", "madina", "lad bazaar", "nayapul"],
        "lat": 17.3616,
        "lon": 78.4747,
        "bbox": (17.3520, 78.4650, 17.3710, 78.4850),
    },
    "dilsukhnagar": {
        "name": "Dilsukhnagar",
        "aliases": ["dilsukhnagar", "malakpet", "chaitanyapuri", "kothapet"],
        "lat": 17.3688,
        "lon": 78.5247,
        "bbox": (17.3580, 78.5140, 17.3780, 78.5350),
    },
    "lb-nagar": {
        "name": "LB Nagar",
        "aliases": ["lb nagar", "l.b. nagar", "lb nagar ring road", "hayathnagar", "vanasthalipuram"],
        "lat": 17.3457,
        "lon": 78.5522,
        "bbox": (17.3350, 78.5400, 17.3580, 78.5650),
    },
    "uppal": {
        "name": "Uppal",
        "aliases": ["uppal", "uppal ring road", "uppal junction", "nagole", "uppal stadium", "rajiv gandhi stadium"],
        "lat": 17.4058,
        "lon": 78.5591,
        "bbox": (17.3950, 78.5480, 17.4160, 78.5700),
    },
    "kondapur": {
        "name": "Kondapur",
        "aliases": ["kondapur", "kondapur junction", "botanical garden"],
        "lat": 17.4608,
        "lon": 78.3647,
        "bbox": (17.4500, 78.3540, 17.4720, 78.3750),
    },
    "miyapur": {
        "name": "Miyapur",
        "aliases": ["miyapur", "miyapur junction", "allwyn x road"],
        "lat": 17.4968,
        "lon": 78.3614,
        "bbox": (17.4850, 78.3500, 17.5080, 78.3720),
    },
}


def _match_string(text: str) -> Optional[Tuple[str, Dict]]:
    if not text:
        return None
    cleaned = text.lower()
    matches = []
    
    # Exact and word-boundary matching
    for slug, data in CANONICAL_LOCALITIES.items():
        for alias in data["aliases"]:
            # Match whole phrase/word using regex boundary
            pat = r"(?:\b|^)" + re.escape(alias) + r"(?:\b|$)"
            for m in re.finditer(pat, cleaned):
                matches.append((m.start(), len(alias), slug, data))
    if not matches:
        return None
    # Sort by start position descending (latest mention in query text takes precedence),
    # then alias length descending (more specific alias matches tie-break)
    matches.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return matches[0][2], matches[0][3]


class LocationResolver:
    """
    Location resolver adhering to the strict precedence hierarchy:
    1. Explicit locality mentioned in query text (e.g. 'What is the traffic situation in Tarnaka?')
    2. Explicit location parameter provided by caller (e.g. location='Nacharam')
    3. Default location fallback only if caller requested a default, otherwise returns None.
    """

    @classmethod
    def resolve(
        cls,
        query_text: Optional[str] = None,
        explicit_location: Optional[str] = None,
        default_location: Optional[str] = None,
    ) -> Optional[ResolvedLocation]:
        # 1. Query text inspection
        if query_text:
            match = _match_string(query_text)
            if match:
                slug, data = match
                res = ResolvedLocation(
                    name=data["name"],
                    slug=slug,
                    lat=data["lat"],
                    lon=data["lon"],
                    bbox=data["bbox"],
                    matched_by="query_text",
                )
                if res.is_within_hyderabad():
                    return res

        # 2. Explicit location parameter
        if explicit_location:
            match = _match_string(explicit_location)
            if match:
                slug, data = match
                res = ResolvedLocation(
                    name=data["name"],
                    slug=slug,
                    lat=data["lat"],
                    lon=data["lon"],
                    bbox=data["bbox"],
                    matched_by="explicit_arg",
                )
                if res.is_within_hyderabad():
                    return res

        # 3. Default fallback if explicitly requested
        if default_location:
            match = _match_string(default_location)
            if match:
                slug, data = match
                res = ResolvedLocation(
                    name=data["name"],
                    slug=slug,
                    lat=data["lat"],
                    lon=data["lon"],
                    bbox=data["bbox"],
                    matched_by="default",
                )
                if res.is_within_hyderabad():
                    return res

        return None

    @classmethod
    def get_supported_localities(cls) -> List[str]:
        return [data["name"] for data in CANONICAL_LOCALITIES.values()]

