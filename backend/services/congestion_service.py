"""
Live TomTom Congestion Index Service
====================================
Computes Network Congestion Index across 21 monitored Hyderabad junctions.
Driven ONLY by live TomTom Traffic Flow Segment Data API.
Zero simulated or placeholder metrics.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger("congestion_service")

# ---------------------------------------------------------------------------
# Constants & Configuration
# ---------------------------------------------------------------------------
POLL_INTERVAL_DEFAULT = 900  # 15 minutes
DAILY_QUOTA_DEFAULT = 2500
CONCURRENCY_LIMIT = 5
REQUEST_TIMEOUT_SECONDS = 8.0

# Database path (SQLite)
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "congestion.db"

# Points config resolution
POINTS_CONFIG_PATHS = [
    Path(__file__).resolve().parent.parent / "config" / "traffic_points.json",
    Path("traffic_points.json").resolve(),
    Path(__file__).resolve().parent.parent.parent / "traffic_points.json",
]


def load_traffic_points() -> List[Dict[str, Any]]:
    for p in POINTS_CONFIG_PATHS:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    points = json.load(f)
                if isinstance(points, list) and len(points) > 0:
                    logger.info("Loaded %d traffic points from %s", len(points), p)
                    return points
            except Exception as e:
                logger.error("Failed loading points from %s: %s", p, e)
    logger.error("Could not find traffic_points.json in any known location!")
    return []


def get_level(val: Optional[float]) -> Optional[str]:
    if val is None:
        return None
    if val < 15.0:
        return "light"
    elif val < 30.0:
        return "moderate"
    elif val < 50.0:
        return "heavy"
    else:
        return "severe"


# ---------------------------------------------------------------------------
# Database Management
# ---------------------------------------------------------------------------
class CongestionDB:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(str(self.db_path), check_same_thread=False)

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS congestion_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    utc_timestamp TEXT NOT NULL,
                    index_pct REAL NOT NULL,
                    valid_points INTEGER NOT NULL,
                    total_points INTEGER NOT NULL
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_congestion_ts ON congestion_snapshots(utc_timestamp);"
            )

    def insert_snapshot(self, utc_ts: str, index_pct: float, valid_points: int, total_points: int):
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO congestion_snapshots (utc_timestamp, index_pct, valid_points, total_points)
                VALUES (?, ?, ?, ?);
                """,
                (utc_ts, index_pct, valid_points, total_points),
            )
            # Prune records older than 14 days on write
            cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
            conn.execute(
                "DELETE FROM congestion_snapshots WHERE utc_timestamp < ?;",
                (cutoff,),
            )

    def get_baseline_for(self, now_utc: datetime) -> Tuple[Optional[float], bool]:
        """
        Baseline = mean index_pct of real snapshots within +/-30 min of (now - 24h).
        """
        target = now_utc - timedelta(hours=24)
        w_start = (target - timedelta(minutes=30)).isoformat()
        w_end = (target + timedelta(minutes=30)).isoformat()

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT index_pct FROM congestion_snapshots
                WHERE utc_timestamp >= ? AND utc_timestamp <= ?;
                """,
                (w_start, w_end),
            )
            rows = cursor.fetchall()

        if not rows:
            return None, False

        mean_val = sum(r[0] for r in rows) / len(rows)
        return round(mean_val, 1), True

    def get_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT utc_timestamp, index_pct FROM congestion_snapshots
                WHERE utc_timestamp >= ?
                ORDER BY utc_timestamp ASC;
                """,
                (cutoff,),
            )
            rows = cursor.fetchall()
        return [{"t": r[0], "value_pct": r[1]} for r in rows]


# ---------------------------------------------------------------------------
# Congestion Index Manager
# ---------------------------------------------------------------------------
class CongestionService:
    def __init__(self, db: Optional[CongestionDB] = None):
        self.db = db or CongestionDB()
        self.points = load_traffic_points()
        self.poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", str(POLL_INTERVAL_DEFAULT)))
        self.daily_quota = int(os.getenv("TOMTOM_DAILY_QUOTA", str(DAILY_QUOTA_DEFAULT)))
        self._bg_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

        # In-memory latest state
        self._latest_result: Dict[str, Any] = {
            "value_pct": None,
            "delta_pp": None,
            "baseline_available": False,
            "valid_points": 0,
            "total_points": len(self.points),
            "level": None,
            "updated_at": None,
            "status": "unavailable",
        }

    def _get_api_key(self) -> str:
        key = os.getenv("TOMTOM_API_KEY", "").strip()
        if not key or key == "YOUR_TOMTOM_API_KEY_HERE" or key == "REPLACE_WITH_YOUR_TOMTOM_KEY":
            return ""
        return key

    def startup_guard(self):
        total_pts = len(self.points)
        interval = self.poll_interval if self.poll_interval > 0 else POLL_INTERVAL_DEFAULT
        requests_per_day = total_pts * (86400.0 / interval)

        if requests_per_day > self.daily_quota:
            logger.warning(
                "STARTUP QUOTA GUARD: Configured %d points polled every %ds will generate ~%.0f requests/day, "
                "which exceeds TOMTOM_DAILY_QUOTA=%d!",
                total_pts,
                interval,
                requests_per_day,
                self.daily_quota,
            )
        else:
            logger.info(
                "Startup quota check OK: ~%.0f requests/day within quota of %d (points=%d, interval=%ds)",
                requests_per_day,
                self.daily_quota,
                total_pts,
                interval,
            )

    async def fetch_point_congestion(
        self, client: httpx.AsyncClient, sem: asyncio.Semaphore, pt: Dict[str, Any], api_key: str
    ) -> Optional[float]:
        """
        Fetches flowSegmentData for a single point with retry and backoff on 429/5xx only.
        Formula:
          congestion = clamp(1 - currentSpeed / freeFlowSpeed, 0, 1)
          if roadClosure is True -> congestion = 1.0
          discard reading if request failed, freeFlowSpeed <= 0, or confidence < 0.6
        """
        lat, lon = pt["lat"], pt["lon"]
        url = (
            f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
            f"?key={api_key}&point={lat},{lon}&unit=KMPH"
        )

        for attempt in range(3):  # attempt 0 = initial, 1 = retry 1, 2 = retry 2
            try:
                async with sem:
                    resp = await client.get(url, timeout=REQUEST_TIMEOUT_SECONDS)

                # Retry with exponential backoff on 429/5xx only
                if resp.status_code in (429, 500, 502, 503, 504):
                    if attempt < 2:
                        await asyncio.sleep(1.0 * (2 ** attempt))
                        continue
                    else:
                        logger.warning("TomTom point %s failed after retries with status %d", pt.get("name"), resp.status_code)
                        return None

                if resp.status_code != 200:
                    return None

                data = resp.json()
                flow = data.get("flowSegmentData", {})
                if not flow:
                    return None

                # Road closure condition
                if flow.get("roadClosure") is True:
                    return 1.0

                current_speed = flow.get("currentSpeed")
                free_flow_speed = flow.get("freeFlowSpeed")
                confidence = flow.get("confidence", 0.0)

                # Discard criteria
                if free_flow_speed is None or current_speed is None:
                    return None
                if free_flow_speed <= 0 or confidence < 0.6:
                    return None

                ratio = 1.0 - (float(current_speed) / float(free_flow_speed))
                return max(0.0, min(1.0, ratio))

            except (httpx.TimeoutException, httpx.RequestError) as exc:
                if attempt < 2:
                    await asyncio.sleep(1.0 * (2 ** attempt))
                    continue
                logger.warning("TomTom point %s network error: %s", pt.get("name"), exc)
                return None
            except Exception as exc:
                logger.warning("Unexpected error fetching point %s: %s", pt.get("name"), exc)
                return None

        return None

    async def poll_cycle(self) -> Dict[str, Any]:
        """
        Executes a single live polling cycle across all monitoring points.
        """
        api_key = self._get_api_key()
        if not api_key:
            logger.error("CRITICAL: TOMTOM_API_KEY is missing or unconfigured! Traffic Congestion Index is unavailable.")
            self._latest_result["status"] = "unavailable"
            self._latest_result["value_pct"] = None
            return self._latest_result

        total_pts = len(self.points)
        if total_pts == 0:
            logger.error("No traffic points configured!")
            self._latest_result["status"] = "unavailable"
            return self._latest_result

        sem = asyncio.Semaphore(CONCURRENCY_LIMIT)
        async with httpx.AsyncClient() as client:
            tasks = [
                self.fetch_point_congestion(client, sem, pt, api_key)
                for pt in self.points
            ]
            results = await asyncio.gather(*tasks, return_exceptions=False)

        valid_readings = [r for r in results if r is not None]
        valid_count = len(valid_readings)
        now_utc = datetime.now(timezone.utc)
        now_iso = now_utc.isoformat()

        logger.info(
            "Congestion poll cycle completed: %d / %d points valid",
            valid_count,
            total_pts,
        )

        # 60% validity threshold
        if valid_count < 0.6 * total_pts:
            logger.warning(
                "Fewer than 60%% of points valid (%d/%d). Maintaining last real value and marking stale.",
                valid_count,
                total_pts,
            )
            # If we had a previous real value, keep it and mark stale; otherwise keep null
            self._latest_result["status"] = "stale"
            self._latest_result["valid_points"] = valid_count
            self._latest_result["total_points"] = total_pts
            return self._latest_result

        # Calculate Network Congestion Index = mean(congestion) * 100, rounded to 1 decimal
        mean_congestion = sum(valid_readings) / valid_count
        index_pct = round(mean_congestion * 100.0, 1)

        # Persist to database
        self.db.insert_snapshot(now_iso, index_pct, valid_count, total_pts)

        # Calculate baseline
        baseline, baseline_available = self.db.get_baseline_for(now_utc)
        delta_pp = round(index_pct - baseline, 1) if baseline_available and baseline is not None else None

        self._latest_result = {
            "value_pct": index_pct,
            "delta_pp": delta_pp,
            "baseline_available": baseline_available,
            "valid_points": valid_count,
            "total_points": total_pts,
            "level": get_level(index_pct),
            "updated_at": now_iso,
            "status": "live",
        }

        return self._latest_result

    async def _poll_loop(self):
        # 1. Execute first poll immediately on startup
        try:
            await self.poll_cycle()
        except Exception as exc:
            logger.exception("Initial congestion poll failed: %s", exc)

        # 2. Subsequent polls at configured interval
        while not self._shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=float(self.poll_interval),
                )
                break  # shutdown requested
            except asyncio.TimeoutError:
                pass  # interval elapsed, run poll

            try:
                await self.poll_cycle()
            except Exception as exc:
                logger.exception("Error during scheduled congestion poll: %s", exc)

    def start_background_task(self):
        self.startup_guard()
        api_key = self._get_api_key()
        if not api_key:
            logger.error("TOMTOM_API_KEY missing at startup! Congestion Index endpoint will report 'unavailable'.")
            self._latest_result["status"] = "unavailable"
            self._latest_result["value_pct"] = None
            return

        self._shutdown_event.clear()
        self._bg_task = asyncio.create_task(self._poll_loop())
        logger.info("Started background CongestionService polling loop (interval=%ds)", self.poll_interval)

    def stop_background_task(self):
        self._shutdown_event.set()
        if self._bg_task and not self._bg_task.done():
            self._bg_task.cancel()
            logger.info("Cancelled background CongestionService polling task")

    def get_current_metrics(self) -> Dict[str, Any]:
        """
        Serves latest metric from in-memory cache and DB. Never calls TomTom on GET.
        Checks if updated_at is older than 2x the poll interval to mark stale.
        """
        api_key = self._get_api_key()
        if not api_key:
            return {
                "value_pct": None,
                "delta_pp": None,
                "baseline_available": False,
                "valid_points": 0,
                "total_points": len(self.points),
                "level": None,
                "updated_at": None,
                "status": "unavailable",
            }

        res = dict(self._latest_result)
        updated_at_str = res.get("updated_at")

        if updated_at_str:
            try:
                updated_at = datetime.fromisoformat(updated_at_str)
                age_sec = (datetime.now(timezone.utc) - updated_at).total_seconds()
                if age_sec > (2 * self.poll_interval):
                    res["status"] = "stale"
            except Exception:
                pass
        else:
            if res.get("value_pct") is None:
                res["status"] = "unavailable"

        return res

    def get_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        return self.db.get_history(hours=hours)


# Global singleton
congestion_service = CongestionService()
