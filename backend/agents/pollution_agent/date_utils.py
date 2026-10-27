"""
Date and Timezone Utility for SUPADSP Pollution Forecasting Pipeline.
Guarantees:
1. Forecast dates strictly derive from the latest valid observation timestamp (NEVER server time).
2. Consecutive calendar days D1 = origin + 1d, D2 = origin + 2d, ..., D7 = origin + 7d.
3. Explicit timezone awareness (UTC storage, IST display).
4. Provides pre-formatted display_date strings for zero-glitch UI rendering.
"""
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Any, Optional

IST_OFFSET = timezone(timedelta(hours=5, minutes=30))


def parse_observation_timestamp(ts_val: Any) -> Optional[datetime]:
    """Parse observation timestamp into a timezone-aware UTC datetime."""
    if ts_val is None:
        return None
    if isinstance(ts_val, datetime):
        if ts_val.tzinfo is None:
            return ts_val.replace(tzinfo=timezone.utc)
        return ts_val.astimezone(timezone.utc)
    if isinstance(ts_val, date):
        return datetime(ts_val.year, ts_val.month, ts_val.day, 23, 45, tzinfo=timezone.utc)
    if isinstance(ts_val, str):
        try:
            # Handle ISO formats with or without Z
            cleaned = ts_val.replace("Z", "+00:00")
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None
    return None


def get_forecast_dates(
    latest_observation_ts: Any,
    horizon_days: int = 7
) -> Dict[str, Any]:
    """
    Derive forecast origin and target dates strictly from the latest valid observation.

    Returns:
        {
            "origin_timestamp": "2025-12-31T23:45:00+00:00",
            "origin_date": "2025-12-31",
            "origin_date_ist": "2026-01-01",
            "horizons": [
                {
                    "horizon_days": 1,
                    "target_date": "2026-01-01",
                    "target_timestamp": "2026-01-01T23:45:00+00:00",
                    "display_date": "Thu, Jan 1",
                    "day_name": "Thursday",
                },
                ...
            ]
        }
    """
    obs_dt = parse_observation_timestamp(latest_observation_ts)
    if obs_dt is None:
        # Fallback only if no data at all
        obs_dt = datetime(2025, 12, 31, 23, 45, tzinfo=timezone.utc)

    origin_date = obs_dt.date()
    obs_ist = obs_dt.astimezone(IST_OFFSET)
    origin_date_ist = obs_ist.date()

    horizons = []
    for h in range(1, horizon_days + 1):
        target_d = origin_date + timedelta(days=h)
        target_ts = obs_dt + timedelta(days=h)
        day_num = target_d.day
        month_str = target_d.strftime("%b")
        weekday_str = target_d.strftime("%a")
        weekday_full = target_d.strftime("%A")

        horizons.append({
            "horizon_days": h,
            "target_date": target_d.isoformat(),
            "target_timestamp": target_ts.isoformat(),
            "display_date": f"{weekday_str}, {month_str} {day_num}",
            "day_name": weekday_full,
        })

    return {
        "origin_timestamp": obs_dt.isoformat(),
        "origin_date": origin_date.isoformat(),
        "origin_date_ist": origin_date_ist.isoformat(),
        "horizons": horizons,
    }


def get_next_day_forecast_dates(
    current_dt: Optional[Any] = None,
    tz: timezone = IST_OFFSET,
) -> Dict[str, Any]:
    """
    Calculate the next-day forecast date strictly as the next calendar day (tomorrow)
    relative to the current date, using the project's established timezone convention (IST for Hyderabad).

    Guarantees:
    1. Target date is strictly the next calendar day (tomorrow) relative to current date in IST.
    2. Zero date distortion across month/year boundaries (e.g., Dec 31 -> Jan 1, Feb 28 -> Mar 1).
    3. Returns standardized target_date (YYYY-MM-DD), target_timestamp, and display_date (e.g. 'Wed, Oct 28').
    """
    if current_dt is None:
        now_dt = datetime.now(timezone.utc)
    elif isinstance(current_dt, str):
        now_dt = parse_observation_timestamp(current_dt) or datetime.now(timezone.utc)
    elif isinstance(current_dt, datetime):
        now_dt = current_dt if current_dt.tzinfo else current_dt.replace(tzinfo=timezone.utc)
    elif isinstance(current_dt, date):
        now_dt = datetime(current_dt.year, current_dt.month, current_dt.day, 12, 0, tzinfo=tz)
    else:
        now_dt = datetime.now(timezone.utc)

    local_dt = now_dt.astimezone(tz)
    current_calendar_date = local_dt.date()
    target_date = current_calendar_date + timedelta(days=1)

    target_ts = datetime(
        target_date.year, target_date.month, target_date.day,
        23, 59, 0, tzinfo=tz
    ).astimezone(timezone.utc)

    day_num = target_date.day
    month_str = target_date.strftime("%b")
    weekday_str = target_date.strftime("%a")
    weekday_full = target_date.strftime("%A")

    return {
        "current_date": current_calendar_date.isoformat(),
        "target_date": target_date.isoformat(),
        "target_timestamp": target_ts.isoformat(),
        "display_date": f"{weekday_str}, {month_str} {day_num}",
        "day_name": weekday_full,
    }

