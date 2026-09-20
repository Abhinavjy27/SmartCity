"""
Specialist Agent Machine-Readable Contracts for the Planner Agent.
Defines endpoints, HTTP methods, required inputs, output metrics, and cross-agent context flows.
"""

from typing import Any, Dict

SPECIALIST_AGENT_CONTRACTS: Dict[str, Dict[str, Any]] = {
    "traffic": {
        "agent_name": "traffic",
        "description": "Monitors congestion, average vehicle speeds, corridor status, and intersection bottlenecks.",
        "purpose": "Provide baseline traffic diagnostics, corridor congestion levels, vehicle counts, and queue bottlenecks for a designated location.",
        "endpoint": "/api/v1/traffic/kpis",
        "method": "GET",
        "required_inputs": ["location"],
        "optional_inputs": ["scenario", "corridors", "purpose"],
        "key_outputs": [
            "congestion_index",
            "average_speed_kmh",
            "vehicle_count",
            "travel_time_index",
            "corridors",
            "sensors",
        ],
        "context_sources": ["weather", "simulation"],
    },
    "weather": {
        "agent_name": "weather",
        "description": "Provides current meteorological telemetry, rainfall, wind speeds, and precipitation forecasts.",
        "purpose": "Provide meteorological observations (temperature, precipitation, wind, storm status) to evaluate weather conditions or roadway friction drag.",
        "endpoint": "/api/v1/weather/current",
        "method": "GET",
        "required_inputs": ["location"],
        "optional_inputs": ["city", "include_forecast", "purpose"],
        "key_outputs": [
            "temperature_c",
            "humidity_pct",
            "condition",
            "precipitation_mm",
            "wind_speed_kmh",
            "forecast_7d",
        ],
        "context_sources": [],
    },
    "pollution": {
        "agent_name": "pollution",
        "description": "Monitors ambient air quality, particulate matter (PM2.5, PM10), and environmental station metrics.",
        "purpose": "Provide environmental air quality indices (AQI, PM2.5, PM10) and monitoring station hotspot readings.",
        "endpoint": "/api/v1/pollution/aqi-summary",
        "method": "GET",
        "required_inputs": ["location"],
        "optional_inputs": ["include_stations", "purpose"],
        "key_outputs": [
            "city_avg_aqi",
            "dominant_pollutant",
            "pm25",
            "pm10",
            "air_quality_category",
            "stations",
        ],
        "context_sources": ["traffic", "weather"],
    },
    "energy": {
        "agent_name": "energy",
        "description": "Monitors electrical substation loads, grid stress, peak demand margins, and power telemetry.",
        "purpose": "Provide electrical grid status, substation load percentages, and capacity telemetry.",
        "endpoint": "/api/v1/energy/grid-status",
        "method": "GET",
        "required_inputs": ["location"],
        "optional_inputs": ["include_substations", "purpose"],
        "key_outputs": [
            "load_pct",
            "current_load_mw",
            "substations",
        ],
        "context_sources": ["weather", "traffic"],
    },
    "simulation": {
        "agent_name": "simulation",
        "description": "Executes Eclipse SUMO / TraCI micro-simulations to verify traffic interventions and scenario experiments under synthetic traffic demand.",
        "purpose": "Test and compare candidate traffic interventions against a defined synthetic baseline scenario (same traffic demand + current conditions vs same traffic demand + candidate intervention).",
        "data_nature": "Simulated/synthetic evidence derived from Eclipse SUMO demand models, NOT live physical telemetry.",
        "supported_interventions": [
            "signal_timing",
            "adaptive_signal_control",
            "rerouting",
            "traffic_diversion",
            "lane_use_changes",
            "turn_restrictions",
            "road_closure",
            "traffic_demand_management",
            "incident_response",
            "combined_strategy",
        ],
        "endpoint": "/api/v1/simulation/run",
        "method": "POST",
        "required_inputs": ["scenario_name", "target_location"],
        "optional_inputs": [
            "duration_steps",
            "signal_optimization",
            "candidate_intervention",
            "weather_drag_applied",
            "intervention_details",
            "purpose",
        ],
        "key_outputs": [
            "metrics",
            "sim_results",
            "scenario",
            "status",
        ],
        "context_sources": ["traffic", "weather"],
    },
}

# Compact representations strictly for LLM prompts to preserve token quotas
COMPACT_CONTRACTS_FOR_PROMPT: Dict[str, Dict[str, Any]] = {
    "traffic": {
        "purpose": "Baseline traffic diagnostics, speeds, corridor bottlenecks",
        "method": "GET",
        "required_inputs": ["location"],
    },
    "weather": {
        "purpose": "Meteorological observations (rain, wind, visibility, drag)",
        "method": "GET",
        "required_inputs": ["location"],
    },
    "pollution": {
        "purpose": "Air quality indices (AQI, PM2.5, PM10) and station readings",
        "method": "GET",
        "required_inputs": ["location"],
    },
    "energy": {
        "purpose": "Grid status, substation load percentages, capacity telemetry",
        "method": "GET",
        "required_inputs": ["location"],
    },
    "simulation": {
        "purpose": "SUMO/TraCI microsimulation to test interventions against baseline",
        "method": "POST",
        "required_inputs": ["scenario_name", "target_location", "intervention"],
        "supported_interventions": [
            "signal_timing",
            "rerouting",
            "lane_use_changes",
            "road_closure",
            "incident_response",
        ],
    },
}

