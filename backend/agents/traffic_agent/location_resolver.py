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
        "aliases": ["dilsukhnagar", "chaitanyapuri", "kothapet", "dilsukh nagar"],
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
    "santosh-nagar": {
        "name": "Santosh Nagar",
        "aliases": ["santosh nagar", "santhosh nagar", "santoshnagar", "santhoshnagar", "is sadan", "saidabad"],
        "lat": 17.3477,
        "lon": 78.5044,
        "bbox": (17.3380, 78.4950, 17.3580, 78.5150),
    },
    "amberpet": {
        "name": "Amberpet",
        "aliases": ["amberpet", "ali cafe", "amberpet main road", "6 no"],
        "lat": 17.3912,
        "lon": 78.5195,
        "bbox": (17.3800, 78.5100, 17.4020, 78.5300),
    },
    "abids": {
        "name": "Abids",
        "aliases": ["abids", "gunfoundry", "gpo", "koti", "sultan bazaar"],
        "lat": 17.3891,
        "lon": 78.4763,
        "bbox": (17.3800, 78.4680, 17.3980, 78.4850),
    },
    "malakpet": {
        "name": "Malakpet",
        "aliases": ["malakpet", "malakpet metro", "race course", "moosarambagh", "chaderghat"],
        "lat": 17.3750,
        "lon": 78.5030,
        "bbox": (17.3650, 78.4950, 17.3850, 78.5120),
    },
    "falaknuma": {
        "name": "Falaknuma",
        "aliases": ["falaknuma", "falaknuma palace", "engine bowli", "chandrayangutta", "shamsheer gunj"],
        "lat": 17.3314,
        "lon": 78.4678,
        "bbox": (17.3200, 78.4550, 17.3420, 78.4780),
    },
    "nampally": {
        "name": "Nampally",
        "aliases": ["nampally", "hyderabad deccan", "mozzam jahi market", "mj market", "public gardens", "exhibition grounds"],
        "lat": 17.3893,
        "lon": 78.4674,
        "bbox": (17.3800, 78.4580, 17.3980, 78.4760),
    },
    "masab-tank": {
        "name": "Masab Tank",
        "aliases": ["masab tank", "masabtank", "humayun nagar", "nmfc", "mahabir hospital", "shantinagar"],
        "lat": 17.4042,
        "lon": 78.4485,
        "bbox": (17.3950, 78.4400, 17.4130, 78.4580),
    },
    "tolichowki": {
        "name": "Tolichowki",
        "aliases": ["tolichowki", "toli chowki", "shaikpet", "paramount colony", "seven tombs"],
        "lat": 17.3973,
        "lon": 78.4080,
        "bbox": (17.3880, 78.3980, 17.4070, 78.4180),
    },
    "manikonda": {
        "name": "Manikonda",
        "aliases": ["manikonda", "puppy colony", "shaikpet dargha", "ou colony"],
        "lat": 17.3995,
        "lon": 78.3842,
        "bbox": (17.3900, 78.3750, 17.4100, 78.3950),
    },
    "raidurg": {
        "name": "Raidurg",
        "aliases": ["raidurg", "raidurgam", "biodiversity", "biodiversity park", "t-hub", "knowledge city"],
        "lat": 17.4332,
        "lon": 78.3789,
        "bbox": (17.4240, 78.3700, 17.4420, 78.3880),
    },
    "chandanagar": {
        "name": "Chandanagar",
        "aliases": ["chandanagar", "chanda nagar", "bhel", "gangaram"],
        "lat": 17.4930,
        "lon": 78.3260,
        "bbox": (17.4830, 78.3150, 17.5030, 78.3370),
    },
    "lingampally": {
        "name": "Lingampally",
        "aliases": ["lingampally", "serilingampally", "bhel township", "hcu", "university of hyderabad"],
        "lat": 17.4870,
        "lon": 78.3180,
        "bbox": (17.4770, 78.3070, 17.4970, 78.3280),
    },
    "patancheru": {
        "name": "Patancheru",
        "aliases": ["patancheru", "patancheru ida", "icrisat", "muttangi"],
        "lat": 17.5284,
        "lon": 78.2676,
        "bbox": (17.5180, 78.2550, 17.5380, 78.2800),
    },
    "sanathnagar": {
        "name": "Sanathnagar",
        "aliases": ["sanathnagar", "sanath nagar", "fateh nagar", "czech colony", "bharat nagar", "moosapet"],
        "lat": 17.4589,
        "lon": 78.4428,
        "bbox": (17.4490, 78.4330, 17.4680, 78.4520),
    },
    "nizampet": {
        "name": "Nizampet",
        "aliases": ["nizampet", "nizampet road", "bachupally", "pragathi nagar"],
        "lat": 17.5173,
        "lon": 78.3840,
        "bbox": (17.5070, 78.3730, 17.5270, 78.3950),
    },
    "bowenpally": {
        "name": "Bowenpally",
        "aliases": ["bowenpally", "new bowenpally", "old bowenpally", "hasmathpet", "tadbund"],
        "lat": 17.4716,
        "lon": 78.4834,
        "bbox": (17.4620, 78.4730, 17.4810, 78.4940),
    },
    "alwal": {
        "name": "Alwal",
        "aliases": ["alwal", "old alwal", "lothkunta", "machabollaram"],
        "lat": 17.5023,
        "lon": 78.5134,
        "bbox": (17.4920, 78.5030, 17.5120, 78.5240),
    },
    "malkajgiri": {
        "name": "Malkajgiri",
        "aliases": ["malkajgiri", "naredmet", "anandbagh", "vinayak nagar", "sainikpuri", "as rao nagar", "a.s. rao nagar", "ecil", "moula ali"],
        "lat": 17.4509,
        "lon": 78.5283,
        "bbox": (17.4410, 78.5180, 17.4610, 78.5390),
    },
    "habsiguda": {
        "name": "Habsiguda",
        "aliases": ["habsiguda", "street no 8", "ngri", "ramanathapur"],
        "lat": 17.4172,
        "lon": 78.5446,
        "bbox": (17.4080, 78.5350, 17.4260, 78.5540),
    },
    "somajiguda": {
        "name": "Somajiguda",
        "aliases": ["somajiguda", "raj bhavan", "raj bhavan road", "yashoda hospital", "khairatabad"],
        "lat": 17.4256,
        "lon": 78.4583,
        "bbox": (17.4160, 78.4490, 17.4350, 78.4680),
    },
    "kompally": {
        "name": "Kompally",
        "aliases": ["kompally", "jeedimetla", "suchitra", "suchitra circle", "quthbullapur", "medchal"],
        "lat": 17.5385,
        "lon": 78.4860,
        "bbox": (17.5280, 78.4750, 17.5480, 78.4970),
    },
    "shamshabad": {
        "name": "Shamshabad",
        "aliases": ["shamshabad", "rgia", "hyderabad airport", "airport", "gmr"],
        "lat": 17.2403,
        "lon": 78.4294,
        "bbox": (17.2280, 78.4150, 17.2520, 78.4440),
    },
    "attapur": {
        "name": "Attapur",
        "aliases": ["attapur", "hyderguda attapur", "pillar no", "rajendranagar"],
        "lat": 17.3686,
        "lon": 78.4356,
        "bbox": (17.3590, 78.4250, 17.3780, 78.4460),
    },
    "balapur": {
        "name": "Balapur",
        "aliases": ["balapur", "balapur crossroads", "balapur x roads", "kanchanbagh", "drdl", "dmrl"],
        "lat": 17.3242,
        "lon": 78.5133,
        "bbox": (17.3140, 78.5030, 17.3340, 78.5240),
    },
    "badangpet": {
        "name": "Badangpet",
        "aliases": ["badangpet", "meerpet", "almasguda", "kurmalguda", "nadargul"],
        "lat": 17.3210,
        "lon": 78.5305,
        "bbox": (17.3080, 78.5180, 17.3380, 78.5450),
    },
    "karmanghat": {
        "name": "Karmanghat",
        "aliases": ["karmanghat", "champapet", "saroornagar", "hasthinapuram", "hastinapuram", "bn reddy nagar"],
        "lat": 17.3410,
        "lon": 78.5330,
        "bbox": (17.3300, 78.5200, 17.3550, 78.5480),
    },
    "vanasthalipuram": {
        "name": "Vanasthalipuram",
        "aliases": ["vanasthalipuram", "hayathnagar", "autonagar", "saheb nagar"],
        "lat": 17.3303,
        "lon": 78.5683,
        "bbox": (17.3180, 78.5550, 17.3450, 78.5850),
    },
    "bollaram": {
        "name": "Bollaram",
        "aliases": ["bollaram", "ida bollaram", "bollaram industrial"],
        'lat': 17.5510,
        'lon': 78.3580,
        "bbox": (17.5400, 78.3470, 17.5620, 78.3690),
    },
}


# Stop words for candidate extraction during fuzzy matching
STOP_WORDS = {
    "weather", "traffic", "pollution", "air", "quality", "aqi", "energy", "grid", "power",
    "in", "at", "for", "of", "near", "around", "how", "is", "the", "what", "show", "tell",
    "me", "about", "status", "condition", "conditions", "forecast", "today", "now", "please",
    "hyderabad", "telangana", "area", "junction", "corridor", "road", "street", "city",
    "current", "situation", "live", "update", "updates", "report", "check", "view"
}


def _fuzzy_match_string(text: str) -> Optional[Tuple[str, Dict]]:
    """
    Perform fuzzy matching against known Hyderabad locality aliases to gracefully
    handle typos, phonetic misspellings (e.g. 'ammerpet' -> 'ameerpet', 'secunderbad' -> 'secunderabad',
    'gachibowly' -> 'gachibowli', 'santoshnagar' -> 'santosh nagar').
    """
    if not text:
        return None
    import difflib

    cleaned = text.lower()
    words = [w for w in re.sub(r"[^\w\s\-]", " ", cleaned).split() if w]
    if not words:
        return None

    # Pre-build list of all aliases mapped to (slug, data)
    alias_map: Dict[str, Tuple[str, Dict]] = {}
    for slug, data in CANONICAL_LOCALITIES.items():
        for alias in data["aliases"]:
            alias_map[alias.lower()] = (slug, data)

    alias_keys = list(alias_map.keys())
    best_match: Optional[Tuple[str, Dict]] = None
    best_score = 0.0

    # Test n-grams from length 3 down to 1
    for n in (3, 2, 1):
        for i in range(len(words) - n + 1):
            phrase = " ".join(words[i : i + n])
            if phrase in STOP_WORDS or all(w in STOP_WORDS for w in words[i : i + n]):
                continue
            matches = difflib.get_close_matches(phrase, alias_keys, n=1, cutoff=0.75)
            if matches:
                matched_alias = matches[0]
                ratio = difflib.SequenceMatcher(None, phrase, matched_alias).ratio()
                if ratio > best_score:
                    best_score = ratio
                    best_match = alias_map[matched_alias]

    return best_match


def _dynamic_geocode_hyderabad(phrase: str) -> Optional[Tuple[str, Dict]]:
    """
    Fallback dynamic geocoder for un-indexed Hyderabad metropolitan localities
    (e.g. Badangpet, Meerpet, Almasguda, Karmanghat, Gandipet).
    Queries Open-Meteo and OpenStreetMap Nominatim with strict bounding validation within Hyderabad (17.15-17.65 N, 78.15-78.75 E).
    """
    if not phrase or len(phrase.strip()) < 3:
        return None
    import urllib.parse
    clean_name = phrase.strip().title()

    # 1. Open-Meteo Geocoding
    try:
        import httpx
        clean_url = urllib.parse.quote(clean_name)
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={clean_url}&count=5&language=en&format=json"
        resp = httpx.get(url, timeout=2.5)
        if resp.status_code == 200:
            res_list = resp.json().get("results") or []
            for r in res_list:
                if r.get("country_code") == "IN" and (r.get("admin1") == "Telangana" or r.get("admin2") == "Hyderabad"):
                    lat = float(r["latitude"])
                    lon = float(r["longitude"])
                    if HYDERABAD_BOUNDS["min_lat"] <= lat <= HYDERABAD_BOUNDS["max_lat"] and HYDERABAD_BOUNDS["min_lon"] <= lon <= HYDERABAD_BOUNDS["max_lon"]:
                        slug = re.sub(r"[^a-z0-9]+", "-", clean_name.lower()).strip("-")
                        data = {
                            "name": clean_name,
                            "aliases": [clean_name.lower()],
                            "lat": lat,
                            "lon": lon,
                            "bbox": (lat - 0.01, lon - 0.01, lat + 0.01, lon + 0.01),
                        }
                        CANONICAL_LOCALITIES[slug] = data
                        return slug, data
    except Exception:
        pass

    # 2. Nominatim Geocoding
    try:
        import httpx
        nom_query = urllib.parse.quote(f"{clean_name}, Hyderabad, India")
        nom_url = f"https://nominatim.openstreetmap.org/search?q={nom_query}&format=json&limit=1"
        resp = httpx.get(nom_url, headers={"User-Agent": "SUPADSP-SmartCity/2.0"}, timeout=2.5)
        if resp.status_code == 200:
            nom_data = resp.json()
            if nom_data and len(nom_data) > 0:
                lat = float(nom_data[0]["lat"])
                lon = float(nom_data[0]["lon"])
                if HYDERABAD_BOUNDS["min_lat"] <= lat <= HYDERABAD_BOUNDS["max_lat"] and HYDERABAD_BOUNDS["min_lon"] <= lon <= HYDERABAD_BOUNDS["max_lon"]:
                    slug = re.sub(r"[^a-z0-9]+", "-", clean_name.lower()).strip("-")
                    data = {
                        "name": clean_name,
                        "aliases": [clean_name.lower()],
                        "lat": lat,
                        "lon": lon,
                        "bbox": (lat - 0.01, lon - 0.01, lat + 0.01, lon + 0.01),
                    }
                    CANONICAL_LOCALITIES[slug] = data
                    return slug, data
    except Exception:
        pass

    return None


def _extract_query_candidate_locality(query: str) -> Optional[str]:
    """Extract candidate locality phrase from query text via prepositional patterns."""
    patterns = [
        r"\b(?:in|at|for|around|near|of|to)\s+([A-Za-z0-9\s\-]+?)(?:\s+(?:today|tomorrow|now|right now|currently|this|tonight|please|\?|$)|[?,.]|$)",
        r"(?:how is|what is|check|show|tell me about)\s+(?:the\s+)?(?:traffic|weather|pollution|air quality|aqi|energy)\s+(?:in|at|for|around|near|of)?\s*([A-Za-z0-9\s\-]+?)(?:\s+(?:today|tomorrow|now|right now|currently|this|tonight|please|\?|$)|[?,.]|$)",
    ]
    for p in patterns:
        m = re.search(p, query, re.IGNORECASE)
        if m:
            cand = m.group(1).strip()
            if cand.lower() not in STOP_WORDS and len(cand) > 2:
                return cand
    return None


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
    if matches:
        # Sort by start position descending (latest mention in query text takes precedence),
        # then alias length descending (more specific alias matches tie-break)
        matches.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return matches[0][2], matches[0][3]

    # If exact regex boundary match did not hit, attempt fuzzy matching for typos/misspellings
    fuzzy = _fuzzy_match_string(text)
    if fuzzy:
        return fuzzy[0], fuzzy[1]

    # Extract prepositional candidate location and geocode dynamically within Hyderabad
    candidate = _extract_query_candidate_locality(text)
    if candidate:
        geo_res = _dynamic_geocode_hyderabad(candidate)
        if geo_res:
            return geo_res[0], geo_res[1]

    return None


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

