"""
Dynamic Real-Time Load Computation Engine for SUPADSP Energy Agent.
Calculates diurnal curve dynamics, cross-domain weather/traffic telemetry impacts,
substation-level metrics, and deterministic severity level classifications.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.agents.energy_agent.dataset_loader import (
    get_empirical_hourly_factor,
    load_energy_dataset_stats,
)
from backend.agents.energy_agent.schema import (
    HourlyLoadItem,
    SeverityLevel,
    SubstationData,
    SubstationStatus,
    ZoneConsumption,
)
from backend.agents.energy_agent.substations import (
    SUBSTATIONS_DB,
    ZONE_METRICS_CONFIG,
    match_substations_by_location,
)


def compute_diurnal_factor(hour: int, minute: int = 0) -> float:
    """
    Computes time-of-day load factor between 0.70 and 1.22 based on urban dual-peak consumption:
    - Blends theoretical Gaussian curve (Hyderabad HVAC + commercial peaks) with
      empirical time-series weights from datasets/raw/energy/household_power_consumption.txt.
    """
    t = hour + (minute / 60.0)
    
    # Dual Gaussian peaks modeling Hyderabad power consumption
    afternoon_peak = 0.22 * math.exp(-((t - 14.0) ** 2) / 8.0)
    evening_peak = 0.18 * math.exp(-((t - 20.0) ** 2) / 6.0)
    morning_ramp = 0.12 * math.exp(-((t - 10.5) ** 2) / 5.0)
    night_trough = -0.15 * math.exp(-((t - 3.5) ** 2) / 6.0)
    
    base_factor = 0.82
    diurnal_model = base_factor + afternoon_peak + evening_peak + morning_ramp + night_trough
    
    # Ingest empirical factor derived from raw energy dataset
    empirical_weight = get_empirical_hourly_factor(hour)
    
    # Weighted ensemble: 85% empirical historical dataset + 15% urban physics model
    blended = (empirical_weight * 0.85) + (diurnal_model * 0.15)
    return max(0.45, min(1.85, blended))


def compute_solar_generation(hour: int, capacity_mw: float) -> float:
    """
    Calculates solar output in MW using solar zenith curve (06:00 to 18:30 peak at 13:00).
    Nominal Hyderabad rooftop + utility solar capacity is approx 10-15% of grid capacity.
    """
    if hour < 6 or hour > 18:
        return 0.0
    solar_peak_mw = capacity_mw * 0.12
    # Sine curve during daylight
    daylight_progress = (hour - 6) / 12.0
    return max(0.0, round(solar_peak_mw * math.sin(daylight_progress * math.pi), 1))


def calculate_weather_impact(
    ambient_temp_c: Optional[float] = None,
    heatwave_threshold_c: float = 38.0,
    base_temp_c: float = 28.0
) -> Tuple[float, float]:
    """
    Calculates temperature-induced HVAC cooling multiplier and MW offset.
    Returns (multiplier, delta_mw_per_1000mw).
    """
    if ambient_temp_c is None:
        ambient_temp_c = 31.5  # Standard nominal daytime temperature in Hyderabad

    if ambient_temp_c <= base_temp_c:
        return 1.0, 0.0

    delta_t = ambient_temp_c - base_temp_c
    if ambient_temp_c >= heatwave_threshold_c:
        # Severe non-linear HVAC surge during heatwave
        multiplier = 1.0 + (0.025 * delta_t) + (0.015 * (ambient_temp_c - heatwave_threshold_c))
    else:
        multiplier = 1.0 + (0.020 * delta_t)

    delta_mw = (multiplier - 1.0) * 1000.0
    return round(multiplier, 4), round(delta_mw, 1)


def calculate_traffic_ev_impact(
    traffic_occupancy_pct: Optional[float] = None,
    ev_fleet_count: Optional[int] = None
) -> Tuple[float, float]:
    """
    Calculates EV fast-charging demand impact based on corridor traffic density.
    Returns (multiplier, ev_mw_added).
    """
    if traffic_occupancy_pct is None and ev_fleet_count is None:
        traffic_occupancy_pct = 68.0  # Moderate baseline traffic

    ev_mw = 0.0
    if ev_fleet_count:
        # Average fast charger draw = 30 kW during dwell time
        ev_mw += (ev_fleet_count * 0.030)

    if traffic_occupancy_pct and traffic_occupancy_pct > 60.0:
        # Heavy traffic correlation with public charging hub utilization
        ev_mw += ((traffic_occupancy_pct - 60.0) * 1.5)

    multiplier = 1.0 + (ev_mw / 4500.0)
    return round(multiplier, 4), round(ev_mw, 1)


def map_load_to_severity(load_pct: float) -> str:
    """
    Maps grid load percentage to system contract severity levels:
    - CRITICAL: load_pct >= 85.0
    - HIGH:     load_pct >= 75.0
    - MODERATE: load_pct < 75.0
    """
    if load_pct >= 85.0:
        return SeverityLevel.CRITICAL.value
    elif load_pct >= 75.0:
        return SeverityLevel.HIGH.value
    else:
        return SeverityLevel.MODERATE.value


def map_substation_status(load_pct: float) -> str:
    """
    Maps substation load percentage to operational status:
    - CRITICAL: load_pct >= 85.0
    - HIGH:     load_pct >= 75.0
    - NORMAL:   load_pct < 75.0
    """
    if load_pct >= 85.0:
        return SubstationStatus.CRITICAL.value
    elif load_pct >= 75.0:
        return SubstationStatus.HIGH.value
    else:
        return SubstationStatus.NORMAL.value


def generate_hourly_profile(
    capacity_mw: float,
    current_hour: int,
    weather_multiplier: float = 1.0,
    ev_impact_mw: float = 0.0
) -> List[HourlyLoadItem]:
    """
    Generates 24-hour diurnal load vs capacity profile.
    """
    hourly_items: List[HourlyLoadItem] = []
    
    for h in range(24):
        hour_str = f"{str(h).padStart(2, '0') if hasattr(str(h), 'padStart') else f'{h:02d}'}:00"
        factor = compute_diurnal_factor(h, 0)
        
        # Load % curve centered around base 78% adjusted by weather and factor
        base_curve_pct = 78.0 * (factor / 1.0) * weather_multiplier
        base_curve_pct = max(38.0, min(95.0, base_curve_pct))
        
        solar_mw = compute_solar_generation(h, capacity_mw)
        ev_mw = ev_impact_mw * (1.2 if (17 <= h <= 21) else 0.7) if ev_impact_mw > 0 else 0.0
        
        hourly_items.append(
            HourlyLoadItem(
                h=hour_str,
                load=round(base_curve_pct, 1),
                capacity=92.0,
                solar_generation_mw=round(solar_mw, 1),
                ev_load_mw=round(ev_mw, 1),
            )
        )
        
    return hourly_items


def compute_zone_breakdown(
    substations: List[SubstationData],
    weather_multiplier: float = 1.0
) -> List[ZoneConsumption]:
    """
    Aggregates substation loads into zone-level consumption metrics.
    """
    zones_map: Dict[str, Dict[str, Any]] = {}
    
    # Initialize from default config
    for zone_name, cfg in ZONE_METRICS_CONFIG.items():
        zones_map[zone_name] = {
            "consumption": 0.0,
            "peak": cfg["peak_base"] * weather_multiplier,
            "color": cfg["color"],
            "count": 0,
            "load_sum": 0.0,
            "cap_sum": 0.0,
        }
        
    for sub in substations:
        z = sub.zone
        if z not in zones_map:
            zones_map[z] = {
                "consumption": 0.0,
                "peak": 75.0,
                "color": "#38bdf8",
                "count": 0,
                "load_sum": 0.0,
                "cap_sum": 0.0,
            }
        zones_map[z]["consumption"] += sub.current_load_mw
        zones_map[z]["load_sum"] += sub.current_load_mw
        zones_map[z]["cap_sum"] += sub.capacity_mw
        zones_map[z]["count"] += 1
        zones_map[z]["peak"] = max(zones_map[z]["peak"], sub.load_pct)
        
    result: List[ZoneConsumption] = []
    for z_name, data in zones_map.items():
        if data["count"] > 0 or z_name in ["HITECH City", "Gachibowli", "Secunderabad", "Kukatpally", "Old City", "LB Nagar"]:
            consumption_val = data["consumption"] if data["consumption"] > 0 else ZONE_METRICS_CONFIG.get(z_name, {}).get("nominal_mwh", 250)
            peak_val = data["peak"] if data["peak"] > 0 else 75.0
            result.append(
                ZoneConsumption(
                    zone=z_name,
                    consumption=round(consumption_val, 1),
                    peak=round(min(98.0, peak_val), 1),
                    color=data["color"],
                    active_substations=data["count"] if data["count"] > 0 else 1,
                )
            )
            
    return result


def compute_telemetry_state(
    location: Optional[str] = None,
    ambient_temp_c: Optional[float] = None,
    traffic_occupancy_pct: Optional[float] = None,
    ev_count: Optional[int] = None,
    now: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Main telemetry compilation function.
    Reads location query, contextual parameters, and calculates real-time grid state.
    """
    if now is None:
        now = datetime.now(timezone.utc)
        
    hour = now.hour
    minute = now.minute
    
    # 1. Match relevant substations
    raw_substations = match_substations_by_location(location)
    
    # 2. Contextual impact factors
    weather_mult, weather_offset_mw = calculate_weather_impact(ambient_temp_c)
    traffic_mult, ev_offset_mw = calculate_traffic_ev_impact(traffic_occupancy_pct, ev_count)
    diurnal_factor = compute_diurnal_factor(hour, minute)
    
    # Combined load factor
    load_multiplier = diurnal_factor * weather_mult * traffic_mult
    
    computed_substations: List[SubstationData] = []
    total_capacity_mw = 0.0
    total_current_load_mw = 0.0
    
    for sub in raw_substations:
        cap = float(sub["capacity_mw"])
        base_pct = float(sub.get("base_load_pct", 75.0))
        
        # Calculate dynamic substation load
        # Specialized boost for tech hubs if EV/traffic is elevated
        zone_boost = 1.03 if (sub["zone"] in ["HITECH City", "Gachibowli"] and traffic_mult > 1.0) else 1.0
        
        sub_load_pct = base_pct * (load_multiplier / 0.95) * zone_boost
        sub_load_pct = max(35.0, min(96.5, sub_load_pct))
        
        current_mw = round((sub_load_pct / 100.0) * cap, 1)
        total_capacity_mw += cap
        total_current_load_mw += current_mw
        
        status_str = map_substation_status(sub_load_pct)
        
        computed_substations.append(
            SubstationData(
                id=sub["id"],
                name=sub["name"],
                capacity_mw=cap,
                current_load_mw=current_mw,
                load_pct=round(sub_load_pct, 1),
                status=status_str,
                voltage_kv=sub.get("voltage_kv", 132),
                zone=sub.get("zone", "Hyderabad Central"),
                latitude=sub.get("latitude"),
                longitude=sub.get("longitude"),
                feeder_lines=sub.get("feeder_lines", 6),
                peak_load_pct=round(min(98.0, sub_load_pct * 1.08), 1),
            )
        )
        
    # Aggregate grid percentage
    overall_load_pct = round((total_current_load_mw / total_capacity_mw) * 100.0, 1) if total_capacity_mw > 0 else 78.4
    overall_severity = map_load_to_severity(overall_load_pct)
    
    solar_gen_mw = compute_solar_generation(hour, total_capacity_mw)
    
    # Cumulative consumption approximation
    total_consumption_mwh = round(total_current_load_mw * 0.38 + (total_capacity_mw * 0.15), 1)
    
    # Transmission & grid efficiency score (lower efficiency under high heat/stress)
    efficiency_score = round(max(78.0, 92.5 - (0.15 * max(0.0, overall_load_pct - 65.0)) - (0.2 * max(0.0, (ambient_temp_c or 30.0) - 30.0))), 1)
    
    hourly_load = generate_hourly_profile(total_capacity_mw, hour, weather_mult, ev_offset_mw)
    zone_data = compute_zone_breakdown(computed_substations, weather_mult)
    
    return {
        "source": "Live Energy Agent API",
        "timestamp": now.isoformat(),
        "location": location or "Hyderabad Central",
        "current_load_mw": round(total_current_load_mw, 1),
        "capacity_mw": round(total_capacity_mw, 1),
        "load_pct": overall_load_pct,
        "solar_generation_mw": solar_gen_mw,
        "total_consumption_mwh": total_consumption_mwh,
        "efficiency_score_pct": efficiency_score,
        "substations": computed_substations,
        "hourly_load": hourly_load,
        "zone_data": zone_data,
        "severity": overall_severity,
        "weather_impact_mw": round(weather_offset_mw * total_capacity_mw / 1000.0, 1),
        "ev_traffic_impact_mw": round(ev_offset_mw, 1),
    }
