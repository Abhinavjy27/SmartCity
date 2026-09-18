"""
Intelligent Grid Optimization & Peak-Shaving Service for SUPADSP Energy Agent.
Generates dynamic load mitigation strategies, demand-response recommendations, and battery dispatch plans.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from backend.agents.energy_agent.schema import (
    EnergyRecommendation,
    PeakShavingRequest,
    PeakShavingResponse,
    SubstationData,
)
from backend.agents.energy_agent.substations import SUBSTATIONS_DB, ZONE_METRICS_CONFIG


def generate_recommendations(
    substations: List[SubstationData],
    load_pct: float,
    ambient_temp_c: Optional[float] = None,
    traffic_occupancy_pct: Optional[float] = None
) -> List[EnergyRecommendation]:
    """
    Synthesizes multiple targeted mitigation recommendations based on real-time grid telemetry and stress indicators.
    Returns 5 to 6 distinct, actionable recommendations.
    """
    recs: List[EnergyRecommendation] = []
    
    # Check for critical or high substations
    critical_subs = [s for s in substations if s.load_pct >= 85.0]
    high_subs = [s for s in substations if 75.0 <= s.load_pct < 85.0]
    
    # 1. Base demand-response / off-peak load shifting
    recs.append(
        EnergyRecommendation(
            title="Shift non-critical industrial & commercial loads to off-peak hours (22:00–06:00)",
            impact="12–18% peak reduction",
            priority="HIGH" if load_pct >= 75.0 else "MEDIUM",
            category="DEMAND_RESPONSE",
            estimated_savings_mw=round(load_pct * 1.8, 1)
        )
    )
    
    # 2. Zone-specific targeted demand response and feeder rebalancing
    if critical_subs:
        target_sub = critical_subs[0]
        recs.append(
            EnergyRecommendation(
                title=f"Activate emergency demand response & feeder load-shedding prevention for {target_sub.zone} zone ({target_sub.name})",
                impact="18% localized reduction",
                priority="CRITICAL",
                category="LOAD_SHEDDING_PREVENTION",
                target_zone=target_sub.zone,
                estimated_savings_mw=round(target_sub.current_load_mw * 0.18, 1)
            )
        )
    elif high_subs:
        target_sub = high_subs[0]
        recs.append(
            EnergyRecommendation(
                title=f"Activate demand response & feeder balancing program for {target_sub.zone} zone ({target_sub.name})",
                impact="8–12% localized reduction",
                priority="HIGH",
                category="DEMAND_RESPONSE",
                target_zone=target_sub.zone,
                estimated_savings_mw=round(target_sub.current_load_mw * 0.10, 1)
            )
        )
    else:
        target_zone = substations[0].zone if substations else "HITECH City"
        recs.append(
            EnergyRecommendation(
                title=f"Activate proactive demand response program for {target_zone} zone",
                impact="8% load reduction",
                priority="HIGH",
                category="DEMAND_RESPONSE",
                target_zone=target_zone,
                estimated_savings_mw=28.5
            )
        )
        
    # 3. Dynamic street lighting optimization linked to traffic volume
    street_impact = "15% savings" if (traffic_occupancy_pct is None or traffic_occupancy_pct < 70) else "10% savings"
    recs.append(
        EnergyRecommendation(
            title="Optimize street lighting dimming schedule & LED luminance based on real-time traffic volume",
            impact=street_impact,
            priority="MEDIUM",
            category="INFRASTRUCTURE_EFFICIENCY",
            estimated_savings_mw=14.2
        )
    )
    
    # 4. Solar and BESS recommendations (Heatwave / high temp adaptation)
    if ambient_temp_c and ambient_temp_c >= 38.0:
        recs.append(
            EnergyRecommendation(
                title=f"Heatwave Protocol: Dispatch 40 MW Battery Energy Storage (BESS) to buffer HVAC surge at {ambient_temp_c}°C",
                impact="25% peak offset",
                priority="CRITICAL",
                category="BESS_DISPATCH",
                estimated_savings_mw=40.0
            )
        )
    else:
        recs.append(
            EnergyRecommendation(
                title="Dispatch localized 20–40 MWh Battery Energy Storage (BESS) packs during peak transformer load hours",
                impact="18% peak offset",
                priority="HIGH" if load_pct >= 80.0 else "MEDIUM",
                category="BESS_DISPATCH",
                estimated_savings_mw=25.0
            )
        )

    # 5. Rooftop Solar Microgrid Direct Feed-in
    recs.append(
        EnergyRecommendation(
            title="Deploy solar-assisted microgrid power at institutional, commercial, and government buildings",
            impact="20% peak offset",
            priority="MEDIUM",
            category="RENEWABLE_INTEGRATION",
            estimated_savings_mw=22.0
        )
    )

    # 6. Smart Commercial HVAC & EV Fast-Charging Modulation
    recs.append(
        EnergyRecommendation(
            title="Throttle commercial HVAC setpoints (+1.5°C) and modulate high-power DC EV fast-charging hubs",
            impact="10–14% demand relief",
            priority="HIGH" if load_pct >= 75.0 else "MEDIUM",
            category="SMART_LOAD_MODULATION",
            estimated_savings_mw=16.8
        )
    )
        
    return recs


def execute_peak_shaving(request: PeakShavingRequest) -> PeakShavingResponse:
    """
    Executes algorithmic peak shaving scenario calculation.
    Resolves baseline load dynamically from requested zone or target substations.
    """
    zone = request.zone or "HITECH City"
    target_reduction = request.target_reduction_mw if request.target_reduction_mw is not None else 25.0
    
    # 1. Resolve baseline load dynamically
    if request.target_substations:
        target_ids = {s.upper() for s in request.target_substations}
        matched_subs = [s for s in SUBSTATIONS_DB if s["id"].upper() in target_ids]
        if matched_subs:
            original_load = sum(float(s["capacity_mw"]) * (float(s.get("base_load_pct", 75.0)) / 100.0) for s in matched_subs)
        else:
            original_load = 342.0
    else:
        zone_subs = [s for s in SUBSTATIONS_DB if s.get("zone", "").lower() == zone.lower()]
        if zone_subs:
            original_load = sum(float(s["capacity_mw"]) * (float(s.get("base_load_pct", 75.0)) / 100.0) for s in zone_subs)
        else:
            original_load = float(ZONE_METRICS_CONFIG.get(zone, {}).get("nominal_mwh", 342.0))
            
    original_load = round(original_load, 1)
    
    if target_reduction > 0:
        bess_contribution = min(15.0, target_reduction * 0.5)
        solar_offset = min(10.0, target_reduction * 0.3)
        curtailed = max(0.0, target_reduction - bess_contribution - solar_offset)
        target_load = max(0.0, original_load - target_reduction)
        actions = [
            f"Throttle commercial HVAC setpoints by +1.5°C across {zone} commercial parks (saving {curtailed:.1f} MW)",
            f"Discharge 20 MWh localized BESS battery packs at primary substations (supplying {bess_contribution:.1f} MW)",
            f"Route rooftop solar microgrid generation directly to feeder lines (offsetting {solar_offset:.1f} MW)",
            "Schedule dynamic street-lighting dimming offsets after 22:00"
        ]
    else:
        bess_contribution = 0.0
        solar_offset = 0.0
        curtailed = 0.0
        target_load = original_load
        actions = [
            f"Grid operating at nominal load ({original_load:.1f} MW) for {zone}; maintaining standard automated telemetry monitoring."
        ]
    
    return PeakShavingResponse(
        status="OPTIMIZED",
        zone=zone,
        original_load_mw=original_load,
        target_load_mw=round(target_load, 1),
        curtailed_mw=round(curtailed, 1),
        bess_discharge_mw=round(bess_contribution, 1),
        solar_offset_mw=round(solar_offset, 1),
        actions=actions
    )
