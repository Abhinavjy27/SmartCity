"""
CPCB AQI Engine — Indian National Air Quality Index calculation.

Implements the official CPCB breakpoint methodology:
- Continuous concentration breakpoints supporting decimal concentrations
- Sub-index calculation per pollutant via linear interpolation
- Overall AQI = max(valid CPCB sub-indices)
- Strict CPCB sufficiency enforcement: >= 3 pollutants including PM2.5 or PM10
- Categories: Good / Satisfactory / Moderate / Poor / Very Poor / Severe
"""
import math
from typing import Optional

from .data_quality import validate_reading, validate_aqi_sufficiency

# ── CPCB Continuous Breakpoint Tables ──
# Each entry: (C_lo, C_hi, I_lo, I_hi)
# Boundaries are continuous floats to correctly evaluate decimal concentration readings.
BREAKPOINTS = {
    "PM2.5": [  # 24-hr avg, µg/m³
        (0.0, 30.0, 0, 50),
        (30.0, 60.0, 50, 100),
        (60.0, 90.0, 100, 200),
        (90.0, 120.0, 200, 300),
        (120.0, 250.0, 300, 400),
        (250.0, 500.0, 400, 500),
    ],
    "PM10": [  # 24-hr avg, µg/m³
        (0.0, 50.0, 0, 50),
        (50.0, 100.0, 50, 100),
        (100.0, 250.0, 100, 200),
        (250.0, 350.0, 200, 300),
        (350.0, 430.0, 300, 400),
        (430.0, 600.0, 400, 500),
    ],
    "SO2": [  # 24-hr avg, µg/m³
        (0.0, 40.0, 0, 50),
        (40.0, 80.0, 50, 100),
        (80.0, 380.0, 100, 200),
        (380.0, 800.0, 200, 300),
        (800.0, 1600.0, 300, 400),
        (1600.0, 2400.0, 400, 500),
    ],
    "NO2": [  # 24-hr avg, µg/m³
        (0.0, 40.0, 0, 50),
        (40.0, 80.0, 50, 100),
        (80.0, 180.0, 100, 200),
        (180.0, 280.0, 200, 300),
        (280.0, 400.0, 300, 400),
        (400.0, 600.0, 400, 500),
    ],
    "CO": [  # 8-hr max, mg/m³
        (0.0, 1.0, 0, 50),
        (1.0, 2.0, 50, 100),
        (2.0, 10.0, 100, 200),
        (10.0, 17.0, 200, 300),
        (17.0, 34.0, 300, 400),
        (34.0, 50.0, 400, 500),
    ],
    "O3": [  # 8-hr max, µg/m³
        (0.0, 50.0, 0, 50),
        (50.0, 100.0, 50, 100),
        (100.0, 168.0, 100, 200),
        (168.0, 208.0, 200, 300),
        (208.0, 748.0, 300, 400),
        (748.0, 1000.0, 400, 500),
    ],
    "NH3": [  # 24-hr avg, µg/m³
        (0.0, 200.0, 0, 50),
        (200.0, 400.0, 50, 100),
        (400.0, 800.0, 100, 200),
        (800.0, 1200.0, 200, 300),
        (1200.0, 1800.0, 300, 400),
        (1800.0, 2400.0, 400, 500),
    ],
}

AQI_CATEGORIES = [
    (0, 50, "Good", "#2F8F72"),
    (51, 100, "Satisfactory", "#6BBF59"),
    (101, 200, "Moderate", "#F4A62A"),
    (201, 300, "Poor", "#E5483F"),
    (301, 400, "Very Poor", "#8B0000"),
    (401, 500, "Severe", "#5C0029"),
]


def calculate_sub_index(pollutant: str, concentration: float) -> Optional[int]:
    """
    Calculate the CPCB sub-index for a given pollutant and concentration.
    Handles continuous floating-point concentrations across boundary intervals.
    Returns None if pollutant is unknown or concentration is invalid.
    """
    if pollutant not in BREAKPOINTS:
        return None

    res = validate_reading(pollutant, concentration)
    if not res["valid"]:
        return None

    conc = res["value"]

    # Iterate through continuous breakpoints
    for i, (c_lo, c_hi, i_lo, i_hi) in enumerate(BREAKPOINTS[pollutant]):
        # First interval includes c_lo; subsequent intervals are (c_lo, c_hi]
        in_range = (c_lo <= conc <= c_hi) if i == 0 else (c_lo < conc <= c_hi)
        if in_range:
            # Linear interpolation formula
            sub_index = ((i_hi - i_lo) / (c_hi - c_lo)) * (conc - c_lo) + i_lo
            return int(math.floor(sub_index + 0.5))

    # Concentration exceeds highest breakpoint — capped at 500 per CPCB rules
    last = BREAKPOINTS[pollutant][-1]
    if conc > last[1]:
        return 500

    return None


def calculate_aqi(concentrations: dict) -> dict:
    """
    Calculate overall CPCB AQI from a dict of pollutant concentrations.
    Enforces CPCB Sufficiency (§10):
      - Must have >= 3 valid CPCB pollutants
      - Must have at least one particulate (PM2.5 or PM10)
    If sufficiency fails, AQI is returned as None (unavailable).

    Args:
        concentrations: {"PM2.5": 48.5, "PM10": 78.0, "NO2": 26.0, ...}

    Returns:
        {
            "aqi": int or None,
            "category": str,
            "color": str,
            "dominant_pollutant": str or None,
            "dominant_value": float or None,
            "sub_indices": dict,
            "source": "cpcb_engine",
            "reason": str or None
        }
    """
    # Calculate sub-indices for all recognized CPCB pollutants
    sub_indices = {}
    for pollutant in BREAKPOINTS:
        val = concentrations.get(pollutant)
        if val is not None:
            si = calculate_sub_index(pollutant, val)
            if si is not None:
                sub_indices[pollutant] = si

    # Validate sufficiency
    sufficiency = validate_aqi_sufficiency(concentrations)
    if not sufficiency["sufficient"]:
        return {
            "aqi": None,
            "category": "Unavailable",
            "color": "#999999",
            "dominant_pollutant": None,
            "dominant_value": None,
            "sub_indices": sub_indices,
            "source": "cpcb_engine",
            "reason": sufficiency["reason"],
        }

    # Overall AQI = max of valid sub-indices
    aqi_value = max(sub_indices.values())
    dominant = max(sub_indices, key=sub_indices.get)
    category, color = get_aqi_category(aqi_value)
    dominant_val = concentrations.get(dominant)

    return {
        "aqi": aqi_value,
        "category": category,
        "color": color,
        "dominant_pollutant": dominant,
        "dominant_value": float(dominant_val) if dominant_val is not None else None,
        "sub_indices": sub_indices,
        "source": "cpcb_engine",
        "reason": None,
    }


def get_aqi_category(aqi_value: Optional[int]) -> tuple:
    """Return (category_name, color) for a given AQI value."""
    if aqi_value is None:
        return ("Unavailable", "#999999")
    for lo, hi, cat, color in AQI_CATEGORIES:
        if lo <= aqi_value <= hi:
            return (cat, color)
    if aqi_value > 500:
        return ("Severe", "#5C0029")
    return ("Unavailable", "#999999")


def get_dominant_pollutant(concentrations: dict) -> Optional[str]:
    """Return the pollutant with the highest sub-index, or None."""
    result = calculate_aqi(concentrations)
    return result.get("dominant_pollutant")
