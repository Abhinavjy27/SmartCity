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
        "endpoint": "/api/v1/pollution/analyze",
        "method": "POST",
        "default_payload": {
            "objective": "Analyze air quality and pollution levels",
            "location": "Narayanguda, Hyderabad",
        },
        "module_path": "backend.agents.pollution_agent.main",
    },
    "simulation": {
        "agent_name": "simulation_agent",
        "env_url_key": "SIMULATION_AGENT_URL",
        "endpoint": "/api/v1/simulation/run",
        "method": "POST",
        "default_payload": {
            "scenario_name": "synthetic_normal",
            "location": "Narayanguda, Hyderabad",
            "duration_seconds": 120,
            "seed": 42,
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
    payload = dict(config.get("default_payload") or {})
    if context and isinstance(context, dict):
        if capability in context and isinstance(context[capability], dict):
            payload.update(context[capability])
        else:
            payload.update(context)

    # Allow endpoint override from context if provided
    if isinstance(payload, dict) and "_endpoint" in payload:
        endpoint = payload.pop("_endpoint")
    if isinstance(payload, dict) and "_method" in payload:
        method = payload.pop("_method")

    # Prepare parameters for GET vs JSON body for POST
    get_params = None
    if method == "GET" and isinstance(payload, dict):
        get_params = {k: v for k, v in payload.items() if isinstance(v, (str, int, float, bool))}

    # Extract optional location or query params from context
    params: Dict[str, Any] = {}
    if context and isinstance(context, dict):
        if "location" in context and context["location"]:
            params["location"] = context["location"]
        elif capability in context and isinstance(context[capability], dict) and "location" in context[capability]:
            params["location"] = context[capability]["location"]

        # Forward cross-domain contextual query parameters
        cap_dict = context[capability] if (capability in context and isinstance(context[capability], dict)) else {}
        for param_key in ["ambient_temp_c", "traffic_occupancy_pct", "ev_count", "temperature_c", "zone", "status"]:
            if param_key in context and context[param_key] is not None:
                params[param_key] = context[param_key]
            elif param_key in cap_dict and cap_dict[param_key] is not None:
                params[param_key] = cap_dict[param_key]

    # If explicit URL is configured in environment, dispatch over HTTP
    if agent_url:
        full_url = f"{agent_url.rstrip('/')}{endpoint}"
        try:
            if method == "POST":
                resp = requests.post(full_url, json=payload or {}, timeout=5.0)
            else:
                resp = requests.get(full_url, params=params or None, timeout=5.0)
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
            resp = client.get(endpoint, params=params or None)

        if resp.status_code >= 400:
            raise RuntimeError(f"Agent '{config['agent_name']}' returned HTTP {resp.status_code}: {resp.text}")
        return resp.json()
    except Exception as exc:
        raise RuntimeError(f"Failed to dispatch to agent '{config['agent_name']}': {str(exc)}") from exc


# Public alias
dispatch_agent = _dispatch_agent
