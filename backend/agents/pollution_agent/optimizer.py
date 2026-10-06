from typing import List, Dict, Any

class InterventionOptimizer:
    def __init__(self):
        pass

    def generate_interventions(self, sensor_data: dict) -> List[Dict[str, Any]]:
        """
        Purely deterministic rule-based generator for municipal interventions.
        Uses cumulative independent rules to generate a tiered set of recommendations.
        """
        interventions = []
        aqi = sensor_data.get("city_avg_aqi", 0)
        pm25 = sensor_data.get("pm25", 0.0)
        # Using a default low wind speed if not provided to simulate sub-conditions
        wind_speed = sensor_data.get("wind_speed", 1.5)

        # Tier 1 (MODERATE: AQI >= 100)
        if aqi >= 100 or pm25 >= 40.0:
            interventions.append({
                "action_type": "PUBLIC_TRANSIT_BOOST",
                "description": "Subsidize public transit fares temporarily to encourage reduced private vehicle usage.",
                "expected_impact_pct": 10.0,
                "feasibility_score": 7.0
            })
            interventions.append({
                "action_type": "SMART_TRAFFIC_LIGHTS",
                "description": "Optimize traffic signal timing to minimize stop-and-go idle emissions.",
                "expected_impact_pct": 5.5,
                "feasibility_score": 9.0
            })

        # Tier 2 (HIGH: AQI >= 150)
        if aqi >= 150 or pm25 >= 80.0:
            interventions.append({
                "action_type": "TRAFFIC_DIVERSION",
                "description": "Reroute heavy trucks during peak congestion hours to reduce PM emissions.",
                "expected_impact_pct": 15.0,
                "feasibility_score": 8.0
            })
            interventions.append({
                "action_type": "DUST_SUPPRESSION",
                "description": "Deploy municipal water sprinklers on major arterial roads and open construction sites.",
                "expected_impact_pct": 8.5,
                "feasibility_score": 9.5
            })

        # Tier 3 (CRITICAL: AQI >= 200)
        if aqi >= 200 or pm25 >= 150.0:
            interventions.append({
                "action_type": "EMERGENCY_LOCKDOWN",
                "description": "Halt all non-essential construction and heavy industrial activity immediately.",
                "expected_impact_pct": 25.0,
                "feasibility_score": 4.0
            })
            
            # Sub-condition: Stagnant air (wind_speed < 2.0) worsens the critical AQI
            if wind_speed < 2.0:
                interventions.append({
                    "action_type": "CONSTRUCTION_HALT",
                    "description": "Implement an absolute freeze on all demolition and earth-moving activities due to stagnant wind conditions.",
                    "expected_impact_pct": 12.0,
                    "feasibility_score": 8.5
                })

        # Nominal/Safe (AQI < 100) - Only apply if no other tiers were triggered
        if not interventions:
            interventions.append({
                "action_type": "GREEN_INFRASTRUCTURE",
                "description": "Maintain current green corridors and schedule standard localized street sweeping.",
                "expected_impact_pct": 2.0,
                "feasibility_score": 10.0
            })

        return interventions
