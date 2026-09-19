"""
Data quality validation for pollution observations.
Implements three strictly separated data-quality concepts (§8):
  A. Dashboard observation quality (validate_station_reading)
  B. CPCB AQI calculation sufficiency (validate_aqi_sufficiency)
  C. BiLSTM forecast readiness (validate_forecast_readiness)
"""
import math
import logging
from datetime import datetime, date, timedelta, timezone
from typing import Optional

from .config import MIN_DAILY_READINGS, MIN_DAYS_FOR_FORECAST, STATION_STALE_THRESHOLD_HOURS

logger = logging.getLogger(__name__)

# Valid ranges for pollutant concentrations (µg/m³ unless noted)
VALID_RANGES = {
    "PM2.5": (0.0, 1000.0),
    "PM10": (0.0, 1500.0),
    "NO": (0.0, 500.0),
    "NO2": (0.0, 600.0),
    "NOx": (0.0, 800.0),
    "NH3": (0.0, 2400.0),
    "CO": (0.0, 50.0),      # mg/m³
    "SO2": (0.0, 2400.0),
    "O3": (0.0, 1000.0),
    "Benzene": (0.0, 500.0),
    "Toluene": (0.0, 500.0),
    "Xylene": (0.0, 500.0),
}

# The 12 required pollutant features for the BiLSTM forecast model
REQUIRED_FORECAST_POLLUTANTS = [
    "PM2.5", "PM10", "NO", "NO2", "NOx", "NH3",
    "CO", "SO2", "O3", "Benzene", "Toluene", "Xylene",
]

# CPCB AQI Pollutants
CPCB_AQI_POLLUTANTS = ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3", "NH3"]


def validate_reading(pollutant: str, value) -> dict:
    """
    Validate a single pollutant reading.
    Rejects None, NaN, inf, non-numeric, negative, or out-of-range values.
    Returns: {"valid": bool, "issue": str or None, "value": float or None}
    """
    if value is None:
        return {"valid": False, "issue": "missing", "value": None}

    try:
        val = float(value)
    except (ValueError, TypeError):
        return {"valid": False, "issue": "non_numeric", "value": None}

    if math.isnan(val) or math.isinf(val):
        return {"valid": False, "issue": "nan_or_inf", "value": None}

    if val < 0.0:
        return {"valid": False, "issue": "negative", "value": None}

    if pollutant in VALID_RANGES:
        lo, hi = VALID_RANGES[pollutant]
        if val > hi:
            return {"valid": False, "issue": f"exceeds_max_{hi}", "value": None}
        if val < lo:
            return {"valid": False, "issue": f"below_min_{lo}", "value": None}

    return {"valid": True, "issue": None, "value": val}


# ── Concept A: Dashboard Observation Quality ───────────────────────

def validate_station_reading(reading: dict) -> dict:
    """
    Validate all pollutant values in an individual station reading for UI display.
    """
    issues = []
    valid_count = 0
    total = len(VALID_RANGES)

    for pollutant in VALID_RANGES:
        val = reading.get(pollutant)
        result = validate_reading(pollutant, val)
        if result["valid"]:
            valid_count += 1
        elif result["issue"] != "missing":
            issues.append({"pollutant": pollutant, "issue": result["issue"]})

    # Check timestamp staleness
    ts = reading.get("timestamp")
    stale = False
    if ts:
        try:
            if isinstance(ts, str):
                ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            else:
                ts_dt = ts
            now = datetime.now(ts_dt.tzinfo or timezone.utc)
            age_hours = (now - ts_dt).total_seconds() / 3600
            stale = age_hours > STATION_STALE_THRESHOLD_HOURS
        except Exception:
            stale = True

    return {
        "valid_features": valid_count,
        "total_features": total,
        "coverage": round(valid_count / total * 100, 1) if total > 0 else 0,
        "stale": stale,
        "issues": issues,
    }


def compute_overall_data_quality(readings: list) -> dict:
    """Compute summary data quality metrics across all station readings."""
    total_stations = len(readings)
    active_stations = 0
    stale_stations = 0
    quality_issues = []

    for r in readings:
        qr = validate_station_reading(r)
        if qr["coverage"] > 0:
            active_stations += 1
        if qr["stale"]:
            stale_stations += 1
        if qr["issues"]:
            quality_issues.extend(qr["issues"])

    coverage_pct = round(active_stations / total_stations * 100, 1) if total_stations > 0 else 0

    return {
        "total_stations": total_stations,
        "active_stations": active_stations,
        "stale_stations": stale_stations,
        "coverage_percent": coverage_pct,
        "quality_issues": len(quality_issues),
        "status": "good" if coverage_pct >= 80 else ("degraded" if coverage_pct >= 50 else "poor"),
    }


# ── Concept B: CPCB AQI Calculation Sufficiency ─────────────────────

def validate_aqi_sufficiency(concentrations: dict) -> dict:
    """
    CPCB AQI Calculation Sufficiency Check (§10).
    Official CPCB rules require:
    1. At least 3 valid CPCB pollutants must be monitored.
    2. At least one must be a particulate (PM2.5 or PM10).
    Below this threshold: AQI is unavailable — never computed from an arbitrary single pollutant.
    """
    valid_cpcb = []
    has_particulate = False

    for p in CPCB_AQI_POLLUTANTS:
        val = concentrations.get(p)
        res = validate_reading(p, val)
        if res["valid"]:
            valid_cpcb.append(p)
            if p in ("PM2.5", "PM10"):
                has_particulate = True

    if not has_particulate:
        return {
            "sufficient": False,
            "reason": "Missing required particulate (must have at least PM2.5 or PM10)",
            "valid_pollutants": valid_cpcb,
            "valid_count": len(valid_cpcb),
        }

    if len(valid_cpcb) < 3:
        return {
            "sufficient": False,
            "reason": f"Insufficient CPCB pollutants: {len(valid_cpcb)}/3 minimum required ({', '.join(valid_cpcb)})",
            "valid_pollutants": valid_cpcb,
            "valid_count": len(valid_cpcb),
        }

    return {
        "sufficient": True,
        "reason": None,
        "valid_pollutants": valid_cpcb,
        "valid_count": len(valid_cpcb),
    }


# ── Concept C: BiLSTM Forecast Readiness ───────────────────────────

def validate_forecast_readiness(daily_rows: list) -> dict:
    """
    BiLSTM Forecast Readiness Validation (§7, §8).
    Requires ALL of:
    1. Exactly 7 days (len(daily_rows) == 7).
    2. Real dates that are strictly consecutive (gaps rejected, never filled).
    3. Every day independently passes the completeness threshold (reading_count >= 48).
    4. ALL 12 required pollutant features are present and valid for ALL 7 days.
       (No median imputation, no zero fallback, no missing values allowed).
    """
    if len(daily_rows) != MIN_DAYS_FOR_FORECAST:
        return {
            "ready": False,
            "reason": f"Exactly {MIN_DAYS_FOR_FORECAST} consecutive daily observations required, got {len(daily_rows)}",
            "valid_days": len(daily_rows),
        }

    parsed_dates = []
    issues = []

    for i, row in enumerate(daily_rows):
        dt_val = row.get("date")
        if dt_val is None:
            return {"ready": False, "reason": f"Day {i+1} is missing a valid date"}
        if isinstance(dt_val, str):
            try:
                dt = datetime.fromisoformat(dt_val.replace("Z", "+00:00")).date()
            except Exception:
                return {"ready": False, "reason": f"Day {i+1} has invalid date string: {dt_val}"}
        elif isinstance(dt_val, datetime):
            dt = dt_val.date()
        elif isinstance(dt_val, date):
            dt = dt_val
        else:
            return {"ready": False, "reason": f"Day {i+1} has invalid date type: {type(dt_val)}"}
        parsed_dates.append(dt)

        # Completeness check for the day
        rc = row.get("reading_count", MIN_DAILY_READINGS)
        if rc < MIN_DAILY_READINGS:
            issues.append(f"Day {i+1} ({dt}): reading count {rc} below required {MIN_DAILY_READINGS}")

        # Check all 12 required pollutant features for this day
        missing_feats = []
        for feat in REQUIRED_FORECAST_POLLUTANTS:
            val = row.get(feat)
            res = validate_reading(feat, val)
            if not res["valid"]:
                missing_feats.append(f"{feat}({res['issue']})")

        if missing_feats:
            issues.append(f"Day {i+1} ({dt}) missing valid features: {', '.join(missing_feats)}")

    # Check strictly consecutive dates
    for i in range(len(parsed_dates) - 1):
        d1 = parsed_dates[i]
        d2 = parsed_dates[i + 1]
        diff = (d2 - d1).days
        if diff != 1:
            return {
                "ready": False,
                "reason": f"Non-consecutive dates: {d1} followed by {d2} (gap of {diff} days). Gaps cannot be filled.",
                "issues": issues,
            }

    if issues:
        return {
            "ready": False,
            "reason": f"Quality validation failed for {len(issues)} items: {'; '.join(issues[:3])}",
            "issues": issues,
        }

    return {
        "ready": True,
        "reason": None,
        "valid_days": 7,
        "date_range": (parsed_dates[0].isoformat(), parsed_dates[-1].isoformat()),
        "issues": [],
    }
