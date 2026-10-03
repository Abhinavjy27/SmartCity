"""
Data provider abstraction for pollution data.
Current implementation: CSV files from datasets/raw/pollution/ (TSPCB stations).
MongoDB provider can be swapped in without changing the interface.
No external API is hardcoded — that decision is made by the team later.
"""
from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional
import glob
import logging

from .config import DATASETS_DIR, MIN_DAILY_READINGS
from .data_quality import VALID_RANGES

logger = logging.getLogger(__name__)


class BasePollutionDataProvider(ABC):
    """
    Abstract base provider for pollution observations.
    Cleanly separates historical archive providers from future live streaming providers (§9, §11).
    """

    @property
    @abstractmethod
    def data_mode(self) -> str:
        """Return data mode: 'historical' or 'live'."""
        pass

    @property
    @abstractmethod
    def is_live(self) -> bool:
        """Return True if connected to live real-time telemetry, False if static/historical."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier."""
        pass

    @abstractmethod
    def get_station_names(self) -> list:
        """Return list of available station names."""
        pass

    @abstractmethod
    def get_latest_readings(self) -> list:
        """Get the latest observation reading per station."""
        pass

    @abstractmethod
    def get_observations(
        self,
        station_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        hours: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Query raw 15-minute observations.
        Preserves raw observations and exact timestamps without downsampling or overwriting.
        """
        pass

    @abstractmethod
    def get_latest_observation_timestamp(self) -> Optional[str]:
        """Return the latest actual observation timestamp across all stations."""
        pass

    @abstractmethod
    def get_daily_aggregates(self, n_days: int = 30) -> pd.DataFrame:
        """Aggregate observations to station-level daily values."""
        pass

    @abstractmethod
    def get_city_daily_aggregates(self, n_days: int = 30, min_completeness_ratio: float = 0.5) -> pd.DataFrame:
        """Aggregate observations directly at the city-wide calendar-day level."""
        pass

    @abstractmethod
    def get_historical_trend(self, range_key: str = "24h") -> list:
        """Return trend data points for historical analysis."""
        pass



# Exact normalized prefix mapping — NEVER use substring matching!
# Disambiguates NO vs NO2 vs NOx strictly by exact prefix lookup.
EXACT_PREFIX_MAP = {
    "pm2.5": "PM2.5",
    "pm10": "PM10",
    "no": "NO",
    "no2": "NO2",
    "nox": "NOx",
    "nh3": "NH3",
    "so2": "SO2",
    "co": "CO",
    "ozone": "O3",
    "o3": "O3",
    "benzene": "Benzene",
    "toluene": "Toluene",
    "xylene": "Xylene",
}

# Official TSPCB column names -> internal model feature names
TSPCB_COLUMN_MAP = {
    "PM2.5 (µg/m³)": "PM2.5",
    "PM10 (µg/m³)": "PM10",
    "NO (µg/m³)": "NO",
    "NO2 (µg/m³)": "NO2",
    "NOx (ppb)": "NOx",
    "NH3 (µg/m³)": "NH3",
    "CO (mg/m³)": "CO",
    "SO2 (µg/m³)": "SO2",
    "Ozone (µg/m³)": "O3",
    "Benzene (µg/m³)": "Benzene",
    "Toluene (µg/m³)": "Toluene",
    "Xylene (µg/m³)": "Xylene",
}

POLLUTANT_FEATURES = [
    "PM2.5", "PM10", "NO", "NO2", "NOx", "NH3",
    "CO", "SO2", "O3", "Benzene", "Toluene", "Xylene",
]

# Station metadata — coordinates & areas for Hyderabad TSPCB stations
# Normalized to support both canonical and filename-derived station names
STATION_METADATA = {
    "Bollaram Industrial": {"lat": 17.5380, "lon": 78.3459, "area": "Bollaram"},
    "Bollaram Industrial Area": {"lat": 17.5380, "lon": 78.3459, "area": "Bollaram"},
    "Central University": {"lat": 17.4618, "lon": 78.3340, "area": "Gachibowli"},
    "ECIL Kapra": {"lat": 17.4719, "lon": 78.5707, "area": "Kapra"},
    "Ecil Kapra": {"lat": 17.4719, "lon": 78.5707, "area": "Kapra"},
    "ICRISAT Patancheru": {"lat": 17.4529, "lon": 78.2756, "area": "Patancheru"},
    "Icrisat Patancheru": {"lat": 17.4529, "lon": 78.2756, "area": "Patancheru"},
    "IDA Pashamylaram": {"lat": 17.5335, "lon": 78.2082, "area": "Pashamylaram"},
    "Ida Pashamylaram": {"lat": 17.5335, "lon": 78.2082, "area": "Pashamylaram"},
    "Kokapet": {"lat": 17.4083, "lon": 78.3508, "area": "Kokapet"},
    "Kompally Municipal": {"lat": 17.5433, "lon": 78.4889, "area": "Kompally"},
    "Kompally Municipal Office": {"lat": 17.5433, "lon": 78.4889, "area": "Kompally"},
    "Nacharam TSIIC": {"lat": 17.4282, "lon": 78.5522, "area": "Nacharam"},
    "Nacharam_Tsiic Iala": {"lat": 17.4282, "lon": 78.5522, "area": "Nacharam"},
    "New Malakpet": {"lat": 17.3645, "lon": 78.4983, "area": "Malakpet"},
    "Ramachandrapuram": {"lat": 17.4449, "lon": 78.2711, "area": "Ramachandrapuram"},
    "Sanathnagar": {"lat": 17.4509, "lon": 78.4483, "area": "Sanathnagar"},
    "Somajiguda": {"lat": 17.4235, "lon": 78.4650, "area": "Somajiguda"},
    "Zoo Park": {"lat": 17.3508, "lon": 78.4527, "area": "Zoo Park"},
}


class HistoricalTSPCBProvider(BasePollutionDataProvider):
    """
    Reads static TSPCB station CSV files from datasets/raw/pollution/ (2024-2025 archive).
    Exposes data mode as 'historical' with is_live=False (§4, §9, §11).
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or DATASETS_DIR
        self._data_cache = None
        self._cache_time = None

    @property
    def data_mode(self) -> str:
        return "historical"

    @property
    def is_live(self) -> bool:
        return False

    @property
    def provider_name(self) -> str:
        return "TSPCB Static CSV Archive (2024-2025)"

    def _load_all_stations(self) -> pd.DataFrame:
        """Load and normalize all station CSVs into a single DataFrame."""
        if self._data_cache is not None and self._cache_time:
            age = (datetime.now(timezone.utc) - self._cache_time).total_seconds()
            if age < 3600:  # 1 hour cache
                return self._data_cache

        csv_files = glob.glob(str(self.data_dir / "hyd-*-tspcb-2024-25.csv"))
        if not csv_files:
            csv_files = glob.glob(str(self.data_dir / "*.csv"))

        if not csv_files:
            logger.warning(f"No CSV files found in {self.data_dir}")
            return pd.DataFrame()

        frames = []
        for fp in csv_files:
            try:
                df = pd.read_csv(fp, on_bad_lines="skip", low_memory=False)
                stem = Path(fp).stem
                station = stem.replace("hyd-", "").replace("-tspcb-2024-25", "").replace("-", " ").title()
                df["station_name"] = station
                frames.append(df)
            except Exception as e:
                logger.warning(f"Failed to read {fp}: {e}")

        if not frames:
            return pd.DataFrame()

        combined = pd.concat(frames, ignore_index=True)

        # Parse timestamp with timezone-aware UTC handling
        if "Timestamp" in combined.columns:
            combined["timestamp"] = pd.to_datetime(combined["Timestamp"], errors="coerce", utc=True)
        elif "To Date" in combined.columns:
            combined["timestamp"] = pd.to_datetime(combined["To Date"], errors="coerce", utc=True)

        # Deterministic column resolution: exact prefix match before '('
        # Guarantees NO, NO2, and NOx are never confused.
        rename_map = {}
        for col in combined.columns:
            prefix = col.split("(")[0].strip().lower()
            if prefix in EXACT_PREFIX_MAP:
                rename_map[col] = EXACT_PREFIX_MAP[prefix]

        combined.rename(columns=rename_map, inplace=True)

        # Filter invalid readings BEFORE aggregation (§4)
        # NaN, inf, non-numeric, negative values, and out-of-range values are rejected.
        for feat in POLLUTANT_FEATURES:
            if feat in combined.columns:
                s = pd.to_numeric(combined[feat], errors="coerce")
                lo, hi = VALID_RANGES.get(feat, (0, 10000))
                # Set invalid to NaN so it never leaks into daily aggregates
                combined[feat] = s.where((s >= lo) & (s <= hi) & np.isfinite(s), np.nan)

        combined.dropna(subset=["timestamp"], inplace=True)
        combined.sort_values("timestamp", inplace=True)

        combined["date"] = combined["timestamp"].dt.date

        self._data_cache = combined
        self._cache_time = datetime.now(timezone.utc)
        return combined

    def get_station_names(self) -> list:
        """Return list of available station names."""
        df = self._load_all_stations()
        if df.empty:
            return []
        return sorted(df["station_name"].unique().tolist())

    def get_latest_observation_timestamp(self) -> Optional[str]:
        """Return the latest actual observation timestamp across all stations in the dataset."""
        df = self._load_all_stations()
        if df.empty or "timestamp" not in df.columns:
            return None
        max_ts = df["timestamp"].max()
        return max_ts.isoformat() if pd.notna(max_ts) else None

    def get_observations(
        self,
        station_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        hours: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Query raw 15-minute observations. Filter by station, time range, or last N hours
        relative to the latest observation in the dataset.
        Preserves raw observations and timestamps without overwrite or silent imputation.
        """
        df = self._load_all_stations()
        if df.empty:
            return pd.DataFrame()

        filtered = df.copy()
        if station_name:
            filtered = filtered[filtered["station_name"] == station_name]

        if hours is not None and hours > 0:
            anchor = end_time if end_time is not None else filtered["timestamp"].max()
            if pd.isna(anchor):
                return pd.DataFrame()
            start_window = anchor - timedelta(hours=hours)
            filtered = filtered[(filtered["timestamp"] >= start_window) & (filtered["timestamp"] <= anchor)]
        else:
            if start_time is not None:
                filtered = filtered[filtered["timestamp"] >= start_time]
            if end_time is not None:
                filtered = filtered[filtered["timestamp"] <= end_time]

        return filtered.sort_values("timestamp").reset_index(drop=True)

    def get_latest_readings(self) -> list:
        """Get the most recent reading per station with explicit data_mode and observation timestamp."""
        df = self._load_all_stations()
        if df.empty:
            return []

        results = []
        for station, sdf in df.groupby("station_name"):
            latest = sdf.iloc[-1]
            reading = {
                "station_name": station,
                "timestamp": latest["timestamp"].isoformat() if pd.notna(latest["timestamp"]) else None,
                "data_mode": self.data_mode,
                "is_live": self.is_live,
                "area": STATION_METADATA.get(station, {}).get("area", station),
                "lat": STATION_METADATA.get(station, {}).get("lat"),
                "lon": STATION_METADATA.get(station, {}).get("lon"),
            }
            for feat in POLLUTANT_FEATURES:
                val = latest.get(feat)
                reading[feat] = float(val) if pd.notna(val) else None
            results.append(reading)
        return results

    def get_daily_aggregates(self, n_days: int = 30) -> pd.DataFrame:
        """
        Aggregate 15-minute TSPCB data to station-level daily values.

        Temporal Representation (§1, §8):
        - All 12 pollutant features represent the 24-hour daily arithmetic mean of valid observations,
          matching the verified training representation of city_day.csv (including CO and O3).
        - Direct arithmetic mean over calendar day; no hourly double-averaging.

        Station Daily Completeness Rule (§3):
        - Nominal expected readings per station per day = 96 (every 15 minutes).
        - A day is valid for a pollutant only if valid_count >= MIN_DAILY_READINGS (48, 50% threshold).
        - If below threshold, daily value is set to NaN (no median or zero imputation).
        """
        df = self._load_all_stations()
        if df.empty:
            return pd.DataFrame()

        max_date = df["date"].max()
        min_date = max_date - timedelta(days=n_days)
        filtered = df[df["date"] >= min_date].copy()

        if filtered.empty:
            return pd.DataFrame()

        # Group by station and date
        grouped = filtered.groupby(["station_name", "date"])

        rows = []
        for (station, dt), group in grouped:
            total_readings = len(group)
            day_row = {
                "station_name": station,
                "date": dt,
                "reading_count": total_readings,
                "expected_count": 96,
                "completeness": {},
            }

            for feat in POLLUTANT_FEATURES:
                if feat in group.columns:
                    valid_series = group[feat].dropna()
                    valid_count = len(valid_series)
                    comp_ratio = valid_count / 96.0
                    is_complete = valid_count >= MIN_DAILY_READINGS

                    day_row["completeness"][feat] = {
                        "valid_count": int(valid_count),
                        "expected_count": 96,
                        "completeness_ratio": round(comp_ratio, 4),
                        "is_complete": bool(is_complete),
                    }

                    if is_complete:
                        day_row[feat] = float(valid_series.mean())
                    else:
                        day_row[feat] = np.nan
                else:
                    day_row["completeness"][feat] = {
                        "valid_count": 0,
                        "expected_count": 96,
                        "completeness_ratio": 0.0,
                        "is_complete": False,
                    }
                    day_row[feat] = np.nan

            rows.append(day_row)

        daily_df = pd.DataFrame(rows)
        return daily_df

    def get_city_daily_aggregates(self, n_days: int = 30, min_completeness_ratio: float = 0.5) -> pd.DataFrame:
        """
        Aggregate 15-minute TSPCB observations DIRECTLY at the city-wide calendar-day level.

        Production Daily Aggregation (§1):
        - Aggregates valid TSPCB observations directly at the calendar-day level.
        - Does NOT average hourly means (avoids artificial weighting distortion).
        - daily_mean = arithmetic mean of all valid observations for that pollutant on that calendar day.

        Validation Before Aggregation (§2):
        - Numeric conversion, NaN rejected, negative values rejected, out-of-range/sentinel values rejected.
        - Valid zero accepted.
        - Valid observation counts calculated strictly AFTER validation.

        Daily Completeness Calculation (§3):
        - valid observation count per pollutant per day
        - expected observation count = active_stations * 96 nominal readings/day
        - completeness ratio = valid_count / expected_count
        - If valid_count < MIN_DAILY_READINGS (48) or completeness_ratio < min_completeness_ratio,
          pollutant is marked as np.nan (unavailable). No median or zero imputation.

        CO and O3 Representation (§8):
        - CO and O3 represent daily arithmetic means of valid observations (empirically reconciled
          and verified against Rohan Rao city_day.csv across all 26 cities and 5.5 years).
        """
        df = self._load_all_stations()
        if df.empty:
            return pd.DataFrame()

        max_date = df["date"].max()
        min_date = max_date - timedelta(days=n_days)
        filtered = df[df["date"] >= min_date].copy()

        if filtered.empty:
            return pd.DataFrame()

        # Calendar-day grouping directly across the city
        grouped = filtered.groupby("date")

        rows = []
        for dt, group in grouped:
            active_stations = group["station_name"].nunique()
            expected_total = active_stations * 96 if active_stations > 0 else 96

            day_row = {
                "date": dt,
                "active_stations": active_stations,
                "expected_readings": expected_total,
                "reading_count": len(group),
                "completeness": {},
            }

            for feat in POLLUTANT_FEATURES:
                if feat in group.columns:
                    valid_series = group[feat].dropna()
                    valid_count = len(valid_series)
                    comp_ratio = valid_count / expected_total if expected_total > 0 else 0.0

                    is_complete = (valid_count >= MIN_DAILY_READINGS) and (comp_ratio >= min_completeness_ratio)

                    day_row["completeness"][feat] = {
                        "valid_count": int(valid_count),
                        "expected_count": int(expected_total),
                        "completeness_ratio": round(comp_ratio, 4),
                        "is_complete": bool(is_complete),
                    }

                    if is_complete:
                        # Direct daily arithmetic mean of valid observations across the calendar day
                        day_row[feat] = float(valid_series.mean())
                    else:
                        day_row[feat] = np.nan
                else:
                    day_row["completeness"][feat] = {
                        "valid_count": 0,
                        "expected_count": int(expected_total),
                        "completeness_ratio": 0.0,
                        "is_complete": False,
                    }
                    day_row[feat] = np.nan

            rows.append(day_row)

        city_daily_df = pd.DataFrame(rows)
        return city_daily_df

    def get_historical_trend(self, range_key: str = "24h") -> list:
        """Get historical AQI trend for a given time range."""
        from .aqi_engine import calculate_aqi

        df = self._load_all_stations()
        if df.empty:
            return []

        range_map = {
            "live": timedelta(hours=1),
            "1h": timedelta(hours=1),
            "6h": timedelta(hours=6),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
        }
        delta = range_map.get(range_key, timedelta(hours=24))

        max_ts = df["timestamp"].max()
        min_ts = max_ts - delta
        filtered = df[df["timestamp"] >= min_ts].copy()

        if filtered.empty:
            return []

        if range_key in ("live", "1h"):
            freq = "15min"
        elif range_key == "6h":
            freq = "30min"
        elif range_key == "24h":
            freq = "1h"
        elif range_key == "7d":
            freq = "6h"
        else:
            freq = "1D"

        filtered = filtered.set_index("timestamp")
        pollutant_cols = [c for c in POLLUTANT_FEATURES if c in filtered.columns]
        resampled = filtered[pollutant_cols].resample(freq).mean()

        trend = []
        for ts, row in resampled.iterrows():
            conc = {p: float(row[p]) for p in pollutant_cols if pd.notna(row.get(p))}
            if conc:
                result = calculate_aqi(conc)
                if result.get("aqi") is not None:
                    trend.append({
                        "time": ts.strftime("%I:%M %p") if delta <= timedelta(hours=24) else ts.strftime("%b %d"),
                        "timestamp": ts.isoformat(),
                        "aqi": result["aqi"],
                        "category": result["category"],
                        "pm25": round(conc.get("PM2.5", 0), 1) if conc.get("PM2.5") is not None else None,
                        "source": "cpcb_engine",
                    })
        return trend


# Backward compatibility alias
TSPCBDataProvider = HistoricalTSPCBProvider


class PlaceholderLivePollutionProvider(BasePollutionDataProvider):
    """
    Placeholder integration boundary for the future team-approved live TSPCB/CPCB telemetry provider.

    IMPORTANT ARCHITECTURAL RULE:
    Until the project team approves and supplies a live TSPCB/CPCB data source, the system must
    not claim to provide live/current telemetry. The placeholder provider exists only as an integration
    boundary. Once the approved provider is supplied, it must provide real observations without requiring
    changes to downstream AQI, forecasting, or frontend logic.
    """

    @property
    def data_mode(self) -> str:
        return "live"

    @property
    def is_live(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return "Approved Live Pollution Telemetry (Pending Team Approval)"

    def get_station_names(self) -> list:
        return []

    def get_latest_readings(self) -> list:
        return []

    def get_observations(
        self,
        station_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        hours: Optional[int] = None,
    ) -> pd.DataFrame:
        return pd.DataFrame()

    def get_latest_observation_timestamp(self) -> Optional[str]:
        return None

    def get_daily_aggregates(self, n_days: int = 30) -> pd.DataFrame:
        return pd.DataFrame()

    def get_city_daily_aggregates(self, n_days: int = 30, min_completeness_ratio: float = 0.5) -> pd.DataFrame:
        return pd.DataFrame()

    def get_historical_trend(self, range_key: str = "24h") -> list:
        return []


# Singleton data provider (§9: pluggable provider abstraction)
_provider: Optional[BasePollutionDataProvider] = None


_historical_provider: Optional[BasePollutionDataProvider] = None

def get_data_provider(force_historical: bool = False) -> BasePollutionDataProvider:
    """
    Return the active pollution data provider.
    When a custom provider is injected via set_data_provider(), return it (unless it is live and force_historical is requested).
    When POLLUTION_LIVE_MODE=True and no custom provider was injected:
      - returns OpenAQLiveProvider for regular/live calls
      - returns HistoricalTSPCBProvider when force_historical=True
    Otherwise returns HistoricalTSPCBProvider.
    """
    global _provider, _historical_provider
    if _provider is not None:
        if force_historical and getattr(_provider, "is_live", False):
            if _historical_provider is None:
                _historical_provider = HistoricalTSPCBProvider()
            return _historical_provider
        return _provider

    if force_historical:
        if _historical_provider is None:
            _historical_provider = HistoricalTSPCBProvider()
        return _historical_provider

    from .config import POLLUTION_LIVE_MODE
    if POLLUTION_LIVE_MODE:
        from .live_provider import OpenAQLiveProvider
        _provider = OpenAQLiveProvider()
    else:
        if _historical_provider is None:
            _historical_provider = HistoricalTSPCBProvider()
        _provider = _historical_provider
    return _provider


def set_data_provider(provider: BasePollutionDataProvider) -> None:
    """
    Allow runtime injection of an alternate provider (§9).
    Enables future live TSPCB/CPCB streaming providers to be plugged in without changing downstream consumers.
    """
    global _provider
    _provider = provider
    try:
        from .unified_forecast.inference import UnifiedForecaster
        forecaster = UnifiedForecaster.get_instance()
        forecaster.clear_cache()
    except Exception:
        pass


def reset_data_provider() -> None:
    """Reset provider singleton to default HistoricalTSPCBProvider."""
    global _provider
    _provider = None
    try:
        from .unified_forecast.inference import UnifiedForecaster
        forecaster = UnifiedForecaster.get_instance()
        forecaster.clear_cache()
    except Exception:
        pass
