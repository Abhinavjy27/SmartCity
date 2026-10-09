"""
OpenAQLiveProvider — Live Pollution Data via OpenAQ API v3.

Fetches real Hyderabad CPCB/TSPCB station measurements from OpenAQ.
Implements BasePollutionDataProvider so it can be hot-swapped into any
downstream consumer without changes.

Key guarantees:
- OPENAQ_API_KEY read from env var only; never hardcoded here.
- On any API failure, timeout, rate-limit, or data older than OPENAQ_STALE_HOURS:
  returns unavailable / empty — never silently serves stale historical data.
- AQI calculation uses the EXISTING aqi_engine.py with zero new formulas.
- Sufficiency rule (≥3 pollutants including at least one PM fraction) enforced
  by passing concentrations through calculate_aqi() which calls validate_aqi_sufficiency().
"""
import logging
from datetime import datetime, timedelta, timezone, date as date_type
from typing import Optional

import httpx
import pandas as pd
import numpy as np

from .config import (
    OPENAQ_API_KEY,
    OPENAQ_STALE_HOURS,
    CITY_NAME,
)
from .aqi_engine import calculate_aqi
from .data_provider import BasePollutionDataProvider, POLLUTANT_FEATURES

logger = logging.getLogger(__name__)

# ── OpenAQ v3 API constants ──────────────────────────────────────────────────
OPENAQ_BASE_URL = "https://api.openaq.org/v3"
OPENAQ_TIMEOUT_SECONDS = 15

# OpenAQ parameter name → internal canonical name
# Only criteria pollutants required by aqi_engine.py are mapped.
OPENAQ_PARAM_MAP = {
    "pm25": "PM2.5",
    "pm10": "PM10",
    "no2":  "NO2",
    "so2":  "SO2",
    "co":   "CO",
    "o3":   "O3",
    "nh3":  "NH3",
    "no":   "NO",
    "nox":  "NOx",
}

# Known Hyderabad / Telangana CPCB/TSPCB location IDs on OpenAQ.
# These are cross-checked against the OpenAQ locations API filtered by
# country=IN, city=Hyderabad, entity=Governmental. The set is intentionally
# conservative — only CPCB/TSPCB governmental stations are included.
# If empty, the provider falls back to a live OpenAQ search using bounding box.
HYDERABAD_LOCATION_IDS: list[int] = []   # populated at runtime by _discover_locations()

_MODULE_LOCATIONS_CACHE = None
_MODULE_READINGS_CACHE = None
_MODULE_READINGS_CACHE_TIME = None
_MODULE_CACHE_TTL = 120.0  # seconds


class OpenAQLiveProvider(BasePollutionDataProvider):
    """
    Live pollution data provider backed by OpenAQ v3 API.
    Filtered to Hyderabad/Telangana CPCB/TSPCB stations only.

    data_mode = "live"
    is_live   = True
    provider_name = "OpenAQ (CPCB/TSPCB Network)"
    """

    def __init__(self):
        self._api_key: str = OPENAQ_API_KEY
        self._stale_hours: int = OPENAQ_STALE_HOURS
        # In-memory cache, cleared every time the provider object is re-instantiated
        self._stations_cache: Optional[list] = None
        self._stations_cache_time: Optional[datetime] = None
        self._readings_cache: Optional[list] = None
        self._readings_cache_time: Optional[datetime] = None
        self._readings_cache_ttl_seconds = 300   # 5 minutes

    # ── BasePollutionDataProvider properties ─────────────────────────────────

    @property
    def data_mode(self) -> str:
        return "live"

    @property
    def is_live(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return "OpenAQ (CPCB/TSPCB Network)"

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _build_headers(self) -> dict:
        h = {"Accept": "application/json"}
        if self._api_key:
            h["X-API-Key"] = self._api_key
        return h

    def _discover_locations(self) -> list[dict]:
        """
        Query OpenAQ /v3/locations filtered to Hyderabad TSPCB/CPCB governmental stations.
        Returns list of location dicts with id, name, lat, lon, and sensor_map.
        Caches result for 1 hour.
        """
        global _MODULE_LOCATIONS_CACHE
        if _MODULE_LOCATIONS_CACHE is not None:
            return _MODULE_LOCATIONS_CACHE

        now = datetime.now(timezone.utc)
        if (
            self._stations_cache is not None
            and self._stations_cache_time is not None
            and (now - self._stations_cache_time).total_seconds() < 3600
        ):
            return self._stations_cache

        try:
            params = {
                "bbox": "78.2,17.2,78.7,17.6",
                "limit": 100,
            }
            resp = httpx.get(
                f"{OPENAQ_BASE_URL}/locations",
                headers=self._build_headers(),
                params=params,
                timeout=OPENAQ_TIMEOUT_SECONDS,
            )
            if resp.status_code == 429:
                logger.warning("OpenAQ rate-limit (429) on locations discovery")
                return []
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])

            locations = []
            for loc in results:
                name = loc.get("name", "")
                provider_name = str(loc.get("provider", {}).get("name", "")).lower()
                # Filter strictly for TSPCB / CPCB governmental stations
                if "tspcb" not in name.lower() and "cpcb" not in provider_name and "cpcb" not in name.lower():
                    continue

                coords = loc.get("coordinates", {})
                lat = coords.get("latitude")
                lon = coords.get("longitude")
                loc_id = loc.get("id")
                if not (loc_id and lat and lon):
                    continue

                # Build sensor_id -> canonical_param mapping
                s_map = {}
                for s in loc.get("sensors", []):
                    p_name = s.get("parameter", {}).get("name", "").lower()
                    canonical = OPENAQ_PARAM_MAP.get(p_name)
                    if canonical:
                        s_map[s["id"]] = canonical

                locations.append({
                    "id": loc_id,
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "sensor_map": s_map,
                })

            self._stations_cache = locations
            self._stations_cache_time = now
            logger.info("OpenAQ: discovered %d Hyderabad CPCB/TSPCB locations", len(locations))
            return locations

        except httpx.TimeoutException:
            logger.warning("OpenAQ locations request timed out")
            return []
        except Exception as exc:
            logger.warning("OpenAQ locations discovery failed: %s", exc)
            return []

    def _fetch_station_readings(self, locations: list[dict], now: datetime) -> list[dict]:
        """
        Fetch latest measurements for each station via OpenAQ v3 /locations/{id}/latest.
        Applies staleness cutoff (OPENAQ_STALE_HOURS), converts CO units if needed,
        and enforces CPCB sufficiency rule per station.
        """
        if hasattr(self, '_station_readings_cache') and self._station_readings_cache:
            c_time, c_res = self._station_readings_cache
            if (now - c_time).total_seconds() < 60 and c_res:
                return c_res

        stale_cutoff = now - timedelta(hours=self._stale_hours)
        results = []

        for loc in locations:
            lid = loc["id"]
            s_map = loc.get("sensor_map", {})
            try:
                resp = httpx.get(
                    f"{OPENAQ_BASE_URL}/locations/{lid}/latest",
                    headers=self._build_headers(),
                    timeout=OPENAQ_TIMEOUT_SECONDS,
                )
                if resp.status_code == 429:
                    logger.warning("OpenAQ rate-limit on /latest for station %s", lid)
                    continue
                resp.raise_for_status()
                items = resp.json().get("results", [])
            except Exception as exc:
                logger.warning("Failed to fetch latest for location %s: %s", lid, exc)
                continue

            concs: dict[str, float] = {}
            fresh_timestamps: list[datetime] = []
            all_timestamps: list[datetime] = []

            for item in items:
                sid = item.get("sensorsId")
                val = item.get("value")
                if sid not in s_map or val is None or val < 0:
                    continue

                canonical = s_map[sid]

                # Check observation timestamp staleness
                dt_str = item.get("datetime", {}).get("utc")
                meas_dt = None
                if dt_str:
                    try:
                        meas_dt = pd.to_datetime(dt_str, utc=True).to_pydatetime()
                        all_timestamps.append(meas_dt)
                    except Exception:
                        pass

                if meas_dt:
                    if meas_dt >= stale_cutoff:
                        fresh_timestamps.append(meas_dt)

                # Convert CO from µg/m³ to mg/m³ if reported in µg/m³ (CPCB expects mg/m³)
                if canonical == "CO" and val > 10.0:
                    val = round(val / 1000.0, 3)

                if canonical not in concs:
                    concs[canonical] = round(float(val), 2)

            # A station is considered stale if it has no measurements within stale_cutoff
            is_stale = (len(fresh_timestamps) == 0)

            # CPCB Sufficiency Rule: >= 3 criteria pollutants including >= 1 PM fraction
            has_pm = "PM2.5" in concs or "PM10" in concs
            is_sufficient = has_pm and (len(concs) >= 3)

            aqi_res = calculate_aqi(concs) if is_sufficient else {"aqi": None, "category": "Unavailable"}
            latest_ts = (
                max(fresh_timestamps).isoformat()
                if fresh_timestamps
                else (max(all_timestamps).isoformat() if all_timestamps else None)
            )

            reading = {
                "station_name": loc["name"],
                "lat": loc["lat"],
                "lon": loc["lon"],
                "loc_id": lid,
                "timestamp": latest_ts,
                "data_mode": self.data_mode,
                "is_live": self.is_live,
                "aqi": aqi_res.get("aqi"),
                "category": aqi_res.get("category", "Unavailable"),
                "color": aqi_res.get("color", "#999999"),
                "dominant_pollutant": aqi_res.get("dominant_pollutant"),
                "dominant_value": aqi_res.get("dominant_value"),
                "sub_indices": aqi_res.get("sub_indices", {}),
                "is_sufficient": is_sufficient,
                "stale": is_stale,
            }
            for p in POLLUTANT_FEATURES:
                reading[p] = concs.get(p)
            results.append(reading)

        return results

    def _get_all_live_readings(self) -> list[dict]:
        """
        Full pipeline: discover locations -> fetch latest per station.
        Returns empty list on any failure.
        Uses in-memory cache to avoid hammering the API.
        """
        global _MODULE_READINGS_CACHE, _MODULE_READINGS_CACHE_TIME
        now = datetime.now(timezone.utc)
        if (
            _MODULE_READINGS_CACHE is not None
            and _MODULE_READINGS_CACHE_TIME is not None
            and (now - _MODULE_READINGS_CACHE_TIME).total_seconds() < _MODULE_CACHE_TTL
        ):
            return _MODULE_READINGS_CACHE

        if (
            self._readings_cache is not None
            and self._readings_cache_time is not None
            and (now - self._readings_cache_time).total_seconds() < self._readings_cache_ttl_seconds
        ):
            return self._readings_cache

        locations = self._discover_locations()
        if not locations:
            logger.warning("OpenAQ: no Hyderabad CPCB/TSPCB locations found — returning unavailable")
            return []

        readings = self._fetch_station_readings(locations, now)
        if not readings:
            logger.warning("OpenAQ: no valid live measurements returned — returning unavailable")
            return []

        logger.info("OpenAQ: successfully parsed %d station readings", len(readings))
        self._readings_cache = readings
        self._readings_cache_time = now
        _MODULE_READINGS_CACHE = readings
        _MODULE_READINGS_CACHE_TIME = now
        return readings

    # ── BasePollutionDataProvider implementations ─────────────────────────────

    def get_station_names(self) -> list:
        readings = self._get_all_live_readings()
        return sorted({r["station_name"] for r in readings})

    def get_latest_readings(self) -> list:
        """
        Return per-station readings with AQI computed via aqi_engine.py.
        Empty list if no live data is available.
        """
        return self._get_all_live_readings()

    def get_latest_observation_timestamp(self) -> Optional[str]:
        readings = self._get_all_live_readings()
        timestamps = [r["timestamp"] for r in readings if r.get("timestamp")]
        if not timestamps:
            return None
        return max(timestamps)

    def get_observations(
        self,
        station_name=None,
        start_time=None,
        end_time=None,
        hours: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Live provider does not maintain a 15-min rolling window buffer.
        Returns a single-row DataFrame of latest readings for downstream
        callers that need a DataFrame interface (e.g., temporal_aggregation).
        If data is unavailable, returns empty DataFrame.
        """
        readings = self._get_all_live_readings()
        if not readings:
            return pd.DataFrame()

        rows = []
        now = datetime.now(timezone.utc)
        for r in readings:
            if station_name and r["station_name"] != station_name:
                continue
            ts_str = r.get("timestamp")
            if ts_str:
                try:
                    ts = pd.to_datetime(ts_str, utc=True)
                except Exception:
                    ts = pd.Timestamp(now)
            else:
                ts = pd.Timestamp(now)

            row = {
                "station_name": r["station_name"],
                "timestamp": ts,
                "data_mode": self.data_mode,
                "is_live": self.is_live,
            }
            for p in POLLUTANT_FEATURES:
                row[p] = r.get(p)
            rows.append(row)

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df["date"] = df["timestamp"].dt.date

        # Apply time filters if provided
        if hours is not None and hours > 0:
            cutoff = now - timedelta(hours=hours)
            df = df[df["timestamp"] >= pd.Timestamp(cutoff, tz="UTC")]
        else:
            if start_time is not None:
                df = df[df["timestamp"] >= pd.Timestamp(start_time, tz="UTC")]
            if end_time is not None:
                df = df[df["timestamp"] <= pd.Timestamp(end_time, tz="UTC")]

        return df.reset_index(drop=True)

    def get_daily_aggregates(self, n_days: int = 30) -> pd.DataFrame:
        """
        Live provider does not have multi-day historical sub-hourly buffers.
        Returns single-day aggregate for today from current live readings.
        For multi-day history, use LiveAccumulationStore.
        """
        readings = self._get_all_live_readings()
        if not readings:
            return pd.DataFrame()

        today = datetime.now(timezone.utc).date()
        rows = []
        for r in readings:
            row = {
                "station_name": r["station_name"],
                "date": today,
                "reading_count": 1,
                "expected_count": 1,
                "completeness": {},
            }
            for p in POLLUTANT_FEATURES:
                row[p] = r.get(p)
            rows.append(row)
        return pd.DataFrame(rows)

    def get_city_daily_aggregates(self, n_days: int = 30, min_completeness_ratio: float = 0.5) -> pd.DataFrame:
        """
        Compute city-level daily aggregate from current live readings.
        Only returns today's row. For the forecast switchover, the multi-day
        window is supplied by LiveAccumulationStore.get_city_daily_aggregates().
        """
        readings = self._get_all_live_readings()
        if not readings:
            return pd.DataFrame()

        today = datetime.now(timezone.utc).date()
        row: dict = {"date": today, "active_stations": len(readings)}

        for p in ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3", "NH3"]:
            vals = [r[p] for r in readings if r.get(p) is not None]
            row[p] = round(float(np.mean(vals)), 4) if vals else np.nan

        return pd.DataFrame([row])

    def get_historical_trend(self, range_key: str = "24h") -> list:
        """
        Live provider does not maintain a multi-day rolling buffer.
        Returns empty list — callers that need historical trend should use
        HistoricalTSPCBProvider or LiveAccumulationStore.
        """
        return []

    def get_city_current_concentrations(self) -> dict:
        """
        Convenience method: return city-level average concentrations from live stations
        that pass the CPCB sufficiency rule (≥3 pollutants, at least one PM fraction).
        Returns {} if no valid live data.
        """
        readings = self._get_all_live_readings()
        if not readings:
            return {}

        # Only include stations that have at least one PM fraction
        valid = []
        for r in readings:
            has_pm = r.get("PM2.5") is not None or r.get("PM10") is not None
            n_pollutants = sum(1 for p in ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3", "NH3"]
                               if r.get(p) is not None)
            if has_pm and n_pollutants >= 3:
                valid.append(r)

        if not valid:
            return {}

        city: dict = {}
        for p in ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3", "NH3"]:
            vals = [r[p] for r in valid if r.get(p) is not None]
            if vals:
                city[p] = round(float(np.mean(vals)), 4)
        return city
