"""
Simulation Agent Application Service.
Executes scenario-based intervention experiments in Eclipse SUMO 1.27.1 via TraCI.
Applies dynamic traffic signal modifications without modifying the base network on disk,
collects microscopic vehicle telemetry, and performs rigorous baseline vs intervention comparisons.
"""

from __future__ import annotations

import datetime
import logging
import math
import os
import random
import threading
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Set, Tuple

import traci
import traci.exceptions

from backend.agents.simulation_agent.schemas import (
    InterventionPayload,
    InterventionType,
    SimulationEvidenceResponse,
    SimulationScenarioRequest,
)
from backend.agents.traffic_agent.demand_generator import SyntheticDemandGenerator
from backend.agents.traffic_agent.metrics import SumoMetricsCollector
from backend.agents.traffic_agent.schemas import (
    CorridorMetric,
    SimulationMetadata,
    SimulationMetrics,
    SourceInfo,
)
from backend.agents.traffic_agent.sumo_runner import SumoExecutionError, SumoRunner

logger = logging.getLogger(__name__)

# Valid Narayanguda network traffic lights mapped to arterial corridors
# Discovered empirically from simulations/networks/narayanguda_network.net.xml
CORRIDOR_TLS_MAPPING: Dict[str, List[Tuple[str, int, float]]] = {
    # Corridor key: [(tls_id, green_phase_index, default_boost_sec), ...]
    "westbound": [
        ("cluster_308783170_3158879059_3217073805_4433969588", 0, 19.0),
        ("cluster_308783191_3180193628_3652519114_9713126197", 0, 20.0),
    ],
    "hyderguda": [
        ("cluster_308783170_3158879059_3217073805_4433969588", 0, 19.0),
        ("cluster_308783191_3180193628_3652519114_9713126197", 0, 20.0),
    ],
    "cor_wb": [
        ("cluster_308783170_3158879059_3217073805_4433969588", 0, 19.0),
        ("cluster_308783191_3180193628_3652519114_9713126197", 0, 20.0),
    ],
    "northbound": [
        ("cluster_308783170_3158879059_3217073805_4433969588", 0, 15.0),
    ],
    "chikkadapally": [
        ("cluster_308783170_3158879059_3217073805_4433969588", 0, 15.0),
    ],
    "cor_nb": [
        ("cluster_308783170_3158879059_3217073805_4433969588", 0, 15.0),
    ],
    "southbound": [
        ("cluster_308783170_3158879059_3217073805_4433969588", 2, 15.0),
    ],
    "barkatpura": [
        ("cluster_308783170_3158879059_3217073805_4433969588", 2, 15.0),
    ],
    "cor_sb": [
        ("cluster_308783170_3158879059_3217073805_4433969588", 2, 15.0),
    ],
    "eastbound": [
        ("cluster_308783191_3180193628_3652519114_9713126197", 2, 15.0),
    ],
    "himayat nagar": [
        ("cluster_308783191_3180193628_3652519114_9713126197", 2, 15.0),
    ],
    "cor_eb": [
        ("cluster_308783191_3180193628_3652519114_9713126197", 2, 15.0),
    ],
}

KNOWN_INTERSECTIONS = {
    "cluster_10727855887_11564229701_11564229702_3158978742_#1more",
    "cluster_308783170_3158879059_3217073805_4433969588",
    "cluster_308783191_3180193628_3652519114_9713126197",
}


class SimulationService:
    """
    Simulation Agent service orchestrating SUMO intervention experiments
    with dynamic TraCI signal manipulation and empirical delta computation.
    """

    _lock = threading.Lock()

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
        self.sumo_binary = SumoRunner._resolve_sumo_binary(sumo_binary)

    @staticmethod
    def generate_scenario_id(
        intervention: Optional[Any],
        seed: Optional[int] = 42,
        duration: Optional[int] = None,
    ) -> str:
        """
        Generates a deterministic, structured scenario identity to prevent
        accidental duplicate simulation and enable cross-scenario tracking.
        Incorporates duration to make scenario identities horizon-aware.
        """
        dur_str = f":dur{int(duration)}s" if duration is not None else ""
        seed_str = f":seed{seed}" if seed is not None else ""
        if not intervention:
            return f"baseline{dur_str}{seed_str}"
        raw_type = intervention.get("type", "signal_timing") if isinstance(intervention, dict) else getattr(intervention, "type", "signal_timing")
        itype = raw_type.value if hasattr(raw_type, "value") else str(raw_type)
        target = (intervention.get("target") if isinstance(intervention, dict) else getattr(intervention, "target", None)) or "Westbound"
        params = (intervention.get("parameters") if isinstance(intervention, dict) else getattr(intervention, "parameters", {})) or {}

        if itype in ("rerouting", "traffic_diversion"):
            div = params.get("diversion_fraction", 0.15)
            return f"rerouting:{target}:div{float(div):.2f}{dur_str}{seed_str}"

        adj = params.get("green_time_adjustment_sec")
        if adj is not None:
            adj_str = f"adj{float(adj):+.1f}s"
        else:
            adj_str = "default"
        return f"{itype}:{target}:{adj_str}{dur_str}{seed_str}"


    def run_intervention_simulation(
        self,
        req: SimulationScenarioRequest,
    ) -> SimulationEvidenceResponse:
        """
        Executes a real Eclipse SUMO simulation with the specified intervention
        and returns structured empirical telemetry and baseline comparison.
        """
        if not os.path.isfile(self.network_path):
            raise SumoExecutionError(
                f"Narayanguda network file not found: {self.network_path}",
                {"network_path": self.network_path},
            )

        duration = req.duration_seconds or 120
        seed = req.seed if req.seed is not None else 42
        scenario_id = req.scenario_id or self.generate_scenario_id(req.intervention, seed=seed, duration=duration)

        try:
            scenario = self.demand_generator.validate_scenario(req.scenario_name)
        except ValueError:
            logger.info(f"Scenario '{req.scenario_name}' mapped to 'synthetic_normal' demand profile.")
            scenario = "synthetic_normal"

        route_file = self.demand_generator.generate_route_file(
            scenario=scenario,
            duration_seconds=duration,
            seed=seed,
        )

        # Validate intervention target and plan intervention
        intervention_details = self._resolve_intervention_plan(req.intervention)

        is_rerouting = (
            intervention_details is not None
            and intervention_details.get("type") == "rerouting"
        )
        selected_trip_ids: Set[str] = set()
        total_eligible_count = 0
        req_div_fraction = 0.0
        reroute_mode = "alternative_route"
        target_corr_key = "westbound"

        if is_rerouting:
            target_corr_key = intervention_details.get("target_corridor_key", "westbound").lower()
            req_div_fraction = intervention_details["parameters"]["diversion_fraction"]
            reroute_mode = intervention_details["parameters"].get("reroute_mode", "alternative_route")

            eligible_trip_ids: List[str] = []
            try:
                tree = ET.parse(route_file)
                for trip_elem in tree.getroot().findall("trip"):
                    t_id = trip_elem.attrib.get("id", "")
                    if target_corr_key in t_id.lower():
                        eligible_trip_ids.append(t_id)
            except Exception as e:
                logger.warning(f"Could not parse trips from route file {route_file}: {e}")

            eligible_trip_ids.sort()
            total_eligible_count = len(eligible_trip_ids)
            target_reroute_count = max(1, int(round(total_eligible_count * req_div_fraction))) if total_eligible_count > 0 else 0

            # Deterministic vehicle selection using simulation seed
            rng = random.Random(seed)
            if total_eligible_count > 0 and target_reroute_count > 0:
                selected_trip_ids = set(rng.sample(eligible_trip_ids, min(target_reroute_count, total_eligible_count)))
            else:
                selected_trip_ids = set()

            logger.info(
                f"Simulation Agent configured rerouting: corridor='{target_corr_key}', "
                f"eligible={total_eligible_count}, selected={len(selected_trip_ids)} (req_fraction={req_div_fraction})"
            )

        rerouted_vids: Set[str] = set()
        reroute_records: Dict[str, Dict[str, Any]] = {}

        with self._lock:
            self._ensure_clean_state()

            cmd = [
                self.sumo_binary,
                "-n",
                self.network_path,
                "-r",
                route_file,
                "--no-step-log",
                "true",
                "--time-to-teleport",
                "300",
                "--waiting-time-memory",
                str(duration),
                "--no-warnings",
                "true",
            ]

            collector = SumoMetricsCollector(free_flow_speed_kmh=50.0)

            try:
                traci.start(cmd)
                logger.info(
                    f"Simulation Agent started SUMO: scenario='{scenario}', "
                    f"intervention='{req.intervention.type if req.intervention else 'none'}'"
                )

                # Dynamically apply signal timing adjustments through TraCI if requested
                if intervention_details and intervention_details.get("type") == "signal_timing":
                    self._apply_signal_adjustments(intervention_details)

                for _ in range(duration):
                    traci.simulationStep()
                    collector.record_step(traci)

                    # Dynamically reroute eligible vehicles when active on the network
                    if is_rerouting and selected_trip_ids:
                        remaining_targets = selected_trip_ids - rerouted_vids
                        if remaining_targets:
                            active_vids = set(traci.vehicle.getIDList())
                            for vid in sorted(remaining_targets):
                                if vid in active_vids:
                                    try:
                                        cur_edge = traci.vehicle.getRoadID(vid)
                                        # Never reroute while inside junction internal lanes (e.g. starts with ':')
                                        if not cur_edge or cur_edge.startswith(":"):
                                            continue

                                        cur_route = list(traci.vehicle.getRoute(vid))
                                        cur_idx = traci.vehicle.getRouteIndex(vid)

                                        # Ensure vehicle has downstream edges ahead before rerouting
                                        if cur_idx < len(cur_route) - 2:
                                            dest_edge = cur_route[-1]
                                            bottleneck_edge = cur_route[min(cur_idx + 2, len(cur_route) - 2)]

                                            if reroute_mode == "travel_time_balanced":
                                                # Adapt edge travel time to penalize congested corridor segment
                                                traci.edge.adaptTraveltime(bottleneck_edge, 10000.0)
                                                traci.vehicle.rerouteTraveltime(vid, currentTravelTimes=True)
                                                traci.edge.adaptTraveltime(bottleneck_edge, -1)
                                                new_route = list(traci.vehicle.getRoute(vid))
                                                if new_route != cur_route and bottleneck_edge not in new_route:
                                                    rerouted_vids.add(vid)
                                                    reroute_records[vid] = {
                                                        "status": "success",
                                                        "mode": "travel_time_balanced",
                                                        "cur_edge": cur_edge,
                                                        "bottleneck_bypassed": bottleneck_edge,
                                                        "original_route_length": len(cur_route),
                                                        "new_route_length": len(new_route),
                                                    }
                                            else:
                                                # Mode: alternative_route
                                                traci.edge.adaptTraveltime(bottleneck_edge, 10000.0)
                                                alt_stage = traci.simulation.findRoute(cur_edge, dest_edge)
                                                traci.edge.adaptTraveltime(bottleneck_edge, -1)

                                                if (
                                                    alt_stage.edges
                                                    and list(alt_stage.edges) != cur_route[cur_idx:]
                                                    and bottleneck_edge not in alt_stage.edges
                                                    and alt_stage.edges[0] == cur_edge
                                                ):
                                                    full_new_route = cur_route[:cur_idx] + list(alt_stage.edges)
                                                    traci.vehicle.setRoute(vid, full_new_route)
                                                    verified_route = list(traci.vehicle.getRoute(vid))
                                                    if verified_route == full_new_route:
                                                        rerouted_vids.add(vid)
                                                        reroute_records[vid] = {
                                                            "status": "success",
                                                            "mode": "alternative_route",
                                                            "cur_edge": cur_edge,
                                                            "bottleneck_bypassed": bottleneck_edge,
                                                            "original_route_length": len(cur_route),
                                                            "new_route_length": len(full_new_route),
                                                        }
                                    except Exception as exc:
                                        logger.warning(f"Rerouting TraCI attempt failed for vehicle {vid}: {exc}")

                collector.finalize_active_vehicles(traci)

            except traci.exceptions.FatalTraCIError as exc:
                logger.error(f"Fatal TraCI error during simulation intervention: {exc}")
                raise SumoExecutionError(f"TraCI communication failure: {exc}") from exc
            except Exception as exc:
                logger.error(f"Simulation Agent runtime failure: {exc}")
                raise SumoExecutionError(f"Simulation execution failed: {exc}") from exc
            finally:
                self._ensure_clean_state()

        execution_metadata: Optional[Dict[str, Any]] = None
        if is_rerouting:
            actual_div_fraction = round(len(rerouted_vids) / total_eligible_count, 4) if total_eligible_count > 0 else 0.0

            if total_eligible_count == 0:
                exec_status = "no_eligible_vehicles"
                exec_reason = f"No trips found matching target corridor '{target_corr_key}' in demand scenario."
            elif len(rerouted_vids) == len(selected_trip_ids) and len(rerouted_vids) > 0:
                exec_status = "completed"
                exec_reason = f"Successfully rerouted {len(rerouted_vids)} of {total_eligible_count} eligible vehicles."
            elif len(rerouted_vids) > 0:
                exec_status = "partial"
                exec_reason = f"Rerouted {len(rerouted_vids)} of {len(selected_trip_ids)} selected vehicles (actual diversion {actual_div_fraction:.1%})."
            else:
                exec_status = "failed"
                exec_reason = "No valid alternative routes could be assigned to eligible vehicles."

            execution_metadata = {
                "status": exec_status,
                "reason": exec_reason,
                "target_corridor": intervention_details["target"],
                "requested_diversion_fraction": req_div_fraction,
                "actual_diversion_fraction": actual_div_fraction,
                "eligible_vehicle_count": total_eligible_count,
                "rerouted_vehicle_count": len(rerouted_vids),
                "rerouting_success": len(rerouted_vids) > 0,
                "alternative_route_count": len(rerouted_vids),
                "reroute_mode": reroute_mode,
                "rerouted_vehicles": [
                    {"vehicle_id": v_id, **v_info} for v_id, v_info in reroute_records.items()
                ],
            }
            intervention_details["execution"] = execution_metadata

        metrics = collector.calculate_summary()
        raw_corridors = collector.get_corridor_summaries()

        # Build CorridorMetric objects
        corridors: List[CorridorMetric] = []
        for c in raw_corridors:
            corridors.append(
                CorridorMetric(
                    id=c.get("id", "COR_UNKNOWN"),
                    name=c.get("name", "Unknown Corridor"),
                    avg_speed=c.get("avg_speed"),
                    status=c.get("status", "NO_DATA"),
                    value=c.get("value"),
                    color=c.get("color", "#64748b"),
                )
            )

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        metadata = SimulationMetadata(
            duration_seconds=duration,
            steps_simulated=duration,
            random_seed=seed,
            demand_profile=scenario,
            network_name="narayanguda_network.net.xml",
            timestamp=now_iso,
            step_length_sec=1.0,
        )

        source_info = SourceInfo(
            type="simulation",
            engine="SUMO",
            synthetic=True,
            network="narayanguda_network.net.xml",
            sumo_version="1.27.1",
            disclaimer=(
                f"Candidate intervention '{req.intervention.type.value if req.intervention else 'baseline'}' "
                f"executed in Eclipse SUMO microsimulation boundary under synthetic demand '{scenario}'."
            ),
        )

        target_name = req.intervention.target if req.intervention else None
        comparison = self._calculate_comparison(
            baseline_metrics=req.baseline_metrics,
            intervention_metrics=metrics,
            raw_corridors=raw_corridors,
            target_corridor=target_name,
            seed=seed,
            scenario_id=scenario_id,
            scenario=scenario,
            duration=duration,
            network_name="narayanguda_network.net.xml",
        )

        trade_offs = comparison.get("corridor_trade_offs", []) if comparison else []
        trade_off_sum = comparison.get("trade_off_summary") if comparison else None

        b_ref = req.baseline_reference or (comparison.get("baseline_reference") if comparison else None)
        b_summary = comparison.get("baseline_summary") if comparison else None

        return SimulationEvidenceResponse(
            scenario_id=scenario_id,
            scenario=scenario,
            duration_seconds=duration,
            seed=seed,
            network_name="narayanguda_network.net.xml",
            location=req.location,
            status="COMPLETED",
            intervention_applied=intervention_details,
            execution=execution_metadata,
            metrics=metrics,
            corridors=corridors,
            source=source_info,
            comparison=comparison,
            metadata=metadata,
            corridor_trade_offs=trade_offs,
            trade_off_summary=trade_off_sum,
            baseline_reference=b_ref,
            baseline_metrics=b_summary,
            average_speed_kmh=metrics.average_speed_kmh,
            average_delay_sec=metrics.average_delay_sec,
            average_waiting_time_sec=metrics.average_waiting_time_sec,
            congestion_index=metrics.congestion_index,
            throughput=metrics.throughput,
            total_vehicles=metrics.total_vehicles,
            teleported_vehicles=metrics.teleported_vehicles,
            max_halting_vehicles=metrics.max_halting_vehicles,
            arrived_vehicles=metrics.arrived_vehicles,
            active_at_end=metrics.active_at_end,
            completed_trips_avg_waiting_time_sec=metrics.completed_trips_avg_waiting_time_sec,
            completed_trips_avg_delay_sec=metrics.completed_trips_avg_delay_sec,
            completed_trips_avg_duration_sec=metrics.completed_trips_avg_duration_sec,
        )

    def _resolve_intervention_plan(
        self, intervention: Optional[InterventionPayload]
    ) -> Optional[Dict[str, Any]]:
        """
        Validates the candidate intervention and resolves target corridors/intersections
        to explicit, verified SUMO traffic-light IDs and phase adjustments.
        """
        if not intervention:
            return None

        # Handle Rerouting Intervention
        if intervention.type in (InterventionType.REROUTING, InterventionType.TRAFFIC_DIVERSION):
            target_str = str(intervention.target or "").strip().lower()
            params = intervention.parameters or {}

            matched_corridor = None
            for corr_name in ["westbound", "northbound", "southbound", "eastbound"]:
                if corr_name in target_str:
                    matched_corridor = corr_name
                    break

            if not matched_corridor:
                alias_map = {
                    "hyderguda": "westbound",
                    "cor_wb": "westbound",
                    "chikkadapally": "northbound",
                    "cor_nb": "northbound",
                    "barkatpura": "southbound",
                    "cor_sb": "southbound",
                    "himayat nagar": "eastbound",
                    "cor_eb": "eastbound",
                }
                for alias_k, c_name in alias_map.items():
                    if alias_k in target_str:
                        matched_corridor = c_name
                        break

            if not matched_corridor:
                raise ValueError(
                    f"Cannot map rerouting intervention target '{intervention.target}' to a known corridor. "
                    f"Supported corridor targets: Westbound, Northbound, Southbound, Eastbound."
                )

            # Defensive parameter bounds validation
            raw_div = params.get("diversion_fraction", 0.15)
            if raw_div is None or not isinstance(raw_div, (int, float)):
                raise ValueError(f"diversion_fraction must be a numeric value. Received: {raw_div}")
            div_frac = float(raw_div)
            if math.isnan(div_frac) or math.isinf(div_frac):
                raise ValueError("diversion_fraction must be a finite real number")
            if div_frac <= 0.0 or div_frac > 0.50:
                raise ValueError(
                    f"diversion_fraction must be strictly greater than 0.0 and less than or equal to 0.50. "
                    f"Received: {div_frac}"
                )

            reroute_mode = params.get("reroute_mode", "alternative_route")
            if reroute_mode not in ("alternative_route", "travel_time_balanced"):
                raise ValueError(
                    f"Unsupported reroute_mode '{reroute_mode}'. Supported modes: 'alternative_route', 'travel_time_balanced'"
                )

            return {
                "type": "rerouting",
                "applied": True,
                "target": matched_corridor.capitalize(),
                "target_corridor_key": matched_corridor,
                "parameters": {
                    "diversion_fraction": div_frac,
                    "reroute_mode": reroute_mode,
                    "alternative_arterial": params.get("alternative_arterial"),
                },
            }

        if intervention.type not in (InterventionType.SIGNAL_TIMING, InterventionType.ADAPTIVE_SIGNAL_CONTROL):
            logger.info(f"Intervention type '{intervention.type.value}' is candidate-only; running baseline reference.")
            return {"type": intervention.type.value, "applied": False, "note": f"Intervention '{intervention.type.value}' is candidate-only in this milestone"}

        target_str = str(intervention.target or "").strip().lower()
        params = intervention.parameters or {}

        # 1. Check if an explicit known intersection ID was supplied
        explicit_intersection = params.get("target_intersection") or params.get("intersection_id")
        if explicit_intersection and explicit_intersection in KNOWN_INTERSECTIONS:
            phase_idx = int(params.get("phase_index", 0))
            delta_sec = float(params.get("green_time_adjustment_sec", 15.0))
            return {
                "type": "signal_timing",
                "applied": True,
                "target": explicit_intersection,
                "adjustments": [(explicit_intersection, phase_idx, delta_sec)],
            }

        # 2. Check corridor mapping
        matched_adjustments: List[Tuple[str, int, float]] = []
        for corr_token, adj_list in CORRIDOR_TLS_MAPPING.items():
            if corr_token in target_str:
                matched_adjustments.extend(adj_list)
                break

        if not matched_adjustments:
            # Check if any known intersection ID matches
            for known_id in KNOWN_INTERSECTIONS:
                if known_id.lower() in target_str:
                    matched_adjustments.append((known_id, 0, 15.0))
                    break

        if not matched_adjustments:
            raise ValueError(
                f"Cannot map intervention target '{intervention.target}' to a verified Narayanguda traffic light. "
                f"Supported corridor targets: Westbound, Northbound, Southbound, Eastbound, or explicit intersection ID."
            )

        # Allow parameter override of delta seconds if specified
        custom_boost = params.get("green_time_adjustment_sec")
        if custom_boost is not None:
            boost_val = float(custom_boost)
            matched_adjustments = [(tls_id, p_idx, boost_val) for (tls_id, p_idx, _) in matched_adjustments]

        return {
            "type": "signal_timing",
            "applied": True,
            "target": intervention.target,
            "adjustments": matched_adjustments,
        }

    def _apply_signal_adjustments(self, plan: Dict[str, Any]) -> None:
        """
        Dynamically modifies traffic light logic via TraCI without touching .net.xml.
        """
        adjustments = plan.get("adjustments", [])
        for tls_id, target_phase_idx, delta_sec in adjustments:
            try:
                # Retrieve current logic for the traffic light
                logics = traci.trafficlight.getCompleteRedYellowGreenDefinition(tls_id)
                if not logics:
                    logger.warning(f"No logic definition found for traffic light {tls_id}")
                    continue

                logic = logics[0]
                phases = list(logic.phases)
                if target_phase_idx >= len(phases):
                    logger.warning(
                        f"Phase index {target_phase_idx} out of range for {tls_id} (total phases: {len(phases)})"
                    )
                    continue

                # Adjust the duration of the green phase
                curr_dur = phases[target_phase_idx].duration
                new_dur = max(5.0, curr_dur + delta_sec)
                phases[target_phase_idx] = traci.trafficlight.Phase(new_dur, phases[target_phase_idx].state)

                # If reducing opposing phase to maintain approximate cycle time
                opposing_phase_idx = 2 if target_phase_idx == 0 and len(phases) > 2 else (
                    0 if target_phase_idx == 2 and len(phases) > 2 else None
                )
                if opposing_phase_idx is not None and len(phases) > opposing_phase_idx:
                    opp_dur = phases[opposing_phase_idx].duration
                    if opp_dur > delta_sec + 5.0:
                        phases[opposing_phase_idx] = traci.trafficlight.Phase(
                            opp_dur - delta_sec, phases[opposing_phase_idx].state
                        )

                logic.phases = tuple(phases)
                traci.trafficlight.setCompleteRedYellowGreenDefinition(tls_id, logic)
                logger.info(
                    f"Modified traffic light {tls_id} Phase {target_phase_idx}: {curr_dur}s -> {new_dur}s "
                    f"(opposing phase {opposing_phase_idx} adjusted)"
                )
            except Exception as exc:
                logger.error(f"Failed to apply signal adjustment on {tls_id}: {exc}")
                raise

    @staticmethod
    def _calculate_comparison(
        baseline_metrics: Optional[Dict[str, Any]],
        intervention_metrics: SimulationMetrics,
        raw_corridors: List[Dict[str, Any]],
        target_corridor: Optional[str] = None,
        seed: int = 42,
        scenario_id: Optional[str] = None,
        scenario: Optional[str] = None,
        duration: Optional[int] = None,
        network_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calculates exact mathematical comparisons between baseline and intervention metrics.
        Returns explicit 'baseline_missing' status with fair_comparison=False if baseline data is absent.
        """
        int_speed = intervention_metrics.average_speed_kmh
        int_delay = intervention_metrics.average_delay_sec
        int_wait = intervention_metrics.average_waiting_time_sec
        int_cong = intervention_metrics.congestion_index
        int_tp = intervention_metrics.throughput
        int_teleport = intervention_metrics.teleported_vehicles
        int_halting = intervention_metrics.max_halting_vehicles

        # If baseline evidence was not supplied or is not a dictionary, report explicit missing status
        if not baseline_metrics or not isinstance(baseline_metrics, dict):
            return {
                "status": "baseline_missing",
                "fair_comparison": False,
                "scenario_id": scenario_id,
                "baseline_seed": None,
                "intervention_seed": seed,
                "baseline_scenario": None,
                "intervention_scenario": scenario,
                "message": "Comparison unavailable — baseline evidence was not supplied.",
                "baseline_summary": None,
                "intervention_summary": {
                    "average_speed_kmh": int_speed,
                    "average_delay_sec": int_delay,
                    "average_waiting_time_sec": int_wait,
                    "congestion_index": int_cong,
                    "throughput": int_tp,
                },
                "speed_change_pct": None,
                "delay_reduction_pct": None,
                "waiting_time_reduction_pct": None,
                "congestion_reduction_pct": None,
                "throughput_change": None,
                "corridor_comparisons": [],
                "corridor_trade_offs": [],
            }

        # Guard: An intervention MUST NOT be used as a baseline (prevent intervention chaining)
        b_scen_id = str(baseline_metrics.get("scenario_id") or "").lower()
        b_int_app = baseline_metrics.get("intervention_applied")
        b_int = baseline_metrics.get("intervention")
        is_int = (
            (b_int_app and isinstance(b_int_app, dict) and bool(b_int_app.get("type") or b_int_app.get("target") or b_int_app.get("parameters")))
            or (b_int and isinstance(b_int, dict) and bool(b_int.get("type") or b_int.get("target") or b_int.get("parameters")))
            or b_scen_id.startswith(("signal_timing", "rerouting", "lane_reversal", "speed_limit"))
        )
        if is_int:
            logger.error(
                f"Multi-intervention chaining rejected: Attempted to use intervention '{b_scen_id}' as baseline for '{scenario_id}'. "
                f"All interventions must be compared against a canonical baseline."
            )
            return {
                "status": "baseline_invalid_intervention",
                "fair_comparison": False,
                "scenario_id": scenario_id,
                "baseline_seed": None,
                "intervention_seed": seed,
                "baseline_scenario": None,
                "intervention_scenario": scenario,
                "message": f"Comparison invalid — attempted to use intervention '{b_scen_id}' as baseline. Interventions cannot be chained.",
                "baseline_summary": None,
                "intervention_summary": {
                    "average_speed_kmh": int_speed,
                    "average_delay_sec": int_delay,
                    "average_waiting_time_sec": int_wait,
                    "congestion_index": int_cong,
                    "throughput": int_tp,
                },
                "speed_change_pct": None,
                "delay_reduction_pct": None,
                "waiting_time_reduction_pct": None,
                "congestion_reduction_pct": None,
                "throughput_change": None,
                "corridor_comparisons": [],
                "corridor_trade_offs": [],
            }

        # Flexible baseline scalar extraction across top-level, nested 'metrics', or 'baseline_summary'
        b_metrics = baseline_metrics.get("metrics") if isinstance(baseline_metrics.get("metrics"), dict) else {}
        b_summary = baseline_metrics.get("baseline_summary") if isinstance(baseline_metrics.get("baseline_summary"), dict) else {}

        def _get_val(key: str, *alt_keys: str) -> Optional[float]:
            for k in (key, *alt_keys):
                for src in (baseline_metrics, b_metrics, b_summary):
                    if isinstance(src, dict) and src.get(k) is not None:
                        try:
                            return float(src[k])
                        except (ValueError, TypeError):
                            pass
            return None

        base_speed = _get_val("average_speed_kmh", "speed_kmh", "network_average_speed_kmh", "avg_speed")
        base_delay = _get_val("average_delay_sec", "delay_sec", "network_average_delay_s", "avg_delay")
        base_wait = _get_val("average_waiting_time_sec", "waiting_time_sec", "waiting_sec", "network_average_waiting_time_s", "avg_waiting")
        base_cong = _get_val("congestion_index", "congestion")
        base_tp = _get_val("throughput", "total_arrived") or 0
        base_teleport = _get_val("teleported_vehicles") or 0
        base_halting = _get_val("max_halting_vehicles") or 0

        # If baseline scalar speed and delay are completely missing, reject fake comparison
        if base_speed is None and base_delay is None and base_wait is None:
            return {
                "status": "baseline_missing",
                "fair_comparison": False,
                "scenario_id": scenario_id,
                "baseline_seed": None,
                "intervention_seed": seed,
                "baseline_scenario": None,
                "intervention_scenario": scenario,
                "message": "Comparison unavailable — baseline evidence was not supplied.",
                "baseline_summary": None,
                "intervention_summary": {
                    "average_speed_kmh": int_speed,
                    "average_delay_sec": int_delay,
                    "average_waiting_time_sec": int_wait,
                    "congestion_index": int_cong,
                    "throughput": int_tp,
                },
                "speed_change_pct": None,
                "delay_reduction_pct": None,
                "waiting_time_reduction_pct": None,
                "congestion_reduction_pct": None,
                "throughput_change": None,
                "corridor_comparisons": [],
                "corridor_trade_offs": [],
            }

        # Calculate network metric deltas
        speed_change_kmh = None
        if base_speed is not None and int_speed is not None:
            speed_change_kmh = round(int_speed - base_speed, 2)

        # Speed: positive percentage = higher speed (improvement)
        speed_change_pct = None
        if base_speed is not None and int_speed is not None and base_speed > 0:
            speed_change_pct = round(((int_speed - base_speed) / base_speed) * 100.0, 2)

        # --- LEGACY fields (reduction semantics: positive = improvement) ---
        # These are kept for backward compatibility with existing tests/consumers.
        # Do NOT use these in new logic; use *_change_pct below instead.
        delay_reduction_pct = None
        if base_delay is not None and int_delay is not None and base_delay > 0:
            delay_reduction_pct = round(((base_delay - int_delay) / base_delay) * 100.0, 2)

        waiting_time_reduction_pct = None
        if base_wait is not None and int_wait is not None and base_wait > 0:
            waiting_time_reduction_pct = round(((base_wait - int_wait) / base_wait) * 100.0, 2)

        congestion_reduction_pct = None
        if base_cong is not None and int_cong is not None and base_cong > 0:
            congestion_reduction_pct = round(((base_cong - int_cong) / base_cong) * 100.0, 2)

        # --- NEW signed change fields (raw signed delta: positive = worsened for delay/waiting/congestion) ---
        # speed_change_pct:         positive = improved (higher speed is better)
        # delay_change_pct:         negative = improved (lower delay is better)
        # waiting_time_change_pct:  negative = improved (lower waiting is better)
        # congestion_change_pct:    negative = improved (lower congestion is better)
        # throughput_change:        positive = improved (more arrivals is better)
        delay_change_pct = None
        if base_delay is not None and int_delay is not None and base_delay > 0:
            delay_change_pct = round(((int_delay - base_delay) / base_delay) * 100.0, 2)

        waiting_time_change_pct = None
        if base_wait is not None and int_wait is not None and base_wait > 0:
            waiting_time_change_pct = round(((int_wait - base_wait) / base_wait) * 100.0, 2)

        congestion_change_pct = None
        if base_cong is not None and int_cong is not None and base_cong > 0:
            congestion_change_pct = round(((int_cong - base_cong) / base_cong) * 100.0, 2)

        throughput_change = (int_tp or 0) - (base_tp or 0)
        max_halting_change = (int_halting or 0) - (base_halting or 0)
        teleported_vehicle_change = (int_teleport or 0) - (base_teleport or 0)

        # Baseline corridor speed extraction supporting dict or list format
        base_corridor_speeds: Dict[str, float] = {}
        if isinstance(baseline_metrics.get("corridor_speeds"), dict):
            for k, v in baseline_metrics["corridor_speeds"].items():
                if v is not None:
                    try:
                        base_corridor_speeds[str(k).lower().strip()] = float(v)
                    except (ValueError, TypeError):
                        pass

        b_corridors = baseline_metrics.get("corridors", [])
        if isinstance(b_corridors, list):
            for c in b_corridors:
                if isinstance(c, dict):
                    cid = c.get("id")
                    cname = c.get("name")
                    cspd = c.get("avg_speed") or c.get("speed_kmh")
                    if cspd is not None:
                        try:
                            f_spd = float(cspd)
                            if cid:
                                base_corridor_speeds[str(cid).lower().strip()] = f_spd
                            if cname:
                                base_corridor_speeds[str(cname).lower().strip()] = f_spd
                        except (ValueError, TypeError):
                            pass

        corridor_comparisons: List[Dict[str, Any]] = []
        corridor_trade_offs: List[str] = []
        target_comp = None

        for int_c in raw_corridors:
            cid = int_c.get("id")
            c_name = int_c.get("name")
            int_c_spd = int_c.get("avg_speed")

            base_c_spd = None
            if cid and str(cid).lower().strip() in base_corridor_speeds:
                base_c_spd = base_corridor_speeds[str(cid).lower().strip()]
            elif c_name and str(c_name).lower().strip() in base_corridor_speeds:
                base_c_spd = base_corridor_speeds[str(c_name).lower().strip()]
            else:
                for b_key, b_val in base_corridor_speeds.items():
                    if (cid and b_key in str(cid).lower()) or (c_name and b_key in str(c_name).lower()):
                        base_c_spd = b_val
                        break

            c_delta_kmh = None
            c_delta_pct = None
            if base_c_spd is not None and int_c_spd is not None:
                c_delta_kmh = round(int_c_spd - base_c_spd, 2)
                if base_c_spd > 0:
                    c_delta_pct = round(((int_c_spd - base_c_spd) / base_c_spd) * 100.0, 2)

            is_target = bool(target_corridor and (target_corridor.lower() in str(c_name or "").lower() or (cid and target_corridor.lower() in str(cid).lower())))

            comp_obj = {
                "id": cid,
                "name": c_name,
                "baseline_speed_kmh": base_c_spd,
                "intervention_speed_kmh": int_c_spd,
                "speed_change_kmh": c_delta_kmh,
                "speed_change_pct": c_delta_pct,
                "is_target": is_target,
            }
            corridor_comparisons.append(comp_obj)

            if is_target:
                target_comp = comp_obj

            # Track corridors that degraded (trade-offs)
            if c_delta_pct is not None and c_delta_pct < -0.5:
                corridor_trade_offs.append(f"{c_name}: {c_delta_pct:+.1f}% ({base_c_spd} -> {int_c_spd} km/h)")

        # Rigorous fair comparison verification: seed, duration, scenario, network
        b_meta = baseline_metrics.get("metadata", {}) if isinstance(baseline_metrics.get("metadata"), dict) else {}
        b_seed = baseline_metrics.get("seed") if baseline_metrics.get("seed") is not None else b_meta.get("random_seed")
        b_scenario = baseline_metrics.get("scenario_name") or baseline_metrics.get("scenario") or b_meta.get("demand_profile")
        b_dur = baseline_metrics.get("duration_seconds") if baseline_metrics.get("duration_seconds") is not None else b_meta.get("duration_seconds")
        b_net = baseline_metrics.get("network_name") or b_meta.get("network_name") or (baseline_metrics.get("source", {}).get("network") if isinstance(baseline_metrics.get("source"), dict) else None)

        mismatches: List[str] = []
        seed_mismatch = (b_seed is None or int(b_seed) != int(seed))
        if seed_mismatch:
            mismatches.append(f"seed (baseline={b_seed}, intervention={seed})")
        if duration is not None and b_dur is not None and int(b_dur) != int(duration):
            mismatches.append(f"duration (baseline={b_dur}s, intervention={duration}s)")
        if scenario is not None and b_scenario is not None and str(b_scenario).strip().lower() != str(scenario).strip().lower():
            mismatches.append(f"scenario (baseline={b_scenario}, intervention={scenario})")
        if network_name is not None and b_net is not None and str(b_net).strip().lower() != str(network_name).strip().lower():
            mismatches.append(f"network (baseline={b_net}, intervention={network_name})")

        fair_comparison = (len(mismatches) == 0 and b_seed is not None)
        fair_comparison_warning = None
        if not fair_comparison:
            if seed_mismatch and b_seed is not None:
                fair_comparison_warning = (
                    f"Random seeds differ (baseline seed={b_seed}, intervention seed={seed}). "
                    "Comparison may reflect stochastic divergence. Paired comparison is NOT FAIR."
                )
            elif mismatches:
                fair_comparison_warning = f"Paired comparison invalid due to mismatched conditions: {', '.join(mismatches)}. Comparison is NOT FAIR."
            elif b_seed is None:
                fair_comparison_warning = "Baseline seed unknown. Fair comparison cannot be formally verified."

        # Synthesize trade-off summary using NEW signed delay_change_pct
        trade_off_parts = []
        if target_comp and target_comp.get("speed_change_pct") is not None:
            trade_off_parts.append(f"Target corridor '{target_comp['name']}' speed changed by {target_comp['speed_change_pct']:+.1f}%.")
        if corridor_trade_offs:
            trade_off_parts.append(f"Trade-offs observed on {len(corridor_trade_offs)} other corridor(s): {'; '.join(corridor_trade_offs)}.")
        if delay_change_pct is not None:
            if delay_change_pct > 0:
                trade_off_parts.append(f"Network delay worsened by {delay_change_pct:.1f}%.")
            elif delay_change_pct < 0:
                trade_off_parts.append(f"Network delay improved by {abs(delay_change_pct):.1f}%.")

        trade_off_summary = " ".join(trade_off_parts) if trade_off_parts else None

        return {
            "status": "SUCCESS",
            "scenario_id": scenario_id,
            # Speed (positive = improved)
            "speed_change_kmh": speed_change_kmh,
            "speed_change_pct": speed_change_pct,
            # NEW signed change fields: negative = improved for delay/waiting/congestion
            "delay_change_pct": delay_change_pct,
            "waiting_time_change_pct": waiting_time_change_pct,
            "congestion_change_pct": congestion_change_pct,
            # LEGACY reduction fields (positive = improved): kept for backward compatibility
            "delay_reduction_pct": delay_reduction_pct,
            "waiting_time_reduction_pct": waiting_time_reduction_pct,
            "congestion_reduction_pct": congestion_reduction_pct,
            # Throughput (positive = more arrivals = improved)
            "throughput_change": throughput_change,
            "max_halting_change": max_halting_change,
            "teleported_vehicle_change": teleported_vehicle_change,
            "corridor_comparisons": corridor_comparisons,
            "corridor_trade_offs": corridor_trade_offs,
            "trade_off_summary": trade_off_summary,
            "target_corridor_speed_change_pct": target_comp.get("speed_change_pct") if target_comp else None,
            "fair_comparison": fair_comparison,
            "fair_comparison_warning": fair_comparison_warning,
            "baseline_seed": b_seed,
            "intervention_seed": seed,
            "baseline_duration_seconds": b_dur,
            "intervention_duration_seconds": duration,
            "baseline_scenario": b_scenario,
            "intervention_scenario": scenario,
            "baseline_network": b_net,
            "intervention_network": network_name,
            "baseline_summary": {
                "average_speed_kmh": base_speed,
                "average_delay_sec": base_delay,
                "average_waiting_time_sec": base_wait,
                "congestion_index": base_cong,
                "throughput": base_tp,
            },
            "intervention_summary": {
                "average_speed_kmh": int_speed,
                "average_delay_sec": int_delay,
                "average_waiting_time_sec": int_wait,
                "congestion_index": int_cong,
                "throughput": int_tp,
            },
            "baseline_reference": baseline_metrics.get("baseline_reference") or {
                "scenario_id": baseline_metrics.get("scenario_id") or f"baseline:dur{b_dur}s:seed{b_seed}",
                "scenario": b_scenario,
                "duration_seconds": b_dur,
                "seed": b_seed,
                "network": b_net,
            },
        }


    @staticmethod
    def _ensure_clean_state() -> None:
        """Safely terminates any active TraCI connection without raising."""
        try:
            if traci.isLoaded():
                traci.close()
        except Exception:
            pass


_service_instance: Optional[SimulationService] = None


def get_simulation_service() -> SimulationService:
    global _service_instance
    if _service_instance is None:
        _service_instance = SimulationService()
    return _service_instance
