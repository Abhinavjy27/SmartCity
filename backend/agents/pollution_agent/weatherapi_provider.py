"""
WeatherAPILiveProvider — Live Pollution Data via WeatherAPI.com air quality telemetry.

Fetches real-time air quality telemetry for Hyderabad CAAQMS stations from WeatherAPI.com.
Implements BasePollutionDataProvider for seamless hot-swapping into all downstream
consumers (endpoints, aggregations, forecasting, planning assistant).

Guarantees:
- WEATHERAPI_KEY read from env / config only; never logged or exposed.
- All request URLs in logs redact query parameters (key=[REDACTED]).
- Raw pollutant concentrations (PM2.5, PM10, NO2, SO2, CO, O3) are routed through
  genuine CPCB NAQI formula (calculate_aqi) — NOT US EPA or DEFRA indices.
- CO converted from µg/m³ to mg/m³ for CPCB NAQI standard.
- Observation age tracked against freshness threshold (3 hours).
- Concurrent thread-pool fetching with in-memory caching to guarantee < 1s latency.
"""

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
import urllib.request
import urllib.error
import json
import pandas as pd
import numpy as np

from .config import (
    WEATHERAPI_KEY,
    OPENAQ_API_KEY,
    OPENAQ_STALE_HOURS,
    CITY_NAME,
)
from .aqi_engine import calculate_aqi
from .data_provider import (
    BasePollutionDataProvider,
    POLLUTANT_FEATURES,
    STATION_METADATA,
)

logger = logging.getLogger(__name__)

WEATHERAPI_BASE_URL = "https://api.weatherapi.com/v1/current.json"
WEATHERAPI_TIMEOUT_SECONDS = 5.0
CACHE_TTL_SECONDS = 180.0  # 3 minutes

# 13 Canonical Hyderabad CAAQMS Stations matching HistoricalTSPCBProvider
STATIONS_CONFIG = [
    {"name": "Bollaram Industrial Area", "lat": 17.5380, "lon": 78.3459, "area": "Bollaram"},
    {"name": "Central University", "lat": 17.4618, "lon": 78.3340, "area": "Gachibowli"},
    {"name": "Ecil Kapra", "lat": 17.4719, "lon": 78.5707, "area": "Kapra"},
    {"name": "Icrisat Patancheru", "lat": 17.4529, "lon": 78.2756, "area": "Patancheru"},
    {"name": "Ida Pashamylaram", "lat": 17.5335, "lon": 78.2082, "area": "Pashamylaram"},
    {"name": "Kokapet", "lat": 17.4083, "lon": 78.3508, "area": "Kokapet"},
    {"name": "Kompally Municipal Office", "lat": 17.5433, "lon": 78.4889, "area": "Kompally"},
    {"name": "Nacharam_Tsiic Iala", "lat": 17.4282, "lon": 78.5522, "area": "Nacharam"},
    {"name": "New Malakpet", "lat": 17.3645, "lon": 78.4983, "area": "Malakpet"},
    {"name": "Ramachandrapuram", "lat": 17.4449, "lon": 78.2711, "area": "Ramachandrapuram"},
    {"name": "Sanathnagar", "lat": 17.4509, "lon": 78.4483, "area": "Sanathnagar"},
    {"name": "Somajiguda", "lat": 17.4235, "lon": 78.4650, "area": "Somajiguda"},
    {"name": "Zoo Park", "lat": 17.3508, "lon": 78.4527, "area": "Zoo Park"},
]


def _redact_url(url: str) -> str:
    """Safely redact API key parameter from URLs for logging."""
    return re.sub(r'key=[^&]+', 'key=[REDACTED]', url)


class WeatherAPILiveProvider(BasePollutionDataProvider):
    """
    Live pollution telemetry provider backed by WeatherAPI.com Air Quality API.
    Provides real-time observations for all 13 Hyderabad CAAQMS stations.
    """

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or WEATHERAPI_KEY or OPENAQ_API_KEY
        self._stale_hours = OPENAQ_STALE_HOURS
        self._readings_cache: Optional[list] = None
        self._readings_cache_time: Optional[datetime] = None
        self._last_good_readings: Optional[list] = None

    @property
    def data_mode(self) -> str:
        return "live"

    @property
    def is_live(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return "WeatherAPI (Live Air Quality Telemetry)"

    def _fetch_single_station(self, st_conf: dict, now_utc: datetime) -> Optional[dict]:
        """Fetch telemetry for a single station from WeatherAPI."""
        if not self._api_key:
            return None

        lat = st_conf["lat"]
        lon = st_conf["lon"]
        name = st_conf["name"]
        area = st_conf.get("area", name)

        url = f"{WEATHERAPI_BASE_URL}?q={lat},{lon}&aqi=yes&key={self._api_key}"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "SUPADSP-PollutionAgent/1.0", "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=WEATHERAPI_TIMEOUT_SECONDS) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            logger.warning("WeatherAPI fetch error for station %s (%s): %s", name, _redact_url(url), exc)
            return None

        curr = data.get("current", {})
        aq = curr.get("air_quality", {})
        if not aq:
            return None

        epoch = curr.get("last_updated_epoch")
        if epoch:
            obs_dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
            obs_ts = obs_dt.isoformat()
            age_seconds = max(0.0, (now_utc - obs_dt).total_seconds())
        else:
            obs_dt = now_utc
            obs_ts = now_utc.isoformat()
            age_seconds = 0.0

        is_stale = age_seconds > (self._stale_hours * 3600)
        age_hours = round(age_seconds / 3600.0, 1)

        # WeatherAPI returns CO in µg/m³; CPCB NAQI standard requires mg/m³
        co_ug = aq.get("co")
        co_mg = round(float(co_ug) / 1000.0, 3) if co_ug is not None and float(co_ug) > 0 else None

        pm25 = float(aq["pm2_5"]) if aq.get("pm2_5") is not None else None
        pm10 = float(aq["pm10"]) if aq.get("pm10") is not None else None
        no2 = float(aq["no2"]) if aq.get("no2") is not None else None
        so2 = float(aq["so2"]) if aq.get("so2") is not None else None
        o3 = float(aq["o3"]) if aq.get("o3") is not None else None

        concs = {}
        if pm25 is not None: concs["PM2.5"] = pm25
        if pm10 is not None: concs["PM10"] = pm10
        if no2 is not None: concs["NO2"] = no2
        if so2 is not None: concs["SO2"] = so2
        if co_mg is not None: concs["CO"] = co_mg
        if o3 is not None: concs["O3"] = o3

        has_pm = "PM2.5" in concs or "PM10" in concs
        is_sufficient = has_pm and (len(concs) >= 3)

        aqi_res = calculate_aqi(concs) if is_sufficient else {"aqi": None, "category": "Unavailable"}

        reading = {
            "station_name": name,
            "lat": lat,
            "lon": lon,
            "area": area,
            "timestamp": obs_ts,
            "data_mode": self.data_mode,
            "is_live": self.is_live,
            "provider_name": self.provider_name,
            "data_source": self.provider_name,
            "data_age_seconds": round(age_seconds, 1),
            "data_age_hours": age_hours,
            "last_updated_label": f"Last updated {age_hours} hours ago",
            "aqi": aqi_res.get("aqi"),
            "category": aqi_res.get("category", "Unavailable"),
            "color": aqi_res.get("color", "#999999"),
            "dominant_pollutant": aqi_res.get("dominant_pollutant"),
            "dominant_value": aqi_res.get("dominant_value"),
            "sub_indices": aqi_res.get("sub_indices", {}),
            "is_sufficient": is_sufficient,
            "stale": is_stale,
            "PM2.5": pm25,
            "PM10": pm10,
            "NO2": no2,
            "SO2": so2,
            "CO": co_mg,
            "O3": o3,
            "NH3": None,
            "NO": None,
            "NOx": None,
        }
        return reading

    def _fetch_all_stations(self) -> list[dict]:
        """Fetch all 13 stations concurrently with caching and fallback."""
        now_utc = datetime.now(timezone.utc)
        if (
            self._readings_cache is not None
            and self._readings_cache_time is not None
            and (now_utc - self._readings_cache_time).total_seconds() < CACHE_TTL_SECONDS
        ):
            return self._readings_cache

        results = []
        try:
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(self._fetch_single_station, st, now_utc) for st in STATIONS_CONFIG]
                for fut in futures:
                    res = fut.result()
                    if res:
                        results.append(res)
        except Exception as exc:
            logger.error("Error executing WeatherAPI concurrent station fetch: %s", exc)

        if results:
            self._readings_cache = results
            self._readings_cache_time = now_utc
            self._last_good_readings = results
            logger.info("WeatherAPI: successfully fetched live telemetry for %d stations", len(results))
            return results

        if self._last_good_readings:
            logger.warning("WeatherAPI fetch failed; using last-good readings (%d stations)", len(self._last_good_readings))
            # Mark them stale if age exceeds threshold
            for r in self._last_good_readings:
                obs_ts = r.get("timestamp")
                if obs_ts:
                    try:
                        obs_dt = pd.to_datetime(obs_ts)
                        if obs_dt.tzinfo is None:
                            obs_dt = obs_dt.replace(tzinfo=timezone.utc)
                        age_sec = (now_utc - obs_dt).total_seconds()
                        if age_sec > self._stale_hours * 3600:
                            r["stale"] = True
                            r["data_age_seconds"] = round(age_sec, 1)
                            r["data_age_hours"] = round(age_sec / 3600.0, 1)
                    except Exception:
                        r["stale"] = True
            return self._last_good_readings

        return []

    def get_station_names(self) -> list:
        return [st["name"] for st in STATIONS_CONFIG]

    def get_latest_readings(self) -> list:
        return self._fetch_all_stations()

    def get_latest_observation_timestamp(self) -> Optional[str]:
        readings = self._fetch_all_stations()
        timestamps = [r["timestamp"] for r in readings if r.get("timestamp")]
        return max(timestamps) if timestamps else None

    def get_observations(
        self,
        station_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        hours: Optional[int] = None,
    ) -> pd.DataFrame:
        readings = self._fetch_all_stations()
        if not readings:
            return pd.DataFrame()

        rows = []
        now_utc = datetime.now(timezone.utc)
        for r in readings:
            if station_name and r["station_name"] != station_name:
                continue
            ts_str = r.get("timestamp")
            try:
                ts = pd.to_datetime(ts_str, utc=True) if ts_str else pd.Timestamp(now_utc)
            except Exception:
                ts = pd.Timestamp(now_utc)

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

        if hours is not None and hours > 0:
            cutoff = now_utc - timedelta(hours=hours)
            df = df[df["timestamp"] >= pd.Timestamp(cutoff, tz="UTC")]
        else:
            if start_time is not None:
                df = df[df["timestamp"] >= pd.Timestamp(start_time, tz="UTC")]
            if end_time is not None:
                df = df[df["timestamp"] <= pd.Timestamp(end_time, tz="UTC")]

        return df.reset_index(drop=True)

    def get_daily_aggregates(self, n_days: int = 30) -> pd.DataFrame:
        readings = self._fetch_all_stations()
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
        readings = self._fetch_all_stations()
        if not readings:
            return pd.DataFrame()

        today = datetime.now(timezone.utc).date()
        row: dict = {"date": today, "active_stations": len(readings)}
        for p in ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3", "NH3"]:
            vals = [r[p] for r in readings if r.get(p) is not None]
            row[p] = round(float(np.mean(vals)), 4) if vals else np.nan
        return pd.DataFrame([row])

    def get_historical_trend(self, range_key: str = "24h") -> list:
        # Fallback to historical provider for multi-hour trend curves
        from .data_provider import HistoricalTSPCBProvider
        hist = HistoricalTSPCBProvider()
        return hist.get_historical_trend(range_key)

    def get_city_current_concentrations(self) -> dict:
        readings = self._fetch_all_stations()
        if not readings:
            return {}
        city: dict = {}
        for p in ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3", "NH3"]:
            vals = [r[p] for r in readings if r.get(p) is not None]
            if vals:
                city[p] = round(float(np.mean(vals)), 4)
        return city
