"""
Eclipse SUMO Process Runner and TraCI Lifecycle Controller.
Safely connects, steps, collects microscopic telemetry, and guarantees clean TraCI termination.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
import threading
from typing import Any, Dict, List, Optional, Tuple

import traci
import traci.exceptions

from backend.agents.traffic_agent.metrics import SumoMetricsCollector
from backend.agents.traffic_agent.schemas import SimulationMetrics

logger = logging.getLogger(__name__)


class SumoExecutionError(Exception):
    """Raised when SUMO fails to locate, configure, launch, or execute."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


class SumoRunner:
    """
    Manages SUMO execution and TraCI communication.
    Ensures safe single-instance or labeled connection lifecycles with guaranteed cleanup.
    """

    _lock = threading.Lock()

    def __init__(self, sumo_binary: Optional[str] = None):
        self.sumo_binary = self._resolve_sumo_binary(sumo_binary)

    @staticmethod
    def _resolve_sumo_binary(preferred: Optional[str] = None) -> str:
        """Finds the SUMO executable across environment variables and standard install paths."""
        candidates = []
        if preferred:
            candidates.append(preferred)

        env_bin = os.getenv("SUMO_BINARY")
        if env_bin:
            candidates.append(env_bin)

        which_sumo = shutil.which("sumo")
        if which_sumo:
            candidates.append(which_sumo)

        sumo_home = os.getenv("SUMO_HOME")
        if sumo_home:
            candidates.append(os.path.join(sumo_home, "bin", "sumo.exe"))
            candidates.append(os.path.join(sumo_home, "bin", "sumo"))

        candidates.extend([
            r"C:\Program Files (x86)\Eclipse\Sumo\bin\sumo.exe",
            r"C:\Program Files\Eclipse\Sumo\bin\sumo.exe",
            "/usr/bin/sumo",
            "/usr/local/bin/sumo",
        ])

        for path in candidates:
            if path and os.path.isfile(path) and os.access(path, os.X_OK):
                return path

        # Fallback to plain binary name if in PATH
        if which_sumo:
            return which_sumo

        raise SumoExecutionError(
            "Eclipse SUMO executable not found. Ensure SUMO 1.27.1 is installed and SUMO_HOME is set."
        )

    def run_simulation(
        self,
        net_file: str,
        route_file: str,
        duration_seconds: int = 120,
        free_flow_speed_kmh: float = 50.0,
        time_to_teleport: int = 300,
    ) -> Tuple[SimulationMetrics, List[Dict[str, Any]]]:
        """
        Executes a headless SUMO simulation for duration_seconds, accumulating microscopic
        vehicle telemetry and returning empirical metrics.
        Guarantees TraCI is closed cleanly even if an exception occurs.
        """
        if not os.path.isfile(net_file):
            raise SumoExecutionError(f"Network file not found: {net_file}", {"net_file": net_file})
        if not os.path.isfile(route_file):
            raise SumoExecutionError(f"Route file not found: {route_file}", {"route_file": route_file})

        # TraCI commands are thread-locked to protect single-port connections
        with self._lock:
            # Ensure any dangling connection is closed before starting
            self._ensure_clean_state()

            cmd = [
                self.sumo_binary,
                "-n",
                net_file,
                "-r",
                route_file,
                "--no-step-log",
                "true",
                "--time-to-teleport",
                str(time_to_teleport),
                "--waiting-time-memory",
                str(duration_seconds),
                "--no-warnings",
                "true",
            ]

            collector = SumoMetricsCollector(free_flow_speed_kmh=free_flow_speed_kmh)

            try:
                traci.start(cmd)
                logger.info(f"Started SUMO simulation: {net_file} with {route_file} for {duration_seconds}s")

                for _ in range(duration_seconds):
                    traci.simulationStep()
                    collector.record_step(traci)

                collector.finalize_active_vehicles(traci)

            except traci.exceptions.FatalTraCIError as exc:
                logger.error(f"Fatal TraCI simulation error: {exc}")
                raise SumoExecutionError(f"TraCI communication failed: {exc}") from exc
            except Exception as exc:
                logger.error(f"SUMO simulation runtime failure: {exc}")
                raise SumoExecutionError(f"SUMO simulation failed: {exc}") from exc
            finally:
                self._ensure_clean_state()

            summary = collector.calculate_summary()
            corridors = collector.get_corridor_summaries()
            return summary, corridors

    @staticmethod
    def _ensure_clean_state() -> None:
        """Safely terminates any active TraCI connection without raising."""
        try:
            if traci.isLoaded():
                traci.close()
        except Exception:
            pass
