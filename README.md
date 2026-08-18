# SUPADSP — Smart Urban Planning & AI Decision Support Platform

> Enterprise-grade AI-powered decision support for municipal urban planning. Built for GHMC/HMDA, Hyderabad.

[![License](https://img.shields.io/badge/license-Government--Restricted-red.svg)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)]()
[![TypeScript](https://img.shields.io/badge/typescript-5.x-blue.svg)]()

---

## Overview

SUPADSP enables government officials to **monitor city conditions**, **predict future events**, **optimize resources**, **evaluate planning scenarios**, and **make AI-assisted strategic decisions** across three core intelligence domains:

- **Traffic Intelligence** — forecasting, congestion prediction, signal optimization, route planning
- **Pollution Intelligence** — AQI forecasting, hotspot detection, dispersion modeling, source attribution
- **Energy Intelligence** — demand forecasting, peak prediction, building efficiency, grid optimization

The platform uses a **Supervisor AI Agent** orchestrating **8 specialist agents** with **50+ sub-agents**, powered entirely by locally-trained ML/DL models — **no external LLM APIs**.

## Architecture

| Layer | Technology |
|---|---|
| Frontend | React 18, MapLibre GL JS, Recharts, D3.js |
| API Gateway | Kong (OSS) |
| Backend | FastAPI (Python) |
| AI/ML | PyTorch, XGBoost, pymoo (NSGA-II), SUMO |
| GIS | GeoServer, Martin, PostGIS, pgRouting |
| Databases | PostgreSQL 16, PostGIS 3.4+, TimescaleDB, Redis 7, MinIO |
| MLOps | MLflow, Feast, Evidently AI, Apache Airflow |
| Identity | Keycloak (OAuth2/OIDC) |
| Messaging | Apache Kafka |
| Infrastructure | Docker & Docker Compose |
| Monitoring | Prometheus, Grafana, Loki, Jaeger |

## Project Structure

```
SUPADSP/
├── frontend/          → React 18 + TypeScript dashboard application
├── backend/           → FastAPI microservices (Supervisor, Agents, Platform)
├── ml/                → ML model training, experiments, serving
├── datasets/          → Raw, processed, synthetic, and feature datasets
├── simulations/       → SUMO traffic simulation configs and outputs
├── database/          → Database schemas, migrations, seeds
├── infrastructure/    → Docker & Docker Compose configuration
├── kafka/             → Event bus topics, schemas, producers/consumers
├── configs/           → Environment-specific configurations
├── scripts/           → Setup, deployment, maintenance scripts
├── tests/             → Unit, integration, API, e2e, performance tests
├── tools/             → OSM, GIS, model, and diagnostic utilities
├── docs/              → Architecture, API, database, deployment docs
├── logs/              → Application logs (gitignored)
└── backups/           → Database backups (gitignored)
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 20+ & npm 10+
- PostgreSQL 16 with PostGIS & TimescaleDB extensions
- Redis 7
- Apache Kafka

### Development Setup

```bash
# Clone the repository
git clone https://github.com/your-org/SUPADSP.git
cd SUPADSP

# Copy environment file
cp .env.example .env

# Start infrastructure services
docker compose up -d postgres redis kafka minio

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Frontend setup
cd ../frontend
npm install
npm run dev
```

### Using Make

```bash
make setup          # Full development setup
make dev            # Start all services in development mode
make test           # Run all tests
make lint           # Lint all code
make build          # Build production images
make deploy-staging # Deploy to staging via ArgoCD
```

## Documentation

| Document | Location |
|---|---|
| Consolidated Architecture | `docs/architecture/SUPADSP_Architecture_Consolidated.md` |
| API Documentation | `docs/api/` |
| Database Schemas | `docs/database/` |
| Deployment Guide | `docs/deployment/` |
| Security Architecture | `docs/security/` |
| User Manual | `docs/user_manual/` |

## Core Constraint

> **No external LLM APIs** (OpenAI, Claude, Gemini, etc.) are used anywhere in the operational workflow. The entire AI system relies on locally-trained Machine Learning, Deep Learning, Graph Neural Networks, Optimization, Simulation, Computer Vision, Time-Series Forecasting, Reinforcement Learning, and Statistical Models.

## License

Government Restricted — Internal Use Only. See [LICENSE](LICENSE) for details.
