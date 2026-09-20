"""
Pydantic Schemas and Contracts for the SUMO Simulation Agent.
Defines machine-validatable intervention specifications, scenario requests,
and empirical simulation evidence models.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator

from backend.agents.traffic_agent.schemas import (
    CorridorMetric,
    SimulationMetadata,
    SimulationMetrics,
    SourceInfo,
)


class InterventionType(str, Enum):
    SIGNAL_TIMING = "signal_timing"
    ADAPTIVE_SIGNAL_CONTROL = "adaptive_signal_control"
    REROUTING = "rerouting"
    TRAFFIC_DIVERSION = "traffic_diversion"
    LANE_USE_CHANGES = "lane_use_changes"
    TURN_RESTRICTIONS = "turn_restrictions"
    ROAD_CLOSURE = "road_closure"
    TRAFFIC_DEMAND_MANAGEMENT = "traffic_demand_management"
    INCIDENT_RESPONSE = "incident_response"
    COMBINED_STRATEGY = "combined_strategy"


class SignalTimingParameters(BaseModel):
    target_corridor: Optional[str] = Field(default=None, description="Corridor name or directional token (e.g. Westbound)")
    target_intersection: Optional[str] = Field(default=None, description="Empirical SUMO traffic light ID")
    phase_index: Optional[int] = Field(default=None, description="Specific traffic light phase to modify")
    green_time_adjustment_sec: float = Field(default=15.0, description="Delta seconds to adjust green phase duration")
    cycle_duration_sec: Optional[float] = Field(default=None, description="Total cycle duration override if applicable")


class ReroutingParameters(BaseModel):
    target_corridor: Optional[str] = Field(default=None, description="Target corridor (e.g. Westbound, Northbound, Southbound, Eastbound)")
    diversion_fraction: float = Field(default=0.15, description="Fraction of eligible vehicles to divert. Defensive bound: 0.0 < fraction <= 0.50")
    reroute_mode: str = Field(default="alternative_route", description="Rerouting mode: 'alternative_route' or 'travel_time_balanced'")
    alternative_arterial: Optional[str] = Field(default=None, description="Optional descriptive alternative arterial label")
    alternative_route: Optional[List[str]] = Field(default=None, description="Optional explicit sequence of edge IDs")

    @model_validator(mode="after")
    def validate_bounds(self) -> "ReroutingParameters":
        import math
        val = self.diversion_fraction
        if val is None or not isinstance(val, (int, float)):
            raise ValueError(f"diversion_fraction must be a numeric value. Received: {val}")
        if math.isnan(val) or math.isinf(val):
            raise ValueError("diversion_fraction must be a finite real number")
        if val <= 0.0 or val > 0.50:
            raise ValueError(
                f"diversion_fraction must be strictly greater than 0.0 and less than or equal to 0.50. "
                f"Received: {val}"
            )
        if self.reroute_mode not in ("alternative_route", "travel_time_balanced"):
            raise ValueError(
                f"Unsupported reroute_mode '{self.reroute_mode}'. Supported modes: 'alternative_route', 'travel_time_balanced'"
            )
        return self


class InterventionPayload(BaseModel):
    type: InterventionType = Field(default=InterventionType.SIGNAL_TIMING, description="Category of intervention")
    target: Optional[str] = Field(default="Westbound", description="Target corridor, junction, or roadway segment")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Detailed domain parameters for intervention")

    @model_validator(mode="before")
    @classmethod
    def normalize_intervention(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Normalize string types if provided as string
            t = data.get("type")
            if isinstance(t, str):
                t_clean = t.strip().lower()
                for member in InterventionType:
                    if member.value == t_clean:
                        data["type"] = member
                        break
        return data

    @model_validator(mode="after")
    def validate_payload_parameters(self) -> "InterventionPayload":
        if self.type in (InterventionType.REROUTING, InterventionType.TRAFFIC_DIVERSION):
            # If parameters are supplied, run defensive validation
            if self.parameters:
                params_to_check = dict(self.parameters)
                params_to_check.setdefault("target_corridor", self.target)
                ReroutingParameters(**params_to_check)
        return self


class BaselineReference(BaseModel):
    """
    Structured baseline reference containing essential metrics for comparison
    without duplicating massive telemetry arrays or hourly series.
    """
    scenario_name: str = Field(default="synthetic_normal", description="Baseline demand scenario profile")
    seed: int = Field(default=42, description="Baseline RNG seed")
    duration_seconds: int = Field(default=120, description="Baseline duration in seconds")
    average_speed_kmh: Optional[float] = Field(default=None, description="Baseline network average speed in km/h")
    average_delay_sec: Optional[float] = Field(default=None, description="Baseline average vehicle delay in seconds")
    average_waiting_time_sec: Optional[float] = Field(default=None, description="Baseline average waiting time in seconds")
    congestion_index: Optional[float] = Field(default=None, description="Baseline congestion index")
    throughput: Optional[int] = Field(default=0, description="Baseline completed trips")
    corridors: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Baseline corridor metrics list")
    corridor_speeds: Optional[Dict[str, float]] = Field(default_factory=dict, description="Baseline corridor speeds map")


class SimulationScenarioRequest(BaseModel):
    scenario_id: Optional[str] = Field(default=None, description="Deterministic scenario identifier (e.g. signal_timing:Westbound:adj+19.0s:seed42)")
    scenario_name: str = Field(default="synthetic_normal", description="Demand profile scenario")
    location: str = Field(default="Narayanguda, Hyderabad", description="Target urban locality")
    target_location: Optional[str] = None
    duration_seconds: int = Field(default=120, description="Simulation duration in seconds")
    duration_steps: Optional[int] = Field(default=None, description="Legacy step parameter (alias for duration_seconds)")
    seed: int = Field(default=42, description="RNG seed for deterministic vehicle demand generation")
    intervention: Optional[InterventionPayload] = Field(default=None, description="Structured candidate intervention")
    candidate_intervention: Optional[str] = Field(default=None, description="Freeform text or shorthand intervention name")
    signal_optimization: Optional[bool] = Field(default=None, description="Legacy boolean flag for signal optimization")
    baseline_metrics: Optional[Dict[str, Any]] = Field(default=None, description="Baseline traffic metrics for comparison")
    baseline_reference: Optional[Dict[str, Any]] = Field(default=None, description="Structured canonical baseline reference")

    @model_validator(mode="before")
    @classmethod
    def sync_legacy_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if data.get("target_location") and not data.get("location"):
                data["location"] = data["target_location"]
            if data.get("duration_steps") and not data.get("duration_seconds"):
                data["duration_seconds"] = int(data["duration_steps"])
            # If candidate_intervention given as string without intervention payload
            if not data.get("intervention") and data.get("candidate_intervention"):
                data["intervention"] = {
                    "type": "signal_timing",
                    "target": data.get("candidate_intervention"),
                    "parameters": {},
                }
            elif not data.get("intervention") and data.get("signal_optimization"):
                data["intervention"] = {
                    "type": "signal_timing",
                    "target": "Westbound",
                    "parameters": {"green_time_adjustment_sec": 15.0},
                }
        return data


class SimulationEvidenceResponse(BaseModel):
    scenario_id: Optional[str] = Field(default=None, description="Deterministic scenario identifier")
    scenario: str
    location: str
    status: str = "COMPLETED"
    intervention_applied: Optional[Dict[str, Any]] = None
    execution: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Execution telemetry including requested vs actual diversion, rerouted vehicle count, and bypassed edges"
    )
    metrics: SimulationMetrics
    corridors: List[CorridorMetric] = Field(default_factory=list)
    source: SourceInfo
    comparison: Optional[Dict[str, Any]] = None
    metadata: Optional[SimulationMetadata] = None
    corridor_trade_offs: Optional[List[str]] = Field(default_factory=list, description="Descriptions of corridors that experienced speed degradation")
    trade_off_summary: Optional[str] = Field(default=None, description="Summary narrative of corridor and network trade-offs")

    # Horizon, Seed & Network preservation
    duration_seconds: Optional[int] = Field(default=None, description="Simulation duration in seconds")
    seed: Optional[int] = Field(default=None, description="Random seed used in simulation")
    network_name: Optional[str] = Field(default=None, description="Network file name")
    baseline_reference: Optional[Dict[str, Any]] = Field(default=None, description="Canonical baseline reference used for comparison")
    baseline_metrics: Optional[Dict[str, Any]] = Field(default=None, description="Canonical baseline summary metrics")

    # Top-level backward compatibility fields for dashboard and tests
    average_speed_kmh: Optional[float] = None
    average_delay_sec: Optional[float] = None
    average_waiting_time_sec: Optional[float] = None
    congestion_index: Optional[float] = None
    throughput: Optional[int] = None
    total_vehicles: Optional[int] = None
    teleported_vehicles: Optional[int] = None
    max_halting_vehicles: Optional[int] = None
    arrived_vehicles: Optional[int] = None
    active_at_end: Optional[int] = None
    completed_trips_avg_waiting_time_sec: Optional[float] = None
    completed_trips_avg_delay_sec: Optional[float] = None
    completed_trips_avg_duration_sec: Optional[float] = None

