# VOLUME 3: ENTERPRISE DATA ARCHITECTURE

## Smart Urban Planning & AI Decision Support Platform

**Document ID:** SUPADSP-ARCH-V2-VOL3  
**Version:** 2.0.0  
**Classification:** Government Restricted — Internal Use Only

---

## Table of Contents — Volume 3

1. [Data Architecture Overview](#1-data-architecture-overview)
2. [Data Sources](#2-data-sources)
3. [Data Ingestion Layer](#3-data-ingestion-layer)
4. [ETL/ELT Pipeline](#4-etlelt-pipeline)
5. [Polyglot Database Architecture](#5-polyglot-database-architecture)
6. [Complete Database Schema](#6-complete-database-schema)
7. [Data Governance Framework](#7-data-governance-framework)
8. [Data Quality Framework](#8-data-quality-framework)
9. [Feature Store Architecture](#9-feature-store-architecture)

---

## 1. Data Architecture Overview

### 1.1 Data Architecture Principles

| # | Principle | Description |
|---|---|---|
| DAP-01 | **Single Source of Truth** | Each data entity has exactly one authoritative source; all consumers read from that source |
| DAP-02 | **Data Governance** | Every dataset has a designated owner, steward, access policy, and retention policy |
| DAP-03 | **Data Quality First** | All data passes through validation before entering the platform; quality gates at every stage |
| DAP-04 | **Schema Evolution** | Schemas evolve without breaking consumers (backward-compatible changes, Avro/JSON Schema) |
| DAP-05 | **Metadata-Driven Design** | Every dataset is cataloged with rich metadata (source, lineage, quality, freshness) |
| DAP-06 | **Immutable Raw Data** | Raw ingested data is never modified; transformations produce new datasets |
| DAP-07 | **Version-Controlled Datasets** | Training datasets are versioned (DVC) for ML reproducibility |
| DAP-08 | **Enterprise Data Lineage** | Full traceability from raw source to prediction to recommendation |
| DAP-09 | **Data Provenance** | Every data point carries metadata about its origin, transformation, and quality |
| DAP-10 | **Master Data Management** | Canonical reference data (wards, zones, roads, buildings) managed centrally |
| DAP-11 | **Security by Design** | Encryption at rest and in transit; row-level security; least-privilege access |

### 1.2 Data Flow Architecture

```
╔══════════════════════════════════════════════════════════════════════════╗
║                        DATA FLOW ARCHITECTURE                           ║
║                                                                          ║
║  ┌─────────────────────────────────────────────────────────────────┐    ║
║  │                    EXTERNAL DATA SOURCES                        │    ║
║  │  IMD │ CPCB │ OSM │ ISRO │ GHMC │ HMDA │ TGSPDCL │ Census    │    ║
║  └───────────────────────┬─────────────────────────────────────────┘    ║
║                          │                                               ║
║                          ▼                                               ║
║  ┌─────────────────────────────────────────────────────────────────┐    ║
║  │                    INGESTION LAYER                               │    ║
║  │  Batch Ingestion │ Scheduled Import │ API Connectors │ Upload   │    ║
║  │  File Connectors │ Schema Validation │ Data Profiling           │    ║
║  └───────────────────────┬─────────────────────────────────────────┘    ║
║                          │                                               ║
║                          ▼                                               ║
║  ┌─────────────────────────────────────────────────────────────────┐    ║
║  │                    RAW DATA LAKE (MinIO)                        │    ║
║  │  Immutable raw data │ Versioned │ Partitioned by source/date   │    ║
║  └───────────────────────┬─────────────────────────────────────────┘    ║
║                          │                                               ║
║                          ▼                                               ║
║  ┌─────────────────────────────────────────────────────────────────┐    ║
║  │                    ETL/ELT PIPELINE (Airflow)                   │    ║
║  │  Validate → Clean → Transform → Feature Engineering →          │    ║
║  │  Quality Check → Store                                          │    ║
║  └───────┬──────────┬──────────┬──────────┬──────────┬────────────┘    ║
║          │          │          │          │          │                    ║
║          ▼          ▼          ▼          ▼          ▼                    ║
║  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐          ║
║  │PostgreSQL││ PostGIS  ││Timescale ││  Redis   ││  Elastic ││         ║
║  │          ││          ││   DB     ││          ││  search  ││         ║
║  └──────────┘└──────────┘└──────────┘└──────────┘└──────────┘          ║
║          │          │          │                                          ║
║          ▼          ▼          ▼                                          ║
║  ┌─────────────────────────────────────────────────────────────────┐    ║
║  │                    FEATURE STORE (Feast)                        │    ║
║  │  Online Features (Redis) │ Offline Features (Parquet/MinIO)    │    ║
║  └───────────────────────┬─────────────────────────────────────────┘    ║
║                          │                                               ║
║                          ▼                                               ║
║  ┌─────────────────────────────────────────────────────────────────┐    ║
║  │                    ML PLATFORM                                  │    ║
║  │  Training Datasets │ Inference Datasets │ Model Artifacts       │    ║
║  └─────────────────────────────────────────────────────────────────┘    ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## 2. Data Sources

### 2.1 Complete Data Source Registry

| Source ID | Source Name | Organization | Data Type | Format | Frequency | Protocol | Priority |
|---|---|---|---|---|---|---|---|
| DS-001 | IMD Weather Stations | India Meteorological Department | Weather observations | CSV/API | Hourly | REST API / FTP | Critical |
| DS-002 | ERA5 Reanalysis | ECMWF/Copernicus | Historical weather (40yr) | NetCDF/GRIB | Bulk download | CDS API | High |
| DS-003 | CPCB Air Quality | Central Pollution Control Board | AQI station readings | CSV/API | Hourly | REST API | Critical |
| DS-004 | CPCB Industrial Monitoring | CPCB | Industrial emissions | CSV | Daily | FTP/Portal | High |
| DS-005 | OpenStreetMap | OSM Community | Road network, buildings | .osm.pbf | Quarterly update | Geofabrik download | Critical |
| DS-006 | ISRO Bhuvan | ISRO/NRSC | Satellite imagery, DEM | GeoTIFF | Seasonal | Web portal/API | Medium |
| DS-007 | Landsat/Sentinel | USGS/ESA | Thermal + optical bands | GeoTIFF | Bi-weekly | Copernicus/USGS API | Medium |
| DS-008 | GHMC Ward Data | GHMC | Administrative boundaries, permits | GeoJSON/CSV | As updated | Database/API | Critical |
| DS-009 | HMDA Zone Data | HMDA | Metropolitan zones, development plans | GeoJSON/CSV | Quarterly | Database/API | High |
| DS-010 | Traffic Probe Data | SUMO Simulation / GPS probes | Vehicle speeds, volumes | CSV/Parquet | 5-15 min | Simulation/API | Critical |
| DS-011 | METR-LA / PeMS-BAY | Caltrans | Traffic benchmark data | CSV | Historical bulk | Download | High (benchmarking) |
| DS-012 | TGNPDCL Consumption | TGNPDCL | Energy consumption, grid load | CSV/API | Hourly | Database/API | Critical |
| DS-013 | TGSPDCL Consumption | TGSPDCL | Energy consumption, grid load | CSV/API | Hourly | Database/API | Critical |
| DS-014 | ASHRAE Energy | ASHRAE | Building energy benchmark | CSV | Historical bulk | Kaggle download | High (training) |
| DS-015 | Census Population | Census of India | Ward-level population | CSV | Decennial + projections | Download | Medium |
| DS-016 | Government Buildings | GHMC/CPWD | Building registry, consumption | CSV/Excel | Quarterly | Manual upload | Medium |
| DS-017 | Traffic Signal Data | Hyderabad Traffic Police | Signal timing, intersection data | CSV | As updated | Database/API | High |
| DS-018 | Accident Records | Hyderabad Traffic Police | Historical accident data | CSV/Excel | Monthly | Database/Portal | Medium |
| DS-019 | Construction Permits | GHMC | Active construction zones | CSV/GeoJSON | Weekly | Database/API | Medium |
| DS-020 | Event Calendar | GHMC/Tourism | Festivals, events, holidays | JSON/CSV | Monthly | Manual upload | Medium |
| DS-021 | Power Substations | TGNPDCL/TGSPDCL | Substation locations, capacity | GeoJSON/CSV | Quarterly | Manual upload | High |
| DS-022 | Hospital Registry | GHMC Health | Hospital locations, capacity | GeoJSON/CSV | Quarterly | Download | Medium |
| DS-023 | School Registry | Education Dept | School locations | GeoJSON/CSV | Annual | Download | Low |
| DS-024 | Police Station Registry | Hyderabad Police | Station locations | GeoJSON/CSV | As updated | Download | Low |
| DS-025 | Fire Station Registry | Fire Department | Station locations | GeoJSON/CSV | As updated | Download | Low |
| DS-026 | Metro/Bus Routes | Hyderabad Metro/TSRTC | Route geometries, schedules | GTFS/GeoJSON | Quarterly | GTFS feed | Medium |
| DS-027 | Lake/Water Bodies | GHMC/HMDA | Water body boundaries | GeoJSON | As updated | PostGIS | Medium |
| DS-028 | Industrial Zone Registry | TSPCB/HMDA | Industrial area boundaries | GeoJSON | Quarterly | Database | Medium |
| DS-029 | Drainage Network | GHMC Engineering | Drain network geometry | GeoJSON/Shapefile | As updated | PostGIS | Medium |
| DS-030 | Elevation Data (DEM) | ISRO/USGS | Digital Elevation Model | GeoTIFF | One-time | Download | Medium |

---

## 3. Data Ingestion Layer

### 3.1 Ingestion Architecture

```
                    ┌──────────────────────────────────┐
                    │         INGESTION LAYER           │
                    │         (Apache Airflow)          │
                    └──────────┬───────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
    ┌─────▼─────┐      ┌──────▼──────┐     ┌──────▼──────┐
    │   Batch    │      │  Scheduled  │     │   Manual    │
    │ Ingestion  │      │   Import    │     │   Upload    │
    │            │      │             │     │             │
    │ • One-time │      │ • Cron-     │     │ • File      │
    │   bulk     │      │   scheduled │     │   upload    │
    │   downloads│      │ • API       │     │   portal    │
    │ • OSM      │      │   polling   │     │ • Excel     │
    │ • ERA5     │      │ • IMD       │     │ • CSV       │
    │ • Census   │      │ • CPCB      │     │ • Shapefile │
    │ • Satellite│      │ • TGNPDCL   │     │ • GeoJSON   │
    └─────┬──────┘      └──────┬──────┘     └──────┬──────┘
          │                    │                    │
          └────────────────────┼────────────────────┘
                               │
                    ┌──────────▼───────────────────────┐
                    │     INGESTION PIPELINE            │
                    │                                   │
                    │  1. Schema Validation             │
                    │  2. Duplicate Detection           │
                    │  3. Data Profiling                │
                    │  4. Metadata Extraction           │
                    │  5. Quality Gate                  │
                    │  6. Store Raw → MinIO             │
                    │  7. Catalog → Metadata Store      │
                    └──────────────────────────────────┘
```

### 3.2 Ingestion Connectors

| Connector Type | Technology | Data Sources |
|---|---|---|
| **REST API Connector** | Python `requests` + retry logic | IMD API, CPCB API, TGNPDCL API |
| **FTP/SFTP Connector** | `paramiko` | CPCB bulk downloads, government file servers |
| **File System Connector** | `watchdog` + file parsers | Manual uploads (CSV, Excel, Shapefile) |
| **Database Connector** | SQLAlchemy / psycopg2 | GHMC database, HMDA database |
| **Geospatial Connector** | `geopandas` + `osmnx` + `rasterio` | OSM, GeoTIFF, Shapefiles, NetCDF |
| **Bulk Download Connector** | `wget` / `requests` scripts | ERA5, METR-LA, ASHRAE, satellite imagery |
| **GTFS Connector** | GTFS parser | Metro and bus route/schedule data |

### 3.3 Ingestion Schedule

| Data Source | Schedule | Type | Estimated Volume |
|---|---|---|---|
| IMD Weather | Every hour | Scheduled API polling | ~100 KB/hour |
| CPCB Air Quality | Every hour | Scheduled API polling | ~50 KB/hour |
| TGNPDCL Energy | Every hour | Scheduled API polling | ~200 KB/hour |
| Traffic Probe Data | Every 5-15 minutes | Stream / scheduled batch | ~1 MB/15min |
| OpenStreetMap | Quarterly | Manual batch | ~500 MB per extract |
| Satellite Imagery | Seasonal | Manual batch | ~2 GB per scene |
| Construction Permits | Weekly | Scheduled API polling | ~10 KB/week |
| Event Calendar | Monthly | Manual upload | ~5 KB/month |
| Government Buildings | Quarterly | Manual upload | ~50 KB/quarter |

---

## 4. ETL/ELT Pipeline

### 4.1 Pipeline Architecture (Apache Airflow)

```
Raw Data (MinIO)
       │
       ▼
┌──────────────┐
│   EXTRACT    │  Read from MinIO raw zone
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  VALIDATE    │  Schema validation (Great Expectations)
│              │  Null detection, range validation
│              │  Spatial/coordinate validation
│              │  Timestamp validation
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  NORMALIZE   │  Unit conversion, coordinate system standardization
│              │  Time zone normalization (IST)
│              │  Encoding standardization
└──────┬───────┘
       │
       ▼
┌──────────────┐
│    CLEAN     │  Missing value imputation (domain-specific strategies)
│              │  Outlier detection and handling
│              │  Duplicate removal
│              │  Data type correction
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  TRANSFORM   │  Resample to consistent time bins:
│              │    Traffic: 5-15 minute bins
│              │    Pollution: 1 hour bins
│              │    Energy: 1 hour bins
│              │    Weather: 1 hour bins
│              │  Z-score normalization (fit on training split only)
│              │  Spatial transformations (reprojection, clipping)
│              │  Temporal alignment across domains
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   FEATURE    │  Calendar features (hour, day, holiday, festival)
│ ENGINEERING  │  Spatial features (adjacency for GNNs, buffer zones)
│              │  Cross-domain merging (traffic vol → pollution frame)
│              │  Lagged features, rolling aggregates
│              │  Graph structure features (for GNN)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  QUALITY     │  Final quality gate (Great Expectations)
│   CHECK      │  Completeness, consistency, timeliness checks
│              │  Profile report generation
└──────┬───────┘
       │
       ├──► TimescaleDB (time-series data)
       ├──► PostGIS (spatial data)
       ├──► PostgreSQL (relational/reference data)
       ├──► Feature Store (Feast) update
       ├──► Training dataset generation (Parquet → MinIO)
       └──► Inference dataset generation
```

### 4.2 Domain-Specific ETL Pipelines

#### Traffic ETL Pipeline
| Stage | Operations |
|---|---|
| Extract | Ingest speed/volume data from SUMO simulation output or traffic probe API |
| Validate | Check speed ranges (0-120 km/h), volume ranges, coordinate validity |
| Clean | Impute missing segments using spatial interpolation, remove stuck-sensor readings |
| Transform | Resample to 5-15 min bins, normalize per-channel (z-score on training split) |
| Feature Engineering | Add calendar features, weather features, adjacency matrix for GNN, lagged speeds |
| Store | TimescaleDB (raw time series), Feature Store (engineered features), MinIO (training datasets) |

#### Pollution ETL Pipeline
| Stage | Operations |
|---|---|
| Extract | Ingest AQI readings from CPCB stations |
| Validate | Check pollutant ranges (PM2.5: 0-999, AQI: 0-500), station coordinates |
| Clean | Impute missing readings using temporal interpolation (document strategy explicitly), flag long gaps |
| Transform | Resample to 1-hour bins, normalize, merge traffic volume as feature |
| Feature Engineering | Add weather features, wind direction, industrial activity flags, calendar |
| Store | TimescaleDB, Feature Store, MinIO |

#### Energy ETL Pipeline
| Stage | Operations |
|---|---|
| Extract | Ingest consumption data from TGNPDCL/TGSPDCL |
| Validate | Check load ranges, meter readings, substation capacity |
| Clean | Handle meter resets, missing readings, outlier consumption spikes |
| Transform | Resample to 1-hour bins, normalize |
| Feature Engineering | Add weather (temperature → cooling demand), calendar, building metadata |
| Store | TimescaleDB, Feature Store, MinIO |

---

## 5. Polyglot Database Architecture

### 5.1 Database Selection Rationale

```
┌──────────────────────────────────────────────────────────────────────┐
│                 POLYGLOT DATABASE ARCHITECTURE                       │
│                                                                      │
│  Workload ──────────────────────────► Best-Fit Database              │
│                                                                      │
│  Relational data (users, roles,    ──► PostgreSQL 16                │
│  policies, recommendations, audit)                                   │
│                                                                      │
│  Spatial/vector data (roads,       ──► PostGIS 3.4+                 │
│  buildings, wards, infrastructure)    (PostgreSQL extension)         │
│                                                                      │
│  Time-series data (traffic speeds, ──► TimescaleDB 2.x              │
│  AQI readings, energy load,           (PostgreSQL extension)         │
│  predictions, model metrics)                                         │
│                                                                      │
│  Cache (session, hot queries,      ──► Redis 7.x                    │
│  precomputed tiles, API cache)                                       │
│                                                                      │
│  Binary objects (model artifacts,  ──► MinIO                        │
│  satellite images, raw datasets,      (S3-compatible)               │
│  reports, camera frames)                                             │
│                                                                      │
│  Full-text search (policy docs,    ──► Elasticsearch 8.x            │
│  knowledge base, audit log search,                                   │
│  recommendation search)                                              │
│                                                                      │
│  ML experiment tracking,           ──► MLflow + PostgreSQL           │
│  model registry                       (MLflow backend)               │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.2 PostgreSQL — Relational Data

**Purpose:** Core relational data store for application entities, business logic data, and audit trails.

**Stored Data:**
- User accounts, roles, permissions, departments
- Policy recommendations, approval history, decision audit trail
- Configuration parameters, feature flags, system settings
- AI model metadata (model registry table linking to MLflow)
- Report metadata, notification history
- Workflow states, approval chains
- Government regulations metadata (full-text in Elasticsearch)

**Advantages:** Enterprise-grade reliability, ACID transactions, rich SQL, extension ecosystem (PostGIS, TimescaleDB), row-level security, mature tooling, government-proven.

**Scaling Strategy:** Vertical scaling for Phase 1; read replicas for Phase 2; partitioning by tenant for Phase 3.

**Backup Strategy:** pg_dump daily, WAL archiving for point-in-time recovery, cross-region replication for DR.

### 5.3 PostGIS — Spatial Data

**Purpose:** All vector spatial data, spatial queries, spatial analysis.

**Stored Data:**
- Road network (nodes + edges with attributes)
- GHMC ward boundaries (150 wards)
- HMDA zone boundaries (5 zones)
- Administrative boundaries at all levels
- Building footprints with attributes
- Hospital, school, police station, fire station locations
- Power substations and grid infrastructure
- Metro routes, bus routes, metro stations
- Lake and water body boundaries
- Drainage network
- Industrial zone boundaries
- Construction zone geometries
- Traffic signal locations
- AQI monitoring station locations

**Key Spatial Operations:**
| Operation | Use Case | SQL Example |
|---|---|---|
| ST_Contains | Find which ward a point falls in | `SELECT ward_id FROM wards WHERE ST_Contains(geom, ST_MakePoint(78.37, 17.44))` |
| ST_Buffer | Find infrastructure within X meters | `SELECT * FROM hospitals WHERE ST_DWithin(geom, target_geom, 5000)` |
| ST_Intersection | Clip data to area of interest | `SELECT ST_Intersection(road.geom, ward.geom) ...` |
| ST_Length | Calculate road segment lengths | `SELECT ST_Length(geom::geography) FROM road_segments` |
| ST_Distance | Nearest facility analysis | `SELECT *, ST_Distance(geom, target) AS dist ORDER BY dist LIMIT 5` |
| pgr_dijkstra | Shortest path routing | Via pgRouting extension |

**Spatial Indexes:** GiST indexes on all geometry columns; R-tree for point-in-polygon queries.

### 5.4 TimescaleDB — Time Series Data

**Purpose:** All time-series data including sensor readings, predictions, and model metrics.

**Stored Data:**
- Traffic speed/volume per road segment (5-15 min resolution)
- AQI and pollutant readings per station (hourly)
- Energy consumption per zone/substation (hourly)
- Weather observations (hourly)
- Prediction outputs (logged for comparison)
- Model performance metrics over time
- System metrics history

**Advantages:** Hypertable partitioning (automatic time-based partitioning), continuous aggregates (materialized views auto-refreshed), native time-window functions, compression (10x+), full SQL compatibility with PostgreSQL.

**Key Features Used:**
| Feature | Use Case |
|---|---|
| Hypertables | Auto-partition traffic/pollution/energy time series by time |
| Continuous Aggregates | Pre-aggregated hourly/daily/weekly rollups for dashboard queries |
| Compression | Compress data older than 30 days (10x storage reduction) |
| Retention Policies | Auto-delete raw data older than configurable period, keep aggregates |
| Time_bucket | Efficient time-window aggregation queries |

**Retention Strategy:**
| Data Type | Raw Retention | Aggregated Retention |
|---|---|---|
| Traffic (5-min) | 90 days | 5 years (hourly), indefinite (daily) |
| Pollution (hourly) | 1 year | Indefinite (daily) |
| Energy (hourly) | 1 year | Indefinite (daily) |
| Weather (hourly) | 2 years | Indefinite (daily) |
| Predictions | 2 years | Indefinite (daily summary) |
| Model metrics | 1 year | Indefinite (daily) |

### 5.5 Redis — Cache Layer

**Purpose:** High-speed caching for frequently accessed data, session management, and real-time data.

**Stored Data:**
| Data | TTL | Purpose |
|---|---|---|
| Session tokens | 30 min | User session management |
| JWT tokens | Token lifetime | Authentication token cache |
| Last prediction per domain/location | 15 min | Avoid redundant predictions |
| Precomputed GIS tiles | 1 hour | Fast tile serving |
| Precomputed heatmaps | 30 min | Dashboard rendering |
| Current weather context | 1 hour | Avoid repeated weather API calls |
| Active alerts | Until resolved | Real-time alert display |
| API rate limiting counters | 1 min window | Rate limiting at API gateway |
| Optimization Pareto fronts | 1 hour | Cache for common optimization queries |
| Dashboard widget data | 5 min | Fast dashboard loading |

### 5.6 MinIO — Object Storage

**Purpose:** S3-compatible object storage for large binary objects.

**Stored Data:**
| Bucket | Contents | Lifecycle |
|---|---|---|
| `raw-data` | Raw ingested files (CSV, Excel, NetCDF, GeoTIFF) | Immutable, retained per policy |
| `training-datasets` | Versioned training datasets (Parquet format) | Versioned via DVC |
| `model-artifacts` | Trained model files (.pt, .pkl, .onnx) | Versioned via MLflow |
| `satellite-imagery` | Satellite scenes (GeoTIFF) | Long-term retention |
| `reports` | Generated PDF/Excel reports | 5-year retention |
| `gis-raster-cache` | Precomputed raster tiles, heatmaps | Refreshed on schedule |
| `documents` | Government documents, regulations | Indefinite |
| `camera-frames` | Traffic camera frame archives (future) | 30-day retention |
| `backups` | Database backup archives | Per DR policy |

### 5.7 Elasticsearch — Search & Knowledge

**Purpose:** Full-text search across documents, policies, audit logs, and recommendations.

**Indexes:**

| Index | Contents | Use Case |
|---|---|---|
| `policies` | Government policy documents | Policy search, precedent lookup |
| `regulations` | Environmental, traffic, energy regulations | Compliance checking, knowledge retrieval |
| `recommendations` | Historical AI recommendations | Precedent search, trend analysis |
| `audit-logs` | Comprehensive audit trail | Security audit, compliance reporting |
| `knowledge-base` | Urban planning guidelines, standards, manuals | Knowledge retrieval for Verification Agent |
| `reports` | Generated report metadata and content | Report search |
| `notifications` | Notification history | Notification audit |

---

## 6. Complete Database Schema

### 6.1 PostgreSQL Schema — Core Application

#### Users & Authentication

```sql
-- Users table
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    department_id UUID REFERENCES departments(department_id),
    role_id UUID REFERENCES roles(role_id),
    is_active BOOLEAN DEFAULT true,
    keycloak_id VARCHAR(255) UNIQUE,
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(user_id)
);

-- Roles
CREATE TABLE roles (
    role_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_name VARCHAR(100) UNIQUE NOT NULL,
    role_code VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Permissions
CREATE TABLE permissions (
    permission_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    permission_name VARCHAR(100) UNIQUE NOT NULL,
    permission_code VARCHAR(100) UNIQUE NOT NULL,
    module VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL, -- READ, WRITE, APPROVE, ADMIN
    description TEXT
);

-- Role-Permission mapping
CREATE TABLE role_permissions (
    role_id UUID REFERENCES roles(role_id),
    permission_id UUID REFERENCES permissions(permission_id),
    PRIMARY KEY (role_id, permission_id)
);

-- Departments
CREATE TABLE departments (
    department_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    department_name VARCHAR(255) NOT NULL,
    department_code VARCHAR(50) UNIQUE NOT NULL,
    organization VARCHAR(255), -- GHMC, HMDA, Traffic Police, TSPCB, etc.
    parent_department_id UUID REFERENCES departments(department_id),
    head_user_id UUID REFERENCES users(user_id),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### Recommendations & Policies

```sql
-- Recommendations
CREATE TABLE recommendations (
    recommendation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES planning_requests(request_id),
    recommendation_version INT DEFAULT 1,
    status VARCHAR(50) DEFAULT 'GENERATED', 
    -- GENERATED, UNDER_REVIEW, APPROVED, REJECTED, IMPLEMENTED, VERIFIED
    executive_summary TEXT NOT NULL,
    primary_action TEXT NOT NULL,
    location_name VARCHAR(255),
    ward_ids UUID[],
    time_frame JSONB,
    estimated_cost_inr NUMERIC(15,2),
    estimated_timeline_days INT,
    expected_benefits JSONB,
    expected_risks JSONB,
    alternative_strategies JSONB,
    confidence_score NUMERIC(4,3),
    confidence_breakdown JSONB,
    explainability JSONB,
    compliance_status JSONB,
    implementation_priority VARCHAR(20),
    department_assignment UUID REFERENCES departments(department_id),
    approval_chain JSONB,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    generated_by_agent VARCHAR(100),
    model_versions JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_recommendations_status ON recommendations(status);
CREATE INDEX idx_recommendations_department ON recommendations(department_assignment);
CREATE INDEX idx_recommendations_generated ON recommendations(generated_at);

-- Recommendation approval workflow
CREATE TABLE recommendation_approvals (
    approval_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id UUID REFERENCES recommendations(recommendation_id),
    stage VARCHAR(100) NOT NULL, 
    -- DEPARTMENT_REVIEW, TECHNICAL_VALIDATION, POLICY_REVIEW, COMMISSIONER_APPROVAL
    approver_id UUID REFERENCES users(user_id),
    status VARCHAR(50) DEFAULT 'PENDING',
    -- PENDING, APPROVED, REJECTED, REVISION_REQUESTED
    comments TEXT,
    revision_notes TEXT,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Planning requests
CREATE TABLE planning_requests (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id),
    raw_request TEXT NOT NULL,
    parsed_intent VARCHAR(100),
    intent_confidence NUMERIC(4,3),
    domains TEXT[],
    location_context JSONB,
    temporal_context JSONB,
    execution_status VARCHAR(50) DEFAULT 'RECEIVED',
    -- RECEIVED, PROCESSING, COMPLETED, FAILED, TIMEOUT
    execution_dag JSONB,
    execution_start TIMESTAMPTZ,
    execution_end TIMESTAMPTZ,
    execution_time_ms INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### Scenarios & Simulations

```sql
-- Simulation scenarios
CREATE TABLE simulation_scenarios (
    scenario_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID REFERENCES planning_requests(request_id),
    scenario_name VARCHAR(255) NOT NULL,
    scenario_type VARCHAR(100), 
    -- ROAD_CLOSURE, CONSTRUCTION, FESTIVAL, WEATHER, EMERGENCY, POLICY_IMPACT
    parameters JSONB NOT NULL,
    baseline_results JSONB,
    scenario_results JSONB,
    comparison_metrics JSONB,
    status VARCHAR(50) DEFAULT 'PENDING',
    created_by UUID REFERENCES users(user_id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Optimization runs
CREATE TABLE optimization_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID REFERENCES planning_requests(request_id),
    algorithm VARCHAR(100) NOT NULL, -- NSGA_II, NSGA_III, MILP, BAYESIAN
    objectives JSONB NOT NULL,
    constraints JSONB,
    pareto_front JSONB,
    selected_solution JSONB,
    hypervolume NUMERIC(10,6),
    execution_time_ms INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### AI Models & MLOps

```sql
-- AI model registry (complementary to MLflow)
CREATE TABLE ai_models (
    model_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name VARCHAR(255) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    domain VARCHAR(100) NOT NULL, -- traffic, pollution, energy, weather, anomaly
    algorithm VARCHAR(100) NOT NULL,
    mlflow_run_id VARCHAR(255),
    mlflow_model_uri VARCHAR(500),
    training_dataset_id UUID,
    evaluation_metrics JSONB,
    owner_id UUID REFERENCES users(user_id),
    approval_status VARCHAR(50) DEFAULT 'PENDING',
    -- PENDING, APPROVED, DEPLOYED, DEPRECATED, ROLLED_BACK
    deployment_status VARCHAR(50) DEFAULT 'NOT_DEPLOYED',
    inference_endpoint VARCHAR(500),
    drift_status VARCHAR(50) DEFAULT 'STABLE', -- STABLE, DRIFTING, CRITICAL
    last_retrained TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(model_name, model_version)
);

-- Model version history
CREATE TABLE model_versions (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id UUID REFERENCES ai_models(model_id),
    version VARCHAR(50) NOT NULL,
    training_started TIMESTAMPTZ,
    training_completed TIMESTAMPTZ,
    metrics JSONB, -- {mae, mape, rmse, accuracy, f1, etc.}
    parameters JSONB, -- hyperparameters
    artifact_path VARCHAR(500), -- MinIO path
    promoted_to_production BOOLEAN DEFAULT false,
    promoted_at TIMESTAMPTZ,
    promoted_by UUID REFERENCES users(user_id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### Configuration & Administration

```sql
-- System configuration
CREATE TABLE system_config (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_key VARCHAR(255) UNIQUE NOT NULL,
    config_value JSONB NOT NULL,
    description TEXT,
    category VARCHAR(100),
    is_sensitive BOOLEAN DEFAULT false,
    updated_by UUID REFERENCES users(user_id),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Feature flags
CREATE TABLE feature_flags (
    flag_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flag_name VARCHAR(100) UNIQUE NOT NULL,
    is_enabled BOOLEAN DEFAULT false,
    description TEXT,
    enabled_for_roles UUID[],
    enabled_for_departments UUID[],
    updated_by UUID REFERENCES users(user_id),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit logs (append-only)
CREATE TABLE audit_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id UUID,
    before_state JSONB,
    after_state JSONB,
    ip_address INET,
    user_agent TEXT,
    session_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_created ON audit_logs(created_at);

-- Notifications
CREATE TABLE notifications (
    notification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id),
    type VARCHAR(50) NOT NULL, -- EMAIL, SMS, IN_APP, PUSH
    category VARCHAR(100) NOT NULL, -- ALERT, RECOMMENDATION, SYSTEM, APPROVAL
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    is_read BOOLEAN DEFAULT false,
    read_at TIMESTAMPTZ,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 6.2 PostGIS Schema — Spatial Data

```sql
-- Road segments (imported from OSM via osmnx)
CREATE TABLE road_segments (
    segment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    osm_id BIGINT,
    name VARCHAR(255),
    road_type VARCHAR(50), -- motorway, primary, secondary, tertiary, residential
    lanes INT,
    speed_limit INT, -- km/h
    length_m NUMERIC(10,2),
    capacity_veh_hr INT,
    ward_id UUID REFERENCES wards(ward_id),
    geom GEOMETRY(LINESTRING, 4326) NOT NULL
);

CREATE INDEX idx_road_segments_geom ON road_segments USING GIST(geom);
CREATE INDEX idx_road_segments_ward ON road_segments(ward_id);
CREATE INDEX idx_road_segments_type ON road_segments(road_type);

-- Intersections / Junctions
CREATE TABLE intersections (
    intersection_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255),
    intersection_type VARCHAR(50), -- signalized, roundabout, uncontrolled
    num_approaches INT,
    has_signal BOOLEAN DEFAULT false,
    signal_id UUID REFERENCES traffic_signals(signal_id),
    ward_id UUID REFERENCES wards(ward_id),
    geom GEOMETRY(POINT, 4326) NOT NULL
);

CREATE INDEX idx_intersections_geom ON intersections USING GIST(geom);

-- GHMC Wards
CREATE TABLE wards (
    ward_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ward_number INT UNIQUE NOT NULL,
    ward_name VARCHAR(255) NOT NULL,
    zone_id UUID REFERENCES hmda_zones(zone_id),
    area_sq_km NUMERIC(8,3),
    population INT,
    population_density NUMERIC(10,2),
    geom GEOMETRY(MULTIPOLYGON, 4326) NOT NULL
);

CREATE INDEX idx_wards_geom ON wards USING GIST(geom);

-- HMDA Zones
CREATE TABLE hmda_zones (
    zone_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    zone_name VARCHAR(255) NOT NULL,
    zone_code VARCHAR(50) UNIQUE NOT NULL,
    area_sq_km NUMERIC(10,3),
    geom GEOMETRY(MULTIPOLYGON, 4326) NOT NULL
);

CREATE INDEX idx_hmda_zones_geom ON hmda_zones USING GIST(geom);

-- Buildings
CREATE TABLE buildings (
    building_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    osm_id BIGINT,
    building_type VARCHAR(100), -- residential, commercial, government, industrial, educational, hospital
    name VARCHAR(255),
    floors INT,
    height_m NUMERIC(6,2),
    area_sq_m NUMERIC(10,2),
    ward_id UUID REFERENCES wards(ward_id),
    is_government BOOLEAN DEFAULT false,
    geom GEOMETRY(POLYGON, 4326) NOT NULL
);

CREATE INDEX idx_buildings_geom ON buildings USING GIST(geom);
CREATE INDEX idx_buildings_type ON buildings(building_type);
CREATE INDEX idx_buildings_govt ON buildings(is_government) WHERE is_government = true;

-- Critical infrastructure
CREATE TABLE hospitals (
    hospital_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    hospital_type VARCHAR(100), -- government, private, specialty
    beds INT,
    ward_id UUID REFERENCES wards(ward_id),
    geom GEOMETRY(POINT, 4326) NOT NULL
);

CREATE TABLE police_stations (
    station_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    station_type VARCHAR(50),
    ward_id UUID REFERENCES wards(ward_id),
    geom GEOMETRY(POINT, 4326) NOT NULL
);

CREATE TABLE fire_stations (
    station_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    ward_id UUID REFERENCES wards(ward_id),
    geom GEOMETRY(POINT, 4326) NOT NULL
);

CREATE TABLE schools (
    school_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    school_type VARCHAR(100),
    ward_id UUID REFERENCES wards(ward_id),
    geom GEOMETRY(POINT, 4326) NOT NULL
);

-- Power infrastructure
CREATE TABLE power_substations (
    substation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    capacity_mva NUMERIC(10,2),
    voltage_kv NUMERIC(8,2),
    discom VARCHAR(50), -- TGNPDCL or TGSPDCL
    ward_id UUID REFERENCES wards(ward_id),
    geom GEOMETRY(POINT, 4326) NOT NULL
);

-- Traffic signals
CREATE TABLE traffic_signals (
    signal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    junction_name VARCHAR(255),
    signal_type VARCHAR(50),
    num_phases INT,
    cycle_time_seconds INT,
    ward_id UUID REFERENCES wards(ward_id),
    geom GEOMETRY(POINT, 4326) NOT NULL
);

-- Metro stations
CREATE TABLE metro_stations (
    station_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    line VARCHAR(50),
    ward_id UUID REFERENCES wards(ward_id),
    geom GEOMETRY(POINT, 4326) NOT NULL
);

-- Metro / Bus routes
CREATE TABLE transit_routes (
    route_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    route_name VARCHAR(255) NOT NULL,
    route_type VARCHAR(50), -- metro, bus_ordinary, bus_express, bus_ac
    operator VARCHAR(100), -- Hyderabad Metro, TSRTC
    geom GEOMETRY(MULTILINESTRING, 4326) NOT NULL
);

-- Water bodies
CREATE TABLE water_bodies (
    water_body_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255),
    water_type VARCHAR(50), -- lake, river, reservoir, tank
    area_sq_km NUMERIC(8,3),
    geom GEOMETRY(MULTIPOLYGON, 4326) NOT NULL
);

-- Industrial zones
CREATE TABLE industrial_zones (
    zone_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    zone_type VARCHAR(100), -- manufacturing, pharmaceutical, IT, mixed
    area_sq_km NUMERIC(8,3),
    num_facilities INT,
    geom GEOMETRY(MULTIPOLYGON, 4326) NOT NULL
);

-- AQI monitoring stations
CREATE TABLE aqi_stations (
    station_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    station_name VARCHAR(255) NOT NULL,
    station_code VARCHAR(50) UNIQUE,
    operator VARCHAR(100), -- CPCB, TSPCB
    station_type VARCHAR(50), -- continuous, manual
    ward_id UUID REFERENCES wards(ward_id),
    geom GEOMETRY(POINT, 4326) NOT NULL
);

-- Construction zones (active)
CREATE TABLE construction_zones (
    construction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_name VARCHAR(255),
    construction_type VARCHAR(100),
    affected_road_segments UUID[],
    start_date DATE,
    expected_end_date DATE,
    status VARCHAR(50), -- active, completed, planned
    impact_level VARCHAR(20), -- low, medium, high
    geom GEOMETRY(POLYGON, 4326) NOT NULL
);
```

### 6.3 TimescaleDB Schema — Time Series

```sql
-- Traffic time series
CREATE TABLE traffic_observations (
    time TIMESTAMPTZ NOT NULL,
    segment_id UUID NOT NULL,
    speed_kmh NUMERIC(6,2),
    volume INT,
    occupancy NUMERIC(5,2),
    data_source VARCHAR(50), -- sensor, probe, simulation
    quality_flag VARCHAR(20) DEFAULT 'GOOD'
);

SELECT create_hypertable('traffic_observations', 'time');
CREATE INDEX idx_traffic_obs_segment ON traffic_observations(segment_id, time DESC);

-- Continuous aggregate: hourly traffic
CREATE MATERIALIZED VIEW traffic_hourly
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 hour', time) AS bucket,
       segment_id,
       AVG(speed_kmh) AS avg_speed,
       SUM(volume) AS total_volume,
       AVG(occupancy) AS avg_occupancy
FROM traffic_observations
GROUP BY bucket, segment_id;

-- AQI time series
CREATE TABLE pollution_observations (
    time TIMESTAMPTZ NOT NULL,
    station_id UUID NOT NULL,
    aqi INT,
    pm25 NUMERIC(7,2),
    pm10 NUMERIC(7,2),
    no2 NUMERIC(7,2),
    so2 NUMERIC(7,2),
    co NUMERIC(7,2),
    o3 NUMERIC(7,2),
    data_source VARCHAR(50),
    quality_flag VARCHAR(20) DEFAULT 'GOOD'
);

SELECT create_hypertable('pollution_observations', 'time');

-- Energy consumption time series
CREATE TABLE energy_observations (
    time TIMESTAMPTZ NOT NULL,
    zone_id UUID NOT NULL,
    substation_id UUID,
    load_mw NUMERIC(10,3),
    demand_mw NUMERIC(10,3),
    supply_mw NUMERIC(10,3),
    data_source VARCHAR(50),
    quality_flag VARCHAR(20) DEFAULT 'GOOD'
);

SELECT create_hypertable('energy_observations', 'time');

-- Weather observations
CREATE TABLE weather_observations (
    time TIMESTAMPTZ NOT NULL,
    station_id VARCHAR(50) NOT NULL,
    temperature_c NUMERIC(5,2),
    humidity_pct NUMERIC(5,2),
    rainfall_mm NUMERIC(7,2),
    wind_speed_kmh NUMERIC(6,2),
    wind_direction_deg INT,
    pressure_hpa NUMERIC(7,2),
    visibility_km NUMERIC(6,2),
    data_source VARCHAR(50)
);

SELECT create_hypertable('weather_observations', 'time');

-- Prediction log (tracking all predictions for comparison)
CREATE TABLE prediction_log (
    time TIMESTAMPTZ NOT NULL,
    model_id UUID NOT NULL,
    model_version VARCHAR(50),
    domain VARCHAR(50),
    location_id UUID,
    prediction_horizon_hours INT,
    predicted_value NUMERIC(10,3),
    actual_value NUMERIC(10,3), -- filled in when actual is available
    confidence_lower NUMERIC(10,3),
    confidence_upper NUMERIC(10,3),
    prediction_error NUMERIC(10,3), -- filled in when actual is available
    metadata JSONB
);

SELECT create_hypertable('prediction_log', 'time');

-- Model performance metrics
CREATE TABLE model_metrics (
    time TIMESTAMPTZ NOT NULL,
    model_id UUID NOT NULL,
    metric_name VARCHAR(100), -- mae, mape, rmse, accuracy, latency_ms
    metric_value NUMERIC(12,6),
    data_window VARCHAR(50) -- last_hour, last_day, last_week
);

SELECT create_hypertable('model_metrics', 'time');
```

---

## 7. Data Governance Framework

### 7.1 Data Governance Structure

| Role | Responsibility | Person/Team |
|---|---|---|
| **Data Owner** | Accountable for data quality, access, and lifecycle for a domain | Department Head (e.g., Traffic Planning Officer for traffic data) |
| **Data Steward** | Day-to-day data quality, metadata, lineage management | Assigned data analyst per domain |
| **Data Custodian** | Technical management — backups, security, access provisioning | Platform Engineering Team |
| **Data Consumer** | Uses data for analysis, prediction, reporting | AI Agents, Dashboard Users |

### 7.2 Data Lifecycle Management

| Phase | Policy |
|---|---|
| **Creation/Ingestion** | All data enters through validated ingestion pipelines; raw data stored immutably in MinIO |
| **Storage** | Data stored in purpose-optimized databases; encrypted at rest |
| **Processing** | ETL pipelines with quality gates; lineage tracked |
| **Usage** | Access controlled via RBAC; row-level security for department-scoped data |
| **Archival** | Data older than retention period compressed and archived to cold storage |
| **Deletion** | PII data deleted per policy; scientific data retained for model training |

### 7.3 Data Lineage

Every data artifact tracks its lineage:

```
Raw AQI CSV (CPCB download, 2024-01-01)
   → Ingestion Pipeline (validated, profiled)
   → Raw Zone (MinIO: raw-data/cpcb/2024/01/01/)
   → ETL Pipeline (cleaned, imputed, transformed)
   → TimescaleDB (pollution_observations table)
   → Feature Engineering (merged with weather, traffic)
   → Feature Store (pollution_features entity)
   → Training Dataset v2.1 (MinIO: training-datasets/pollution/v2.1/)
   → Model Training (TFT, MLflow experiment-42)
   → Model Artifact (MinIO: model-artifacts/pollution-tft-v2.1.pt)
   → Inference → Prediction
   → Recommendation REC-2026-08-001
```

---

## 8. Data Quality Framework

### 8.1 Quality Dimensions

| Dimension | Definition | Measurement |
|---|---|---|
| **Completeness** | Percentage of non-null values in required fields | `COUNT(non_null) / COUNT(total) * 100` |
| **Accuracy** | Data correctly represents the real-world entity | Range validation, cross-source comparison |
| **Consistency** | Same data in different stores agrees | Cross-database reconciliation checks |
| **Timeliness** | Data is available within expected freshness window | `NOW() - max(timestamp)` vs. expected frequency |
| **Validity** | Data conforms to business rules and formats | Schema validation, constraint checks |
| **Uniqueness** | No unintended duplicates | Duplicate detection on natural keys |

### 8.2 Great Expectations Integration

```python
# Example expectation suite for pollution data
expectation_suite = {
    "data_asset_type": "pollution_observations",
    "expectations": [
        {"expectation_type": "expect_column_values_to_not_be_null",
         "kwargs": {"column": "time"}},
        {"expectation_type": "expect_column_values_to_not_be_null",
         "kwargs": {"column": "station_id"}},
        {"expectation_type": "expect_column_values_to_be_between",
         "kwargs": {"column": "aqi", "min_value": 0, "max_value": 500}},
        {"expectation_type": "expect_column_values_to_be_between",
         "kwargs": {"column": "pm25", "min_value": 0, "max_value": 999}},
        {"expectation_type": "expect_column_values_to_be_between",
         "kwargs": {"column": "pm10", "min_value": 0, "max_value": 999}},
        {"expectation_type": "expect_column_values_to_be_of_type",
         "kwargs": {"column": "time", "type_": "TIMESTAMP"}},
    ]
}
```

---

## 9. Feature Store Architecture

### 9.1 Feature Store Design (Feast)

```
┌──────────────────────────────────────────────────────┐
│                   FEATURE STORE (Feast)               │
│                                                       │
│  ┌─────────────────────────────────────────────────┐ │
│  │            FEATURE REGISTRY                      │ │
│  │  Defines features, entities, data sources        │ │
│  │  Version-controlled in Git                       │ │
│  └─────────────────────────────────────────────────┘ │
│                                                       │
│  ┌──────────────────────┐ ┌────────────────────────┐ │
│  │   OFFLINE STORE      │ │    ONLINE STORE        │ │
│  │   (Parquet on MinIO) │ │    (Redis)             │ │
│  │                      │ │                        │ │
│  │   For batch training │ │   For real-time        │ │
│  │   Historical features│ │   inference            │ │
│  │   Feature retrieval  │ │   Low-latency reads    │ │
│  └──────────────────────┘ └────────────────────────┘ │
│                                                       │
│  Feature Groups:                                      │
│  • Traffic Features   • Energy Features              │
│  • Pollution Features • Weather Features             │
│  • GIS Features       • Calendar Features            │
│  • Spatial Features   • Historical Features          │
│  • Event Features     • Cross-Domain Features        │
└──────────────────────────────────────────────────────┘
```

### 9.2 Feature Definitions

#### Traffic Features
| Feature Name | Type | Source | Description |
|---|---|---|---|
| `segment_avg_speed_1h` | Float | TimescaleDB | Average speed on segment over last 1 hour |
| `segment_avg_speed_24h` | Float | TimescaleDB | Average speed over last 24 hours |
| `segment_volume_1h` | Int | TimescaleDB | Total vehicle volume in last hour |
| `segment_congestion_index` | Float | Computed | volume / capacity ratio |
| `road_type_encoded` | Int | PostGIS | Encoded road type (motorway=1, primary=2, ...) |
| `num_lanes` | Int | PostGIS | Number of lanes |
| `speed_limit` | Int | PostGIS | Posted speed limit |
| `is_peak_hour` | Bool | Calendar | Whether current time is peak hour |
| `day_of_week` | Int | Calendar | 0=Monday, 6=Sunday |
| `is_holiday` | Bool | Calendar | Whether today is a public holiday |
| `is_festival` | Bool | Calendar | Whether a festival is active |
| `adjacent_segment_avg_speed` | Float | GNN | Average speed of graph-adjacent segments |
| `historical_same_hour_speed` | Float | TimescaleDB | Historical average speed at this hour |

#### Pollution Features
| Feature Name | Type | Source | Description |
|---|---|---|---|
| `station_aqi_1h` | Int | TimescaleDB | AQI at station in last hour |
| `station_pm25_1h` | Float | TimescaleDB | PM2.5 at station in last hour |
| `station_pm10_1h` | Float | TimescaleDB | PM10 in last hour |
| `nearby_traffic_volume` | Int | Cross-domain | Total traffic volume within 2km radius |
| `wind_speed` | Float | Weather | Current wind speed |
| `wind_direction` | Int | Weather | Current wind direction (degrees) |
| `temperature` | Float | Weather | Current temperature |
| `humidity` | Float | Weather | Current humidity |
| `rainfall_1h` | Float | Weather | Rainfall in last hour |
| `industrial_proximity` | Float | PostGIS | Distance to nearest industrial zone |
| `population_density` | Float | PostGIS | Population density of ward |

#### Energy Features
| Feature Name | Type | Source | Description |
|---|---|---|---|
| `zone_load_1h` | Float | TimescaleDB | Current zone load (MW) |
| `zone_load_24h_avg` | Float | TimescaleDB | 24-hour average load |
| `zone_peak_load_today` | Float | TimescaleDB | Peak load so far today |
| `temperature` | Float | Weather | Current temperature (→ cooling demand) |
| `cooling_degree_days` | Float | Computed | CDD for the day |
| `building_count` | Int | PostGIS | Number of buildings in zone |
| `govt_building_pct` | Float | PostGIS | Percentage of government buildings |
| `is_business_day` | Bool | Calendar | Whether today is a working day |

#### Weather Features
| Feature Name | Type | Source | Description |
|---|---|---|---|
| `temperature_c` | Float | IMD/ERA5 | Temperature in Celsius |
| `humidity_pct` | Float | IMD/ERA5 | Relative humidity percentage |
| `rainfall_mm` | Float | IMD/ERA5 | Rainfall in mm |
| `wind_speed_kmh` | Float | IMD/ERA5 | Wind speed |
| `wind_direction_deg` | Int | IMD/ERA5 | Wind direction |
| `pressure_hpa` | Float | IMD/ERA5 | Atmospheric pressure |
| `cloud_cover_pct` | Float | IMD/ERA5 | Cloud cover percentage |

### 9.3 Feature Versioning

Features are versioned alongside training datasets:
- Feature definitions stored in Git (Feast feature repo)
- Feature values for training snapshotted to MinIO (Parquet) with DVC versioning
- Model training logs reference exact feature version used
- Feature drift monitored (comparison of training distribution vs. inference distribution)

---

*End of Volume 3 — Enterprise Data Architecture*

*Next: Volume 4 — AI/ML Platform & MLOps*
