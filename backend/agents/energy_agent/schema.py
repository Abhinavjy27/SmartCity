"""
Pydantic Schemas for the SUPADSP Real-Time Energy Agent.
Maintains contract compliance with SUPADSP planner, supervisor, and frontend views.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SubstationStatus(str, Enum):
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SeverityLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SubstationData(BaseModel):
    id: str = Field(..., description="Unique substation identifier, e.g. SUB_01")
    name: str = Field(..., description="Substation name with voltage tier, e.g. Madhapur 220kV")
    capacity_mw: float = Field(..., description="Rated transformer capacity in MW")
    current_load_mw: float = Field(..., description="Real-time measured load in MW")
    load_pct: float = Field(..., description="Current load as a percentage of capacity")
    status: str = Field(..., description="Operational status: CRITICAL, HIGH, or NORMAL")
    voltage_kv: int = Field(default=132, description="Operating voltage tier (33, 132, 220, 400 kV)")
    zone: str = Field(default="Hyderabad Central", description="Urban planning zone or municipality")
    latitude: Optional[float] = Field(default=None, description="Substation geographic latitude")
    longitude: Optional[float] = Field(default=None, description="Substation geographic longitude")
    feeder_lines: Optional[int] = Field(default=6, description="Number of active downstream feeder lines")
    peak_load_pct: Optional[float] = Field(default=None, description="24h peak load percentage")


class HourlyLoadItem(BaseModel):
    h: str = Field(..., description="Hour label in 24h format, e.g. '00:00'")
    load: float = Field(..., description="Aggregate grid load percentage or MW")
    capacity: float = Field(default=92.0, description="Nominal grid safety capacity ceiling percentage")
    solar_generation_mw: Optional[float] = Field(default=0.0, description="Solar power contribution in MW")
    ev_load_mw: Optional[float] = Field(default=0.0, description="EV charging load component in MW")


class ZoneConsumption(BaseModel):
    zone: str = Field(..., description="Zone / Corridor name, e.g. HITECH City")
    consumption: float = Field(..., description="Daily total consumption in MWh or MW")
    peak: float = Field(..., description="Peak load percentage observed")
    color: str = Field(default="#00f0ff", description="UI visualization hex color")
    active_substations: Optional[int] = Field(default=3, description="Number of substations in zone")


class EnergyRecommendation(BaseModel):
    title: str = Field(..., description="Concise recommendation title")
    impact: str = Field(..., description="Estimated percentage reduction or MW saved")
    priority: str = Field(default="MEDIUM", description="Urgency priority: CRITICAL, HIGH, MEDIUM, LOW")
    category: Optional[str] = Field(default="LOAD_SHEDDING", description="Intervention category")
    target_zone: Optional[str] = Field(default=None, description="Target municipality zone")
    estimated_savings_mw: Optional[float] = Field(default=None, description="Estimated power savings in MW")


class GridStatusResponse(BaseModel):
    source: str = Field(default="Live Energy Agent API", description="Data source indicator")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp of telemetry snapshot")
    location: Optional[str] = Field(default="Hyderabad Central", description="Filtered location/corridor name")
    current_load_mw: float = Field(..., description="Current total grid load in Megawatts (MW)")
    capacity_mw: float = Field(..., description="Total nominal grid capacity in Megawatts (MW)")
    load_pct: float = Field(..., description="Overall grid load percentage")
    solar_generation_mw: float = Field(default=0.0, description="Real-time renewable solar generation in MW")
    total_consumption_mwh: float = Field(..., description="Cumulative daily energy consumption in MWh")
    efficiency_score_pct: float = Field(default=87.2, description="Grid transmission and load efficiency %")
    substations: List[SubstationData] = Field(default_factory=list, description="List of monitored substations")
    hourly_load: List[HourlyLoadItem] = Field(default_factory=list, description="24-hour diurnal load forecast/profile")
    zone_data: List[ZoneConsumption] = Field(default_factory=list, description="Zone-wise consumption breakdown")
    recommendations: List[EnergyRecommendation] = Field(default_factory=list, description="AI mitigation recommendations")
    severity: str = Field(default="MODERATE", description="Contract severity: CRITICAL, HIGH, or MODERATE")
    weather_impact_mw: Optional[float] = Field(default=0.0, description="HVAC/weather-induced load offset in MW")
    ev_traffic_impact_mw: Optional[float] = Field(default=0.0, description="EV charging load component in MW")


class EnergyAnalyzeRequest(BaseModel):
    location: Optional[str] = Field(default="Financial District Substation", description="Target location or substation")
    scenario: Optional[str] = Field(default="peak_load_dimming", description="Analysis scenario")
    inputs: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Arbitrary simulation or input metrics")
    ambient_temp_c: Optional[float] = Field(default=None, description="Ambient weather temperature in Celsius")
    traffic_occupancy_pct: Optional[float] = Field(default=None, description="Traffic sensor occupancy / congestion %")
    ev_count: Optional[int] = Field(default=None, description="Estimated active EV fleet count")


class EnergyAnalyzeResponse(BaseModel):
    status: str = Field(default="COMPLETED", description="Analysis status")
    domain: str = Field(default="energy", description="Domain name")
    location: str = Field(..., description="Analyzed location or substation")
    current_load_mw: float = Field(..., description="Current baseline load in MW")
    load_pct: float = Field(..., description="Current load percentage")
    severity: str = Field(..., description="Calculated severity level")
    projected_savings_mw: float = Field(default=6.4, description="Projected MW savings with optimization")
    grid_stability_index: float = Field(default=0.96, description="Grid stability index between 0.0 and 1.0")
    confidence: float = Field(default=0.95, description="Model prediction confidence score")
    recommendations: List[EnergyRecommendation] = Field(default_factory=list)


class PeakShavingRequest(BaseModel):
    zone: Optional[str] = Field(default="HITECH City", description="Target zone for peak shaving")
    target_reduction_mw: Optional[float] = Field(default=25.0, description="Target reduction in MW")
    target_substations: Optional[List[str]] = Field(default_factory=list, description="Specific substation IDs")


class PeakShavingResponse(BaseModel):
    status: str = Field(default="OPTIMIZED", description="Optimization status")
    zone: str = Field(..., description="Optimized zone")
    original_load_mw: float = Field(..., description="Initial load before intervention")
    target_load_mw: float = Field(..., description="Target load after intervention")
    curtailed_mw: float = Field(..., description="Load curtailed via demand response")
    bess_discharge_mw: float = Field(..., description="Battery storage discharge contribution")
    solar_offset_mw: float = Field(..., description="Solar microgrid offset contribution")
    actions: List[str] = Field(default_factory=list, description="Dispatched grid control actions")
