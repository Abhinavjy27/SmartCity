# VOLUME 5: GIS ARCHITECTURE

## Smart Urban Planning & AI Decision Support Platform

**Document ID:** SUPADSP-ARCH-V2-VOL5 | **Version:** 2.0.0 | **Classification:** Government Restricted

---

## 1. GIS-First Design Philosophy

Urban planning is inherently spatial. Every decision the platform supports — where to optimize traffic signals, which wards have the worst pollution, where to allocate energy infrastructure budget — is fundamentally a spatial question. The GIS architecture is not a visualization layer bolted onto the platform; it is a **first-class data, analysis, and presentation platform**.

### 1.1 GIS Architecture Principles

| Principle | Description |
|---|---|
| **OGC Standards Compliance** | All GIS services comply with OGC standards (WMS, WFS, WMTS, WCS) for interoperability |
| **Vector-First Rendering** | Vector tiles for dynamic, stylable, interactive map content (via MapLibre GL JS) |
| **Precomputed Raster Surfaces** | ML-derived surfaces (heatmaps, dispersion) precomputed and cached, not generated per request |
| **Layer Registry** | Centralized registry of all available layers with metadata, access control, and versioning |
| **Spatial Analysis Engine** | PostGIS-powered spatial analysis (buffer, proximity, routing, overlay) available via API |
| **Multi-Resolution** | Data available at city, zone, ward, road-segment levels |

### 1.2 GIS Platform Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                     GIS PLATFORM ARCHITECTURE                        │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  PRESENTATION: MapLibre GL JS (React Component)              │   │
│  │  • Vector tile rendering (GPU-accelerated)                   │   │
│  │  • Layer toggle panel with legend                            │   │
│  │  • Time slider for temporal layers                           │   │
│  │  • Prediction overlay rendering                              │   │
│  │  • Interactive feature popups                                │   │
│  │  • Measurement tools (area, distance)                        │   │
│  │  • Drawing tools (area selection)                            │   │
│  │  • Export tools (PDF, PNG)                                   │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
│                                 │                                    │
│  ┌──────────────────────────────▼───────────────────────────────┐   │
│  │  GIS API GATEWAY (FastAPI)                                   │   │
│  │  • Layer registry & discovery                                │   │
│  │  • Tile request routing                                      │   │
│  │  • Spatial query API                                         │   │
│  │  • Feature info API                                          │   │
│  │  • Authentication & authorization                            │   │
│  │  • Response caching                                          │   │
│  └─────┬────────────────────────────────────────┬───────────────┘   │
│        │                                        │                    │
│  ┌─────▼──────────────┐              ┌──────────▼───────────────┐   │
│  │  VECTOR TILE       │              │  RASTER/OGC              │   │
│  │  SERVER (Martin)   │              │  SERVER (GeoServer)      │   │
│  │                    │              │                          │   │
│  │  • PostGIS → MVT   │              │  • WMS (map images)     │   │
│  │  • Dynamic styling │              │  • WFS (feature data)   │   │
│  │  • High performance│              │  • WMTS (tiled maps)    │   │
│  │  • Rust-based      │              │  • WCS (raster data)    │   │
│  └─────┬──────────────┘              │  • SLD styling          │   │
│        │                              └──────────┬──────────────┘   │
│        │                                         │                   │
│  ┌─────▼─────────────────────────────────────────▼──────────────┐   │
│  │                     PostGIS                                   │   │
│  │  Vector layers, spatial indexes, routing (pgRouting)          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  RASTER/PREDICTION CACHE (Redis + MinIO)                     │   │
│  │  • Precomputed heatmaps (traffic congestion, AQI, energy)   │   │
│  │  • Pollution dispersion surfaces                              │   │
│  │  • Flood risk surfaces                                        │   │
│  │  • Heat island surfaces                                       │   │
│  │  • Refreshed on schedule (not per-request)                   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Layer Management System

### 2.1 Layer Registry

| Layer ID | Layer Name | Category | Source | Type | Update Frequency | Access |
|---|---|---|---|---|---|---|
| LYR-001 | Hyderabad Base Map | Base | OSM | Vector Tiles | Quarterly | All Users |
| LYR-002 | GHMC Ward Boundaries | Administrative | GHMC/PostGIS | Vector | As updated | All Users |
| LYR-003 | HMDA Zone Boundaries | Administrative | HMDA/PostGIS | Vector | As updated | All Users |
| LYR-004 | Road Network | Infrastructure | OSM/PostGIS | Vector | Quarterly | All Users |
| LYR-005 | Metro Routes & Stations | Transport | HMRL/PostGIS | Vector | Quarterly | All Users |
| LYR-006 | Bus Routes | Transport | TSRTC/PostGIS | Vector | Quarterly | All Users |
| LYR-007 | Buildings | Infrastructure | OSM/PostGIS | Vector | Quarterly | All Users |
| LYR-008 | Government Buildings | Infrastructure | GHMC/PostGIS | Vector | Quarterly | All Users |
| LYR-009 | Hospitals | POI | GHMC/PostGIS | Vector (Points) | Quarterly | All Users |
| LYR-010 | Police Stations | POI | Police/PostGIS | Vector (Points) | As updated | All Users |
| LYR-011 | Fire Stations | POI | Fire Dept/PostGIS | Vector (Points) | As updated | All Users |
| LYR-012 | Schools | POI | Education/PostGIS | Vector (Points) | Annual | All Users |
| LYR-013 | Lakes & Water Bodies | Environment | GHMC/PostGIS | Vector | As updated | All Users |
| LYR-014 | Power Substations | Infrastructure | TGSPDCL/PostGIS | Vector (Points) | Quarterly | Energy Officers |
| LYR-015 | Industrial Zones | Land Use | HMDA/PostGIS | Vector | Quarterly | All Users |
| LYR-016 | AQI Monitoring Stations | Monitoring | CPCB/PostGIS | Vector (Points) | As updated | All Users |
| LYR-017 | Traffic Signals | Traffic | Traffic Police/PostGIS | Vector (Points) | As updated | Traffic Officers |
| LYR-018 | Construction Zones | Operational | GHMC/PostGIS | Vector | Weekly | All Users |
| LYR-019 | **Traffic Congestion Heatmap** | **AI Prediction** | **Traffic Agent/Redis** | **Raster (precomputed)** | **Every 15 min** | All Users |
| LYR-020 | **AQI Heatmap** | **AI Prediction** | **Pollution Agent/Redis** | **Raster (precomputed)** | **Every 1 hour** | All Users |
| LYR-021 | **Pollution Dispersion Surface** | **AI Prediction** | **Pollution Agent/MinIO** | **Raster (precomputed)** | **Every 1 hour** | All Users |
| LYR-022 | **Energy Demand Heatmap** | **AI Prediction** | **Energy Agent/Redis** | **Raster (precomputed)** | **Every 1 hour** | Energy Officers |
| LYR-023 | **Flood Risk Surface** | **AI Prediction** | **Weather Agent/MinIO** | **Raster (precomputed)** | **On weather update** | All Users |
| LYR-024 | **Heat Island Surface** | **AI Prediction** | **Satellite Analysis/MinIO** | **Raster (precomputed)** | **Seasonal** | All Users |
| LYR-025 | Weather Overlay | Weather | Weather Agent/Redis | Vector + Raster | Hourly | All Users |
| LYR-026 | Live Alerts | Operational | Kafka/WebSocket | Vector (Points) | Real-time | All Users |
| LYR-027 | Prediction Points | AI Prediction | Model Output/Redis | Vector (Points) | Per request | Authorized Users |
| LYR-028 | Satellite View | Base | Bhuvan/MapTiler | Raster Tiles | As available | All Users |
| LYR-029 | Drainage Network | Infrastructure | GHMC/PostGIS | Vector | As updated | Infrastructure Engineers |
| LYR-030 | Land Use / Zoning | Planning | HMDA/PostGIS | Vector | Annual | Planners |

### 2.2 Spatial Analysis Capabilities

| Analysis | PostGIS Function | Use Case |
|---|---|---|
| Point-in-Polygon | `ST_Contains`, `ST_Within` | Find which ward a location belongs to |
| Buffer Analysis | `ST_Buffer`, `ST_DWithin` | Find hospitals within 5km of a location |
| Proximity Analysis | `ST_Distance`, `ST_ClosestPoint` | Find nearest fire station to incident |
| Route Analysis | `pgr_dijkstra`, `pgr_astar` | Shortest/fastest route between two points |
| Area Calculation | `ST_Area` | Calculate ward area, affected zone size |
| Intersection | `ST_Intersection` | Clip road network to ward boundary |
| Union | `ST_Union` | Merge adjacent affected zones |
| Spatial Join | `ST_Intersects` with JOIN | Find all traffic signals in a given ward |
| Heatmap Generation | Custom function + rasterization | Generate congestion/pollution heatmaps |
| Isochrone Analysis | `pgr_drivingDistance` + `ST_ConcaveHull` | Areas reachable within X minutes |
| Network Analysis | pgRouting functions | Travel time, shortest path, connectivity |

---

## 3. GIS Dashboard Components

### 3.1 Map Controls

| Control | Description |
|---|---|
| **Layer Panel** | Toggleable list of all available layers, grouped by category |
| **Legend** | Dynamic legend showing symbology for active layers |
| **Time Slider** | Temporal control for time-series prediction layers |
| **Basemap Switcher** | Toggle between street map, satellite, terrain views |
| **Drawing Tools** | Draw polygon/circle to select area of interest for analysis |
| **Measurement Tools** | Measure distance and area on the map |
| **Search** | Geocoding search for locations, wards, roads, landmarks |
| **Zoom to Ward/Zone** | Quick navigation to specific wards or zones |
| **Print/Export** | Export current map view as PDF or PNG with legend |
| **Feature Info** | Click on map feature to see detailed attributes |
| **Spatial Filter** | Filter data by map extent or drawn area |

### 3.2 Prediction Visualization

| Visualization | Technology | Update Pattern |
|---|---|---|
| Congestion heatmap | MapLibre heatmap layer from precomputed grid | Redis cache, refreshed every 15 min |
| AQI choropleth | Ward-level choropleth colored by predicted AQI | Redis cache, refreshed hourly |
| Dispersion surface | Raster overlay from precomputed GeoTIFF | MinIO, refreshed hourly |
| Energy demand map | Zone-level choropleth colored by demand | Redis cache, refreshed hourly |
| Flood risk zones | Polygon overlay with risk shading | MinIO, refreshed on weather update |
| Live alerts | Animated markers with severity indicators | WebSocket from Kafka event bus |
| Recommendation overlay | Highlighted area + intervention markers | On-demand per recommendation |

---

*End of Volume 5 — GIS Architecture*

*Next: Volume 6 — Functional Requirements Specification*
