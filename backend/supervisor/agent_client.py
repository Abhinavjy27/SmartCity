"""
SUPADSP Specialist Agent Transport & Client.
Handles dispatching workflow capabilities to specialist agents via HTTP or in-process ASGI execution for local development.
"""

from __future__ import annotations

import importlib
import os
from typing import Any, Dict, Optional

import requests
from fastapi.testclient import TestClient


AGENT_REGISTRY: Dict[str, Dict[str, Any]] = {
    "traffic": {
        "agent_name": "traffic_agent",
        "env_url_key": "TRAFFIC_AGENT_URL",
        "endpoint": "/api/v1/traffic/kpis",
        "method": "GET",
        "module_path": "backend.agents.traffic_agent.main",
    },
    "weather": {
        "agent_name": "weather_agent",
        "env_url_key": "WEATHER_AGENT_URL",
        "endpoint": "/api/v1/weather/current",
        "method": "GET",
        "module_path": "backend.agents.weather_agent.main",
    },
    "energy": {
        "agent_name": "energy_agent",
        "env_url_key": "ENERGY_AGENT_URL",
        "endpoint": "/api/v1/energy/grid-status",
        "method": "GET",
        "module_path": "backend.agents.energy_agent.main",
    },
    "pollution": {
        "agent_name": "pollution_agent",
        "env_url_key": "POLLUTION_AGENT_URL",
        "endpoint": "/api/v1/pollution/aqi-summary",
        "method": "GET",
        "module_path": "backend.agents.pollution_agent.main",
    },
    "simulation": {
        "agent_name": "simulation_agent",
        "env_url_key": "SIMULATION_AGENT_URL",
        "endpoint": "/api/v1/simulation/run",
        "method": "POST",
        "default_payload": {
            "scenario_name": "hyderabad_central",
            "duration_steps": 1000,
            "signal_optimization": True,
        },
        "module_path": "backend.agents.simulation_agent.main",
    },
}


def _dispatch_agent(capability: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Dispatch a capability to its registered specialist agent."""
    if capability not in AGENT_REGISTRY:
        raise ValueError(f"No registered agent configuration for capability: {capability}")

    config = AGENT_REGISTRY[capability]
    agent_url = os.getenv(config["env_url_key"])
    method = config.get("method", "GET")
    endpoint = config.get("endpoint", "/")
    payload = config.get("default_payload")
    if context and isinstance(context, dict) and capability in context:
        payload = context[capability]

    # If explicit URL is configured in environment, dispatch over HTTP
    if agent_url:
        full_url = f"{agent_url.rstrip('/')}{endpoint}"
        try:
            if method == "POST":
                resp = requests.post(full_url, json=payload or {}, timeout=5.0)
            else:
                resp = requests.get(full_url, timeout=5.0)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(f"Agent '{config['agent_name']}' timed out connecting to {full_url}") from exc
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(f"Agent '{config['agent_name']}' unavailable at {full_url}") from exc
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Agent '{config['agent_name']}' HTTP error: {str(exc)}") from exc
        except ValueError as exc:
            raise RuntimeError(f"Agent '{config['agent_name']}' returned invalid JSON response") from exc

    # In-process execution fallback via agent FastAPI application for mock/testing
    try:
        module = importlib.import_module(config["module_path"])
        agent_app = getattr(module, "app", None)
        if agent_app is None:
            raise AttributeError(f"Module '{config['module_path']}' does not expose a FastAPI 'app'")

        client = TestClient(agent_app)
        if method == "POST":
            resp = client.post(endpoint, json=payload or {})
        else:
            resp = client.get(endpoint)

        if resp.status_code >= 400:
            raise RuntimeError(f"Agent '{config['agent_name']}' returned HTTP {resp.status_code}: {resp.text}")
        return resp.json()
    except Exception as exc:
        raise RuntimeError(f"Failed to dispatch to agent '{config['agent_name']}': {str(exc)}") from exc


# Public alias
dispatch_agent = _dispatch_agent
