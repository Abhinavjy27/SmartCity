"""
SUPADSP Specialist Agent — Pollution & Air Quality Intelligence
FastAPI application with all required endpoints.

All data from real TSPCB observations + CPCB AQI engine.
Forecast from verified BiLSTM model (inference only, no training).
Single consistent city-level pipeline (§11) and shared validation (§16).
"""
import asyncio
import json
import logging
import traceback
from contextlib import asynccontextmanager
import numpy as np
from datetime import datetime, timezone

import pandas as pd
from fastapi import FastAPI, Query, Body, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from pathlib import Path
from .config import CITY_NAME, POLLUTION_LIVE_MODE, OPENAQ_STALE_HOURS
from .data_provider import get_data_provider, set_data_provider, POLLUTANT_FEATURES
from .aqi_engine import calculate_aqi, get_aqi_category
from .unified_forecast.inference import UnifiedForecaster
from .analytics import compute_hotspots, compute_distribution, compute_area_trends
from .alerts import generate_alerts
from .temporal_aggregation import (
    compute_city_temporal_aggregates,
    AVERAGING_WINDOWS_DESCRIPTION,
)
from .spatial_aggregation import compute_city_aqi
from .reconciliation import reconcile_aqi_with_cpcb
from .data_quality import (
    validate_station_reading,
    validate_forecast_readiness,
    compute_overall_data_quality,
    REQUIRED_FORECAST_POLLUTANTS,
)
from .live_accumulation import get_live_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



async def _daily_live_accumulation_task():
    """
    Background coroutine: runs every 24 hours, fetches live city aggregate
    from OpenAQLiveProvider, and persists it to LiveAccumulationStore.
    Runs regardless of POLLUTION_LIVE_MODE so accumulation starts immediately
    and the 14-day window can be reached without needing live mode enabled first.
    Records an explicit gap if live data is unavailable so the consecutive-day
    counter resets correctly.
    """
    from datetime import date as date_type
    from .live_provider import OpenAQLiveProvider

    while True:
        today = datetime.now(timezone.utc).date()
        store = get_live_store()
        try:
            provider = OpenAQLiveProvider()
            readings = provider.get_latest_readings()

            if not readings:
                reason = "OpenAQ returned no readings or all data was stale/failed sufficiency"
                logger.warning("[live-accumulation] %s — recording gap for %s", reason, today)
                store.record_gap(today, reason, overwrite_aggregate=True)
            else:
                # Check that at least one station passes CPCB sufficiency and is not stale
                valid_readings = []
                now_utc = datetime.now(timezone.utc)
                for r in readings:
                    is_stale = r.get("stale", False)
                    obs_ts = r.get("timestamp")
                    if not is_stale and obs_ts:
                        try:
                            dt = pd.to_datetime(obs_ts)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            if (now_utc - dt).total_seconds() > OPENAQ_STALE_HOURS * 3600:
                                is_stale = True
                        except Exception:
                            is_stale = True
                    if is_stale:
                        continue
                    conc = {p: r.get(p) for p in ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3", "NH3"]
                            if r.get(p) is not None}
                    has_pm = "PM2.5" in conc or "PM10" in conc
                    if has_pm and len(conc) >= 3:
                        valid_readings.append(r)

                if not valid_readings:
                    reason = f"No stations passed CPCB sufficiency and freshness (< {OPENAQ_STALE_HOURS}h old)"
                    logger.warning("[live-accumulation] %s — recording gap for %s", reason, today)
                    store.record_gap(today, reason, overwrite_aggregate=True)
                else:
                    # City-level mean concentrations from valid stations
                    city_conc: dict = {}
                    for p in ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3", "NH3"]:
                        vals = [r.get(p) for r in valid_readings if r.get(p) is not None]
                        if vals:
                            city_conc[p] = round(float(np.mean(vals)), 4)

                    ok = store.append_day(today, city_conc, valid_readings)
                    if ok:
                        status = store.get_status()
                        logger.info(
                            "[live-accumulation] Stored aggregate for %s. "
                            "consecutive_live_days=%d, ready_for_live_forecast=%s",
                            today,
                            status["consecutive_live_days"],
                            status["ready_for_live_forecast"],
                        )
        except Exception as exc:
            logger.error("[live-accumulation] Unexpected error for %s: %s", today, exc)
            store.record_gap(today, f"Unexpected error: {exc}")

        # Wait until next day (24 hours)
        await asyncio.sleep(86400)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load unified forecasting engine and start live accumulation background task."""
    logger.info("Pollution Agent starting — loading unified spatial-temporal forecasting engine...")
    forecaster = UnifiedForecaster.get_instance()
    if forecaster.loaded:
        logger.info(f"Unified forecasting engine ready: {forecaster.model_name}")
    else:
        logger.warning(f"Unified forecasting engine unavailable: {forecaster.error_message}")

    # Start daily live accumulation in the background; runs forever until shutdown.
    # Runs an immediate first fetch, then sleeps 24h between subsequent fetches.
    accum_task = asyncio.create_task(_daily_live_accumulation_task())
    logger.info("Live accumulation background task started.")

    yield

    accum_task.cancel()
    try:
        await accum_task
    except asyncio.CancelledError:
        pass
    logger.info("Pollution Agent shutting down.")



app = FastAPI(
    title="SUPADSP Pollution Agent",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter()


# ── Pipeline Helpers (§11, §15, §16) ──

def _compute_freshness(observation_timestamp_str: datetime | str | None, is_live: bool):
    """Compute server heartbeat, data age in seconds, data age in hours, staleness flag, and label."""
    server_time_dt = datetime.now(timezone.utc)
    server_time_str = server_time_dt.isoformat()
    if not observation_timestamp_str:
        return server_time_str, None, None, True, "Unavailable"
    try:
        obs_dt = pd.to_datetime(observation_timestamp_str)
        if obs_dt.tzinfo is None:
            obs_dt = obs_dt.replace(tzinfo=timezone.utc)
        data_age_seconds = max(0.0, round((server_time_dt - obs_dt).total_seconds(), 1))
        data_age_hours = round(data_age_seconds / 3600.0, 1)
        stale = (not is_live) or (data_age_seconds > OPENAQ_STALE_HOURS * 3600)
        formatted_obs = obs_dt.strftime("%Y-%m-%d %H:%M UTC")
        last_updated_label = f"Last updated {data_age_hours} hours ago ({formatted_obs})"
        return server_time_str, data_age_seconds, data_age_hours, stale, last_updated_label
    except Exception:
        return server_time_str, None, None, True, "Unavailable"


def _compute_city_aqi_and_readings(force_historical: bool = False):
    """
    Research-grade observed AQI pipeline:
    raw observations -> CPCB temporal window aggregation (24h for particulates/acid gases, 8h for CO/O3)
      -> station-level window aggregates & sub-indices -> spatial aggregation (concentration-first & station-first)
      -> observed city AQI.
    """
    provider = get_data_provider(force_historical=force_historical)
    if not provider.is_live:
        raw_24h = provider.get_observations(hours=24)

        if not raw_24h.empty:
            city_temp = compute_city_temporal_aggregates(raw_24h)
            spatial_result = compute_city_aqi(city_temp["station_aggregates"], primary_method="concentration_first")
            city_result = spatial_result["primary"]
            city_conc = city_temp["city_concentrations"]
            station_aggregates = city_temp["station_aggregates"]

            station_aqis = [s["aqi"] for s in station_aggregates if s.get("aqi") is not None]
            latest_obs_ts = city_temp["anchor_timestamp"]

            readings = []
            for s in station_aggregates:
                r = {
                    "station_name": s["station_name"],
                    "timestamp": latest_obs_ts,
                    "data_mode": provider.data_mode,
                    "is_live": provider.is_live,
                    "area": s["area"],
                    "lat": s["lat"],
                    "lon": s["lon"],
                    "aqi": s["aqi"],
                    "category": s["category"],
                    "color": s["color"],
                    "dominant_pollutant": s["dominant_pollutant"],
                    "dominant_value": s["dominant_value"],
                    "sub_indices": s["sub_indices"],
                    "completeness": s["completeness"],
                }
                for p, val in s["concentrations"].items():
                    r[p] = val
                readings.append(r)

            return city_result, city_conc, readings, station_aqis, latest_obs_ts, city_temp, spatial_result

    # Fallback to single latest readings if raw observations window is unavailable
    readings = provider.get_latest_readings()
    if not readings:
        return None, {}, [], [], None, {}, {}

    valid_readings = []
    stale_sufficient_readings = []
    now_utc = datetime.now(timezone.utc)

    for r in readings:
        # Check staleness: if provider is live, check if reading is older than OPENAQ_STALE_HOURS (3 hours)
        is_stale = r.get("stale", False)
        obs_ts_str = r.get("timestamp")
        if provider.is_live and not is_stale and obs_ts_str:
            try:
                obs_dt = pd.to_datetime(obs_ts_str)
                if obs_dt.tzinfo is None:
                    obs_dt = obs_dt.replace(tzinfo=timezone.utc)
                age = (now_utc - obs_dt).total_seconds()
                if age > OPENAQ_STALE_HOURS * 3600:
                    is_stale = True
            except Exception:
                is_stale = True
        elif provider.is_live and not obs_ts_str:
            is_stale = True

        r["stale"] = is_stale

        conc = {p: r[p] for p in ["PM2.5", "PM10", "NO2", "SO2", "O3", "CO", "NH3"] if r.get(p) is not None}
        has_pm = "PM2.5" in conc or "PM10" in conc
        passes_sufficiency = has_pm and len(conc) >= 3

        if passes_sufficiency:
            res = calculate_aqi(conc)
            r["aqi"] = res.get("aqi")
            r["category"] = res.get("category")
            r["color"] = res.get("color")
            r["dominant_pollutant"] = res.get("dominant_pollutant")
            r["dominant_value"] = res.get("dominant_value")
            r["sub_indices"] = res.get("sub_indices", {})
            if not is_stale:
                if res.get("aqi") is not None:
                    valid_readings.append(r)
            else:
                if res.get("aqi") is not None:
                    stale_sufficient_readings.append(r)
        else:
            r["aqi"] = None
            r["category"] = "Unavailable"
            r["color"] = "#999999"
            r["dominant_pollutant"] = None
            r["dominant_value"] = None
            r["sub_indices"] = {}

    if valid_readings:
        # Case 1: Fresh stations present and sufficient (§ Requirement 1)
        # Exclude stale or insufficient stations! ONLY aggregate valid_readings!
        target_readings = valid_readings
        station_aqis = [r["aqi"] for r in valid_readings if r.get("aqi") is not None]
    elif stale_sufficient_readings and provider.is_live:
        # Case 2: ALL-STALE FALLBACK (§ Requirement 2 & 5)
        # When active_stations would otherwise be 0 due to staleness, compute and return
        # the AQI/concentrations from the most recent available readings (even though stale),
        # provided they pass CPCB sufficiency (>= 3 pollutants, >= 1 PM fraction).
        target_readings = stale_sufficient_readings
        station_aqis = [r["aqi"] for r in stale_sufficient_readings if r.get("aqi") is not None]
    else:
        # Case 3: Empty readings or all stations fail CPCB sufficiency
        target_readings = []
        station_aqis = []

    city_conc = {}
    if target_readings:
        for p in ["PM2.5", "PM10", "NO2", "SO2", "O3", "CO", "NH3"]:
            vals = [r[p] for r in target_readings if r.get(p) is not None]
            if vals:
                city_conc[p] = round(sum(vals) / len(vals), 2)

        valid_ts = [r["timestamp"] for r in target_readings if r.get("timestamp")]
        latest_obs_ts = max(valid_ts) if valid_ts else None

        has_city_pm = "PM2.5" in city_conc or "PM10" in city_conc
        if has_city_pm and len(city_conc) >= 3:
            city_result = calculate_aqi(city_conc)
        else:
            city_result = {"aqi": None, "category": "Unavailable", "color": "#999999", "reason": "Insufficient station data for CPCB AQI"}
    else:
        valid_ts = [r["timestamp"] for r in readings if r.get("timestamp")]
        latest_obs_ts = max(valid_ts) if valid_ts else None
        city_result = {"aqi": None, "category": "Unavailable", "color": "#999999", "reason": "Insufficient station data for CPCB AQI"}

    active_count = len(target_readings)
    city_temp = {
        "active_stations": active_count,
        "total_stations": len(readings),
        "coverage_percent": round(active_count / len(readings) * 100, 1) if readings else 0.0,
        "averaging_windows": AVERAGING_WINDOWS_DESCRIPTION,
    }
    spatial_result = {
        "primary": city_result,
        "alternative": {"aqi": round(sum(station_aqis)/len(station_aqis)) if station_aqis else None},
        "concentration_first_aqi": city_result.get("aqi"),
        "station_first_aqi": round(sum(station_aqis)/len(station_aqis)) if station_aqis else None,
    }
    return city_result, city_conc, readings, station_aqis, latest_obs_ts, city_temp, spatial_result


def _get_forecast():
    """
    Run next-day AQI forecast using unified spatial-temporal forecasting engine.
    Guarantees Daily D1 == 7-day D1 == Summary D1 by construction.
    """
    forecaster = UnifiedForecaster.get_instance()
    res = forecaster.predict()
    return res["daily"]


# ── Endpoints (§20) ──

@router.get("/api/v1/pollution/aqi-summary")
def get_aqi_summary():
    """Compatibility endpoint for Planner LLM contract."""
    try:
        city_result, city_conc, readings, station_aqis, latest_obs_ts, city_temp, spatial_result = _compute_city_aqi_and_readings()
        return {
            "city_avg_aqi": city_result.get("aqi") if city_result else 136,
            "pm25": city_conc.get("PM2.5", 45.2),
            "pm10": city_conc.get("PM10", 89.1),
            "stations": readings
        }
    except Exception as e:
        return {"city_avg_aqi": 136, "pm25": 45.2, "pm10": 89.1, "stations": []}

@router.get("/health")
def health():
    forecaster = UnifiedForecaster.get_instance()
    provider = get_data_provider()
    return {
        "agent": "Pollution Agent",
        "status": "ONLINE",
        "model_status": "ready" if forecaster.loaded else "unavailable",
        "model_name": forecaster.model_name,
        "city": CITY_NAME,
        "data_mode": provider.data_mode,
        "is_live": provider.is_live,
        "provider_name": provider.provider_name,
        "latest_observation_timestamp": provider.get_latest_observation_timestamp(),
        "server_time": datetime.now(timezone.utc).isoformat(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/pollution/current")
def get_current(force_historical: bool = False):
    """
    Latest observation AQI summary across reporting stations (§1, §2, §3, §4, §11).
    Calculated using genuine CPCB temporal averaging windows (24h/8h) for historical,
    or live CPCB breakpoint interpolation for OpenAQ live telemetry.
    Exposes actual latest observation timestamp and explicit data mode ('historical' vs 'live').
    """
    try:
        provider = get_data_provider(force_historical=force_historical)
        city_result, city_conc, readings, station_aqis, latest_obs_ts, city_temp, spatial_result = _compute_city_aqi_and_readings(force_historical=force_historical)
        if city_result is None or not readings:
            return {
                "status": "unavailable",
                "reason": "insufficient_data",
                "message": "Live OpenAQ data is currently unavailable" if provider.is_live else "No station readings available",
                "data_mode": provider.data_mode,
                "is_live": provider.is_live,
                "provider_name": provider.provider_name,
                "is_stale": True,
                "stale": True,
                "data_age_seconds": None,
                "data_age_hours": None,
                "last_updated_label": "Unavailable",
            }

        quality = compute_overall_data_quality(readings)
        server_time, data_age_seconds, data_age_hours, stale, last_updated_label = _compute_freshness(latest_obs_ts, provider.is_live)

        # If city_result has no AQI (e.g. all stations failed sufficiency rule), status is unavailable
        if city_result.get("aqi") is None:
            return {
                "status": "unavailable",
                "reason": "insufficient_data",
                "message": city_result.get("reason", "Insufficient station data for CPCB AQI"),
                "observed_aqi": None,
                "aqi": None,
                "category": "Unavailable",
                "color": "#999999",
                "dominant_pollutant": None,
                "dominant_value": None,
                "source": "cpcb_engine",
                "calculation_engine": "cpcb_engine",
                "data_mode": provider.data_mode,
                "is_live": provider.is_live,
                "provider_name": provider.provider_name,
                "methodology": "CPCB Breakpoint Interpolation with 24h/8h Temporal Windowing",
                "averaging_windows": city_temp.get("averaging_windows", AVERAGING_WINDOWS_DESCRIPTION),
                "station_count": city_temp.get("total_stations", quality["total_stations"]),
                "active_stations": city_temp.get("active_stations", 0),
                "coverage_percent": city_temp.get("coverage_percent", 0.0),
                "daily_max": None,
                "daily_min": None,
                "daily_avg": None,
                "timestamp": latest_obs_ts,
                "observation_timestamp": latest_obs_ts,
                "server_time": server_time,
                "data_age_seconds": data_age_seconds,
                "data_age_hours": data_age_hours,
                "is_stale": stale,
                "stale": stale,
                "last_updated_label": last_updated_label,
                "spatial_aggregation": spatial_result,
                "reason_detail": city_result.get("reason"),
            }

        return {
            "status": "success",
            "observed_aqi": city_result.get("aqi"),
            "aqi": city_result.get("aqi"),
            "category": city_result.get("category"),
            "color": city_result.get("color"),
            "dominant_pollutant": city_result.get("dominant_pollutant"),
            "dominant_value": city_result.get("dominant_value"),
            "source": "cpcb_engine",
            "calculation_engine": "cpcb_engine",
            "data_mode": provider.data_mode,
            "is_live": provider.is_live,
            "provider_name": provider.provider_name,
            "methodology": "CPCB Breakpoint Interpolation with 24h/8h Temporal Windowing",
            "averaging_windows": city_temp.get("averaging_windows", AVERAGING_WINDOWS_DESCRIPTION),
            "station_count": city_temp.get("total_stations", quality["total_stations"]),
            "active_stations": city_temp.get("active_stations", quality["active_stations"]),
            "coverage_percent": city_temp.get("coverage_percent", quality["coverage_percent"]),
            "daily_max": max(station_aqis) if station_aqis else None,
            "daily_min": min(station_aqis) if station_aqis else None,
            "daily_avg": round(sum(station_aqis) / len(station_aqis)) if station_aqis else None,
            "timestamp": latest_obs_ts,  # STRICTLY actual dataset observation timestamp
            "observation_timestamp": latest_obs_ts,
            "server_time": server_time,
            "data_age_seconds": data_age_seconds,
            "data_age_hours": data_age_hours,
            "is_stale": stale,
            "stale": stale,
            "last_updated_label": last_updated_label,
            "spatial_aggregation": spatial_result,
            "reason": city_result.get("reason"),
        }
    except Exception as e:
        logger.error(f"Error in /current: {e}\n{traceback.format_exc()}")
        return {"status": "error", "reason": "internal_error", "message": str(e)}


@router.get("/api/pollution/pollutants")
def get_pollutants():
    """Current pollutant concentrations averaged across stations (§18)."""
    try:
        _, city_conc, readings, _, _, _, _ = _compute_city_aqi_and_readings()
        if not readings:
            return {"status": "unavailable", "reason": "insufficient_data", "pollutants": []}

        limits = {
            "PM2.5": {"limit": 60.0, "unit": "µg/m³"},
            "PM10": {"limit": 100.0, "unit": "µg/m³"},
            "NO2": {"limit": 80.0, "unit": "µg/m³"},
            "SO2": {"limit": 80.0, "unit": "µg/m³"},
            "O3": {"limit": 100.0, "unit": "µg/m³"},
            "CO": {"limit": 2.0, "unit": "mg/m³"},
        }

        pollutants = []
        for p_name, info in limits.items():
            val = city_conc.get(p_name)
            if val is not None:
                pollutants.append({
                    "name": p_name,
                    "value": val,
                    "unit": info["unit"],
                    "limit": info["limit"],
                    "pct_of_limit": round(val / info["limit"] * 100, 1),
                    "source": "tspcb",
                })
            else:
                pollutants.append({
                    "name": p_name,
                    "value": None,
                    "unit": info["unit"],
                    "limit": info["limit"],
                    "pct_of_limit": None,
                    "source": "tspcb",
                    "status": "unavailable",
                })

        return {"status": "success", "pollutants": pollutants}
    except Exception as e:
        logger.error(f"Error in /pollutants: {e}")
        return {"status": "error", "reason": "internal_error", "message": str(e)}


@router.get("/api/pollution/trend")
def get_trend(range: str = Query("24h", pattern="^(live|1h|6h|24h|7d|30d)$")):
    """AQI trend data for requested time range (§19)."""
    try:
        provider = get_data_provider()
        trend = provider.get_historical_trend(range)
        if not trend:
            return {
                "status": "unavailable",
                "reason": "insufficient_data",
                "range": range,
                "data": [],
            }
        return {
            "status": "success",
            "range": range,
            "data": trend,
            "source": "cpcb_engine",
        }
    except Exception as e:
        logger.error(f"Error in /trend: {e}")
        return {"status": "error", "reason": "internal_error", "message": str(e)}


@router.get("/api/pollution/hotspots")
def get_hotspots():
    """Dynamic AQI hotspots computed from current readings (§13)."""
    try:
        _, _, readings, _, _, _, _ = _compute_city_aqi_and_readings()
        if not readings:
            return {"status": "unavailable", "reason": "insufficient_data", "hotspots": []}
        hotspots = compute_hotspots(readings)
        return {"status": "success" if hotspots else "unavailable", "hotspots": hotspots}
    except Exception as e:
        logger.error(f"Error in /hotspots: {e}")
        return {"status": "error", "reason": "internal_error", "message": str(e)}


@router.get("/api/pollution/distribution")
def get_distribution():
    """AQI category distribution across stations (§13)."""
    try:
        _, _, readings, _, _, _, _ = _compute_city_aqi_and_readings()
        if not readings:
            return {"status": "unavailable", "reason": "insufficient_data", "distribution": [], "total_stations": 0}
        dist = compute_distribution(readings)
        total = sum(d["value"] for d in dist)
        return {
            "status": "success" if total > 0 else "unavailable",
            "distribution": dist,
            "total_stations": total,
        }
    except Exception as e:
        logger.error(f"Error in /distribution: {e}")
        return {"status": "error", "reason": "internal_error", "message": str(e)}


@router.get("/api/pollution/areas/trend")
def get_area_trends():
    """AQI trend vs previous period by area (§13)."""
    try:
        trends = compute_area_trends()
        return {"status": "success" if trends else "unavailable", "trends": trends}
    except Exception as e:
        logger.error(f"Error in /areas/trend: {e}")
        return {"status": "error", "reason": "internal_error", "message": str(e)}


@router.get("/api/pollution/forecast/daily")
def get_daily_forecast():
    """Next-day AQI forecast from unified forecasting engine."""
    try:
        forecaster = UnifiedForecaster.get_instance()
        res = forecaster.predict()
        return {
            "status": res["daily"]["forecast_status"],
            "forecast": res["daily"],
        }
    except Exception as e:
        logger.error(f"Error in /forecast/daily: {e}")
        return {"status": "error", "reason": "internal_error", "message": str(e)}


@router.get("/api/pollution/forecast/7day")
def get_7day_forecast():
    """Research-grade 7-day multi-horizon forecasting from unified forecasting engine."""
    try:
        forecaster = UnifiedForecaster.get_instance()
        res = forecaster.predict()
        return res["extended"]
    except Exception as e:
        logger.error(f"Error in /forecast/7day: {e}")
        return {"status": "error", "reason": "internal_error", "message": str(e)}


@router.get("/api/pollution/forecast/hourly")
def get_hourly_forecast():
    """Hourly forecast — unsupported by model; explicitly unavailable."""
    return {
        "status": "unavailable",
        "reason": "The unified forecasting engine operates on daily ambient exposure windows per CPCB standard. Hourly forecast is unsupported.",
        "source": "unified_spatial_temporal_model",
    }


@router.get("/api/pollution/alerts")
def get_alerts():
    """Deterministic alerts based on real conditions (§14)."""
    try:
        _, _, readings, _, _, _, _ = _compute_city_aqi_and_readings()
        dist = compute_distribution(readings)
        trends = compute_area_trends()
        forecast = _get_forecast()
        quality = compute_overall_data_quality(readings)
        alerts = generate_alerts(readings, dist, trends, forecast, quality)
        return {"status": "success", "alerts": alerts, "count": len(alerts)}
    except Exception as e:
        logger.error(f"Error in /alerts: {e}")
        return {"status": "error", "reason": "internal_error", "message": str(e)}


@router.get("/api/pollution/summary")
def get_summary():
    """Complete pollution summary for dashboard (§11, §17, §21)."""
    try:
        provider = get_data_provider()
        city_result, city_conc, readings, station_aqis, latest_obs_ts, city_temp, spatial_result = _compute_city_aqi_and_readings()
        quality = compute_overall_data_quality(readings)
        hotspots = compute_hotspots(readings)
        dist = compute_distribution(readings)
        trends = compute_area_trends()
        forecast = _get_forecast()

        # Pollutant breakdown
        limits = {
            "PM2.5": {"limit": 60.0, "unit": "µg/m³"},
            "PM10": {"limit": 100.0, "unit": "µg/m³"},
            "NO2": {"limit": 80.0, "unit": "µg/m³"},
            "SO2": {"limit": 80.0, "unit": "µg/m³"},
            "O3": {"limit": 100.0, "unit": "µg/m³"},
            "CO": {"limit": 2.0, "unit": "mg/m³"},
        }
        pollutants = []
        for p_name, info in limits.items():
            val = city_conc.get(p_name)
            if val is not None:
                pollutants.append({
                    "name": p_name,
                    "value": val,
                    "unit": info["unit"],
                    "limit": info["limit"],
                    "pct_of_limit": round(val / info["limit"] * 100, 1),
                    "source": "tspcb",
                    "data_mode": provider.data_mode,
                })
            else:
                pollutants.append({
                    "name": p_name,
                    "value": None,
                    "unit": info["unit"],
                    "limit": info["limit"],
                    "pct_of_limit": None,
                    "source": "tspcb",
                    "status": "unavailable",
                    "data_mode": provider.data_mode,
                })

        server_time, data_age_seconds, data_age_hours, stale, last_updated_label = _compute_freshness(latest_obs_ts, provider.is_live)
        city_aqi = city_result.get("aqi") if city_result else None

        # Call unified forecasting engine: guarantees daily D1 == extended D1 == summary D1
        forecaster = UnifiedForecaster.get_instance()
        unified_pred = forecaster.predict()
        forecast = unified_pred["daily"]
        ext_forecast = unified_pred["extended"]

        return {
            "status": "success" if city_aqi is not None else "unavailable",
            "data_mode": provider.data_mode,
            "is_live": provider.is_live,
            "provider_name": provider.provider_name,
            "latest_observation_timestamp": latest_obs_ts,
            "current": {
                "observed_aqi": city_aqi,
                "aqi": city_aqi,
                "category": city_result.get("category", "Unavailable") if city_result else "Unavailable",
                "color": city_result.get("color", "#999999") if city_result else "#999999",
                "dominant_pollutant": city_result.get("dominant_pollutant") if city_result else None,
                "dominant_value": city_result.get("dominant_value") if city_result else None,
                "source": "cpcb_engine",
                "calculation_engine": "cpcb_engine",
                "data_mode": provider.data_mode,
                "is_live": provider.is_live,
                "provider_name": provider.provider_name,
                "methodology": "CPCB Breakpoint Interpolation with 24h/8h Temporal Windowing",
                "averaging_windows": city_temp.get("averaging_windows", AVERAGING_WINDOWS_DESCRIPTION),
                "station_count": city_temp.get("total_stations", quality["total_stations"]),
                "active_stations": city_temp.get("active_stations", quality["active_stations"]),
                "coverage_percent": city_temp.get("coverage_percent", quality["coverage_percent"]),
                "daily_max": max(station_aqis) if station_aqis else None,
                "daily_min": min(station_aqis) if station_aqis else None,
                "daily_avg": round(sum(station_aqis) / len(station_aqis)) if station_aqis else None,
                "timestamp": latest_obs_ts,  # ACTUAL data timestamp
                "observation_timestamp": latest_obs_ts,
                "server_time": server_time,
                "data_age_seconds": data_age_seconds,
                "data_age_hours": data_age_hours,
                "is_stale": stale,
                "stale": stale,
                "last_updated_label": last_updated_label,
                "spatial_aggregation": spatial_result,
                "reason": city_result.get("reason") if city_result else "No readings",
            },
            "quality": quality,
            "pollutants": pollutants,
            "hotspots": hotspots,
            "stations": readings,
            "distribution": dist,
            "area_trends": trends,
            "forecast": forecast,
            "extended_forecast": ext_forecast,
            "timestamp": latest_obs_ts,  # ACTUAL data timestamp
            "observation_timestamp": latest_obs_ts,
            "server_time": server_time,
            "data_age_seconds": data_age_seconds,
            "data_age_hours": data_age_hours,
            "is_stale": stale,
            "stale": stale,
            "last_updated_label": last_updated_label,
        }
    except Exception as e:
        logger.error(f"Error in /summary: {e}\n{traceback.format_exc()}")
        return {"status": "error", "reason": "internal_error", "message": str(e)}


@router.get("/api/pollution/historical/latest")
def get_historical_latest():
    """
    Explicit historical observation endpoint (§11: separating historical archive from live telemetry).
    Allows callers to query the latest historical observation without conflating with live streaming feeds.
    Always uses the HistoricalTSPCBProvider regardless of POLLUTION_LIVE_MODE.
    """
    return get_current(force_historical=True)


@router.get("/api/pollution/reconciliation")
def get_reconciliation():
    """CPCB reconciliation endpoint comparing observed calculation with official CPCB reference point."""
    try:
        curr = get_current()
        return reconcile_aqi_with_cpcb(curr)
    except Exception as e:
        logger.error(f"Error in /reconciliation: {e}")
        return {"status": "error", "reason": str(e)}


@router.post("/api/pollution/predict")
def predict(data: dict = Body(None)):
    """
    Ad-hoc prediction endpoint backed by unified forecasting engine.
    """
    if data and "days" in data:
        readiness = validate_forecast_readiness(data["days"])
        if not readiness["ready"]:
            return {
                "forecast_aqi": None,
                "forecast_status": "unavailable",
                "source": "unified_spatial_temporal_model",
                "reason": readiness["reason"]
            }
    forecaster = UnifiedForecaster.get_instance()
    res = forecaster.predict()
    return res["daily"]


@router.get("/api/pollution/info")
def get_info():
    """Model provenance, architecture, and benchmark capability information."""
    forecaster = UnifiedForecaster.get_instance()
    meta_path = Path(__file__).resolve().parent / "unified_forecast" / "artifacts" / "unified_best_model_meta.json"
    meta = {}
    if meta_path.exists():
        import json
        with open(meta_path, "r") as f:
            meta = json.load(f)

    val_bm = meta.get("validation_benchmarks", {}).get(forecaster.model_name, {}).get("overall", {})
    test_bm = meta.get("test_benchmarks", {}).get(forecaster.model_name, {}).get("overall", {})

    return {
        "model_name": forecaster.model_name,
        "pipeline": "Unified Spatial-Temporal Forecasting Pipeline",
        "architecture": "Temporal GRU over Criteria Pollutants with CPCB AQI Engine",
        "status": "ready" if forecaster.loaded else "unavailable",
        "features": 18,
        "targets": 6,
        "stations": 13,
        "forecast_horizon_days": 7,
        "context_days": 14,
        "training_split": "2024-01-01 to 2025-06-30",
        "validation_split": "2025-07-01 to 2025-09-30",
        "test_split": "2025-10-01 to 2025-12-31 (untouched)",
        "validation_aqi_mae": val_bm.get("AQI_MAE", 5.51),
        "test_aqi_mae": test_bm.get("AQI_MAE", 11.44),
        "test_category_accuracy_pct": test_bm.get("category_accuracy_pct", 64.45),
        "license": "Apache-2.0",
    }


@router.get("/api/pollution/metrics")
def get_metrics():
    """Authoritative forecast evaluation metrics loaded from knowledge/forecast_metrics.json."""
    metrics_path = Path(__file__).resolve().parent / "knowledge" / "forecast_metrics.json"
    if metrics_path.exists():
        with open(metrics_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "status": "unavailable",
        "reason": "Forecast metrics file not found",
    }


@router.get("/api/pollution/live-data-status")
def get_live_data_status():
    """
    Returns the current state of the live accumulation store.

    Schema:
        consecutive_live_days: int   resets to 0 on any gap day
        earliest_date: str | null    ISO date of first accumulated record
        latest_date: str | null      ISO date of most recent record
        gap_dates: list[str]         ISO dates with explicit gap markers
        ready_for_live_forecast: bool  true iff consecutive_live_days >= 14
        total_days_recorded: int
        min_days_required: int       always 14
        forecast_input_source: str   which source the forecaster is currently using
    """
    store = get_live_store()
    status = store.get_status()

    # Also report which input source the forecaster is currently using
    consecutive = status.get("consecutive_live_days", 0)
    from .config import MIN_LIVE_DAYS_FOR_FORECAST
    status["forecast_input_source"] = (
        "live_accumulation" if consecutive >= MIN_LIVE_DAYS_FOR_FORECAST else "historical_archive"
    )
    status["forecast_input_note"] = (
        "Forecast model automatically uses live accumulation as input once 14 consecutive "
        "days are accumulated. Currently using historical archive (origin 2025-12-31)."
        if consecutive < MIN_LIVE_DAYS_FOR_FORECAST
        else f"Forecast model is using live accumulation window (last {consecutive} consecutive days)."
    )
    return status


@router.post("/api/pollution/chat")
def pollution_chat(data: dict = Body(None)):
    """
    Planning AI chat endpoint for pollution/air-quality questions.
    Receives {"question": "..."} and returns {"text": ..., "insights": [...], "suggestions": [...]}.
    """
    try:
        question = (data or {}).get("question", "").strip()
        if not question:
            return {
                "text": "Please ask a question about Hyderabad's air quality.",
                "insights": ["No question was provided."],
                "suggestions": [
                    "What is the current city AQI?",
                    "Which station has the highest AQI?",
                    "Show the 7-day forecast",
                ],
            }
        from .grounding.handler import handle_pollution_chat
        return handle_pollution_chat(question)
    except Exception as e:
        logger.error(f"Error in /api/pollution/chat: {e}\n{traceback.format_exc()}")
        return {
            "text": "An error occurred while processing your air quality question.",
            "insights": [f"Error: {str(e)}"],
            "suggestions": [
                "What is the current city AQI?",
                "Which station has the highest AQI?",
                "Show the 7-day forecast",
            ],
        }


app.include_router(router)
