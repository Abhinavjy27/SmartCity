# SUPADSP — Smart Urban Planning & AI Decision Support Platform

> Enterprise-grade AI-powered decision support platform for municipal urban planning and smart governance in Hyderabad.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)]()
[![React](https://img.shields.io/badge/react-18.x-blue.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)]()

---

## Overview

**SUPADSP** (Smart Urban Planning and Decision Support Platform) enables municipal planners and government administrators to monitor real-time city telemetry, forecast future conditions, simulate interventions, and receive grounded, actionable recommendations across four core intelligence domains:

- **Traffic Intelligence** — Micro-simulation via Eclipse SUMO, corridor flow analysis, congestion prediction, and adaptive signal timing optimization.
- **Pollution Intelligence** — Live air quality ingestion across 13 Hyderabad CAAQMS stations via WeatherAPI telemetry, CPCB NAQI calculation engine, Spatial-Temporal GRU forecasting model, and statutory CPCB/NCAP mitigation playbook reasoning.
- **Weather Intelligence** — Live meteorological telemetry and atmospheric forecasts via accurate WeatherAPI integration, monitoring temperature, humidity, wind vectors, precipitation, and environmental dispersion parameters.
- **Energy Intelligence** — Grid load monitoring, peak shaving analysis, substation load distribution, and battery energy storage simulation.

The platform coordinates specialist domain agents through an autonomous **Planner AI Agent** and **Supervisor API Gateway**, providing natural language decision support with verifiable grounding and deterministic statutory playbook fallbacks.

---

## Key Features

1. **Autonomous Planning AI Assistant**
   - Natural-language interface at `/api/planning/chat` and `/agents/planner/execute`.
   - Domain router supporting traffic, pollution, weather, energy, and multi-domain queries.
   - LLM-powered multi-stage planning and causal analysis with `<think>` tag stripping and strict token controls.
   - Deterministic rule-based fallback grounded in verified statutory mitigation playbooks (CPCB, MoEFCC, NCAP).

2. **Accurate Weather Agent**
   - Live weather telemetry fetching ambient temperature, relative humidity, barometric pressure, wind vectors, and precipitation.
   - Hourly and 7-day weather forecasting using accurate external API telemetry.
   - Atmospheric dispersion context for pollution modeling and weather-traffic correlation analysis.

3. **Grounded Pollution Engine**
   - CPCB breakpoint interpolation engine (PM2.5, PM10, NO2, SO2, CO, O3, NH3) with zero arithmetic hallucination.
   - Live telemetry ingestion from 13 Telangana monitoring stations (Bollaram, Sanathnagar, Zoo Park, ECIL Kapra, etc.).
   - Spatial-Temporal GRU forecaster with KNN covariate modeling.
   - 14-day zero-gap accumulation rule before transitioning from verified historical archive to live-trained forecasts.

4. **Traffic Simulation Loop**
   - SUMO microsimulation for corridor bottlenecks (Narayanguda, Begumpet, Jubilee Hills).
   - Realism audit validating speed, flow, density, and queue length conventions.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React 18 + Vite)                      │
│   Pages: Dashboard, Planning, Traffic, Weather, Pollution, Energy,     │
│          Simulation                                                    │
│   MapLibre GL JS · Recharts · Lucide Icons · TailwindCSS / CSS3        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / JSON
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│               SUPERVISOR API GATEWAY (FastAPI :8000)                  │
│                                                                        │
│   Routes:                                                              │
│   ├── /api/planning/chat         → Planning AI Chat (Domain Router)    │
│   ├── /agents/planner/execute    → Autonomous Multi-Domain Dispatch    │
│   ├── /api/pollution/*           → Specialist Agent - Pollution        │
│   ├── /api/v1/weather/*          → Specialist Agent - Weather          │
│   ├── /api/v1/traffic/*          → Specialist Agent - Traffic          │
│   ├── /api/v1/energy/*           → Specialist Agent - Energy           │
│   └── /api/v1/simulation/*       → Specialist Agent - Simulation       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
    ┌───────────────────────────────┼──────────────────────────────┐
    ▼                               ▼                              ▼
┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐
│   POLLUTION AGENT    │ │    WEATHER AGENT     │ │    TRAFFIC AGENT     │
│   Port: 8002         │ │    Live API Provider │ │    SUMO Simulator    │
│   • CPCB NAQI Engine │ │    • WeatherAPI Sync │ │    • Demand Gen      │
│   • GRU Forecaster   │ │    • Wind & Precip   │ │    • Signal Opt      │
│   • 13-Station Sync  │ │    • 7-Day Forecast  │ │    • Corridor KPIs   │
│   • CPCB Playbook    │ │    • Dispersion Data │ │    • Queue Duration  │
└──────────────────────┘ └──────────────────────┘ └──────────────────────┘
```

---

## Project Structure

```
SmartCity/
├── frontend/                     # React 18 + Vite dashboard application
│   ├── src/pages/                # Dashboard, Planning, Pollution, Weather, Traffic, Energy
│   ├── src/components/           # Charts, maps, gauges, problem solver UI
│   └── src/services/             # API client services & telemetry fetchers
├── backend/
│   ├── supervisor/               # FastAPI Supervisor Gateway & Agent Dispatcher
│   ├── agents/
│   │   ├── planner_agent/        # Autonomous LLM Planner & contract enforcement
│   │   ├── pollution_agent/      # CPCB engine, GRU forecaster, live WeatherAPI client
│   │   ├── weather_agent/        # Accurate WeatherAPI telemetry & forecast provider
│   │   ├── traffic_agent/        # SUMO traffic integration & demand generator
│   │   ├── energy_agent/         # Grid load & power peak analytics
│   │   └── simulation_agent/     # SUMO simulation orchestrator & runners
├── simulations/                  # SUMO road networks, OSM data, configuration files
├── tests/                        # Comprehensive pytest test suites (grounding, contracts, SUMO)
├── eval/                         # Golden evaluation sets & baseline benchmarks
├── scripts/                      # Startup, reproduction, evaluation, and smoke-test utilities
└── docs/                         # Architecture audit, route specifications, API inventory
```

---

## Quick Start

### 1. Prerequisites

- **Python 3.11+**
- **Node.js 18+** & npm
- (Optional) Eclipse SUMO for traffic microsimulations

### 2. Environment Configuration

Copy the example environment configuration:

```bash
cp .env.example .env
```

Configure your credentials in `.env`:
- `WEATHERAPI_KEY`: API key for live air quality and weather telemetry.
- `LLM_PROVIDER`: e.g., `groq` or `openai`.
- `LLM_MODEL`: e.g., `qwen/qwen3.8-27b` or `llama-3.3-70b-versatile`.
- `LLM_API_KEY`: API key for the selected LLM provider.

### 3. Running the Backend

Start the Specialist Agents and Supervisor Gateway:

```bash
# Terminal 1: Pollution Agent (Port 8002)
python -m uvicorn backend.agents.pollution_agent.main:app --host 127.0.0.1 --port 8002

# Terminal 2: Supervisor Gateway (Port 8000)
python -m uvicorn backend.supervisor.main:app --host 127.0.0.1 --port 8000
```

### 4. Running the Frontend

Start the Vite development server:

```bash
cd frontend
npm install
npm run dev
```

Open [`http://localhost:3000`](http://localhost:3000) in your browser.

---

## Testing & Verification

Run the test suite and evaluation benchmarks:

```bash
# Grounding & reasoning test suite (37 tests)
python -m pytest backend/agents/pollution_agent/test_grounding.py

# Full 123-question Golden Set & non-pollution regression
python backend/agents/pollution_agent/eval/run_eval.py

# 60-question 3-mode Advice Evaluation
python backend/agents/pollution_agent/eval/run_advice_eval.py
```

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
