# SUPADSP — Project Structure

## 1. Repository Overview

**SUPADSP (Smart Urban Planning & AI Decision Support Platform)** is a decision support platform developed for municipal urban planning in Hyderabad (GHMC / HMDA). The codebase integrates multi-domain urban datasets (traffic, air quality, energy grid, weather, GIS), simulation scripts, backend services, and a React frontend dashboard.

This document serves as an authoritative navigation reference representing the **actual physical filesystem state** of the repository.

---

## 2. Complete Existing Repository Tree

```
SUPADSP/
├── .editorconfig
├── .env.example
├── .gitignore
├── docker-compose.yml
├── implementation_plan.md
├── legacy_architecture.txt
├── PROJECT_STRUCTURE.md
├── README.md
├── Smart_City_Architecture_Blueprint.pdf
│
├── architecture/
│   ├── SUPADSP_Architecture_Consolidated.md
│   ├── Vol10_Workflows_Reporting_Government_Approval.md
│   ├── Vol1_Executive_Summary_Architecture_Overview.md
│   ├── Vol2_Supervisor_AI_Agent_Architecture.md
│   ├── Vol3_Enterprise_Data_Architecture.md
│   ├── Vol4_AI_ML_Platform_MLOps.md
│   ├── Vol5_GIS_Architecture.md
│   ├── Vol6_Functional_Requirements_Specification.md
│   ├── Vol7_System_Modules_Specification.md
│   ├── Vol8_Security_Architecture.md
│   └── Vol9_Infrastructure_Deployment_Architecture.md
│
├── auth/ (empty)
│
├── backend/
│   ├── admin/ (empty)
│   ├── agents/
│   │   ├── energy_agent/
│   │   │   └── main.py
│   │   ├── optimization_agent/ (empty)
│   │   ├── policy_agent/ (empty)
│   │   ├── pollution_agent/
│   │   │   └── main.py
│   │   ├── simulation_agent/
│   │   │   └── main.py
│   │   ├── traffic_agent/
│   │   │   └── main.py
│   │   ├── verification_agent/ (empty)
│   │   └── weather_agent/
│   │       └── main.py
│   ├── context_service/ (empty)
│   ├── etl/ (empty)
│   ├── gateway/ (empty)
│   ├── gis/ (empty)
│   ├── ingestion/ (empty)
│   ├── monitoring/ (empty)
│   ├── notifications/ (empty)
│   ├── reporting/ (empty)
│   ├── shared/
│   │   ├── config/ (empty)
│   │   ├── constants/ (empty)
│   │   ├── database/ (empty)
│   │   ├── exceptions/ (empty)
│   │   ├── logging/ (empty)
│   │   ├── middleware/ (empty)
│   │   ├── schemas/ (empty)
│   │   ├── security/ (empty)
│   │   └── utils/ (empty)
│   ├── tests/ (empty)
│   ├── Dockerfile
│   └── requirements.txt
│
├── configs/
│   ├── development/ (empty)
│   ├── production/ (empty)
│   ├── staging/ (empty)
│   └── testing/ (empty)
│
├── database/
│   ├── migrations/ (empty)
│   ├── minio/ (empty)
│   ├── postgis/ (empty)
│   ├── redis/ (empty)
│   ├── seeds/ (empty)
│   └── timescaledb/ (empty)
│
├── datasets/
│   ├── raw/
│   │   ├── energy/
│   │   │   └── household_power_consumption.txt
│   │   ├── gis/
│   │   │   ├── southern-zone-260806.osm.pbf
│   │   │   └── telangana_districts.geojson
│   │   ├── pollution/
│   │   │   ├── 17226f5a-ccd0-4439-8fff-abdb5e618a85.csv
│   │   │   ├── 17b80ce4-26e7-4de3-8574-280539b826e6.csv
│   │   │   ├── 28932444-30e8-4937-bdfe-875c29a50865.csv
│   │   │   ├── 3ada2319-b74c-423d-b9d5-47c1639d7988.csv
│   │   │   ├── 4a65fc9e-830f-452c-a88c-4bf7dac90bbe.csv
│   │   │   ├── 547bd8c3-8022-4c35-8d5c-ed19d80712d0.csv
│   │   │   ├── 6ac23909-9a45-4c09-8c1f-a7d1bc5b3f4d.csv
│   │   │   ├── 703aecfe-555b-448e-a6b9-72ddf120f1ec.csv
│   │   │   ├── 778d4eed-44be-4fe5-8e0a-88a01247b062.csv
│   │   │   ├── 8ad84eca-f9e0-4359-88ad-8ca5ab60604b.csv
│   │   │   ├── 9c2add04-8e45-4186-b76f-f65d4feb237a.csv
│   │   │   ├── ac27da56-101e-4caa-a607-353ad05dd7fe.csv
│   │   │   ├── cpcb-aqi.csv.gz
│   │   │   ├── e83d0dba-7914-4d14-b889-3db7684ea5cd.csv
│   │   │   ├── hyd-bollaram-industrial-area-tspcb-2024-25.csv
│   │   │   ├── hyd-central-university-tspcb-2024-25.csv
│   │   │   ├── hyd-ecil-kapra-tspcb-2024-25.csv
│   │   │   ├── hyd-icrisat-patancheru-tspcb-2024-25.csv
│   │   │   ├── hyd-ida-pashamylaram-tspcb-2024-25.csv
│   │   │   ├── hyd-kokapet-tspcb-2024-25.csv
│   │   │   ├── hyd-kompally-municipal-office-tspcb-2024-25.csv
│   │   │   ├── hyd-nacharam_tsiic-iala-tspcb-2024-25.csv
│   │   │   ├── hyd-new-malakpet-tspcb-2024-25.csv
│   │   │   ├── hyd-ramachandrapuram-tspcb-2024-25.csv
│   │   │   ├── hyd-sanathnagar-tspcb-2024-25.csv
│   │   │   ├── hyd-somajiguda-tspcb-2024-25.csv
│   │   │   └── hyd-zoo-park-tspcb-2024-25.csv
│   │   ├── traffic/
│   │   │   ├── hyderabad_traffic_sensors_2023.csv
│   │   │   └── traffic_sensor_adjacency.csv
│   │   └── weather/
│   │       └── hyderabad_weather_2020_2024.csv
│   └── validation/ (empty)
│
├── docker/ (empty)
│
├── docs/
│   ├── api/ (empty)
│   ├── architecture/
│   │   └── SRS_Agentic_AI_Urban_Planning.md
│   ├── backend/ (empty)
│   ├── database/ (empty)
│   ├── deployment/ (empty)
│   ├── diagrams/ (empty)
│   ├── frontend/ (empty)
│   ├── gis/ (empty)
│   ├── ml/ (empty)
│   ├── monitoring/ (empty)
│   └── security/ (empty)
│
├── frontend/
│   ├── public/ (empty)
│   ├── src/
│   │   ├── app/
│   │   │   └── router/ (empty)
│   │   ├── assets/ (empty)
│   │   ├── components/
│   │   │   ├── ai/ (empty)
│   │   │   ├── animations/ (empty)
│   │   │   ├── cards/ (empty)
│   │   │   ├── charts/ (empty)
│   │   │   ├── common/ (empty)
│   │   │   ├── cult-ui/
│   │   │   │   └── CommandMenu.jsx
│   │   │   ├── dashboard/ (empty)
│   │   │   ├── dialogs/ (empty)
│   │   │   ├── footer/ (empty)
│   │   │   ├── forms/ (empty)
│   │   │   ├── gis/ (empty)
│   │   │   ├── loaders/ (empty)
│   │   │   ├── maps/ (empty)
│   │   │   ├── modals/ (empty)
│   │   │   ├── navbar/ (empty)
│   │   │   ├── notifications/ (empty)
│   │   │   ├── reactbits/ (empty)
│   │   │   ├── sidebar/ (empty)
│   │   │   ├── tables/ (empty)
│   │   │   ├── timeline/ (empty)
│   │   │   ├── ui/ (empty)
│   │   │   ├── widgets/ (empty)
│   │   │   ├── AQIGauge.jsx
│   │   │   ├── AnimatedCounter.jsx
│   │   │   ├── GlassCard.jsx
│   │   │   ├── MetricCard.jsx
│   │   │   ├── ParticleBackground.jsx
│   │   │   ├── ProblemSolverSection.jsx
│   │   │   ├── SparklineChart.jsx
│   │   │   └── StatusBadge.jsx
│   │   ├── constants/ (empty)
│   │   ├── contexts/ (empty)
│   │   ├── design-system/
│   │   │   ├── animations/ (empty)
│   │   │   ├── borders/ (empty)
│   │   │   ├── colors/ (empty)
│   │   │   ├── components/ (empty)
│   │   │   ├── icons/ (empty)
│   │   │   ├── shadows/ (empty)
│   │   │   ├── spacing/ (empty)
│   │   │   ├── themes/ (empty)
│   │   │   ├── tokens/ (empty)
│   │   │   └── typography/ (empty)
│   │   ├── features/
│   │   │   ├── administration/ (empty)
│   │   │   ├── analytics/ (empty)
│   │   │   ├── audit/ (empty)
│   │   │   ├── auth/ (empty)
│   │   │   ├── dashboard/ (empty)
│   │   │   ├── energy/ (empty)
│   │   │   ├── gis/ (empty)
│   │   │   ├── optimization/ (empty)
│   │   │   ├── pollution/ (empty)
│   │   │   ├── recommendation/ (empty)
│   │   │   ├── reports/ (empty)
│   │   │   ├── simulation/ (empty)
│   │   │   ├── traffic/ (empty)
│   │   │   └── weather/ (empty)
│   │   ├── hooks/ (empty)
│   │   ├── layouts/
│   │   │   ├── AdminLayout/ (empty)
│   │   │   ├── AuthLayout/ (empty)
│   │   │   ├── BlankLayout/ (empty)
│   │   │   ├── DashboardLayout/ (empty)
│   │   │   ├── GISLayout/ (empty)
│   │   │   └── DashboardLayout.jsx
│   │   ├── locales/ (empty)
│   │   ├── pages/
│   │   │   ├── AIModels/ (empty)
│   │   │   ├── Administration/ (empty)
│   │   │   ├── Analytics/ (empty)
│   │   │   ├── Approvals/ (empty)
│   │   │   ├── Audit/ (empty)
│   │   │   ├── Authentication/ (empty)
│   │   │   ├── Dashboard/ (empty)
│   │   │   ├── Energy/ (empty)
│   │   │   ├── GIS/ (empty)
│   │   │   ├── Notifications/ (empty)
│   │   │   ├── Optimization/ (empty)
│   │   │   ├── Pollution/ (empty)
│   │   │   ├── Profile/ (empty)
│   │   │   ├── Recommendation/ (empty)
│   │   │   ├── Reports/ (empty)
│   │   │   ├── Settings/ (empty)
│   │   │   ├── Simulation/ (empty)
│   │   │   ├── Traffic/ (empty)
│   │   │   ├── Weather/ (empty)
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Energy.jsx
│   │   │   ├── Planning.jsx
│   │   │   ├── Pollution.jsx
│   │   │   ├── Simulation.jsx
│   │   │   ├── Traffic.jsx
│   │   │   └── Weather.jsx
│   │   ├── services/
│   │   │   ├── api/ (empty)
│   │   │   ├── auth/ (empty)
│   │   │   ├── kafka/ (empty)
│   │   │   ├── map/ (empty)
│   │   │   ├── storage/ (empty)
│   │   │   └── websocket/ (empty)
│   │   ├── store/ (empty)
│   │   ├── styles/ (empty)
│   │   ├── tests/ (empty)
│   │   ├── types/ (empty)
│   │   ├── utils/ (empty)
│   │   ├── App.jsx
│   │   ├── index.css
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   └── vite.config.js
│
├── kafka/
│   ├── consumers/ (empty)
│   ├── producers/ (empty)
│   ├── schemas/ (empty)
│   ├── streams/ (empty)
│   └── topics/ (empty)
│
├── logs/ (empty) (generated/runtime)
│
├── ml/
│   ├── energy/ (empty)
│   ├── explainability/ (empty)
│   ├── optimization/ (empty)
│   ├── pollution/ (empty)
│   ├── serving/ (empty)
│   ├── shared/ (empty)
│   ├── simulation/ (empty)
│   ├── traffic/ (empty)
│   └── weather/ (empty)
│
├── scripts/
│   ├── database/ (empty)
│   ├── deployment/ (empty)
│   ├── migration/ (empty)
│   ├── model_training/ (empty)
│   ├── setup/ (empty)
│   ├── simulation/ (empty)
│   ├── download_datasets.py
│   ├── generate_traffic_dataset.py
│   └── test_download.py
│
├── simulations/
│   ├── configs/
│   │   └── hyderabad_sim.sumocfg
│   ├── detectors/
│   │   └── hyderabad_detectors.add.xml
│   ├── networks/
│   │   └── hyderabad_network.net.xml
│   ├── osm/ (empty)
│   ├── outputs/ (generated/runtime)
│   │   ├── hyderabad_simulation_results.json
│   │   └── hyderabad_traffic_metrics.csv
│   ├── routes/
│   │   └── hyderabad_traffic.rou.xml
│   ├── scenarios/ (empty)
│   ├── scripts/
│   │   └── run_hyderabad_simulation.py
│   ├── sumo/ (empty)
│   ├── traffic_lights/ (empty)
│   └── trips/ (empty)
│
├── tests/
│   ├── api/ (empty)
│   ├── backend/ (empty)
│   ├── e2e/ (empty)
│   ├── frontend/ (empty)
│   ├── integration/ (empty)
│   ├── load/ (empty)
│   ├── performance/ (empty)
│   ├── security/ (empty)
│   └── unit/ (empty)
│
└── tools/
    ├── benchmarking/ (empty)
    ├── diagnostics/ (empty)
    ├── gis_tools/ (empty)
    ├── model_tools/ (empty)
    ├── osm_tools/ (empty)
    └── synthetic_data/ (empty)
```

---

## 3. Folder Responsibilities

### Root Level Files
- `.editorconfig` — Editor formatting and whitespace configuration.
- `.env.example` — Environment variable template file.
- `.gitignore` — Git ignore file for excluding node modules, caches, and runtime files.
- `docker-compose.yml` — Container configuration for database, cache, storage, message broker, and identity services.
- `implementation_plan.md` — Project planning and architecture redesign document.
- `legacy_architecture.txt` — Reference notes on legacy system architecture.
- `PROJECT_STRUCTURE.md` — Repository structure and directory navigation document.
- `README.md` — Project documentation and setup instructions.
- `Smart_City_Architecture_Blueprint.pdf` — Architecture blueprint reference document.

---

### `architecture/`
Contains architecture specification documents:
- `SUPADSP_Architecture_Consolidated.md`: Master consolidated architecture specification.
- `Vol1_Executive_Summary_Architecture_Overview.md` to `Vol10_Workflows_Reporting_Government_Approval.md`: Detailed architecture volumes covering executive overview, agent architecture, data, ML/MLOps, GIS, functional requirements, modules, security, deployment, and government approval workflows.

---

### `auth/` *(empty)*
Reserved directory for authentication assets, realm definitions, and identity policies.

---

### `backend/`
FastAPI backend service layer containing `Dockerfile` and `requirements.txt`:
- `admin/` *(empty)*: Reserved directory for administrative and user management modules.
- `agents/`: Domain agent service implementations:
  - `energy_agent/main.py`: FastAPI service for substation load monitoring and recommendations.
  - `pollution_agent/main.py`: FastAPI service for AQI summaries and sensor monitoring.
  - `simulation_agent/main.py`: FastAPI service for triggering simulation runs.
  - `traffic_agent/main.py`: FastAPI service for traffic KPIs and signal optimization endpoints.
  - `weather_agent/main.py`: FastAPI service for current weather telemetry.
  - `optimization_agent/` *(empty)*: Reserved directory for optimization agent services.
  - `policy_agent/` *(empty)*: Reserved directory for policy synthesis agent services.
  - `verification_agent/` *(empty)*: Reserved directory for policy verification services.
- `context_service/` *(empty)*: Reserved directory for spatial and historical context handling.
- `etl/` *(empty)*: Reserved directory for ETL pipelines.
- `gateway/` *(empty)*: Reserved directory for API gateway services.
- `gis/` *(empty)*: Reserved directory for backend GIS endpoints and tile processing.
- `ingestion/` *(empty)*: Reserved directory for live sensor data ingestion services.
- `monitoring/` *(empty)*: Reserved directory for service health and metrics services.
- `notifications/` *(empty)*: Reserved directory for alert notification dispatching.
- `reporting/` *(empty)*: Reserved directory for report generation services.
- `shared/`: Shared backend modules:
  - `config/` *(empty)*, `constants/` *(empty)*, `database/` *(empty)*, `exceptions/` *(empty)*, `logging/` *(empty)*, `middleware/` *(empty)*, `schemas/` *(empty)*, `security/` *(empty)*, `utils/` *(empty)*.
- `tests/` *(empty)*: Reserved directory for backend service tests.

---

### `configs/`
Environment-specific configuration directory containing empty subdirectories:
- `development/` *(empty)*, `production/` *(empty)*, `staging/` *(empty)*, `testing/` *(empty)*.

---

### `database/`
Database scripts, migrations, and storage assets containing empty subdirectories:
- `migrations/` *(empty)*: Schema migration scripts.
- `minio/` *(empty)*: MinIO object storage configurations.
- `postgis/` *(empty)*: PostGIS spatial database scripts.
- `redis/` *(empty)*: Redis cache configurations.
- `seeds/` *(empty)*: Database seed data.
- `timescaledb/` *(empty)*: TimescaleDB hypertable scripts.

---

### `datasets/`
Data storage directory:
- `raw/`: Raw input datasets:
  - `energy/`: Contains `household_power_consumption.txt`.
  - `gis/`: Contains `southern-zone-260806.osm.pbf` and `telangana_districts.geojson`.
  - `pollution/`: Contains 27 TSPCB and CPCB monitoring station CSVs and archives.
  - `traffic/`: Contains `hyderabad_traffic_sensors_2023.csv` and `traffic_sensor_adjacency.csv`.
  - `weather/`: Contains `hyderabad_weather_2020_2024.csv`.
- `validation/` *(empty)*: Reserved directory for validation datasets.

---

### `docker/` *(empty)*
Reserved directory for Docker build files and compose configurations.

---

### `docs/`
Documentation directory:
- `architecture/`: Contains `SRS_Agentic_AI_Urban_Planning.md` (Software Requirements Specification).
- `api/` *(empty)*, `backend/` *(empty)*, `database/` *(empty)*, `deployment/` *(empty)*, `diagrams/` *(empty)*, `frontend/` *(empty)*, `gis/` *(empty)*, `ml/` *(empty)*, `monitoring/` *(empty)*, `security/` *(empty)*: Reserved directories for domain-specific documentation.

---

### `frontend/`
React 18 frontend dashboard application containing `package.json`, `package-lock.json`, `index.html`, and `vite.config.js`:
- `public/` *(empty)*: Static public assets directory.
- `src/`: Application source code:
  - `App.jsx`: Main routing and layout component.
  - `index.css`: Global styles and design system tokens.
  - `main.jsx`: Vite application entry point.
  - `components/`: UI components (`AQIGauge.jsx`, `AnimatedCounter.jsx`, `GlassCard.jsx`, `MetricCard.jsx`, `ParticleBackground.jsx`, `ProblemSolverSection.jsx`, `SparklineChart.jsx`, `StatusBadge.jsx`, `cult-ui/CommandMenu.jsx`) along with categorized subdirectories (`ai/`, `animations/`, `cards/`, `charts/`, `common/`, `dashboard/`, `dialogs/`, `footer/`, `forms/`, `gis/`, `loaders/`, `maps/`, `modals/`, `navbar/`, `notifications/`, `reactbits/`, `sidebar/`, `tables/`, `timeline/`, `ui/`, `widgets/`).
  - `layouts/`: Layout components (`DashboardLayout.jsx`) and layout subdirectories (`AdminLayout/`, `AuthLayout/`, `BlankLayout/`, `DashboardLayout/`, `GISLayout/`).
  - `pages/`: Page views (`Dashboard.jsx`, `Traffic.jsx`, `Pollution.jsx`, `Energy.jsx`, `Weather.jsx`, `Planning.jsx`, `Simulation.jsx`) and page subdirectories (`AIModels/`, `Administration/`, `Analytics/`, `Approvals/`, `Audit/`, `Authentication/`, `Dashboard/`, `Energy/`, `GIS/`, `Notifications/`, `Optimization/`, `Pollution/`, `Profile/`, `Recommendation/`, `Reports/`, `Settings/`, `Simulation/`, `Traffic/`, `Weather/`).
  - `app/router/` *(empty)*, `assets/` *(empty)*, `constants/` *(empty)*, `contexts/` *(empty)*, `design-system/` *(empty subdirectories)*, `features/` *(empty subdirectories)*, `hooks/` *(empty)*, `locales/` *(empty)*, `services/` *(empty subdirectories)*, `store/` *(empty)*, `styles/` *(empty)*, `tests/` *(empty)*, `types/` *(empty)*, `utils/` *(empty)*.

---

### `kafka/`
Message streaming assets containing empty subdirectories:
- `consumers/` *(empty)*, `producers/` *(empty)*, `schemas/` *(empty)*, `streams/` *(empty)*, `topics/` *(empty)*.

---

### `logs/` *(empty) (generated/runtime)*
Runtime directory for storing application and container log outputs.

---

### `ml/`
Machine learning models and training routines containing empty subdirectories:
- `energy/` *(empty)*, `explainability/` *(empty)*, `optimization/` *(empty)*, `pollution/` *(empty)*, `serving/` *(empty)*, `shared/` *(empty)*, `simulation/` *(empty)*, `traffic/` *(empty)*, `weather/` *(empty)*.

---

### `scripts/`
Operational automation scripts:
- `download_datasets.py`: Downloader script for weather, GIS, pollution, and energy datasets.
- `generate_traffic_dataset.py`: Traffic dataset and sensor adjacency matrix generator.
- `test_download.py`: Test download script.
- `database/` *(empty)*, `deployment/` *(empty)*, `migration/` *(empty)*, `model_training/` *(empty)*, `setup/` *(empty)*, `simulation/` *(empty)*: Automation script subdirectories.

---

### `simulations/`
SUMO microscopic traffic simulation files:
- `configs/hyderabad_sim.sumocfg`: SUMO configuration file.
- `detectors/hyderabad_detectors.add.xml`: Loop detector definitions.
- `networks/hyderabad_network.net.xml`: Network topology file.
- `routes/hyderabad_traffic.rou.xml`: Vehicle routes file.
- `scripts/run_hyderabad_simulation.py`: Simulation runner script.
- `outputs/` *(generated/runtime)*: Generated simulation output files (`hyderabad_simulation_results.json`, `hyderabad_traffic_metrics.csv`).
- `osm/` *(empty)*, `scenarios/` *(empty)*, `sumo/` *(empty)*, `traffic_lights/` *(empty)*, `trips/` *(empty)*.

---

### `tests/`
Test suites directory containing empty subdirectories:
- `api/` *(empty)*, `backend/` *(empty)*, `e2e/` *(empty)*, `frontend/` *(empty)*, `integration/` *(empty)*, `load/` *(empty)*, `performance/` *(empty)*, `security/` *(empty)*, `unit/` *(empty)*.

---

### `tools/`
Utility tools directory containing empty subdirectories:
- `benchmarking/` *(empty)*, `diagnostics/` *(empty)*, `gis_tools/` *(empty)*, `model_tools/` *(empty)*, `osm_tools/` *(empty)*, `synthetic_data/` *(empty)*.

---

## 4. Where to Put New Files

Place new files into their corresponding existing directories:

| What You Are Adding | Existing Destination Directory |
|---|---|
| New React Component | `frontend/src/components/` (or subdirectories such as `cards/`, `charts/`, `ui/`) |
| New React Page View | `frontend/src/pages/` |
| New Frontend Feature Code | `frontend/src/features/<domain>/` |
| New Backend Agent Implementation | `backend/agents/<agent_name>/` |
| New Backend Gateway / Service Code | `backend/gateway/` or `backend/<module>/` |
| New Shared Backend Utility / Schema | `backend/shared/schemas/` or `backend/shared/utils/` |
| New ML Training Script / Model | `ml/<domain>/` |
| New Database Migration | `database/migrations/` |
| New Database Seed | `database/seeds/` |
| New Raw Dataset | `datasets/raw/<domain>/` |
| New SUMO Simulation Config / Route | `simulations/configs/` or `simulations/routes/` |
| New Operational Script | `scripts/<category>/` |
| New Test Suite | `tests/<tier>/` (e.g. `tests/unit/`, `tests/api/`) |
| New Technical Documentation | `docs/<domain>/` |

---

## 5. Repository Rules

1. **Physical Filesystem Source of Truth:** Do not add files or folders to documentation unless they physically exist in the repository.
2. **No Placeholder Files:** Do not create `.gitkeep` files or empty placeholder files in the workspace.
3. **Runtime Data Separation:** Generated outputs (`logs/`, `simulations/outputs/`) must remain clearly identified as runtime data.
4. **Environment Isolation:** Use `.env.example` as the configuration template. Never commit real credentials or secrets.
5. **Preserve Directory Hierarchy:** Place all new implementations strictly within the existing folder structure.
