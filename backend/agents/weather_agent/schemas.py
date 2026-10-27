"""
Pydantic schemas and contracts for the SUPADSP Weather Agent.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WeatherCurrentResponse(BaseModel):
    source: str = Field(..., description="Data provider source description")
    provider: str = Field(..., description="Name of the weather provider")
    is_live: bool = Field(..., description="Whether telemetry is real-time live or fallback")
    timestamp: str = Field(..., description="ISO UTC timestamp of retrieval")
    city: str = Field("Hyderabad", description="Queried city or locality name")
    latitude: Optional[float] = Field(None, description="Resolved latitude")
    longitude: Optional[float] = Field(None, description="Resolved longitude")
    temperature_c: float = Field(..., description="Current ambient temperature in Celsius")
    humidity_pct: int = Field(..., description="Relative humidity percentage")
    wind_speed_kmh: float = Field(..., description="Wind speed in km/h")
    wind_direction: str = Field(..., description="Cardinal wind direction (e.g. WSW, NE)")
    precipitation_mm: float = Field(0.0, description="Precipitation accumulation in mm")
    condition: str = Field(..., description="Text description of weather condition")
    icon: str = Field("Sun", description="Lucide icon identifier for UI rendering")
    feels_like_c: float = Field(..., description="Apparent temperature in Celsius")
    dew_point_c: Optional[float] = Field(None, description="Dew point in Celsius")
    pressure_hpa: float = Field(1012.0, description="Surface atmospheric pressure in hPa")
    uv_index: Optional[float] = Field(None, description="UV Index rating")
    visibility_km: Optional[float] = Field(10.0, description="Visibility in kilometers")
    forecast_7d: List[Dict[str, Any]] = Field(default_factory=list)
    hourly_temp: List[Dict[str, Any]] = Field(default_factory=list)
    weekly_precipitation: List[Dict[str, Any]] = Field(default_factory=list)
    correlations: List[Dict[str, Any]] = Field(default_factory=list)


class WeatherForecastDay(BaseModel):
    day: str
    date: str
    high: int
    low: int
    condition: str
    rain: str
    icon: str
    avg_humidity: Optional[int] = None
    max_wind_kmh: Optional[float] = None
    precipitation_mm: Optional[float] = 0.0


class WeatherForecastResponse(BaseModel):
    source: str
    provider: str
    is_live: bool
    timestamp: str
    city: str
    forecast_7d: List[WeatherForecastDay]
    hourly: List[Dict[str, Any]]


class WeatherAlertItem(BaseModel):
    title: str
    desc: str
    time: str
    color: str
    severity: str = "MODERATE"


class WeatherAlertsResponse(BaseModel):
    source: str
    timestamp: str
    alerts: List[WeatherAlertItem]
    risk_level: str
    primary_risk: str
    probability_pct: int
    time_window: str


class WeatherAnalyzeRequest(BaseModel):
    location: Optional[str] = "Hyderabad"
    objective: Optional[str] = None
    include_forecast: Optional[bool] = True


class WeatherAnalyzeResponse(BaseModel):
    location: str
    timestamp: str
    weather: WeatherCurrentResponse
    cross_domain_impacts: Dict[str, Any]
    recommendations: List[str]
