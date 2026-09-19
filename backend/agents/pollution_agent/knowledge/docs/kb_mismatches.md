# Knowledge Base Mismatches

| Topic | Doc A (`POLLUTION_AGENT_TECHNICAL_AUDIT.md`) | Doc B (`RESEARCH_REPORT.md`) | Code (`backend/agents/pollution_agent/*`) | Winner (Code) |
|---|---|---|---|---|
| **Primary Pollutants** | Mentions 7 criteria pollutants | Mentions 6 primary criteria pollutants | `aqi_engine.py` supports 7 pollutants (`PM2.5`, `PM10`, `NO2`, `SO2`, `CO`, `O3`, `NH3`) | 7 Pollutants |
| **Completeness Rule** | Mentions 50% data-completeness rules | Mentions 50% / $\ge 16$ hours of valid data | `temporal_aggregation.py` requires `count >= 16 * 4` for 24h metrics (67%) and `count >= 6 * 4` for 8h metrics | 16 valid hours (67%) |
| **Endpoint Prefixes** | Mentions port 8002 and `/api/v1/pollution/current` | Mentions port 8002 | `main.py` is mounted via APIRouter, likely `/api/pollution` based on recent code structure changes | `main.py` APIRouter prefix |
| **Number of Stations** | Mentions 19 CAAQMS stations | Mentions 13 CAAQMS stations | `config.py` contains 13 active stations (based on earlier task audits) | 13 Stations |
| **Deployed Forecaster** | Mentions Day-1: Ganesh BiLSTM | Mentions BiLSTM | `unified_forecast` test logs show `TemporalGRU_KNNCovariate` is actually deployed and loaded as singleton | `TemporalGRU_KNNCovariate` |
| **Forecast Accuracy** | Does not list specific MAE | Mentions MAE across different models | Artifact evaluate outputs / tests dictate actual live MAE | Artifact outputs |
| **Reconciliation** | Does not mention `reconciliation.py` | Does not mention `reconciliation.py` | `reconciliation.py` contains `reconcile_aqi_with_cpcb` | Exists in code to align AQI with CPCB official API responses if they diverge. |
