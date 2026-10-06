from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class PollutionAnalyzeRequest(BaseModel):
    objective: str = Field(..., description="The planning objective or analytical question.")
    location: str = Field(..., description="The target urban location or corridor.")
    data_mode: Optional[Literal["current", "historical", "auto"]] = Field(
        default="historical",
        description="Whether to fetch current modelled atmospheric air quality or analyze the historical CSV dataset.",
    )


class PollutionIntervention(BaseModel):
    action_type: str
    description: str
    expected_impact_pct: float
    feasibility_score: float


class PollutionAnalyzeResponse(BaseModel):
    city_avg_aqi: int
    pm25: float
    pm10: float
    stations: List[str] = Field(default_factory=list)
    suggested_interventions: List[PollutionIntervention] = Field(default_factory=list)
    data_mode: str = Field(default="historical", description="'current' or 'historical'")
    data_source: str = Field(
        default="open-meteo-air-quality-historical",
        description="Identifies the dataset or API endpoint source.",
    )
    data_timestamp: Optional[str] = Field(default=None, description="Timestamp of the observation/model.")
    retrieved_at: Optional[str] = Field(default=None, description="ISO timestamp when telemetry was retrieved.")
    category: Optional[str] = Field(default=None, description="Air quality health category (e.g. Moderate).")
    is_modelled: bool = Field(
        default=True,
        description="True indicates numerical atmospheric model data, not physical ground monitoring stations.",
    )
    pollutants: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Auxiliary chemical concentrations (CO, NO2, SO2, O3) if available.",
    )
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    location: Optional[str] = Field(default=None)
