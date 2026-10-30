"""
AirQualityForecastProvider — Atmospheric Air Quality Forecast Engine.

Fetches real-time air quality forecasts from Open-Meteo CAMS Global / WeatherAPI endpoints,
aggregates hourly pollutant windows per CPCB statutory protocols:
- PM2.5, PM10, NO2, SO2: 24h arithmetic mean (minimum >= 16 valid hours)
- CO, O3: Maximum of 8h rolling arithmetic means (minimum >= 6 valid hours per 8h window)
- CO converted from µg/m³ to mg/m³ (divided by 1000)
- Feeds aggregated concentrations into CPCB NAQI calculation engine (aqi_engine.py)
- Returns exact JSON shape consumed by the dashboard frontend
- Caches results for 60 minutes with up to 6 hours stale fallback on network failure
- Zero archive-model fallback; failure returns status=unavailable
- Never pads missing days; returns only days with sufficient data
"""

import math
import re
import time
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple
from collections import defaultdict

from .config import WEATHERAPI_KEY, CITY_NAME
from .aqi_engine import calculate_aqi

logger = logging.getLogger(__name__)

OPEN_METEO_FORECAST_URL = (
    "https://air-quality-api.open-meteo.com/v1/air-quality?"
    "latitude=17.385&longitude=78.4867&"
    "hourly=pm2_5,pm10,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone&"
    "forecast_days=7&timezone=Asia%2FKolkata&domains=cams_global"
)

HYDERABAD_LAT = 17.385
HYDERABAD_LON = 78.4867
FORECAST_CACHE_TTL_SECONDS = 3600.0  # 60 minutes
MAX_STALE_CACHE_SECONDS = 21600.0    # 6 hours max stale fallback
FORECAST_TIMEOUT_SECONDS = 10.0
IST = timezone(timedelta(hours=5, minutes=30))


def _redact_url(url: str) -> str:
    """Safely redact API key parameter from URLs for server logs."""
    return re.sub(r'key=[^&]+', 'key=[REDACTED]', url)


def _is_valid_reading(val: Any) -> bool:
    """Check if an hourly pollutant measurement is valid and non-negative."""
    if val is None:
        return False
    try:
        f = float(val)
        return not (math.isnan(f) or math.isinf(f)) and f >= 0.0
    except (ValueError, TypeError):
        return False


def aggregate_forecast_day(forecast_day_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Aggregate 24 hourly air_quality readings for a single forecast day according to CPCB rules.

    Rules:
    - Asia/Kolkata dates from the API's own date field.
    - PM2.5, PM10, NO2, SO2: 24h mean, requiring >= 16 valid hours.
    - CO, O3: Maximum of 8h rolling means, requiring >= 6 valid hours per window.
    - CO converted from µg/m³ to mg/m³ (divide by 1000).
    - Missing NH3 handled without imputing.
    - Computes CPCB AQI via calculate_aqi(concentrations).
    - If data is insufficient (< 16h, or fails CPCB sufficiency), returns None (never filled or interpolated).
    """
    if not isinstance(forecast_day_dict, dict):
        return None

    target_date = forecast_day_dict.get("date")
    if not target_date:
        return None

    hours = forecast_day_dict.get("hour", [])
    if len(hours) != 24:
        if len(hours) < 16:
            return None

    # 1. 24-hour mean for PM2.5, PM10, NO2, SO2 (>= 16 valid hours)
    concentrations: Dict[str, float] = {}

    pollutant_keys = {
        "PM2.5": "pm2_5",
        "PM10": "pm10",
        "NO2": "no2",
        "SO2": "so2",
    }

    for standard_name, api_key in pollutant_keys.items():
        valid_vals = []
        for h in hours:
            aq = h.get("air_quality")
            if isinstance(aq, dict):
                raw_val = aq.get(api_key)
                if _is_valid_reading(raw_val):
                    valid_vals.append(float(raw_val))
        if len(valid_vals) >= 16:
            concentrations[standard_name] = round(sum(valid_vals) / len(valid_vals), 2)

    # 2. Maximum of 8h rolling means for CO and O3 (>= 6 valid hours per window)
    n_hours = len(hours)
    window_size = 8
    num_windows = max(0, n_hours - window_size + 1)

    co_rolling_means = []
    for w in range(num_windows):
        win_hours = hours[w : w + window_size]
        win_vals = []
        for h in win_hours:
            aq = h.get("air_quality")
            if isinstance(aq, dict):
                raw_val = aq.get("co")
                if _is_valid_reading(raw_val):
                    win_vals.append(float(raw_val))
        if len(win_vals) >= 6:
            co_rolling_means.append(sum(win_vals) / len(win_vals))

    if co_rolling_means:
        max_co_ug = max(co_rolling_means)
        concentrations["CO"] = round(max_co_ug / 1000.0, 3)

    o3_rolling_means = []
    for w in range(num_windows):
        win_hours = hours[w : w + window_size]
        win_vals = []
        for h in win_hours:
            aq = h.get("air_quality")
            if isinstance(aq, dict):
                raw_val = aq.get("o3")
                if _is_valid_reading(raw_val):
                    win_vals.append(float(raw_val))
        if len(win_vals) >= 6:
            o3_rolling_means.append(sum(win_vals) / len(win_vals))

    if o3_rolling_means:
        concentrations["O3"] = round(max(o3_rolling_means), 2)

    # 3. CPCB NAQI Sufficiency Enforcement
    has_particulate = ("PM2.5" in concentrations) or ("PM10" in concentrations)
    if not has_particulate or len(concentrations) < 3:
        return None

    aqi_res = calculate_aqi(concentrations)
    if aqi_res.get("aqi") is None:
        return None

    try:
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        display_date = dt.strftime("%a, %b ") + str(dt.day)
    except Exception:
        display_date = target_date

    return {
        "target_date": target_date,
        "display_date": display_date,
        "target_timestamp": f"{target_date}T23:59:59+05:30",
        "aqi": aqi_res["aqi"],
        "predicted_aqi": aqi_res["aqi"],
        "category": aqi_res["category"],
        "color": aqi_res["color"],
        "dominant_pollutant": aqi_res["dominant_pollutant"],
        "concentrations": concentrations,
        "pollutants": concentrations,
    }


class WeatherAPIForecastProvider:
    """
    Provider for live air quality forecasts powered by atmospheric dispersion telemetry.
    Adheres strictly to CPCB NAQI aggregation formulas and frontend response schemas.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_ttl_seconds: float = FORECAST_CACHE_TTL_SECONDS,
        max_stale_seconds: float = MAX_STALE_CACHE_SECONDS,
        forecast_url: Optional[str] = None,
    ):
        self._api_key = api_key or WEATHERAPI_KEY
        self._cache_ttl = cache_ttl_seconds
        self._max_stale_seconds = max_stale_seconds
        self._forecast_url = forecast_url or OPEN_METEO_FORECAST_URL
        self._cache: Optional[Tuple[float, Dict[str, Any]]] = None
        self._last_good_cache: Optional[Tuple[float, Dict[str, Any]]] = None

    def clear_cache(self) -> None:
        """Clear cache state for testing."""
        self._cache = None
        self._last_good_cache = None

    def _unavailable_response(self, reason: str) -> Dict[str, Any]:
        """Construct a standardized unavailable forecast response."""
        return {
            "status": "unavailable",
            "reason": reason,
            "daily": {
                "forecast_aqi": None,
                "forecast_status": "unavailable",
                "source": "External modeled air-quality forecast",
                "model_name": "External Model",
                "reason": reason,
            },
            "extended": {
                "status": "unavailable",
                "architecture": "External Model",
                "reason": reason,
                "forecast": [],
                "metrics": None,
            },
        }

    def process_open_meteo_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process Open-Meteo air quality forecast JSON into CPCB aggregated forecast."""
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        if not times:
            return self._unavailable_response("No hourly forecast timestamps returned by air-quality provider.")

        by_date = defaultdict(list)
        for idx, t_str in enumerate(times):
            d_str = t_str.split("T")[0]
            by_date[d_str].append(idx)

        # Origin date: today in Asia/Kolkata
        ist_now = datetime.now(IST)
        today_str = ist_now.strftime("%Y-%m-%d")

        # Future forecast horizons (target_date > today)
        future_dates = sorted([d for d in by_date.keys() if d > today_str])
        if not future_dates:
            # Fallback to all dates if today_str is past end of dataset
            future_dates = sorted(by_date.keys())

        valid_days = []
        for d in future_dates:
            indices = by_date[d]
            concs: Dict[str, float] = {}

            # 24h mean >= 16 valid hours
            mapping = [
                ("PM2.5", "pm2_5"),
                ("PM10", "pm10"),
                ("NO2", "nitrogen_dioxide"),
                ("SO2", "sulphur_dioxide"),
            ]
            for std_name, key in mapping:
                raw_list = hourly.get(key, [])
                valid_vals = [raw_list[i] for i in indices if i < len(raw_list) and _is_valid_reading(raw_list[i])]
                if len(valid_vals) >= 16:
                    concs[std_name] = round(sum(valid_vals) / len(valid_vals), 2)

            # CO: max 8h rolling mean >= 6 valid hours, converted µg/m³ -> mg/m³
            raw_co = hourly.get("carbon_monoxide", [])
            co_means = []
            for w in range(len(indices) - 8 + 1):
                win_indices = indices[w : w + 8]
                win_vals = [raw_co[i] for i in win_indices if i < len(raw_co) and _is_valid_reading(raw_co[i])]
                if len(win_vals) >= 6:
                    co_means.append(sum(win_vals) / len(win_vals))
            if co_means:
                concs["CO"] = round(max(co_means) / 1000.0, 3)

            # O3: max 8h rolling mean >= 6 valid hours in µg/m³
            raw_o3 = hourly.get("ozone", [])
            o3_means = []
            for w in range(len(indices) - 8 + 1):
                win_indices = indices[w : w + 8]
                win_vals = [raw_o3[i] for i in win_indices if i < len(raw_o3) and _is_valid_reading(raw_o3[i])]
                if len(win_vals) >= 6:
                    o3_means.append(sum(win_vals) / len(win_vals))
            if o3_means:
                concs["O3"] = round(max(o3_means), 2)

            # CPCB NAQI Sufficiency Enforcement
            has_particulate = ("PM2.5" in concs) or ("PM10" in concs)
            if not has_particulate or len(concs) < 3:
                continue

            aqi_res = calculate_aqi(concs)
            if aqi_res.get("aqi") is None:
                continue

            try:
                dt = datetime.strptime(d, "%Y-%m-%d")
                display_date = dt.strftime("%a, %b ") + str(dt.day)
            except Exception:
                display_date = d

            valid_days.append({
                "target_date": d,
                "display_date": display_date,
                "target_timestamp": f"{d}T23:59:59+05:30",
                "aqi": aqi_res["aqi"],
                "predicted_aqi": aqi_res["aqi"],
                "category": aqi_res["category"],
                "color": aqi_res["color"],
                "dominant_pollutant": aqi_res["dominant_pollutant"],
                "concentrations": concs,
                "pollutants": concs,
            })

        if not valid_days:
            return self._unavailable_response("Air quality forecast data is currently unavailable due to insufficient hourly observations.")

        origin_date = today_str
        origin_timestamp = f"{origin_date}T23:59:59+05:30"

        extended_days = []
        for idx, d in enumerate(valid_days):
            h_num = idx + 1
            item = {
                "day": h_num,
                "horizon_days": h_num,
                "target_date": d["target_date"],
                "target_timestamp": d["target_timestamp"],
                "display_date": d["display_date"],
                "aqi": d["aqi"],
                "predicted_aqi": d["aqi"],
                "category": d["category"],
                "color": d["color"],
                "dominant_pollutant": d["dominant_pollutant"],
                "concentrations": d["concentrations"],
                "pollutants": d["pollutants"],
                "model": "External Model",
            }
            extended_days.append(item)

        d1 = extended_days[0]
        daily_forecast = {
            "forecast_aqi": d1["aqi"],
            "forecast_status": "success",
            "source": "External modeled air-quality forecast",
            "model_name": "External Model",
            "forecast_horizon": "1 Day (Next-Day)",
            "forecast_date": d1["target_date"],
            "display_date": d1["display_date"],
            "target_timestamp": d1["target_timestamp"],
            "origin_timestamp": origin_timestamp,
            "sequence_days": None,
            "category": d1["category"],
            "color": d1["color"],
            "dominant_pollutant": d1["dominant_pollutant"],
            "predicted_concentrations": d1["concentrations"],
            "confidence": "Atmospheric dispersion forecast",
            "methodology": "Meteorological & Chemical Dispersion Modeling with CPCB AQI Engine",
            "forecast_input_source": "external_forecast",
            "forecast_basis": "CAMS global atmospheric dispersion model",
        }

        extended_forecast = {
            "status": "success",
            "architecture": "External Model",
            "forecast_origin_date": origin_date,
            "origin_timestamp": origin_timestamp,
            "forecast_input_source": "external_forecast",
            "forecast_basis": "CAMS global atmospheric dispersion model",
            "forecast": extended_days,
            "metrics": None,
        }

        return {
            "status": "success",
            "origin_timestamp": origin_timestamp,
            "forecast_input_source": "external_forecast",
            "forecast_basis": "CAMS global atmospheric dispersion model",
            "daily": daily_forecast,
            "extended": extended_forecast,
        }

    def process_forecast_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch processing according to API payload structure."""
        if "hourly" in data:
            return self.process_open_meteo_json(data)

        # WeatherAPI structure fallback / test compatibility
        forecast_days_raw = data.get("forecast", {}).get("forecastday", [])
        if not forecast_days_raw:
            return self._unavailable_response("No forecast day entries returned by air-quality provider.")

        valid_days: List[Dict[str, Any]] = []
        for fd in forecast_days_raw:
            agg = aggregate_forecast_day(fd)
            if agg is not None:
                valid_days.append(agg)

        if not valid_days:
            return self._unavailable_response("Air quality forecast data is currently unavailable due to insufficient hourly observations.")

        first_date_str = valid_days[0]["target_date"]
        try:
            first_dt = datetime.strptime(first_date_str, "%Y-%m-%d")
            origin_dt = first_dt - timedelta(days=1)
            origin_date = origin_dt.strftime("%Y-%m-%d")
        except Exception:
            origin_date = first_date_str

        origin_timestamp = f"{origin_date}T23:59:59+05:30"

        extended_days = []
        for idx, d in enumerate(valid_days):
            h_num = idx + 1
            item = {
                "day": h_num,
                "horizon_days": h_num,
                "target_date": d["target_date"],
                "target_timestamp": d["target_timestamp"],
                "display_date": d["display_date"],
                "aqi": d["aqi"],
                "predicted_aqi": d["aqi"],
                "category": d["category"],
                "color": d["color"],
                "dominant_pollutant": d["dominant_pollutant"],
                "concentrations": d["concentrations"],
                "pollutants": d["pollutants"],
                "model": "External Model",
            }
            extended_days.append(item)

        d1 = extended_days[0]
        daily_forecast = {
            "forecast_aqi": d1["aqi"],
            "forecast_status": "success",
            "source": "External modeled air-quality forecast",
            "model_name": "External Model",
            "forecast_horizon": "1 Day (Next-Day)",
            "forecast_date": d1["target_date"],
            "display_date": d1["display_date"],
            "target_timestamp": d1["target_timestamp"],
            "origin_timestamp": origin_timestamp,
            "sequence_days": None,
            "category": d1["category"],
            "color": d1["color"],
            "dominant_pollutant": d1["dominant_pollutant"],
            "predicted_concentrations": d1["concentrations"],
            "confidence": "Atmospheric dispersion forecast",
            "methodology": "Meteorological & Chemical Dispersion Modeling with CPCB AQI Engine",
            "forecast_input_source": "external_forecast",
            "forecast_basis": "External atmospheric model forecast",
        }

        extended_forecast = {
            "status": "success",
            "architecture": "External Model",
            "forecast_origin_date": origin_date,
            "origin_timestamp": origin_timestamp,
            "forecast_input_source": "external_forecast",
            "forecast_basis": "External atmospheric model forecast",
            "forecast": extended_days,
            "metrics": None,
        }

        return {
            "status": "success",
            "origin_timestamp": origin_timestamp,
            "forecast_input_source": "external_forecast",
            "forecast_basis": "External atmospheric model forecast",
            "daily": daily_forecast,
            "extended": extended_forecast,
        }

    def get_forecast(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetch and return unified air quality forecast.
        Cached for 60 minutes.
        On provider failure, falls back to cache <= 6 hours old; otherwise returns unavailable.
        Zero fallback to historical archive models.
        """
        now_ts = time.time()
        if not force_refresh and self._cache is not None:
            c_time, c_val = self._cache
            if now_ts - c_time < self._cache_ttl:
                return c_val

        url = self._forecast_url
        if "weatherapi.com" in url and not self._api_key:
            logger.warning("WEATHERAPI_KEY is not configured in .env for air-quality forecast.")
            return self._unavailable_response("Air quality forecast service is not configured.")

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "SUPADSP-PollutionAgent/1.0", "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=FORECAST_TIMEOUT_SECONDS) as resp:
                if resp.status != 200:
                    raise Exception(f"HTTP status {resp.status}")
                payload = json.loads(resp.read().decode("utf-8"))

            res = self.process_forecast_json(payload)
            if res["status"] == "success":
                self._cache = (now_ts, res)
                self._last_good_cache = (now_ts, res)
                return res
            else:
                return res

        except Exception as exc:
            logger.warning("Air-quality forecast request failed (%s): %s", _redact_url(url), exc)
            if self._last_good_cache is not None:
                lg_time, lg_val = self._last_good_cache
                if now_ts - lg_time <= self._max_stale_seconds:
                    logger.info("Serving last-good air-quality forecast from cache (age: %.1f hours)", (now_ts - lg_time) / 3600.0)
                    return lg_val

            return self._unavailable_response(f"Air quality forecast provider is unavailable: {exc}")


_forecast_provider_instance: Optional[WeatherAPIForecastProvider] = None


def get_weatherapi_forecast_provider() -> WeatherAPIForecastProvider:
    """Singleton getter for forecast provider."""
    global _forecast_provider_instance
    if _forecast_provider_instance is None:
        _forecast_provider_instance = WeatherAPIForecastProvider()
    return _forecast_provider_instance
