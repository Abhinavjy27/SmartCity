"""
Traffic Agent Application Service.
Coordinates demand generation, SUMO execution, metrics extraction, and structured evidence packaging.
Explicitly distinguishes synthetic demand assumptions, empirical TraCI simulation results,
and derived presentation data for the frontend dashboard.
"""

from __future__ import annotations

import datetime
import logging
import os
from typing import Any, Dict, List, Optional

from backend.agents.traffic_agent.demand_generator import SyntheticDemandGenerator
from backend.agents.traffic_agent.schemas import (
    BottleneckEvidence,
    BottleneckInfo,
    CandidateIntervention,
    PotentialTradeOff,
    SignalOptimizationCandidate,
    SignalOptimizationRequest,
    SignalOptimizationResponse,
    SimulationMetadata,
    SimulationMetrics,
    SourceInfo,
    TrafficEvidenceResponse,
    TrafficObservations,
)
from backend.agents.traffic_agent.sumo_runner import SumoExecutionError, SumoRunner

logger = logging.getLogger(__name__)


class TrafficService:
    """
    Traffic Intelligence service orchestrating Eclipse SUMO baseline simulations
    over the Narayanguda road network with reproducible synthetic demand.
    """

    def __init__(
        self,
        network_path: Optional[str] = None,
        routes_dir: Optional[str] = None,
        sumo_binary: Optional[str] = None,
    ):
        pkg_dir = os.path.dirname(os.path.abspath(__file__))
        smartcity_root = os.path.abspath(os.path.join(pkg_dir, "..", "..", ".."))

        self.network_path = network_path or os.getenv(
            "SUMO_NETWORK_PATH",
            os.path.join(smartcity_root, "simulations", "networks", "narayanguda_network.net.xml"),
        )
        self.routes_dir = routes_dir or os.getenv(
            "SUMO_ROUTES_DIR",
            os.path.join(smartcity_root, "simulations", "routes"),
        )

        self.demand_generator = SyntheticDemandGenerator(routes_dir=self.routes_dir)
        self.sumo_runner = SumoRunner(sumo_binary=sumo_binary)
        self._cache: Dict[str, TrafficEvidenceResponse] = {}

    def get_supported_scenarios(self) -> List[str]:
        return self.demand_generator.get_supported_scenarios()

    def run_baseline_simulation(
        self,
        location: str = "Narayanguda, Hyderabad",
        scenario: str = "synthetic_normal",
        duration_seconds: int = 120,
        seed: int = 42,
        purpose: str = "baseline_traffic_analysis",
        force_fresh: bool = False,
    ) -> TrafficEvidenceResponse:
        """
        Runs an authentic Eclipse SUMO microsimulation for the requested scenario
        and returns structured evidence conforming to the contract.
        """
        clean_scenario = self.demand_generator.validate_scenario(scenario)

        if not os.path.isfile(self.network_path):
            raise SumoExecutionError(
                f"Narayanguda SUMO network file not found at: {self.network_path}",
                {"network_path": self.network_path},
            )

        duration_seconds = max(10, min(1800, int(duration_seconds or 120)))
        seed = int(seed if seed is not None else 42)

        cache_key = f"{clean_scenario}_{duration_seconds}_{seed}_{location}"
        if not force_fresh and cache_key in self._cache:
            logger.info(f"Returning cached baseline simulation for {cache_key}")
            return self._cache[cache_key]

        # 1. Generate deterministic synthetic demand route file
        route_file = self.demand_generator.generate_route_file(
            scenario=clean_scenario,
            duration_seconds=duration_seconds,
            seed=seed,
        )

        # 2. Execute SUMO microsimulation via TraCI
        metrics, corridors = self.sumo_runner.run_simulation(
            net_file=self.network_path,
            route_file=route_file,
            duration_seconds=duration_seconds,
        )

        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        metadata = SimulationMetadata(
            duration_seconds=duration_seconds,
            steps_simulated=duration_seconds,
            random_seed=seed,
            demand_profile=clean_scenario,
            network_name=os.path.basename(self.network_path),
            timestamp=now_utc,
            step_length_sec=1.0,
        )

        # 3. Derived UI presentation layers (explicitly distinguished from empirical telemetry)
        hourly_data = self._generate_compatible_hourly_data(metrics, duration_seconds)
        sensors = self._generate_compatible_sensors(corridors, metrics, duration_seconds)

        # 4. Traffic Intelligence: Observations, dynamic bottleneck detection, candidate interventions, and trade-offs
        observations, bottlenecks, candidate_interventions, trade_offs = self.analyze_traffic_conditions(
            metrics=metrics, corridors=corridors, duration_seconds=duration_seconds
        )

        # Build structured evidence response with consistent internal scale [0.0 - 1.0]
        response = TrafficEvidenceResponse(
            source=SourceInfo(
                type="simulation",
                engine="SUMO",
                synthetic=True,
                network=os.path.basename(self.network_path),
            ),
            location=location or "Narayanguda, Hyderabad",
            scenario=clean_scenario,
            status="completed",
            metrics=metrics,
            metadata=metadata,
            observations=observations,
            bottlenecks=bottlenecks,
            candidate_interventions=candidate_interventions,
            trade_offs=trade_offs,
            active_vehicles=metrics.active_vehicles,
            peak_active_vehicles=metrics.peak_active_vehicles,
            total_vehicles=metrics.total_vehicles,
            average_speed_kmh=metrics.average_speed_kmh,
            average_delay_sec=metrics.average_delay_sec,
            average_waiting_time_sec=metrics.average_waiting_time_sec,
            congestion_index=metrics.congestion_index,
            timestamp=now_utc,
            corridors=corridors,
            hourly_data=hourly_data,
            sensors=sensors,
        )

        self._cache[cache_key] = response
        return response

    @staticmethod
    def _generate_compatible_hourly_data(
        metrics: SimulationMetrics, duration_seconds: int
    ) -> List[Dict[str, Any]]:
        """
        Derived presentation data: Synthesizes a 24-hour diurnal profile curve anchored
        on the measured simulation speed. Scaled using actual duration_seconds.
        Not to be interpreted as real historical multi-day sensor telemetry.
        If no speed observations exist (metrics.average_speed_kmh is None), preserves
        None rather than fabricating a default speed.
        """
        base_speed = metrics.average_speed_kmh
        scale_factor = 3600.0 / max(1.0, float(duration_seconds))
        data = []
        for h in range(24):
            if base_speed is not None:
                factor = 1.3 if (h <= 5 or h >= 22) else (0.75 if (8 <= h <= 10 or 17 <= h <= 19) else 1.0)
                spd = round(max(8.0, min(55.0, base_speed * factor)), 1)
                vol = int(round(metrics.total_vehicles * scale_factor * (1.6 if factor < 1.0 else 0.4)))
            else:
                spd = None
                vol = 0
            data.append({"h": f"{h:02d}:00", "speed": spd, "volume": vol})
        return data

    @staticmethod
    def _generate_compatible_sensors(
        corridors: List[Dict[str, Any]], metrics: SimulationMetrics, duration_seconds: int
    ) -> List[Dict[str, Any]]:
        """
        Derived presentation data: Maps corridor simulation performance into junction sensor format
        for the dashboard UI table. Preserves NO_DATA status when a corridor has no observations.

        NOTE: `occ` is a legacy/derived UI compatibility field populated from corridor congestion
        percentage; it is NOT measured SUMO occupancy and must NOT be interpreted as real sensor occupancy.
        When a corridor has no vehicle observations (status = 'NO_DATA'), `occ` is set to None.
        """
        scale_factor = 3600.0 / max(1.0, float(duration_seconds))
        sensors = []
        for idx, c in enumerate(corridors):
            avg_spd = c["avg_speed"]
            vol = int(metrics.total_vehicles * scale_factor // max(1, len(corridors))) if metrics.total_vehicles else 0
            # occ is derived from corridor congestion percentage; preserves None on NO_DATA
            occ = round(min(98.0, c["value"]), 1) if c["value"] is not None else None
            sensors.append({
                "id": f"SENSOR_0{idx + 1}",
                "name": c["name"],
                "speed": avg_spd,
                "volume": vol,
                "occ": occ,
                "congestion": c["status"],
            })
        return sensors

    def analyze_traffic_conditions(
        self,
        metrics: SimulationMetrics,
        corridors: List[Dict[str, Any]],
        duration_seconds: int = 120,
    ) -> Tuple[
        TrafficObservations,
        List[BottleneckInfo],
        List[CandidateIntervention],
        List[PotentialTradeOff],
    ]:
        """
        Analyzes empirical SUMO simulation observations, diagnoses corridor bottlenecks dynamically,
        generates structured candidate interventions across categories, and identifies potential trade-offs.
        """
        observations = TrafficObservations(
            network_average_speed_kmh=metrics.average_speed_kmh,
            average_delay_sec=metrics.average_delay_sec,
            average_waiting_time_sec=metrics.average_waiting_time_sec,
            congestion_index=metrics.congestion_index,
            total_vehicles=metrics.total_vehicles,
            throughput=metrics.throughput,
            max_halting_vehicles=metrics.max_halting_vehicles,
            teleported_vehicles=metrics.teleported_vehicles,
            active_vehicles=metrics.active_vehicles,
            peak_active_vehicles=metrics.peak_active_vehicles,
            free_flow_speed_kmh=metrics.free_flow_speed_kmh,
        )

        bottlenecks: List[BottleneckInfo] = []
        valid_corrs = [c for c in corridors if c.get("avg_speed") is not None]

        # 1. Evidence-Based Bottleneck Detection
        if valid_corrs:
            congested = [c for c in valid_corrs if c.get("status") in ("CRITICAL", "HEAVY")]
            if congested:
                for c in congested:
                    spd = c["avg_speed"]
                    deficit = (
                        round(((metrics.average_speed_kmh - spd) / metrics.average_speed_kmh) * 100, 1)
                        if metrics.average_speed_kmh and metrics.average_speed_kmh > 0
                        else None
                    )
                    bottlenecks.append(
                        BottleneckInfo(
                            corridor=c["name"],
                            corridor_id=c.get("id"),
                            severity=c.get("status", "HEAVY"),
                            reason=f"Severe speed degradation on {c['name']} ({spd} km/h, status: {c.get('status')})",
                            evidence=BottleneckEvidence(
                                speed_kmh=spd,
                                network_average_speed_kmh=metrics.average_speed_kmh,
                                speed_deficit_pct=deficit,
                                delay_sec=metrics.average_delay_sec,
                                waiting_time_sec=metrics.average_waiting_time_sec,
                                congestion_index=metrics.congestion_index,
                                halting_vehicles=metrics.max_halting_vehicles,
                            ),
                        )
                    )
            else:
                # Dynamically diagnose the lowest observed-speed corridor
                slowest = min(valid_corrs, key=lambda c: c["avg_speed"])
                spd = slowest["avg_speed"]
                deficit = (
                    round(((metrics.average_speed_kmh - spd) / metrics.average_speed_kmh) * 100, 1)
                    if metrics.average_speed_kmh and metrics.average_speed_kmh > 0
                    else None
                )
                bottlenecks.append(
                    BottleneckInfo(
                        corridor=slowest["name"],
                        corridor_id=slowest.get("id"),
                        severity="MODERATE" if spd >= 22.0 else "HEAVY",
                        reason=f"Lowest observed-speed corridor ({spd} km/h vs network average {metrics.average_speed_kmh or 'N/A'} km/h)",
                        evidence=BottleneckEvidence(
                            speed_kmh=spd,
                            network_average_speed_kmh=metrics.average_speed_kmh,
                            speed_deficit_pct=deficit,
                            delay_sec=metrics.average_delay_sec,
                            waiting_time_sec=metrics.average_waiting_time_sec,
                            congestion_index=metrics.congestion_index,
                            halting_vehicles=metrics.max_halting_vehicles,
                        ),
                    )
                )

        if metrics.teleported_vehicles and metrics.teleported_vehicles > 0:
            bottlenecks.append(
                BottleneckInfo(
                    corridor="Narayanguda Network Junction",
                    corridor_id="NET_GRIDLOCK",
                    severity="CRITICAL",
                    reason=f"{metrics.teleported_vehicles} vehicles encountered gridlock teleportation timeout",
                    evidence=BottleneckEvidence(
                        speed_kmh=metrics.average_speed_kmh,
                        network_average_speed_kmh=metrics.average_speed_kmh,
                        delay_sec=metrics.average_delay_sec,
                        congestion_index=metrics.congestion_index,
                        halting_vehicles=metrics.max_halting_vehicles,
                    ),
                )
            )

        candidates: List[CandidateIntervention] = []
        trade_offs: List[PotentialTradeOff] = []

        if not valid_corrs:
            return observations, bottlenecks, candidates, trade_offs

        primary_target_name = bottlenecks[0].corridor if bottlenecks else valid_corrs[0]["name"]
        target_dir = "Westbound"
        for d in ["Westbound", "Southbound", "Northbound", "Eastbound"]:
            if d.lower() in primary_target_name.lower():
                target_dir = d
                break

        target_spd = bottlenecks[0].evidence.speed_kmh if bottlenecks and bottlenecks[0].evidence.speed_kmh is not None else 35.0
        opposing_map = {
            "Westbound": "Southbound",
            "Southbound": "Westbound",
            "Northbound": "Southbound",
            "Eastbound": "Westbound",
        }
        opposing_dir = opposing_map.get(target_dir, "Southbound")

        # Category 1: Signal Timing (Executable)
        candidates.append(
            CandidateIntervention(
                type="signal_timing",
                target=target_dir,
                parameters={
                    "green_time_adjustment_sec": 10.0,
                    "min_green_sec": 10.0,
                    "max_green_sec": 60.0,
                    "cycle_sec": 120,
                },
                reason=f"Empirical baseline identifies {target_dir} as lowest observed-speed corridor ({target_spd} km/h). Moderate green extension clears accumulated queues while limiting opposing phase degradation.",
                evidence=[
                    f"Corridor speed: {target_spd} km/h",
                    f"Network average speed: {metrics.average_speed_kmh or 'N/A'} km/h",
                    f"Average vehicle delay: {metrics.average_delay_sec or 0.0}s",
                ],
                executable=True,
                execution_notes="Executable in real SUMO microsimulation via TraCI dynamic TLS in-memory program modification.",
                potential_benefit=f"Increases green split for {target_dir}, improving progression speed and clearing queues.",
                potential_tradeoff=f"Reduces green allocation for conflicting/opposing phase ({opposing_dir}), potentially increasing queue delay.",
            )
        )

        candidates.append(
            CandidateIntervention(
                type="signal_timing",
                target=target_dir,
                parameters={
                    "green_time_adjustment_sec": 19.0,
                    "min_green_sec": 10.0,
                    "max_green_sec": 60.0,
                    "cycle_sec": 120,
                },
                reason=f"Aggressive green extension for {target_dir} to maximize bottleneck throughput during peak directional demand.",
                evidence=[
                    f"Corridor speed: {target_spd} km/h",
                    f"Network congestion index: {metrics.congestion_index or 0.0}",
                ],
                executable=True,
                execution_notes="Executable in real SUMO microsimulation via TraCI dynamic TLS in-memory program modification.",
                potential_benefit=f"Maximizes queue discharge on {target_dir} approach.",
                potential_tradeoff=f"Significant green time penalty on opposing phase ({opposing_dir}), risking secondary queue spillback.",
            )
        )

        # Category 2: Rerouting (Executable in real SUMO via TraCI)
        candidates.append(
            CandidateIntervention(
                type="rerouting",
                target=target_dir,
                parameters={
                    "diversion_fraction": 0.15,
                    "reroute_mode": "alternative_route",
                    "alternative_arterial": "Perimeter Ring Corridor",
                },
                reason=f"Diverting a fraction of traffic destined for {target_dir} upstream prevents bottleneck oversaturation.",
                evidence=[f"Corridor volume concentration on {target_dir}"],
                executable=True,
                execution_notes="Executable in real SUMO microsimulation via TraCI dynamic route re-assignment and network alternative path selection.",
                potential_benefit=f"Directly reduces vehicle arrival rate entering the {target_dir} bottleneck corridor.",
                potential_tradeoff="May shift congestion onto secondary perimeter streets and increase trip circuity.",
            )
        )

        # Category 3: Lane Use (Candidate-Only, executable=False)
        candidates.append(
            CandidateIntervention(
                type="lane_use",
                target=f"{target_dir} Approach",
                parameters={
                    "reversible_lane": True,
                    "dynamic_lane_allocation": "inbound_priority",
                },
                reason=f"Temporarily reassigning an opposing lane to {target_dir} increases corridor capacity during directional peak.",
                evidence=[f"Directional imbalance: {target_dir} speed {target_spd} km/h vs opposing corridors"],
                executable=False,
                execution_notes="Fixed OSM multi-lane geometry in narayanguda_network.net.xml does not currently support dynamic TraCI reversible lane switching without modifying the base network.",
                potential_benefit=f"Expands physical lane capacity on the congested {target_dir} corridor.",
                potential_tradeoff=f"Reduces opposing {opposing_dir} lane capacity and requires physical or dynamic gantry signage.",
            )
        )

        # Category 4: Incident Response (Candidate-Only, executable=False)
        candidates.append(
            CandidateIntervention(
                type="incident_response",
                target=f"{target_dir} Corridor",
                parameters={
                    "speed_harmonization_kmh": 30.0,
                    "rapid_clearance_protocol": True,
                },
                reason="Deploy rapid roadside clearance and upstream variable speed warnings to prevent shockwave propagation.",
                evidence=[
                    f"Peak halting vehicles: {metrics.max_halting_vehicles or 0}",
                    f"Average delay: {metrics.average_delay_sec or 0.0}s",
                ],
                executable=False,
                execution_notes="Incident response requires dynamic obstruction injection or lane closure via TraCI, maintained as candidate specification.",
                potential_benefit="Quickly restores nominal roadway capacity following obstructions or halts.",
                potential_tradeoff="Upstream speed harmonization slightly increases travel time for free-flowing vehicles.",
            )
        )

        # 3. Derive potential trade-offs
        trade_offs.append(
            PotentialTradeOff(
                intervention="signal_timing",
                target=target_dir,
                potential_benefit=f"Extends green duration to clear queued vehicles on {target_dir}",
                potential_tradeoff=f"Reduces cycle split and increases delay for conflicting {opposing_dir} movements",
                affected_corridors=[opposing_dir, "Cross movements at Narayanguda junction"],
            )
        )
        trade_offs.append(
            PotentialTradeOff(
                intervention="rerouting",
                target=target_dir,
                potential_benefit=f"Lowers incoming traffic volume on {target_dir}",
                potential_tradeoff="Transfers delay and vehicle volume to secondary diversion routes",
                affected_corridors=["Perimeter corridors", "Secondary connectors"],
            )
        )
        trade_offs.append(
            PotentialTradeOff(
                intervention="lane_use",
                target=target_dir,
                potential_benefit=f"Increases number of active travel lanes for {target_dir}",
                potential_tradeoff=f"Reduces travel lanes in opposing direction ({opposing_dir}), creating reverse bottleneck",
                affected_corridors=[opposing_dir],
            )
        )

        return observations, bottlenecks, candidates, trade_offs

    @staticmethod
    def validate_signal_timing(
        intersection_id: Optional[str] = None,
        target_corridor: Optional[str] = "Westbound",
        green_adjustment: float = 15.0,
        cycle_sec: int = 120,
    ) -> SignalOptimizationResponse:
        """
        Defensive parameter validation and candidate generator for signal optimization.
        Enforces safety bounds (min green >= 10s, max adjustment <= 45s, cycle 30-240s).
        """
        tls_id = intersection_id or "cluster_308783170_3158879059_3217073805_4433969588"
        target = target_corridor or "Westbound"

        if not (1.0 <= green_adjustment <= 45.0):
            raise ValueError(f"Green time adjustment {green_adjustment}s outside safe range [1.0, 45.0]s")
        if not (30 <= cycle_sec <= 240):
            raise ValueError(f"Cycle duration {cycle_sec}s outside safe range [30, 240]s")

        candidates = [
            SignalOptimizationCandidate(
                intersection_id=tls_id,
                target_corridor=target,
                green_time_adjustment_sec=5.0,
                min_green_sec=10.0,
                max_green_sec=60.0,
                cycle_sec=cycle_sec,
                executable=True,
                rationale="Conservative green extension (+5s) for slight queue clearance with minimal cross-street impact.",
            ),
            SignalOptimizationCandidate(
                intersection_id=tls_id,
                target_corridor=target,
                green_time_adjustment_sec=10.0,
                min_green_sec=10.0,
                max_green_sec=60.0,
                cycle_sec=cycle_sec,
                executable=True,
                rationale="Balanced green extension (+10s) clearing peak queues while maintaining opposing corridor stability.",
            ),
            SignalOptimizationCandidate(
                intersection_id=tls_id,
                target_corridor=target,
                green_time_adjustment_sec=15.0,
                min_green_sec=10.0,
                max_green_sec=60.0,
                cycle_sec=cycle_sec,
                executable=True,
                rationale="Moderate-high green extension (+15s) for significant bottleneck relief.",
            ),
        ]

        if green_adjustment not in [5.0, 10.0, 15.0]:
            candidates.append(
                SignalOptimizationCandidate(
                    intersection_id=tls_id,
                    target_corridor=target,
                    green_time_adjustment_sec=round(green_adjustment, 1),
                    min_green_sec=10.0,
                    max_green_sec=60.0,
                    cycle_sec=cycle_sec,
                    executable=True,
                    rationale=f"Custom requested green extension (+{green_adjustment}s) validated within safe bounds.",
                )
            )

        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return SignalOptimizationResponse(
            status="CANDIDATES_GENERATED",
            intersection_id=tls_id,
            target_corridor=target,
            candidates=candidates,
            validation_status="VALID",
            timestamp=now_utc,
            message=f"Generated {len(candidates)} bounded signal timing candidates for {target} at {tls_id}.",
        )


_service_instance: Optional[TrafficService] = None


def get_traffic_service() -> TrafficService:
    global _service_instance
    if _service_instance is None:
        _service_instance = TrafficService()
    return _service_instance
