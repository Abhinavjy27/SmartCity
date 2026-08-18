# VOLUME 7: SYSTEM MODULES SPECIFICATION

## Smart Urban Planning & AI Decision Support Platform

**Document ID:** SUPADSP-ARCH-V2-VOL7 | **Version:** 2.0.0 | **Classification:** Government Restricted

---

## Module Registry

### Complete System Module List

| Module ID | Module Name | Purpose | Microservice | Port |
|---|---|---|---|---|
| MOD-01 | API Gateway Module | Request routing, auth validation, rate limiting | Kong Gateway | 8000 |
| MOD-02 | Identity & Access Module | Authentication, authorization, RBAC, MFA | Keycloak | 8080 |
| MOD-03 | Supervisor AI Module | Intent understanding, task planning, agent orchestration | supervisor-svc | 8100 |
| MOD-04 | Agent Registry Module | Agent registration, discovery, health monitoring | agent-registry-svc | 8101 |
| MOD-05 | Capability Registry Module | Capability mapping, agent-capability resolution | capability-registry-svc | 8102 |
| MOD-06 | Context Manager Module | Context loading, enrichment, caching | context-manager-svc | 8103 |
| MOD-07 | Traffic Intelligence Module | Traffic forecasting, congestion, signal optimization | traffic-agent-svc | 8200 |
| MOD-08 | Pollution Intelligence Module | AQI prediction, hotspot detection, dispersion modeling | pollution-agent-svc | 8201 |
| MOD-09 | Energy Intelligence Module | Load forecasting, consumption analysis, optimization | energy-agent-svc | 8202 |
| MOD-10 | Weather Intelligence Module | Weather forecasting, severe weather alerts | weather-agent-svc | 8203 |
| MOD-11 | Simulation Module | Scenario simulation, what-if analysis | simulation-agent-svc | 8204 |
| MOD-12 | Optimization Module | Multi-objective optimization, budget allocation | optimization-agent-svc | 8205 |
| MOD-13 | Policy Synthesis Module | Government recommendation generation | policy-synthesis-svc | 8206 |
| MOD-14 | Verification Module | Government rule validation, compliance checking | verification-agent-svc | 8207 |
| MOD-15 | GIS Platform Module | Spatial data serving, tile serving, spatial analysis | gis-api-svc | 8300 |
| MOD-16 | GIS Tile Server Module | Vector tile serving from PostGIS | Martin | 3000 |
| MOD-17 | GIS OGC Server Module | WMS/WFS/WMTS/WCS services | GeoServer | 8081 |
| MOD-18 | Data Ingestion Module | Data source connectors, schema validation, raw storage | ingestion-svc | 8400 |
| MOD-19 | ETL Pipeline Module | Data transformation, feature engineering, quality checks | Apache Airflow | 8401 |
| MOD-20 | Feature Store Module | Feature management, online/offline serving | Feast | 8402 |
| MOD-21 | ML Training Module | Model training, experiment tracking, hyperparameter tuning | training-svc + Airflow | 8403 |
| MOD-22 | Model Serving Module | ML model inference endpoints | model-serving-svc | 8500-8509 |
| MOD-23 | Model Registry Module | Model versioning, stage management, approval workflow | MLflow | 5000 |
| MOD-24 | Model Monitoring Module | Drift detection, performance monitoring | monitoring-svc | 8600 |
| MOD-25 | Notification Module | Alert delivery (email, SMS, in-app, push) | notification-svc | 8601 |
| MOD-26 | Reporting Module | Report generation (PDF, Excel), scheduled reports | reporting-svc | 8602 |
| MOD-27 | Dashboard Module | Web frontend, dashboards, GIS UI | React App | 3000 |
| MOD-28 | Audit Module | Audit log collection, storage, query | audit-svc | 8603 |
| MOD-29 | Admin Module | User management, configuration, system administration | admin-svc | 8604 |
| MOD-30 | Event Bus Module | Event messaging, pub/sub, stream processing | Apache Kafka | 9092 |

---

## Detailed Module Specifications

### MOD-01: API Gateway Module (Kong)

| Section | Detail |
|---|---|
| **Purpose** | Single entry point for all API requests; authentication validation, rate limiting, routing |
| **Technology** | Kong Gateway (OSS) 3.x |
| **Responsibilities** | JWT validation, request routing to backend services, rate limiting, CORS handling, request/response logging, API versioning, load balancing |
| **Inputs** | HTTPS requests from frontend (React app) |
| **Outputs** | Routed requests to backend microservices |
| **Security** | TLS termination, JWT validation (Keycloak public key), WAF rules, IP allowlisting |
| **Scaling** | Horizontal (multiple Kong instances behind L4 load balancer) |
| **Monitoring** | Request count, latency histogram, error rate, upstream health (Prometheus) |
| **Dependencies** | Keycloak (for JWT public key), all backend services (as upstreams) |

#### API Routes

| Route Pattern | Upstream Service | Auth Required | Rate Limit |
|---|---|---|---|
| `/api/v1/supervisor/*` | supervisor-svc:8100 | Yes | 100 req/min |
| `/api/v1/traffic/*` | traffic-agent-svc:8200 | Yes | 200 req/min |
| `/api/v1/pollution/*` | pollution-agent-svc:8201 | Yes | 200 req/min |
| `/api/v1/energy/*` | energy-agent-svc:8202 | Yes | 200 req/min |
| `/api/v1/weather/*` | weather-agent-svc:8203 | Yes | 200 req/min |
| `/api/v1/gis/*` | gis-api-svc:8300 | Yes | 500 req/min |
| `/api/v1/reports/*` | reporting-svc:8602 | Yes | 50 req/min |
| `/api/v1/admin/*` | admin-svc:8604 | Yes (Admin) | 100 req/min |
| `/api/v1/notifications/*` | notification-svc:8601 | Yes | 200 req/min |
| `/auth/*` | Keycloak:8080 | No | 50 req/min |
| `/tiles/*` | Martin:3000 | Optional | 1000 req/min |
| `/geoserver/*` | GeoServer:8081 | Optional | 500 req/min |

---

### MOD-03: Supervisor AI Module

| Section | Detail |
|---|---|
| **Purpose** | Central AI orchestration — intent understanding, task planning, agent dispatch, result aggregation |
| **Technology** | FastAPI (Python), DistilBERT-class classifier, DAG engine |
| **Responsibilities** | Parse NL requests, classify intent, build execution context, construct DAG, dispatch to agents, monitor execution, aggregate results, handle failures, audit logging |
| **Inputs** | Planner requests (NL or structured) via API Gateway |
| **Outputs** | Recommendation packages (JSON) delivered to dashboard |
| **Security** | Authenticated requests only; role-based request filtering; all actions audit-logged |
| **Scaling** | Horizontal (stateless; session state in Redis) |
| **Monitoring** | Request volume, intent classification accuracy, DAG execution time, agent dispatch latency, failure rate |
| **Dependencies** | Agent Registry, Capability Registry, Context Manager, all specialist agents, Redis, PostgreSQL |

#### API Endpoints

| Endpoint | Method | Description | Request | Response |
|---|---|---|---|---|
| `/api/v1/supervisor/request` | POST | Submit a planning request | `{request: "text", session_id: "..."}` | `{request_id, status, estimated_time}` |
| `/api/v1/supervisor/request/{id}` | GET | Get request status and results | - | `{status, results, recommendation}` |
| `/api/v1/supervisor/request/{id}/cancel` | POST | Cancel a running request | - | `{status: "cancelled"}` |
| `/api/v1/supervisor/history` | GET | Get request history for user | Query params: page, limit, filters | `{requests: [...], total, page}` |
| `/api/v1/supervisor/intents` | GET | Get supported intent categories | - | `{intents: [...]}` |
| `/api/v1/supervisor/health` | GET | Health check | - | `{status, agents_healthy, uptime}` |

---

### MOD-07: Traffic Intelligence Module

| Section | Detail |
|---|---|
| **Purpose** | Complete traffic intelligence — forecasting, congestion prediction, optimization |
| **Technology** | FastAPI, PyTorch (DCRNN/GAT+GRU), XGBoost, SUMO (simulation) |
| **Responsibilities** | Traffic speed/volume forecasting, congestion prediction, signal optimization, route planning, accident detection, traffic simulation |
| **Sub-Agents** | 11 sub-agents (see Volume 2 Section 9) |
| **Inputs** | Road graph, historical traffic, weather context, calendar, construction schedule |
| **Outputs** | Traffic forecasts, congestion maps, signal plans, routes, alerts, heatmaps |
| **Security** | Service-to-service auth (mTLS); data access via authorized APIs only |
| **Scaling** | Model serving pods scale horizontally; SUMO simulation requires dedicated compute |
| **Monitoring** | Prediction accuracy (MAPE), latency, throughput, model drift indicators |
| **Dependencies** | Weather Agent (context), PostGIS (road graph), TimescaleDB (historical data), Feature Store |

#### API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/traffic/forecast` | POST | Traffic speed/volume forecast for location + time |
| `/api/v1/traffic/congestion` | POST | Congestion prediction for area |
| `/api/v1/traffic/signal/optimize` | POST | Signal timing optimization for intersection |
| `/api/v1/traffic/route` | POST | Optimal route between two points |
| `/api/v1/traffic/simulate` | POST | Traffic simulation for scenario |
| `/api/v1/traffic/heatmap` | GET | Get current traffic heatmap tile |
| `/api/v1/traffic/alerts` | GET | Get active traffic alerts |
| `/api/v1/traffic/history` | GET | Get historical traffic data |
| `/api/v1/traffic/health` | GET | Agent health check |
| `/api/v1/traffic/metrics` | GET | Prometheus metrics |

---

### MOD-08: Pollution Intelligence Module

| Section | Detail |
|---|---|
| **Purpose** | Air quality intelligence — AQI forecasting, pollutant prediction, hotspot detection, dispersion modeling |
| **Technology** | FastAPI, PyTorch (TFT/LSTM), XGBoost, Gaussian Plume model |
| **Sub-Agents** | 7 sub-agents (see Volume 2 Section 10) |
| **Inputs** | CPCB AQI data, weather, traffic volume (cross-domain), industrial registry, land use |
| **Outputs** | AQI/pollutant forecasts, hotspot maps, dispersion surfaces, source attribution, alerts |
| **Scaling** | Model serving scales horizontally; dispersion computation is CPU-intensive |
| **Dependencies** | Weather Agent, Traffic Agent (volume for emissions), PostGIS, TimescaleDB, Feature Store |

---

### MOD-09: Energy Intelligence Module

| Section | Detail |
|---|---|
| **Purpose** | Energy demand forecasting, consumption analysis, efficiency optimization |
| **Technology** | FastAPI, XGBoost, LightGBM, LSTM |
| **Sub-Agents** | 6 sub-agents (see Volume 2 Section 11) |
| **Inputs** | TGNPDCL/TGSPDCL consumption data, weather, building metadata, substation data |
| **Outputs** | Load forecasts, peak predictions, efficiency scores, optimization recommendations |
| **Dependencies** | Weather Agent, PostGIS, TimescaleDB, Feature Store |

---

### MOD-10: Weather Intelligence Module

| Section | Detail |
|---|---|
| **Purpose** | Weather forecasting and contextual intelligence for all domain agents |
| **Technology** | FastAPI, LSTM/TFT, XGBoost |
| **Sub-Agents** | 3 sub-agents (see Volume 2 Section 12) |
| **Inputs** | IMD station data, ERA5 reanalysis data |
| **Outputs** | Weather forecasts, severe weather alerts, impact analysis |
| **Note** | This is a CONTEXTUAL agent — it enriches domain predictions, not a primary domain |
| **Dependencies** | TimescaleDB, Feature Store |

---

### MOD-15: GIS Platform Module

| Section | Detail |
|---|---|
| **Purpose** | Spatial data API, layer management, spatial analysis |
| **Technology** | FastAPI, PostGIS, GeoServer, Martin |
| **Responsibilities** | Layer registry management, spatial query API, feature info API, tile routing, spatial analysis (buffer, proximity, routing), coordinate transforms |
| **Inputs** | Spatial queries from frontend and other services |
| **Outputs** | GeoJSON features, spatial analysis results, layer metadata |
| **Dependencies** | PostGIS, GeoServer, Martin, Redis (cache) |

#### API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/gis/layers` | GET | List all available layers with metadata |
| `/api/v1/gis/layers/{id}` | GET | Get layer details, style, source |
| `/api/v1/gis/features` | POST | Spatial feature query (by bbox, point, polygon) |
| `/api/v1/gis/features/{id}` | GET | Get feature details by ID |
| `/api/v1/gis/analysis/buffer` | POST | Buffer analysis |
| `/api/v1/gis/analysis/proximity` | POST | Proximity/nearest analysis |
| `/api/v1/gis/analysis/route` | POST | Route analysis (shortest path) |
| `/api/v1/gis/analysis/isochrone` | POST | Isochrone analysis |
| `/api/v1/gis/geocode` | GET | Geocoding search |
| `/api/v1/gis/wards/{id}` | GET | Get ward details + geometry |
| `/api/v1/gis/zones/{id}` | GET | Get zone details + geometry |

---

### MOD-25: Notification Module

| Section | Detail |
|---|---|
| **Purpose** | Multi-channel notification delivery (email, SMS, in-app, push) |
| **Technology** | FastAPI, Kafka consumer, SMTP, SMS gateway, WebSocket |
| **Responsibilities** | Consume alert events from Kafka, route to appropriate channel, manage delivery, track delivery status, manage notification preferences |
| **Inputs** | Kafka events (platform.*.alerts), direct API calls |
| **Outputs** | Email, SMS, in-app notifications, push notifications |
| **Dependencies** | Kafka, SMTP server, SMS gateway, Redis (WebSocket sessions), PostgreSQL (notification history) |

#### Notification Routing Rules

| Alert Type | Email | SMS | In-App | Push |
|---|---|---|---|---|
| Traffic anomaly | ✓ (subscribed users) | ✗ | ✓ (all relevant) | ✓ |
| Pollution threshold | ✓ | ✓ (TSPCB officers) | ✓ | ✓ |
| Energy demand spike | ✓ | ✗ | ✓ | ✓ |
| Severe weather | ✓ | ✓ (all) | ✓ | ✓ |
| Recommendation generated | ✓ (assigned dept) | ✗ | ✓ | ✓ |
| Approval required | ✓ | ✓ | ✓ | ✓ |
| Model drift | ✓ (ML team) | ✗ | ✓ | ✗ |
| System alert | ✓ (admin) | ✓ (critical) | ✓ | ✗ |

---

### MOD-26: Reporting Module

| Section | Detail |
|---|---|
| **Purpose** | Automated and on-demand report generation |
| **Technology** | FastAPI, Jinja2 templates, WeasyPrint (PDF), openpyxl (Excel) |
| **Responsibilities** | Generate daily/weekly/monthly reports, on-demand report generation, template management, scheduled report delivery, report history |
| **Report Types** | Daily operational, weekly summary, monthly analytics, quarterly strategic, annual comprehensive, department-specific, ward-level, ad-hoc analysis |
| **Outputs** | PDF reports, Excel spreadsheets, CSV data exports |
| **Dependencies** | TimescaleDB, PostgreSQL, PostGIS (for map snapshots), MinIO (report storage), Airflow (scheduling) |

---

### MOD-27: Dashboard Module (Frontend)

| Section | Detail |
|---|---|
| **Purpose** | Web-based user interface for all platform features |
| **Technology** | React 18, MapLibre GL JS, Recharts, D3.js, WebSocket |
| **Responsibilities** | Dashboard rendering, GIS map display, form inputs, data visualization, real-time updates, responsive layout |
| **Key Views** | Executive dashboard, traffic dashboard, pollution dashboard, energy dashboard, GIS dashboard, AI dashboard, admin portal, recommendation viewer, report viewer |
| **Dependencies** | API Gateway (all API calls), Martin (vector tiles), GeoServer (WMS/WMTS), WebSocket (real-time alerts) |

#### Frontend Architecture

```
React App
├── /src
│   ├── /components
│   │   ├── /common          (Button, Card, Modal, Table, Form)
│   │   ├── /charts          (LineChart, BarChart, GaugeChart, Heatmap)
│   │   ├── /map             (MapContainer, LayerPanel, Legend, TimeSlider)
│   │   ├── /dashboard       (KPICard, AlertPanel, TrendSparkline)
│   │   ├── /recommendation  (PolicyCard, ApprovalFlow, ComparisonView)
│   │   └── /admin           (UserTable, RoleEditor, ConfigPanel)
│   ├── /pages
│   │   ├── ExecutiveDashboard.jsx
│   │   ├── TrafficDashboard.jsx
│   │   ├── PollutionDashboard.jsx
│   │   ├── EnergyDashboard.jsx
│   │   ├── GISDashboard.jsx
│   │   ├── AIDashboard.jsx
│   │   ├── AnalyticsDashboard.jsx
│   │   ├── RecommendationViewer.jsx
│   │   ├── ReportViewer.jsx
│   │   └── AdminPortal.jsx
│   ├── /hooks                (useAuth, useWebSocket, useGIS, useFetch)
│   ├── /services             (API client, auth client, WebSocket client)
│   ├── /store                (React Context / Zustand state management)
│   ├── /styles               (Design system, CSS variables, themes)
│   └── /utils                (formatters, validators, helpers)
```

---

### MOD-28: Audit Module

| Section | Detail |
|---|---|
| **Purpose** | Comprehensive audit trail for all platform actions |
| **Technology** | FastAPI, Elasticsearch, PostgreSQL (append-only audit_logs table) |
| **Responsibilities** | Capture all user actions, AI decisions, system events; store immutably; provide query API; generate compliance reports |
| **Audit Events** | Login/logout, request submission, recommendation generation, approval/rejection, data access, model deployment, configuration changes, alert acknowledgment |
| **Retention** | 7 years (government compliance) |
| **Dependencies** | Kafka (event ingestion), Elasticsearch (search), PostgreSQL (structured storage) |

#### Audit Event Schema

| Field | Type | Description |
|---|---|---|
| event_id | UUID | Unique event identifier |
| timestamp | Timestamp | Event time (IST) |
| user_id | UUID | Acting user (null for system events) |
| user_role | String | User's role at time of action |
| action | String | Action performed (READ, CREATE, UPDATE, APPROVE, REJECT, LOGIN, etc.) |
| resource_type | String | Type of resource affected (RECOMMENDATION, MODEL, USER, etc.) |
| resource_id | UUID | ID of affected resource |
| details | JSON | Action-specific details |
| ip_address | String | Source IP |
| session_id | String | Session identifier |
| outcome | String | SUCCESS, FAILURE, DENIED |

---

*End of Volume 7 — System Modules Specification*

*Next: Volume 8 — Security Architecture*
