"""
Synthetic Traffic Demand Generator for Narayanguda, Hyderabad SUMO Network.
Generates reproducible, deterministic, intentionally non-uniform traffic flows
for baseline traffic simulation and future intervention comparisons.
"""

from __future__ import annotations

import os
import random
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Pre-computed arterial origin-destination pairs verified across the Narayanguda network.
# These pairs guarantee valid, multi-segment connected vehicle paths across Hyderabad corridors.
DIRECTIONAL_OD_PAIRS: Dict[str, List[Tuple[str, str]]] = {
    "northbound": [
        ("-117258033#2", "-1300440532#0"),
        ("-117258033#2", "-1300440533"),
        ("-117258033#2", "-281764104"),
        ("-117258033#2", "-355688049#0"),
        ("-117258033#2", "-355694710"),
        ("-117258033#2", "-355702531"),
        ("-117258033#2", "-355706789#0"),
        ("-117258033#2", "-355706789#1"),
        ("-117258033#2", "-397570956#0"),
        ("-117258033#2", "-397570975"),
        ("-117258033#2", "-426973470"),
        ("-117258033#2", "-58604213"),
        ("-117258033#1", "-1300440532#0"),
        ("-117258033#0", "-1300440533"),
    ],
    "southbound": [
        ("-1188636191", "-117258033#0"),
        ("-1188636191", "-117258033#1"),
        ("-1188636191", "-117258204#0"),
        ("-1188636191", "-117258204#1"),
        ("-1188636191", "-117258287"),
        ("-1188636191", "-117258288#0"),
        ("-1188636191", "-117258288#2"),
        ("-1188636191", "-117258288#3"),
        ("-1188636191", "-117258289"),
        ("-1188636191", "-1189090274"),
        ("-1188636191", "-142300746"),
        ("-1188636191", "-1455380845"),
    ],
    "eastbound": [
        ("-117255417#0", "-1078707435"),
        ("-117255417#0", "-1300187891"),
        ("-117255417#0", "-1424737088#0"),
        ("-117255417#0", "-1424737088#1"),
        ("-117255417#0", "-1424737088#2"),
        ("-117255417#0", "-213992539#2"),
        ("-117255417#0", "-213992539#3"),
        ("-117255417#0", "-213992539#4"),
        ("-117255417#0", "-28110315"),
        ("-117255417#0", "-281764020"),
        ("-117255417#0", "-281764024"),
        ("-117255417#0", "-281998365"),
    ],
    "westbound": [
        ("-1189143806", "-117253666#0"),
        ("-1189143806", "-117253666#1"),
        ("-1189143806", "-117253666#2"),
        ("-1189143806", "-117253673"),
        ("-1189143806", "-117254190#0"),
        ("-1189143806", "-117254874#0"),
        ("-1189143806", "-117255416"),
        ("-1189143806", "-1188812897"),
        ("-1189143806", "-1242766094#1"),
        ("-1189143806", "-1280841926#0"),
        ("-1189143806", "-1280841926#1"),
        ("-1189143806", "-1280841927"),
    ],
}

# Standardized flow rates (vehicles per hour) per scenario
SCENARIO_DEMAND_PROFILES: Dict[str, Dict[str, int]] = {
    "synthetic_normal": {
        "northbound": 320,
        "southbound": 280,
        "eastbound": 250,
        "westbound": 240,
    },
    "synthetic_peak_northbound": {
        # Deliberately heavy peak demand on northbound corridor
        "northbound": 850,
        "southbound": 160,
        "eastbound": 140,
        "westbound": 120,
    },
    "synthetic_peak_southbound": {
        # Deliberately heavy peak demand on southbound corridor
        "northbound": 160,
        "southbound": 850,
        "eastbound": 140,
        "westbound": 120,
    },
    "synthetic_peak_eastbound": {
        "northbound": 150,
        "southbound": 150,
        "eastbound": 800,
        "westbound": 130,
    },
    "synthetic_peak_westbound": {
        "northbound": 150,
        "southbound": 150,
        "eastbound": 130,
        "westbound": 800,
    },
    "custom_demand": {
        "northbound": 400,
        "southbound": 400,
        "eastbound": 300,
        "westbound": 300,
    },
}


@dataclass
class SyntheticTrip:
    trip_id: str
    depart_time: float
    from_edge: str
    to_edge: str
    corridor: str


class SyntheticDemandGenerator:
    """
    Generates reproducible synthetic route XML files for SUMO microsimulation.
    Uses seeded RNG to guarantee identical vehicle departures for identical seeds.
    """

    def __init__(self, routes_dir: Optional[str] = None):
        if routes_dir is None:
            # Default to SmartCity/simulations/routes
            pkg_dir = os.path.dirname(os.path.abspath(__file__))
            smartcity_root = os.path.abspath(os.path.join(pkg_dir, "..", "..", ".."))
            routes_dir = os.path.join(smartcity_root, "simulations", "routes")
        self.routes_dir = routes_dir
        os.makedirs(self.routes_dir, exist_ok=True)

    def get_supported_scenarios(self) -> List[str]:
        return list(SCENARIO_DEMAND_PROFILES.keys())

    def validate_scenario(self, scenario: str) -> str:
        scen_clean = (scenario or "synthetic_normal").strip().lower()
        if scen_clean not in SCENARIO_DEMAND_PROFILES:
            supported = list(SCENARIO_DEMAND_PROFILES.keys())
            raise ValueError(f"Unsupported scenario '{scenario}'. Supported scenarios: {supported}")
        return scen_clean

    def generate_route_file(
        self,
        scenario: str = "synthetic_normal",
        duration_seconds: int = 120,
        seed: int = 42,
        custom_rates: Optional[Dict[str, int]] = None,
    ) -> str:
        """
        Generates and writes a deterministic .rou.xml file for the given scenario,
        duration, and random seed.
        """
        scenario = self.validate_scenario(scenario)
        filename = f"{scenario}_{duration_seconds}s_seed{seed}.rou.xml"
        output_path = os.path.join(self.routes_dir, filename)

        # Check if already generated
        if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
            return output_path

        rates = dict(SCENARIO_DEMAND_PROFILES[scenario])
        if custom_rates and scenario == "custom_demand":
            rates.update(custom_rates)

        rng = random.Random(seed)
        trips: List[SyntheticTrip] = []
        trip_counter = 0

        for corridor, vph in rates.items():
            od_pairs = DIRECTIONAL_OD_PAIRS.get(corridor, [])
            if not od_pairs:
                continue

            # Number of vehicles to generate in duration_seconds
            num_vehicles = max(1, int(round((vph / 3600.0) * duration_seconds)))

            for _ in range(num_vehicles):
                # Spread departure times evenly with jitter
                depart_time = round(rng.uniform(0.5, max(1.0, duration_seconds - 5.0)), 1)
                from_edge, to_edge = rng.choice(od_pairs)
                trips.append(
                    SyntheticTrip(
                        trip_id=f"veh_{corridor}_{trip_counter}",
                        depart_time=depart_time,
                        from_edge=from_edge,
                        to_edge=to_edge,
                        corridor=corridor,
                    )
                )
                trip_counter += 1

        # Sort trips chronologically by departure time
        trips.sort(key=lambda t: t.depart_time)

        # Build XML
        root = ET.Element("routes")
        root.append(
            ET.Comment(
                f" Generated by SUPADSP SyntheticDemandGenerator. "
                f"Scenario: {scenario}, Duration: {duration_seconds}s, Seed: {seed}. "
                f"Synthetic demand - NOT actual road counts. "
            )
        )

        # Passenger vehicle type definition
        vtype = ET.SubElement(
            root,
            "vType",
            {
                "id": "veh_passenger",
                "accel": "2.6",
                "decel": "4.5",
                "sigma": "0.5",
                "length": "4.5",
                "minGap": "2.5",
                "maxSpeed": "16.67",  # ~60 km/h
                "speedDev": "0.1",
            },
        )

        for t in trips:
            ET.SubElement(
                root,
                "trip",
                {
                    "id": t.trip_id,
                    "depart": f"{t.depart_time:.1f}",
                    "from": t.from_edge,
                    "to": t.to_edge,
                    "type": "veh_passenger",
                },
            )

        tree = ET.ElementTree(root)
        ET.indent(tree, space="    ")
        tree.write(output_path, encoding="utf-8", xml_declaration=True)

        return output_path
