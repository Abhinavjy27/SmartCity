"""
Live Accumulation Store — persists city-level daily aggregates from OpenAQ.

One JSON file per calendar day: YYYY-MM-DD.json under data/live_accumulation/.
A missing file = no data for that day.
An explicit gap file (YYYY-MM-DD.gap.json) = data was unavailable for that day.

Rules:
- A gap file resets the consecutive-days counter.
- Only days where live data passed the CPCB sufficiency rule are written as
  non-gap files.
- No interpolation or backfill ever.

Public API:
    store = LiveAccumulationStore()
    store.append_day(date, city_conc_dict, station_readings)  → True/False
    store.record_gap(date, reason)
    store.get_status() → LiveDataStatus dict
    store.get_recent_city_daily_aggregates(n_days=14) → pd.DataFrame | None
"""
import json
import logging
import os
from datetime import date as date_type, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .config import LIVE_DATA_DIR, MIN_LIVE_DAYS_FOR_FORECAST

logger = logging.getLogger(__name__)


class LiveAccumulationStore:
    """
    Thread-safe (file-level writes are atomic on POSIX, best-effort on Windows)
    daily accumulation store for OpenAQ live city aggregates.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self._dir = Path(data_dir) if data_dir else LIVE_DATA_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    # ── File path helpers ─────────────────────────────────────────────────────

    def _day_path(self, d: date_type) -> Path:
        return self._dir / f"{d.isoformat()}.json"

    def _gap_path(self, d: date_type) -> Path:
        return self._dir / f"{d.isoformat()}.gap.json"

    # ── Write operations ──────────────────────────────────────────────────────

    def append_day(
        self,
        day: date_type,
        city_concentrations: dict,
        station_readings: list,
    ) -> bool:
        """
        Persist a successful day's city-level aggregate.
        Overwrites any existing file for that day (idempotent re-fetch is OK).
        Removes any gap marker for the same day if it exists.

        Args:
            day: calendar date for this record
            city_concentrations: city-wide mean concentrations dict
                {PM2.5: float, PM10: float, ...}  (NaN for missing pollutants)
            station_readings: list of per-station dicts with concentrations

        Returns:
            True on success, False on any write error.
        """
        payload = {
            "date": day.isoformat(),
            "record_type": "aggregate",
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": "OpenAQ (CPCB/TSPCB Network)",
            "city_concentrations": {
                k: (None if (v is None or (isinstance(v, float) and np.isnan(v))) else round(float(v), 4))
                for k, v in city_concentrations.items()
            },
            "station_count": len(station_readings),
            "station_readings": [
                {
                    "station_name": s.get("station_name"),
                    "lat": s.get("lat"),
                    "lon": s.get("lon"),
                    "timestamp": s.get("timestamp"),
                    "concentrations": {
                        p: (None if s.get(p) is None else round(float(s[p]), 4))
                        for p in ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3", "NH3", "NO", "NOx", "NH3"]
                        if p in s
                    },
                }
                for s in station_readings
            ],
        }
        try:
            # Atomic write: write to temp then rename
            target = self._day_path(day)
            tmp = target.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            os.replace(tmp, target)

            # Remove any existing gap marker for this day
            gap = self._gap_path(day)
            if gap.exists():
                gap.unlink()

            logger.info("LiveAccumulationStore: wrote aggregate for %s", day.isoformat())
            return True
        except Exception as exc:
            logger.error("LiveAccumulationStore: failed to write %s: %s", day.isoformat(), exc)
            return False

    def record_gap(self, day: date_type, reason: str, overwrite_aggregate: bool = False) -> bool:
        """
        Record an explicit gap for a day when live data was unavailable.
        If overwrite_aggregate is True, removes any existing invalid/superseded aggregate.
        """
        if self._day_path(day).exists():
            if overwrite_aggregate:
                try:
                    self._day_path(day).unlink(missing_ok=True)
                except Exception:
                    pass
            else:
                logger.debug("LiveAccumulationStore: day %s already has aggregate, not recording gap", day.isoformat())
                return True

        payload = {
            "date": day.isoformat(),
            "record_type": "gap",
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
        }
        try:
            target = self._gap_path(day)
            tmp = target.with_suffix(".gap.tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            os.replace(tmp, target)
            logger.info("LiveAccumulationStore: gap recorded for %s (%s)", day.isoformat(), reason)
            return True
        except Exception as exc:
            logger.error("LiveAccumulationStore: failed to record gap for %s: %s", day.isoformat(), exc)
            return False

    # ── Read operations ───────────────────────────────────────────────────────

    def _all_dates_in_store(self) -> list[date_type]:
        """
        Return sorted list of all calendar dates with any record (aggregate or gap).
        """
        dates = set()
        for p in self._dir.glob("*.json"):
            stem = p.stem
            if stem.endswith(".gap"):
                stem = stem[: -len(".gap")]
            try:
                dates.add(date_type.fromisoformat(stem))
            except ValueError:
                pass
        return sorted(dates)

    def _day_is_gap(self, d: date_type) -> bool:
        """True if the day has only a gap marker and no aggregate."""
        return self._gap_path(d).exists() and not self._day_path(d).exists()

    def _load_day(self, d: date_type) -> Optional[dict]:
        """Load aggregate JSON for a specific day. Returns None if missing or gap."""
        p = self._day_path(d)
        if not p.exists():
            return None
        try:
            with open(p, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception as exc:
            logger.warning("LiveAccumulationStore: failed to load %s: %s", d.isoformat(), exc)
            return None

    def get_status(self) -> dict:
        """
        Return live-data-status dict.

        Schema:
            consecutive_live_days: int   (resets on any gap)
            earliest_date: str | None
            latest_date: str | None
            gap_dates: list[str]
            ready_for_live_forecast: bool  (true iff consecutive_live_days >= MIN_LIVE_DAYS_FOR_FORECAST)
            total_days_recorded: int
        """
        all_dates = self._all_dates_in_store()

        if not all_dates:
            return {
                "consecutive_live_days": 0,
                "earliest_date": None,
                "latest_date": None,
                "gap_dates": [],
                "ready_for_live_forecast": False,
                "total_days_recorded": 0,
                "min_days_required": MIN_LIVE_DAYS_FOR_FORECAST,
            }

        gap_dates = [d for d in all_dates if self._day_is_gap(d)]
        aggregate_dates = [d for d in all_dates if not self._day_is_gap(d)]

        earliest = all_dates[0].isoformat() if all_dates else None
        latest = all_dates[-1].isoformat() if all_dates else None

        # Consecutive days: count backwards from the latest aggregate date
        # through unbroken consecutive days with no gap.
        consecutive = 0
        if aggregate_dates:
            last_agg = aggregate_dates[-1]
            cursor = last_agg
            while True:
                if self._day_is_gap(cursor):
                    break
                if not self._day_path(cursor).exists():
                    break
                consecutive += 1
                cursor -= timedelta(days=1)

        return {
            "consecutive_live_days": consecutive,
            "earliest_date": earliest,
            "latest_date": latest,
            "gap_dates": [d.isoformat() for d in gap_dates],
            "ready_for_live_forecast": consecutive >= MIN_LIVE_DAYS_FOR_FORECAST,
            "total_days_recorded": len(all_dates),
            "min_days_required": MIN_LIVE_DAYS_FOR_FORECAST,
        }

    def get_recent_city_daily_aggregates(self, n_days: int = 14) -> Optional[pd.DataFrame]:
        """
        Return the most recent n_days of consecutive aggregate records as a DataFrame.
        Returns None if there are fewer than n_days consecutive records.

        Columns: date, PM2.5, PM10, NO2, SO2, CO, O3, NH3 (NaN for missing).
        """
        all_dates = sorted(self._all_dates_in_store())
        if not all_dates:
            return None

        # Walk backwards from most recent date collecting consecutive aggregates
        consecutive_aggs: list[date_type] = []
        for d in reversed(all_dates):
            if self._day_is_gap(d):
                break
            data = self._load_day(d)
            if data is None:
                break
            consecutive_aggs.insert(0, d)
            if len(consecutive_aggs) == n_days:
                break

        if len(consecutive_aggs) < n_days:
            return None

        rows = []
        for d in consecutive_aggs:
            data = self._load_day(d)
            if data is None:
                return None   # integrity violation
            conc = data.get("city_concentrations", {})
            row = {"date": d}
            for p in ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3", "NH3"]:
                v = conc.get(p)
                row[p] = float(v) if v is not None else np.nan
            rows.append(row)

        return pd.DataFrame(rows)


# ── Module-level singleton ────────────────────────────────────────────────────

_store: Optional[LiveAccumulationStore] = None


def get_live_store() -> LiveAccumulationStore:
    global _store
    if _store is None:
        _store = LiveAccumulationStore()
    return _store
