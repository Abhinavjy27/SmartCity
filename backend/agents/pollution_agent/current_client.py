"""
Open-Meteo Current Air Quality Client.
Fetches real-time / current modelled atmospheric air quality data from Open-Meteo API.

Note: Open-Meteo provides modelled atmospheric air-quality data based on numerical weather
prediction and aerosol transport models, not physical ground monitoring-station sensors.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

OPEN_METEO_AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# Canonical Hyderabad coordinates
HYDERABAD_COORDINATES: Tuple[float, float] = (17.3850, 78.4867)

# Known supported location coordinates (complete coverage of Hyderabad metropolitan localities)
LOCATION_COORDINATES: Dict[str, Tuple[float, float]] = {
    "hyderabad": (17.3850, 78.4867),
    "narayanguda": (17.3978, 78.4907),
    "tarnaka": (17.4290, 78.5320),
    "nacharam": (17.4320, 78.5600),
    "madhapur": (17.4480, 78.3912),
    "gachibowli": (17.4401, 78.3489),
    "hitec city": (17.4435, 78.3772),
    "hitech city": (17.4435, 78.3772),
    "secunderabad": (17.4399, 78.4983),
    "begumpet": (17.4448, 78.4664),
    "jubilee hills": (17.4318, 78.4073),
    "banjara hills": (17.4239, 78.4238),
    "charminar": (17.3616, 78.4747),
    "sanathnagar": (17.4589, 78.4428),
    "bollaram": (17.5510, 78.3580),
    "patancheru": (17.5284, 78.2676),
    "uppal": (17.4022, 78.5600),
    "kukatpally": (17.4849, 78.4138),
    "miyapur": (17.4968, 78.3614),
    "ameerpet": (17.4375, 78.4482),
    "dilsukhnagar": (17.3688, 78.5247),
    "lb nagar": (17.3457, 78.5522),
    "shamshabad": (17.2403, 78.4294),
    "malakpet": (17.3736, 78.4983),
    "kondapur": (17.4608, 78.3647),
    "mehdipatnam": (17.3916, 78.4414),
    "alwal": (17.5023, 78.5134),
    "lingampally": (17.4870, 78.3180),
}


class PollutionCurrentAPIError(Exception):
    """Raised when fetching current air quality from the Open-Meteo API fails."""
    pass


class PollutionLocationNotSupportedError(PollutionCurrentAPIError):
    """Raised when the requested location cannot be mapped to coordinates."""
    pass


class OpenMeteoCurrentClient:
    """Client for fetching current air quality from the Open-Meteo Air Quality API."""

    def __init__(
        self,
        base_url: str = OPEN_METEO_AIR_QUALITY_URL,
        timeout_seconds: float = 5.0,
    ):
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def resolve_coordinates(location: str) -> Tuple[float, float, str]:
        """
        Resolve geographic coordinates (latitude, longitude) for the given location string.
        Defaults to Hyderabad for Narayanguda or Hyderabad queries.
        """
        loc_clean = (location or "").strip().lower()
        if not loc_clean:
            return HYDERABAD_COORDINATES[0], HYDERABAD_COORDINATES[1], "Hyderabad"

        # Check LocationResolver first for canonical Hyderabad localities and aliases
        try:
            from backend.agents.traffic_agent.location_resolver import LocationResolver
            loc_res = LocationResolver.resolve(explicit_location=location, query_text=location)
            if loc_res:
                return loc_res.lat, loc_res.lon, f"{loc_res.name}, Hyderabad" if "hyderabad" not in loc_res.name.lower() else loc_res.name
        except Exception:
            pass

        # Match specific locality keys first (excluding generic 'hyderabad')
        specific_keys = [k for k in LOCATION_COORDINATES.keys() if k != "hyderabad"]
        for key in sorted(specific_keys, key=len, reverse=True):
            if re.search(r"\b" + re.escape(key) + r"\b", loc_clean):
                coords = LOCATION_COORDINATES[key]
                canonical_name = key.title()
                return coords[0], coords[1], f"{canonical_name}, Hyderabad"

        if "hyderabad" in loc_clean or "telangana" in loc_clean:
            return HYDERABAD_COORDINATES[0], HYDERABAD_COORDINATES[1], "Hyderabad"

        raise PollutionLocationNotSupportedError(
            f"Location '{location}' is not currently configured for current air quality coordinates. "
            f"Supported locations include Narayanguda, Tarnaka, Nacharam, Madhapur, Gachibowli, Secunderabad, and greater Hyderabad."
        )

    def fetch_current_pollution(self, location: str) -> Dict[str, Any]:
        """
        Fetch current atmospheric air quality from Open-Meteo API.
        
        Returns structured dictionary conforming to specialist agent standards.
        Never fabricates values or falls back silently to historical data.
        """
        lat, lon, resolved_loc = self.resolve_coordinates(location)

        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "us_aqi,pm2_5,pm10,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
            "timezone": "Asia/Kolkata",
        }

        retrieved_at = datetime.now(timezone.utc).isoformat()

        logger.info(
            f"[OpenMeteoCurrentClient] Fetching current AQI for '{resolved_loc}' "
            f"(lat={lat}, lon={lon}) from {self.base_url}"
        )

        try:
            resp = requests.get(self.base_url, params=params, timeout=self.timeout_seconds)
        except requests.exceptions.Timeout as exc:
            msg = f"Current air-quality data is temporarily unavailable: Connection to Open-Meteo timed out after {self.timeout_seconds}s."
            logger.error(f"[OpenMeteoCurrentClient] {msg} ({exc})")
            raise PollutionCurrentAPIError(msg) from exc
        except requests.exceptions.ConnectionError as exc:
            msg = "Current air-quality data is temporarily unavailable: Could not establish connection to Open-Meteo API."
            logger.error(f"[OpenMeteoCurrentClient] {msg} ({exc})")
            raise PollutionCurrentAPIError(msg) from exc
        except requests.exceptions.RequestException as exc:
            msg = f"Current air-quality data is temporarily unavailable: HTTP request error ({str(exc)})."
            logger.error(f"[OpenMeteoCurrentClient] {msg}")
            raise PollutionCurrentAPIError(msg) from exc

        if resp.status_code != 200:
            msg = f"Current air-quality data is temporarily unavailable: Open-Meteo returned HTTP {resp.status_code}: {resp.text}"
            logger.error(f"[OpenMeteoCurrentClient] {msg}")
            raise PollutionCurrentAPIError(msg)

        try:
            payload = resp.json()
        except Exception as exc:
            msg = "Current air-quality data is temporarily unavailable: Failed to decode Open-Meteo JSON response."
            logger.error(f"[OpenMeteoCurrentClient] {msg} ({exc})")
            raise PollutionCurrentAPIError(msg) from exc

        current = payload.get("current")
        if not isinstance(current, dict):
            msg = "Current air-quality data is temporarily unavailable: Missing 'current' block in Open-Meteo response."
            logger.error(f"[OpenMeteoCurrentClient] {msg}")
            raise PollutionCurrentAPIError(msg)

        # Parse required variables
        raw_aqi = current.get("us_aqi")
        raw_pm25 = current.get("pm2_5")
        raw_pm10 = current.get("pm10")
        raw_time = current.get("time")

        if raw_aqi is None or raw_pm25 is None or raw_pm10 is None:
            msg = "Current air-quality data is temporarily unavailable: Open-Meteo response is missing AQI, PM2.5, or PM10 measurements."
            logger.error(f"[OpenMeteoCurrentClient] {msg}")
            raise PollutionCurrentAPIError(msg)

        try:
            aqi_val = int(round(float(raw_aqi)))
            pm25_val = round(float(raw_pm25), 1)
            pm10_val = round(float(raw_pm10), 1)
        except (ValueError, TypeError) as exc:
            msg = "Current air-quality data is temporarily unavailable: Non-numeric AQI or particulate values in response."
            logger.error(f"[OpenMeteoCurrentClient] {msg} ({exc})")
            raise PollutionCurrentAPIError(msg) from exc

        # Optional auxiliary pollutants
        def _safe_float(key: str) -> Optional[float]:
            val = current.get(key)
            if val is not None:
                try:
                    return round(float(val), 2)
                except (ValueError, TypeError):
                    return None
            return None

        pollutants = {
            "carbon_monoxide": _safe_float("carbon_monoxide"),
            "nitrogen_dioxide": _safe_float("nitrogen_dioxide"),
            "sulphur_dioxide": _safe_float("sulphur_dioxide"),
            "ozone": _safe_float("ozone"),
        }

        # Determine category based on US AQI standards
        if aqi_val <= 50:
            category = "Good"
        elif aqi_val <= 100:
            category = "Moderate"
        elif aqi_val <= 150:
            category = "Unhealthy for Sensitive Groups"
        elif aqi_val <= 200:
            category = "Unhealthy"
        elif aqi_val <= 300:
            category = "Very Unhealthy"
        else:
            category = "Hazardous"

        return {
            "data_mode": "current",
            "data_source": "open-meteo-air-quality-current",
            "source_type": "modelled",
            "source_provider": "open-meteo",
            "modality": "modelled_atmospheric_estimate",
            "freshness": "live_model_output",
            "data_timestamp": str(raw_time) if raw_time else retrieved_at,
            "retrieved_at": retrieved_at,
            "location": resolved_loc,
            "latitude": lat,
            "longitude": lon,
            "city_avg_aqi": aqi_val,
            "pm25": pm25_val,
            "pm10": pm10_val,
            "category": category,
            "stations": [],  # Open-Meteo is numerical atmospheric modelling, not physical ground monitoring stations
            "is_modelled": True,
            "pollutants": pollutants,
            "units": {
                "aqi": "US AQI",
                "pm25": "µg/m³",
                "pm10": "µg/m³",
                "carbon_monoxide": "µg/m³",
                "nitrogen_dioxide": "µg/m³",
                "sulphur_dioxide": "µg/m³",
                "ozone": "µg/m³"
            },
        }
