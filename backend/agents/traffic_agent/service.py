"""
Traffic Agent Application Service — Live TomTom Traffic Intelligence.
Fulfills all live traffic monitoring, condition analysis, bottleneck diagnosis,
and factual traffic queries using real-time TomTom Traffic Flow and Incidents telemetry.
SUMO is strictly excluded from this service.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Any, Dict, List, Optional

from backend.agents.traffic_agent.location_resolver import LocationResolver, ResolvedLocation
from backend.agents.traffic_agent.schemas import (
    BottleneckEvidence,
    BottleneckInfo,
    CandidateIntervention,
    CorridorMetric,
    PotentialTradeOff,
    SimulationMetadata,
    SimulationMetrics,
    SourceInfo,
    TrafficAnalyzeRequest,
    TrafficEvidenceResponse,
    TrafficObservations,
)
from backend.services.tomtom import (
    FlowSegmentData,
    fetch_all_corridor_flows,
    fetch_flow_segment,
    fetch_incidents,
)

logger = logging.getLogger("traffic_agent.service")


def _run_async(coro):
    """Safely executes an async coroutine from synchronous FastAPI route handlers."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Inside an existing event loop thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


class TrafficService:
    """
    Live Traffic Intelligence service powered exclusively by the TomTom Traffic API.
    Zero SUMO simulation and zero synthetic data fabrication.
    """

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get_supported_scenarios(self) -> List[str]:
        return ["live_observed", "synthetic_normal", "synthetic_peak_westbound"]

    def get_traffic_kpis(
        self,
        location: Optional[str] = None,
        query_text: Optional[str] = None,
        scenario: str = "live_observed",
        duration_seconds: int = 120,
        seed: Optional[int] = None,
        purpose: str = "live_traffic_monitoring",
        force_fresh: bool = False,
    ) -> TrafficEvidenceResponse:
        """
        Retrieves real-time observed traffic KPIs from TomTom for the resolved locality.
        Never runs SUMO or generates synthetic data.
        """
        # 1. Resolve locality
        loc = LocationResolver.resolve(
            query_text=query_text,
            explicit_location=location,
        )

        if not loc or not loc.is_within_hyderabad():
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            return TrafficEvidenceResponse(
                source=SourceInfo(
                    type="observed",
                    engine="TomTom",
                    provider="tomtom",
                    synthetic=False,
                    disclaimer=f"No live TomTom monitoring coverage for '{location}'.",
                ),
                location=location or "Unknown",
                scenario=scenario or "live_observed",
                status="unavailable",
                reason=f"Locality '{location}' is outside monitored Hyderabad coverage.",
                data_source="tomtom_traffic_api",
                source_type="observed",
                source_provider="tomtom",
                timestamp=now_iso,
            )

        # 2. Query TomTom Flow and Incidents
        try:
            flow: FlowSegmentData = _run_async(
                fetch_flow_segment(
                    point=loc.point,
                    corridor_id=loc.slug,
                    corridor_name=loc.name,
                )
            )
        except Exception as exc:
            logger.error(f"TomTom API flow fetch failed for {loc.name}: {exc}")
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            return TrafficEvidenceResponse(
                source=SourceInfo(
                    type="observed",
                    engine="TomTom",
                    provider="tomtom",
                    synthetic=False,
                    disclaimer="TomTom Traffic API is temporarily unreachable.",
                ),
                location=loc.name,
                scenario=scenario or "live_observed",
                status="unavailable",
                reason=f"TomTom Live Traffic API error: {exc}",
                data_source="tomtom_traffic_api",
                source_type="observed",
                source_provider="tomtom",
                timestamp=now_iso,
            )

        # 3. Query Hyderabad Incidents
        incident_count = 0
        try:
            incidents_data = _run_async(fetch_incidents())
            if incidents_data and hasattr(incidents_data, "features"):
                incident_count = len(incidents_data.features)
        except Exception as exc:
            logger.warning(f"Could not fetch incidents: {exc}")

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # 4. Construct TrafficObservations
        # Note: TomTom Flow Segment measures speed, free-flow speed, and travel time delay (flow.delay_seconds).
        # It does NOT measure intersection waiting time (stopped vehicles) or vehicle counts.
        observations = TrafficObservations(
            network_average_speed_kmh=flow.current_speed,
            average_delay_sec=float(flow.delay_seconds),
            average_waiting_time_sec=None,  # Not directly measured by TomTom flow segments
            congestion_index=flow.congestion_ratio,
            free_flow_speed_kmh=flow.free_flow_speed,
            total_vehicles=None,
            throughput=None,
            active_vehicles=None,
        )

        # 5. Build Corridor Metrics
        corridors: List[CorridorMetric] = [
            CorridorMetric(
                id=f"cor_{loc.slug}",
                name=f"{loc.name} Main Corridor",
                avg_speed=flow.current_speed,
                status=flow.status.upper(),
                value=round(flow.congestion_ratio * 100.0, 1),
                color="#E5483F" if flow.congestion_ratio > 0.4 else ("#F4A62A" if flow.congestion_ratio > 0.2 else "#22C55E"),
            )
        ]

        # 6. Build Bottlenecks if congested
        bottlenecks: List[BottleneckInfo] = []
        if flow.congestion_ratio >= 0.20:
            severity = "CRITICAL" if flow.congestion_ratio >= 0.50 else ("HEAVY" if flow.congestion_ratio >= 0.35 else "MODERATE")
            deficit_pct = round(max(0.0, (1.0 - flow.current_speed / max(1.0, flow.free_flow_speed)) * 100.0), 1)
            bottlenecks.append(
                BottleneckInfo(
                    corridor=f"{loc.name} Arterial",
                    corridor_id=f"cor_{loc.slug}",
                    severity=severity,
                    reason=f"Live TomTom speed is {flow.current_speed:.1f} km/h compared to free-flow {flow.free_flow_speed:.1f} km/h (delay +{flow.delay_seconds}s).",
                    evidence=BottleneckEvidence(
                        speed_kmh=flow.current_speed,
                        network_average_speed_kmh=flow.free_flow_speed,
                        speed_deficit_pct=deficit_pct,
                        delay_sec=float(flow.delay_seconds),
                        waiting_time_sec=None,  # Not measured by TomTom flow segments
                        congestion_index=flow.congestion_ratio,
                    ),
                )
            )

        # 7. Candidate Interventions (domain options testable via SUMO simulation agent)
        candidate_interventions: List[CandidateIntervention] = []
        trade_offs: List[PotentialTradeOff] = []
        if bottlenecks:
            candidate_interventions.append(
                CandidateIntervention(
                    type="signal_timing",
                    target=loc.name,
                    parameters={"green_time_adjustment_sec": 15.0},
                    reason=f"Extend green phase on {loc.name} arterial to clear queue build-up.",
                    evidence=[f"Current TomTom speed: {flow.current_speed} km/h (free-flow: {flow.free_flow_speed} km/h)"],
                    executable=True,
                    execution_notes=f"Can be validated in Eclipse SUMO on the authentic {loc.name} network.",
                    potential_benefit=f"Design hypothesis for queue reduction on {loc.name} arterial. Must be verified in SUMO simulation.",
                    potential_tradeoff="Possible secondary delay on intersecting cross-streets.",
                )
            )
            candidate_interventions.append(
                CandidateIntervention(
                    type="rerouting",
                    target=loc.name,
                    parameters={"diversion_fraction": 0.15, "reroute_mode": "alternative_route"},
                    reason=f"Divert fraction of through-traffic from {loc.name} onto parallel arterials.",
                    evidence=[f"Observed congestion ratio {flow.congestion_ratio:.2f}"],
                    executable=True,
                    execution_notes="Testable in SUMO microsimulation.",
                    potential_benefit="Design hypothesis to reduce mainline volume. Requires SUMO simulation to assess network-wide diversion impact.",
                    potential_tradeoff="Adds volume to neighboring secondary roads.",
                )
            )
            trade_offs.append(
                PotentialTradeOff(
                    intervention="signal_timing",
                    target=loc.name,
                    potential_benefit="Green extension clears mainline queue.",
                    potential_tradeoff="May slightly increase wait times on cross-street traffic.",
                    affected_corridors=["Cross-street approach"],
                )
            )

        # 8. Source Provenance
        source_info = SourceInfo(
            type="observed",
            engine="TomTom",
            provider="tomtom",
            synthetic=False,
            disclaimer="Real-time live traffic telemetry observed from TomTom Flow Segment & Incidents API.",
        )

        # For live observed TomTom telemetry, do NOT fabricate simulation metadata (seed, duration, net.xml)
        metadata = None

        return TrafficEvidenceResponse(
            source=source_info,
            location=loc.name,
            scenario="live_observed",
            status="completed",
            metadata=metadata,
            data_source="tomtom_traffic_api",
            source_type="observed",
            source_provider="tomtom",
            current_speed_kmh=flow.current_speed,
            free_flow_speed_kmh=flow.free_flow_speed,
            current_travel_time_sec=flow.current_travel_time,
            free_flow_travel_time_sec=flow.free_flow_travel_time,
            delay_seconds=flow.delay_seconds,
            congestion_ratio=flow.congestion_ratio,
            confidence=flow.confidence,
            road_closure=flow.road_closure,
            average_speed_kmh=flow.current_speed,
            average_delay_sec=float(flow.delay_seconds),
            average_waiting_time_sec=None,  # Not measured by TomTom flow segments
            congestion_index=flow.congestion_ratio,
            timestamp=now_iso,
            observations=observations,
            corridors=[c.model_dump() for c in corridors],
            bottlenecks=bottlenecks,
            candidate_interventions=candidate_interventions,
            trade_offs=trade_offs,
        )

    def analyze_traffic(self, req: TrafficAnalyzeRequest) -> TrafficEvidenceResponse:
        """Fulfills diagnostic traffic analysis requests using real-time TomTom data."""
        return self.get_traffic_kpis(
            location=req.location,
            query_text=getattr(req, "objective", None),
            scenario=req.scenario or "live_observed",
            duration_seconds=req.duration_seconds or 120,
            seed=req.seed,
            purpose=req.purpose or "traffic_analysis",
            force_fresh=req.force_fresh or False,
        )


_default_traffic_service: Optional[TrafficService] = None

def get_traffic_service() -> TrafficService:
    global _default_traffic_service
    if _default_traffic_service is None:
        _default_traffic_service = TrafficService()
    return _default_traffic_service
