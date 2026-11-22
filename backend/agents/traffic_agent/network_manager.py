"""
Dynamic Network Manager for SUPADSP Traffic Simulation.
Manages genuine OpenStreetMap road networks compiled via netconvert.
Strictly prohibits artificial synthetic grids and rejects silent fallbacks.
"""

from __future__ import annotations

import logging
import os
import ssl
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from backend.agents.traffic_agent.location_resolver import CANONICAL_LOCALITIES, LocationResolver

logger = logging.getLogger("traffic_agent.network_manager")

NETCONVERT_BIN_DEFAULT = r"C:\Program Files (x86)\Eclipse\Sumo\bin\netconvert.exe"


class LocalityNetworkError(Exception):
    """Raised when a road network cannot be located, compiled, or loaded for a locality."""
    pass


@dataclass
class NetworkInfo:
    locality_slug: str
    locality_name: str
    network_path: str
    network_filename: str
    osm_path: Optional[str]
    file_size_bytes: int
    edges_count: int
    junctions_count: int
    tls_count: int
    traffic_light_ids: List[str]
    origin: str  # "OSM_NETCONVERT"


class DynamicNetworkManager:
    """
    Manages authentic OpenStreetMap-derived SUMO networks for Hyderabad localities.
    Guarantees no synthetic rectangular grids and no silent locality substitution.
    """

    def __init__(
        self,
        networks_dir: Optional[str] = None,
        osm_dir: Optional[str] = None,
        netconvert_bin: Optional[str] = None,
    ):
        pkg_dir = os.path.dirname(os.path.abspath(__file__))
        smartcity_root = os.path.abspath(os.path.join(pkg_dir, "..", "..", ".."))

        self.networks_dir = networks_dir or os.path.join(smartcity_root, "simulations", "networks")
        self.osm_dir = osm_dir or os.path.join(smartcity_root, "simulations", "osm")
        self.netconvert_bin = netconvert_bin or os.getenv("NETCONVERT_BINARY", NETCONVERT_BIN_DEFAULT)

        os.makedirs(self.networks_dir, exist_ok=True)
        os.makedirs(self.osm_dir, exist_ok=True)
        self._network_cache: Dict[str, NetworkInfo] = {}

    def get_supported_localities(self) -> List[str]:
        return list(CANONICAL_LOCALITIES.keys())

    def get_network(self, locality_slug: str, auto_compile: bool = True) -> NetworkInfo:
        """
        Retrieves the NetworkInfo for the requested locality.
        If the network does not exist and auto_compile is True, attempts to fetch OSM
        and compile via netconvert. Never falls back to Narayanguda.
        """
        slug = (locality_slug or "").strip().lower()
        if slug in self._network_cache:
            return self._network_cache[slug]

        if slug not in CANONICAL_LOCALITIES:
            # Check if slug matches any alias
            resolved = LocationResolver.resolve(explicit_location=slug)
            if resolved:
                slug = resolved.slug
            else:
                raise LocalityNetworkError(
                    f"Unsupported locality '{locality_slug}'. "
                    f"Supported localities with real road networks: {list(CANONICAL_LOCALITIES.keys())}"
                )

        net_filename = f"{slug}_network.net.xml"
        net_path = os.path.join(self.networks_dir, net_filename)

        # Disallow synthetic grid networks
        if net_filename == "hyderabad_network.net.xml":
            raise LocalityNetworkError(
                "Artificial toy grid 'hyderabad_network.net.xml' is strictly prohibited. "
                "Must use genuine OpenStreetMap network."
            )

        if not os.path.isfile(net_path) or os.path.getsize(net_path) < 10000:
            if not auto_compile:
                raise LocalityNetworkError(
                    f"Compiled SUMO network for locality '{slug}' not found at {net_path}."
                )
            logger.info(f"SUMO network for '{slug}' not found. Compiling from OpenStreetMap data...")
            self._fetch_and_compile(slug)

        if not os.path.isfile(net_path) or os.path.getsize(net_path) < 10000:
            raise LocalityNetworkError(
                f"Failed to load or compile authentic SUMO network for locality '{slug}'."
            )

        # Inspect network
        info = self._inspect_network(slug, net_path)
        self._network_cache[slug] = info
        return info

    def _fetch_and_compile(self, slug: str) -> None:
        loc_data = CANONICAL_LOCALITIES[slug]
        osm_path = os.path.join(self.osm_dir, f"{slug}.osm")
        net_path = os.path.join(self.networks_dir, f"{slug}_network.net.xml")

        # Download OSM if needed
        if not os.path.isfile(osm_path) or os.path.getsize(osm_path) < 5000:
            min_lat, min_lon, max_lat, max_lon = loc_data["bbox"]
            url = f"https://api.openstreetmap.org/api/0.6/map?bbox={min_lon},{min_lat},{max_lon},{max_lat}"
            logger.info(f"Downloading real OSM road data for {slug} from {url}...")
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers={"User-Agent": "SmartCityHyderabad/2.0"})
            try:
                with urllib.request.urlopen(req, timeout=45, context=ctx) as resp:
                    data = resp.read()
                    with open(osm_path, "wb") as f:
                        f.write(data)
                logger.info(f"Saved OSM data to {osm_path} ({len(data)} bytes)")
            except Exception as exc:
                raise LocalityNetworkError(f"Failed to download OSM data for '{slug}': {exc}") from exc

        # Compile with netconvert
        cmd = [
            self.netconvert_bin,
            "--osm-files", osm_path,
            "--output-file", net_path,
            "--proj.utm",
            "--geometry.remove",
            "--roundabouts.guess",
            "--ramps.guess",
            "--junctions.join",
            "--tls.guess",
            "--tls.guess-signals",
            "--tls.join",
            "--remove-edges.isolated",
        ]
        logger.info(f"Running netconvert for {slug}: {' '.join(cmd)}")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            logger.error(f"netconvert failed for {slug}: {res.stderr}")
            raise LocalityNetworkError(f"netconvert compilation failed for '{slug}': {res.stderr}")

    def _inspect_network(self, slug: str, net_path: str) -> NetworkInfo:
        edges: Set[str] = set()
        junctions: Set[str] = set()
        tls: Set[str] = set()

        try:
            context = ET.iterparse(net_path, events=("start",))
            for event, elem in context:
                if elem.tag == "edge":
                    edge_id = elem.get("id")
                    if edge_id and not edge_id.startswith(":"):
                        edges.add(edge_id)
                elif elem.tag == "junction":
                    j_id = elem.get("id")
                    if j_id and not j_id.startswith(":"):
                        junctions.add(j_id)
                elif elem.tag == "tlLogic":
                    tl_id = elem.get("id")
                    if tl_id:
                        tls.add(tl_id)
                elem.clear()
        except Exception as exc:
            logger.error(f"Error parsing network file {net_path}: {exc}")

        loc_data = CANONICAL_LOCALITIES.get(slug, {})
        osm_path = os.path.join(self.osm_dir, f"{slug}.osm")
        if not os.path.isfile(osm_path):
            osm_path = None

        return NetworkInfo(
            locality_slug=slug,
            locality_name=loc_data.get("name", slug.capitalize()),
            network_path=net_path,
            network_filename=os.path.basename(net_path),
            osm_path=osm_path,
            file_size_bytes=os.path.getsize(net_path),
            edges_count=len(edges),
            junctions_count=len(junctions),
            tls_count=len(tls),
            traffic_light_ids=sorted(list(tls)),
            origin="OSM_NETCONVERT",
        )

    def list_available_networks(self) -> List[Dict[str, Any]]:
        results = []
        for slug in ["narayanguda", "tarnaka", "nacharam", "madhapur", "gachibowli"]:
            try:
                info = self.get_network(slug, auto_compile=False)
                results.append({
                    "locality": info.locality_name,
                    "slug": info.locality_slug,
                    "filename": info.network_filename,
                    "path": info.network_path,
                    "size_bytes": info.file_size_bytes,
                    "edges": info.edges_count,
                    "junctions": info.junctions_count,
                    "traffic_lights": info.tls_count,
                    "origin": info.origin,
                })
            except Exception:
                continue
        return results


_default_network_manager: Optional[DynamicNetworkManager] = None

def get_network_manager() -> DynamicNetworkManager:
    global _default_network_manager
    if _default_network_manager is None:
        _default_network_manager = DynamicNetworkManager()
    return _default_network_manager
