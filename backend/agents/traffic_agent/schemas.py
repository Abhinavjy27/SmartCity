"""
Pydantic Schemas and Contracts for the SUMO-based Traffic Agent.
Strictly encapsulates simulation boundaries, synthetic demand profiles, and structured evidence.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TrafficScenario(str, Enum):
    SYNTHETIC_NORMAL = "synthetic_normal"
    SYNTHETIC_PEAK_NORTHBOUND = "synthetic_peak_northbound"
    SYNTHETIC_PEAK_SOUTHBOUND = "synthetic_peak_southbound"
    SYNTHETIC_PEAK_EASTBOUND = "synthetic_peak_eastbound"
    SYNTHETIC_PEAK_WESTBOUND = "synthetic_peak_westbound"
    CUSTOM_DEMAND = "custom_demand"


class SourceInfo(BaseModel):
    type: str = "simulation"
    engine: str = "SUMO"
    synthetic: bool = True
    network: str = "narayanguda_network.net.xml"
    sumo_version: str = "1.27.1"
    disclaimer: str = (
        "Synthetic traffic demand executed in Eclipse SUMO microsimulation boundary. "
        "Does NOT represent real-time live GHMC sensor telemetry."
    )


class SimulationMetrics(BaseModel):
    active_vehicles: int = Field(
        ...,
        description="Time-average number of concurrent active vehicles observed on the network",
    )
    peak_active_vehicles: Optional[int] = Field(
        default=0,
        description="Peak simultaneous active vehicles observed on the network",
    )
    total_vehicles: int = Field(
        ...,
        description="Total unique vehicles that actually departed and participated in the simulation",
    )
    average_speed_kmh: Optional[float] = Field(
        default=None,
        description="Mean vehicle speed in km/h across all vehicle-step observations, or None if no observations",
    )
    average_waiting_time_sec: Optional[float] = Field(
        default=None,
        description="Mean accumulated waiting time (speed < 0.1 m/s) per simulated vehicle across its trip, or None if no vehicles",
    )
    average_delay_sec: Optional[float] = Field(
        default=None,
        description="Mean final time loss compared to ideal free flow per simulated vehicle, or None if no vehicles",
    )
    throughput: int = Field(
        ...,
        description="Count of unique vehicles that arrived at their destination (completed trips) during the simulation window",
    )
    congestion_index: Optional[float] = Field(
        default=None,
        description="Dimensionless congestion index [0.0=free-flow, 1.0=gridlock]. Formula: max(0.0, min(1.0, 1.0 - speed/free_flow_speed)), or None if no observations",
    )
    max_halting_vehicles: Optional[int] = Field(
        default=0,
        description="Peak simultaneous halting vehicles (speed < 0.1 m/s) observed across the network",
    )
    teleported_vehicles: Optional[int] = Field(
        default=0,
        description="Count of vehicles that experienced teleportation due to gridlock timeout",
    )
    free_flow_speed_kmh: float = Field(
        default=50.0,
        description="Network reference free-flow speed in km/h",
    )
    arrived_vehicles: Optional[int] = Field(
        default=None,
        description="Count of unique vehicles that completed their trip and arrived at their destination (equivalent to throughput)",
    )
    active_at_end: Optional[int] = Field(
        default=None,
        description="Count of vehicles that were still en route when the simulation horizon terminated",
    )
    completed_trips_avg_waiting_time_sec: Optional[float] = Field(
        default=None,
        description="Mean accumulated waiting time strictly for vehicles that completed their trips (avoids truncation dilution)",
    )
    completed_trips_avg_delay_sec: Optional[float] = Field(
        default=None,
        description="Mean delay (time loss) strictly for vehicles that completed their trips (avoids truncation dilution)",
    )
    completed_trips_avg_duration_sec: Optional[float] = Field(
        default=None,
        description="Mean total trip duration in seconds for completed trips",
    )


class SimulationMetadata(BaseModel):
    duration_seconds: int
    steps_simulated: int
    random_seed: int
    demand_profile: str
    network_name: str
    timestamp: str
    step_length_sec: float = 1.0
    derived_metrics_formulas: Dict[str, str] = Field(
        default_factory=lambda: {
            "average_speed_kmh": "mean(traci.vehicle.getSpeed) * 3.6 across active vehicle-seconds, or None if no vehicles",
            "average_delay_sec": "sum(vehicle.final_time_loss) / total_vehicles, or None if no vehicles",
            "average_waiting_time_sec": "sum(vehicle.accumulated_waiting_time) / total_vehicles, or None if no vehicles",
            "throughput": "unique vehicles arriving at destination (completed trips) during simulation duration",
            "congestion_index": "max(0.0, min(1.0, 1.0 - (average_speed_kmh / free_flow_speed_kmh))) if average_speed_kmh is not None else None",
        }
    )


class CorridorMetric(BaseModel):
    id: str
    name: str
    avg_speed: Optional[float] = Field(
        default=None,
        description="Empirical average speed in km/h on corridor, or None if no vehicle observations",
    )
    status: str = Field(
        ...,
        description="Corridor status: 'SMOOTH' | 'MODERATE' | 'HEAVY' | 'CRITICAL' | 'NO_DATA'",
    )
    value: Optional[float] = Field(
        default=None,
        description="Dimensionless congestion percentage (0.0 to 100.0) or None if no data",
    )
    color: str


class TrafficObservations(BaseModel):
    network_average_speed_kmh: Optional[float] = Field(
        default=None, description="Mean network speed in km/h across observed vehicle steps"
    )
    average_delay_sec: Optional[float] = Field(
        default=None, description="Mean vehicle time loss in seconds compared to free-flow"
    )
    average_waiting_time_sec: Optional[float] = Field(
        default=None, description="Mean vehicle accumulated waiting time (speed < 0.1 m/s) in seconds"
    )
    congestion_index: Optional[float] = Field(
        default=None, description="Dimensionless congestion index [0.0 = free-flow, 1.0 = gridlock]"
    )
    total_vehicles: int = Field(
        default=0, description="Total unique simulated vehicles participating in demand"
    )
    throughput: int = Field(
        default=0, description="Completed vehicle trips arriving at destination during simulation"
    )
    max_halting_vehicles: Optional[int] = Field(
        default=0, description="Peak simultaneous halting vehicles (speed < 0.1 m/s) observed across network"
    )
    teleported_vehicles: Optional[int] = Field(
        default=0, description="Vehicles teleported due to gridlock/jam timeout threshold"
    )
    active_vehicles: int = Field(
        default=0, description="Time-average active concurrent vehicles"
    )
    peak_active_vehicles: Optional[int] = Field(
        default=0, description="Peak concurrent active vehicles observed"
    )
    free_flow_speed_kmh: float = Field(
        default=50.0, description="Network baseline reference free-flow speed"
    )


class BottleneckEvidence(BaseModel):
    speed_kmh: Optional[float] = Field(
        default=None, description="Observed empirical corridor average speed in km/h"
    )
    network_average_speed_kmh: Optional[float] = Field(
        default=None, description="Network average speed for baseline comparative context"
    )
    speed_deficit_pct: Optional[float] = Field(
        default=None, description="Percentage speed deficit below network average or free flow"
    )
    delay_sec: Optional[float] = Field(
        default=None, description="Observed average vehicle delay in seconds"
    )
    waiting_time_sec: Optional[float] = Field(
        default=None, description="Observed average vehicle waiting time in seconds"
    )
    congestion_index: Optional[float] = Field(
        default=None, description="Corridor or network congestion index"
    )
    halting_vehicles: Optional[int] = Field(
        default=None, description="Peak halting vehicles observed on corridor"
    )


class BottleneckInfo(BaseModel):
    corridor: str = Field(..., description="Corridor or junction identified as a bottleneck")
    corridor_id: Optional[str] = Field(default=None, description="Unique corridor identifier")
    severity: str = Field(..., description="Severity classification: CRITICAL | HEAVY | MODERATE | LOW")
    reason: str = Field(..., description="Evidence-backed diagnosis reasoning")
    evidence: BottleneckEvidence = Field(..., description="Empirical evidence telemetry supporting bottleneck diagnosis")


class CandidateIntervention(BaseModel):
    type: str = Field(..., description="Intervention category: signal_timing | rerouting | lane_use | incident_response")
    target: str = Field(..., description="Target corridor, intersection, or arterial")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Configurable parameters for intervention")
    reason: str = Field(..., description="Domain rationale explaining why this intervention candidate is appropriate")
    evidence: List[str] = Field(default_factory=list, description="Empirical observations motivating candidate generation")
    executable: bool = Field(default=False, description="Whether executable via real SUMO TraCI in current milestone")
    execution_notes: Optional[str] = Field(default=None, description="Execution mechanics or architectural limitation rationale")
    potential_benefit: str = Field(..., description="Anticipated operational relief on target bottleneck")
    potential_tradeoff: str = Field(..., description="Potential operational drawback or corridor externality")


class PotentialTradeOff(BaseModel):
    intervention: str = Field(..., description="Intervention category or identifier")
    target: str = Field(..., description="Target corridor or arterial")
    potential_benefit: str = Field(..., description="Expected operational benefit on target corridor")
    potential_tradeoff: str = Field(..., description="Expected adverse impact on opposing or neighboring corridors")
    affected_corridors: List[str] = Field(default_factory=list, description="List of corridors susceptible to secondary effects")


class TrafficEvidenceResponse(BaseModel):
    source: SourceInfo
    location: str
    scenario: str
    status: str = "completed"
    metrics: SimulationMetrics
    metadata: Optional[SimulationMetadata] = None

    # Structured traffic intelligence extensions
    observations: Optional[TrafficObservations] = None
    bottlenecks: List[BottleneckInfo] = Field(default_factory=list)
    candidate_interventions: List[CandidateIntervention] = Field(default_factory=list)
    trade_offs: List[PotentialTradeOff] = Field(default_factory=list)

    # Top-level backward compatibility fields for existing UI / Planner consumers
    active_vehicles: Optional[int] = None
    peak_active_vehicles: Optional[int] = None
    total_vehicles: Optional[int] = None
    average_speed_kmh: Optional[float] = None
    average_delay_sec: Optional[float] = None
    average_waiting_time_sec: Optional[float] = None
    congestion_index: Optional[float] = None
    timestamp: Optional[str] = None
    corridors: Optional[List[Dict[str, Any]]] = None
    hourly_data: Optional[List[Dict[str, Any]]] = None
    sensors: Optional[List[Dict[str, Any]]] = None


class TrafficAnalyzeRequest(BaseModel):
    location: Optional[str] = "Narayanguda, Hyderabad"
    scenario: Optional[str] = "synthetic_normal"
    duration_seconds: Optional[int] = 120
    seed: Optional[int] = 42
    purpose: Optional[str] = "baseline_traffic_analysis"
    force_fresh: Optional[bool] = False
    inputs: Optional[Dict[str, Any]] = None


class SignalOptimizationRequest(BaseModel):
    intersection_id: Optional[str] = Field(default="cluster_308783170_3158879059_3217073805_4433969588")
    target_corridor: Optional[str] = Field(default="Westbound")
    green_time_adjustment_sec: Optional[float] = Field(default=15.0)
    current_cycle_sec: Optional[int] = Field(default=120)
    notes: Optional[str] = Field(default="Signal timing candidate parameterization and defensive validation")


class SignalOptimizationCandidate(BaseModel):
    intersection_id: str
    target_corridor: str
    green_time_adjustment_sec: float
    min_green_sec: float = 10.0
    max_green_sec: float = 60.0
    cycle_sec: int = 120
    executable: bool = True
    rationale: str


class SignalOptimizationResponse(BaseModel):
    status: str = "CANDIDATES_GENERATED"
    intersection_id: Optional[str] = None
    target_corridor: Optional[str] = None
    candidates: List[SignalOptimizationCandidate] = Field(default_factory=list)
    validation_status: str = "VALID"
    timestamp: str
    message: str = "Signal timing candidates parameterized with defensive validation bounds."
