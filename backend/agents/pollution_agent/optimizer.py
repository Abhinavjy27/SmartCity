from typing import List, Dict, Any

class InterventionOptimizer:
    def __init__(self):
        pass

    def generate_interventions(self, sensor_data: dict) -> List[Dict[str, Any]]:
        """
        Generates practical, actionable municipal pollution control recommendations
        structured across Immediate, Medium-term, and Long-term horizons with
        identified stakeholders (GHMC, TSPCB, Traffic Police, Transport Dept).
        Prioritizes interventions based on specific elevated pollutants (PM10 vs PM2.5/NO2).
        """
        interventions = []
        aqi = sensor_data.get("city_avg_aqi", 0)
        pm25 = sensor_data.get("pm25", 0.0)
        pm10 = sensor_data.get("pm10", 0.0)
        pollutants = sensor_data.get("pollutants", {}) or {}
        no2 = pollutants.get("nitrogen_dioxide") or 0.0

        # --- IMMEDIATE MEASURES ---
        # 1. Road Dust and Coarse Particulate Suppression (Triggered by PM10 or Moderate AQI)
        if pm10 >= 50.0 or aqi >= 100:
            interventions.append({
                "action_type": "MECHANIZED_ROAD_SWEEPING",
                "description": "Deploy mechanized sweeping and water-mist spraying on major arterial corridors to remove accumulated roadside silt and prevent vehicle-induced dust resuspension.",
                "horizon": "Immediate",
                "stakeholders": ["GHMC (Sanitation Wing)", "TSPCB"],
                "rationale": "High PM10 levels are predominantly driven by mechanical resuspension of loose roadside soil and construction dust.",
                "feasibility_score": 9.0
            })
            interventions.append({
                "action_type": "WATER_DUST_SUPPRESSION",
                "description": "Deploy water tankers and mist cannons at key traffic junctions and active transit corridors during morning and evening peak hours.",
                "horizon": "Immediate",
                "stakeholders": ["GHMC"],
                "rationale": "Surface moisture binds particulate matter, preventing airborne dispersion during peak vehicle movements.",
                "feasibility_score": 9.5
            })

        # 2. Construction Dust Control (Triggered by PM10 or High AQI)
        if pm10 >= 75.0 or aqi >= 120:
            interventions.append({
                "action_type": "CONSTRUCTION_MATERIAL_COVERING",
                "description": "Enforce strict tarpaulin covering for all dump trucks and tippers transporting sand, aggregate, and debris; mandate wheel-washing at site exits.",
                "horizon": "Immediate",
                "stakeholders": ["GHMC Town Planning", "Traffic Police", "TSPCB"],
                "rationale": "Uncovered transport of earth and building materials leads to continuous spill and pulverization on arterial roadways.",
                "feasibility_score": 8.5
            })

        # 3. Biomass & Waste Burning Prohibition
        if aqi >= 100 or pm25 >= 35.0:
            interventions.append({
                "action_type": "OPEN_BURNING_CONTROL",
                "description": "Intensify ward-level vigilance and zero-tolerance penalties on open burning of municipal solid waste, leaf litter, and plastic debris.",
                "horizon": "Immediate",
                "stakeholders": ["GHMC Enforcement Wing", "Local Ward Officers"],
                "rationale": "Uncontrolled low-temperature combustion produces toxic fine particulates (PM2.5) and carbon monoxide at breathing height.",
                "feasibility_score": 8.0
            })

        # 4. Vehicle Idling Reduction at Intersections
        if aqi >= 120 or pm25 >= 45.0 or no2 >= 20.0:
            interventions.append({
                "action_type": "ANTI_IDLING_ENFORCEMENT",
                "description": "Implement 'Switch Off Ignition at Red Lights' awareness campaigns and synchronize signal cycles along congested corridors to minimize idling time.",
                "horizon": "Immediate",
                "stakeholders": ["Hyderabad Traffic Police", "GHMC"],
                "rationale": "Vehicles consume excess fuel and emit concentrated PM2.5 and NOx during static idling at long signal cycles.",
                "feasibility_score": 8.5
            })

        # --- MEDIUM-TERM MEASURES ---
        interventions.append({
            "action_type": "CONSTRUCTION_SITE_DUST_AUDITS",
            "description": "Mandate continuous perimeter wind-breaking sheets (minimum 6m height), water misting systems, and real-time particulate monitors at all construction sites over 20,000 sq ft.",
            "horizon": "Medium-term",
            "stakeholders": ["GHMC Town Planning", "TSPCB"],
            "rationale": "Provides institutional containment of fugitive dust at source rather than relying on reactive road sweeping.",
            "feasibility_score": 7.5
        })
        interventions.append({
            "action_type": "PUBLIC_TRANSIT_FREQUENCY_BOOST",
            "description": "Augment electric bus feeder services and Metro connectivity along congested corridors to lower private two-wheeler and four-wheeler modal split.",
            "horizon": "Medium-term",
            "stakeholders": ["TSRTC", "Hyderabad Metro Rail", "HMDA"],
            "rationale": "Modal shift from personal motorized vehicles directly curbs primary tailpipe emissions.",
            "feasibility_score": 7.0
        })
        interventions.append({
            "action_type": "COMMERCIAL_FLEET_EMISSION_CHECKS",
            "description": "Deploy automated Pollution Under Control (PUC) verification scanners and mobile testing vans targeting pre-BS-IV commercial diesel vehicles.",
            "horizon": "Medium-term",
            "stakeholders": ["Telangana Transport Department", "Traffic Police"],
            "rationale": "High-emitting commercial trucks and older diesel vehicles contribute disproportionately to urban fine soot.",
            "feasibility_score": 8.0
        })

        # --- LONG-TERM MEASURES ---
        interventions.append({
            "action_type": "GREEN_BUFFER_CORRIDORS",
            "description": "Develop multi-tiered roadside green buffer strips with broad-leaved dust-absorbing indigenous vegetation along major corridors and industrial boundaries.",
            "horizon": "Long-term",
            "stakeholders": ["GHMC Urban Forestry", "HMDA"],
            "rationale": "Foliage acts as a natural biological filter, intercepting airborne particulates and buffering residential zones.",
            "feasibility_score": 7.0
        })
        interventions.append({
            "action_type": "SUSTAINABLE_URBAN_TRANSPORT_PLANNING",
            "description": "Expand non-motorized transport (NMT) infrastructure, dedicated cycling tracks, and pedestrian-priority zones integrated with rapid mass transit.",
            "horizon": "Long-term",
            "stakeholders": ["HMDA", "GHMC", "Unified Metropolitan Transportation Authority (UMTA)"],
            "rationale": "Permanent reduction in city-wide vehicle kilometers travelled (VKT) provides the only lasting protection against urban air degradation.",
            "feasibility_score": 6.5
        })

        return interventions
