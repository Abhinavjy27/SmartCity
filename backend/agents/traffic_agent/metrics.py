"""
Metrics Collector and Mathematical Estimators for SUMO TraCI Simulation.
Extracts empirical microscopic telemetry directly from TraCI at each simulation step
using a per-vehicle lifecycle ledger. Eliminates running-counter distortion and fabrication.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from backend.agents.traffic_agent.schemas import SimulationMetrics


@dataclass
class VehicleRecord:
    """Per-vehicle lifecycle ledger tracking individual vehicle trip trajectory."""

    vid: str
    corridor: Optional[str] = None
    depart_time: Optional[float] = None
    arrival_time: Optional[float] = None
    accumulated_waiting_time: float = 0.0
    final_time_loss: float = 0.0
    arrived: bool = False
    teleported: bool = False


class SumoMetricsCollector:
    """
    Accumulates raw microscopic telemetry across TraCI simulation steps using an explicit
    vehicle ledger to compute mathematically sound aggregate indicators.
    """

    def __init__(self, free_flow_speed_kmh: float = 50.0, step_duration_sec: float = 1.0):
        self.free_flow_speed_kmh = free_flow_speed_kmh
        self.step_duration_sec = step_duration_sec
        self.reset()

    def reset(self) -> None:
        self.step_count = 0
        self.active_vehicle_counts: List[int] = []
        self.vehicles: Dict[str, VehicleRecord] = {}
        self.speed_observations_ms: List[float] = []
        self.halting_samples: List[int] = []
        self.teleported_vids: Set[str] = set()
        self.corridor_speeds: Dict[str, List[float]] = {
            "northbound": [],
            "southbound": [],
            "eastbound": [],
            "westbound": [],
        }

    @staticmethod
    def _extract_corridor(vid: str) -> Optional[str]:
        parts = vid.split("_")
        if len(parts) >= 3 and parts[1] in ("northbound", "southbound", "eastbound", "westbound"):
            return parts[1]
        return None

    def record_step(self, traci_module: Any) -> None:
        """Invoked after each traci.simulationStep()."""
        self.step_count += 1
        current_time = float(self.step_count * self.step_duration_sec)

        # 1. Track teleported vehicles (gridlock timeout)
        try:
            starting_teleports = traci_module.simulation.getStartingTeleportIDList()
            if starting_teleports:
                self.teleported_vids.update(starting_teleports)
                for vid in starting_teleports:
                    if vid in self.vehicles:
                        self.vehicles[vid].teleported = True
        except Exception:
            pass

        # 2. Track newly departed vehicles
        try:
            departed = traci_module.simulation.getDepartedIDList()
            for vid in departed:
                if vid not in self.vehicles:
                    self.vehicles[vid] = VehicleRecord(
                        vid=vid,
                        corridor=self._extract_corridor(vid),
                        depart_time=current_time,
                    )
        except Exception:
            pass

        # 3. Microscopic metrics across active vehicles
        active_vids = traci_module.vehicle.getIDList()
        self.active_vehicle_counts.append(len(active_vids))

        step_halting = 0
        for vid in active_vids:
            try:
                spd_ms = traci_module.vehicle.getSpeed(vid)
                tl_sec = traci_module.vehicle.getTimeLoss(vid)
                self.speed_observations_ms.append(spd_ms)

                if vid not in self.vehicles:
                    self.vehicles[vid] = VehicleRecord(
                        vid=vid,
                        corridor=self._extract_corridor(vid),
                        depart_time=current_time,
                    )

                rec = self.vehicles[vid]
                rec.final_time_loss = tl_sec

                # True accumulated waiting time: accrue step duration whenever speed < 0.1 m/s
                if spd_ms < 0.1:
                    rec.accumulated_waiting_time += self.step_duration_sec
                    step_halting += 1

                if rec.corridor and rec.corridor in self.corridor_speeds:
                    self.corridor_speeds[rec.corridor].append(spd_ms * 3.6)
            except Exception:
                # Vehicle may have transitioned/arrived during step
                pass

        self.halting_samples.append(step_halting)

        # 4. Track arrived vehicles
        try:
            arrived = traci_module.simulation.getArrivedIDList()
            for vid in arrived:
                if vid in self.vehicles:
                    self.vehicles[vid].arrived = True
                    self.vehicles[vid].arrival_time = current_time
        except Exception:
            pass

    def finalize_active_vehicles(self, traci_module: Any) -> None:
        """
        Invoked at the conclusion of the simulation before TraCI disconnects.
        Captures terminal time loss for all vehicles still active on the network.
        """
        try:
            active_vids = traci_module.vehicle.getIDList()
            for vid in active_vids:
                if vid in self.vehicles:
                    self.vehicles[vid].final_time_loss = traci_module.vehicle.getTimeLoss(vid)
        except Exception:
            pass

    def calculate_summary(self) -> SimulationMetrics:
        """
        Compute final empirical metrics from the vehicle ledger.
        Formula documentation:
        - total_vehicles: count of unique simulated vehicles in ledger (0 if empty)
        - average_speed_kmh: mean of vehicle speed observations * 3.6, or None if no observations
        - average_waiting_time_sec: sum(vehicle.accumulated_waiting_time) / total_vehicles, or None if no vehicles
        - average_delay_sec: sum(vehicle.final_time_loss) / total_vehicles, or None if no vehicles
        - throughput: count of vehicles that arrived at destination during duration
        - congestion_index: max(0.0, min(1.0, 1.0 - speed/free_flow_speed)) or None if no observations
        - completed_trips_avg_waiting_time_sec: mean waiting time for arrived vehicles (un-diluted by truncation)
        - completed_trips_avg_delay_sec: mean delay (time loss) for arrived vehicles (un-diluted by truncation)
        - completed_trips_avg_duration_sec: mean trip travel time for arrived vehicles
        """
        total_simulated = len(self.vehicles)

        avg_active = (
            int(round(sum(self.active_vehicle_counts) / len(self.active_vehicle_counts)))
            if self.active_vehicle_counts
            else 0
        )
        peak_active = max(self.active_vehicle_counts) if self.active_vehicle_counts else 0
        finished = [v for v in self.vehicles.values() if v.arrived]
        throughput = len(finished)
        active_at_end = total_simulated - throughput
        teleported_count = len(self.teleported_vids)
        max_halt = max(self.halting_samples) if self.halting_samples else 0

        # 1. Average Speed (None if zero observations; never fabricate free-flow speed)
        if self.speed_observations_ms:
            avg_speed_kmh = round((sum(self.speed_observations_ms) / len(self.speed_observations_ms)) * 3.6, 2)
        else:
            avg_speed_kmh = None

        # 2. Average Waiting Time (per-vehicle accumulated wait time across all simulated vehicles)
        if total_simulated > 0:
            total_wait = sum(v.accumulated_waiting_time for v in self.vehicles.values())
            avg_waiting_time_sec = round(total_wait / total_simulated, 2)
        else:
            avg_waiting_time_sec = None

        # 3. Average Delay (final time loss per simulated vehicle across all simulated vehicles)
        if total_simulated > 0:
            total_delay = sum(v.final_time_loss for v in self.vehicles.values())
            avg_delay_sec = round(total_delay / total_simulated, 2)
        else:
            avg_delay_sec = None

        # 4. Congestion Index (None if zero observations; never report 0.0 on empty network)
        if avg_speed_kmh is not None:
            congestion_index = round(max(0.0, min(1.0, 1.0 - (avg_speed_kmh / self.free_flow_speed_kmh))), 3)
        else:
            congestion_index = None

        # 5. Completed Trip Metrics (strictly for vehicles that traversed their full route)
        if finished:
            completed_wait = round(sum(v.accumulated_waiting_time for v in finished) / len(finished), 2)
            completed_delay = round(sum(v.final_time_loss for v in finished) / len(finished), 2)
            durations = [
                v.arrival_time - v.depart_time
                for v in finished
                if v.arrival_time is not None and v.depart_time is not None
            ]
            completed_dur = round(sum(durations) / len(durations), 1) if durations else None
        else:
            completed_wait = None
            completed_delay = None
            completed_dur = None

        return SimulationMetrics(
            active_vehicles=avg_active,
            peak_active_vehicles=peak_active,
            total_vehicles=total_simulated,
            average_speed_kmh=avg_speed_kmh,
            average_waiting_time_sec=avg_waiting_time_sec,
            average_delay_sec=avg_delay_sec,
            throughput=throughput,
            congestion_index=congestion_index,
            max_halting_vehicles=max_halt,
            teleported_vehicles=teleported_count,
            free_flow_speed_kmh=self.free_flow_speed_kmh,
            arrived_vehicles=throughput,
            active_at_end=active_at_end,
            completed_trips_avg_waiting_time_sec=completed_wait,
            completed_trips_avg_delay_sec=completed_delay,
            completed_trips_avg_duration_sec=completed_dur,
        )

    def get_corridor_summaries(self) -> List[Dict[str, Any]]:
        """
        Compute empirical corridor speed breakdown.
        When a corridor has no vehicle observations, returns None and status 'NO_DATA'
        with zero fabricated speed values.
        """
        corridors_def = [
            {"id": "COR_NB", "key": "northbound", "name": "Narayanguda - Chikkadapally Corridor (Northbound)"},
            {"id": "COR_SB", "key": "southbound", "name": "Narayanguda - Barkatpura Corridor (Southbound)"},
            {"id": "COR_EB", "key": "eastbound", "name": "Himayat Nagar - Barkatpura (Eastbound)"},
            {"id": "COR_WB", "key": "westbound", "name": "Narayanguda - Hyderguda (Westbound)"},
        ]
        results = []
        for c in corridors_def:
            speeds = self.corridor_speeds.get(c["key"], [])
            if speeds:
                avg_sp = round(sum(speeds) / len(speeds), 1)
                cong_pct = round(max(0.0, min(100.0, (1.0 - avg_sp / self.free_flow_speed_kmh) * 100)), 1)
                if avg_sp >= 35.0:
                    status, color = "SMOOTH", "#10b981"
                elif avg_sp >= 22.0:
                    status, color = "MODERATE", "#f59e0b"
                elif avg_sp >= 14.0:
                    status, color = "HEAVY", "#f43f5e"
                else:
                    status, color = "CRITICAL", "#991b1b"
            else:
                # Strictly NO_DATA when no vehicles traversed the corridor
                avg_sp = None
                status = "NO_DATA"
                cong_pct = None
                color = "#6b7280"

            results.append({
                "id": c["id"],
                "name": c["name"],
                "avg_speed": avg_sp,
                "status": status,
                "value": cong_pct,
                "color": color,
            })
        return results
