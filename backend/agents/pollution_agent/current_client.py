"""
Open-Meteo Current Air Quality Client.
Fetches real-time / current modelled atmospheric air quality data from Open-Meteo API.

Note: Open-Meteo provides modelled atmospheric air-quality data based on numerical weather
prediction and aerosol transport models, not physical ground monitoring-station sensors.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

OPEN_METEO_AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# Canonical Hyderabad / Narayanguda coordinates
HYDERABAD_COORDINATES: Tuple[float, float] = (17.3850, 78.4867)

# Known supported location coordinates (extensible)
LOCATION_COORDINATES: Dict[str, Tuple[float, float]] = {
    "hyderabad": (17.3850, 78.4867),
    "narayanguda": (17.3850, 78.4867),
    "narayanguda, hyderabad": (17.3850, 78.4867),
    "gachibowli": (17.4401, 78.3489),
    "gachibowli, hyderabad": (17.4401, 78.3489),
    "hitech city": (17.4435, 78.3772),
    "secunderabad": (17.4399, 78.4983),
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

        for key, coords in LOCATION_COORDINATES.items():
            if key in loc_clean:
                return coords[0], coords[1], location.strip()

        if "hyderabad" in loc_clean or "telangana" in loc_clean:
            return HYDERABAD_COORDINATES[0], HYDERABAD_COORDINATES[1], location.strip()

        raise PollutionLocationNotSupportedError(
            f"Location '{location}' is not currently configured for current air quality coordinates. "
            f"Supported locations include Hyderabad, Narayanguda, Gachibowli, Hitech City, and Secunderabad."
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
            "data_timestamp": str(raw_time) if raw_time else retrieved_at,
            "retrieved_at": retrieved_at,
            "location": resolved_loc,
            "latitude": lat,
            "longitude": lon,
            "city_avg_aqi": aqi_val,
            "pm25": pm25_val,
            "pm10": pm10_val,
            "category": category,
            "stations": [],  # Open-Meteo is numerical atmospheric modelling, not physical stations
            "is_modelled": True,
            "pollutants": pollutants,
        }
