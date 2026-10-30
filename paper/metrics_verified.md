# Verified Multi-Domain Metrics

This file records the metrics actually available in the current workspace. It separates trained predictive models from deterministic services and simulation outputs.

## Pollution forecasting

Source: `backend/agents/pollution_agent/unified_forecast/artifacts/unified_best_model_meta.json` and `paper/main.tex`.

| Model | CV AQI MAE | Test AQI MAE | Test RMSE | Test category accuracy |
|---|---:|---:|---:|---:|
| TemporalGRU + KNN covariates | 10.79 | 11.38 | 14.18 | 63.95% |
| Temporal-only GRU | 10.98 | 11.76 | 14.08 | 64.29% |
| Persistence | 9.74 | 12.21 | 15.93 | 59.47% |
| Chronos-2 + covariates | 8.87 | 12.22 | 15.60 | 64.12% |
| Weighted GAT + GRU | 11.79 | 13.32 | 15.81 | 65.12% |
| Seasonal naive | 12.07 | 13.89 | 17.91 | 61.46% |

Deployed-model horizon metrics:

| Horizon | MAE | RMSE | Category accuracy | Directional accuracy |
|---|---:|---:|---:|---:|
| D1 | 8.76 | 10.85 | 65.1% | 40.0% |
| D2 | 10.40 | 13.04 | 64.0% | 36.5% |
| D3 | 11.49 | 14.43 | 64.0% | 23.5% |
| D4 | 11.94 | 15.06 | 65.1% | 36.5% |
| D5 | 12.00 | 15.06 | 65.1% | 36.5% |
| D6 | 12.44 | 15.15 | 62.8% | 45.9% |
| D7 | 12.63 | 15.10 | 61.6% | 42.4% |

Per-pollutant test results for the deployed model:

| Pollutant | MAE | R2 |
|---|---:|---:|
| PM2.5 | 6.98 | 0.1024 |
| PM10 | 12.06 | 0.06 |
| NO2 | 2.28 | -0.8365 |
| SO2 | 1.54 | -0.79 |
| CO | 0.07 | 0.45 |
| O3 | 1.67 | -0.10 |

## CPCB AQI verification

- 12 usable station comparisons.
- 4/12 exact matches.
- 7/12 within +/-2 AQI points.
- 12/12 prominent-pollutant matches.

## Energy profile benchmark

Command executed from the project root:

```text
python scripts/evaluate_energy_model.py
```

Observed output on the available 150,000-row sample:

- MAPE: 17.32%
- Pseudo-accuracy (100 - MAPE): 82.68%
- R2: 0.8443
- RMSE: 0.2488 kW
- MAE: 0.1988 kW
- Top-eight hourly peak overlap: 100.0%

These are profile-fit metrics on a single-household dataset. The implementation computes empirical hourly weights before the chronological split, so this benchmark has train-test leakage and must not be presented as leakage-free grid forecasting.

## Traffic simulation artifact

Source: `simulations/outputs/hyderabad_simulation_results.json` and `simulations/outputs/hyderabad_traffic_metrics.csv`.

- Duration: 3,600 seconds.
- Intersections monitored: 10.
- Vehicles simulated: 2,342.
- Mean speed: 23.67 km/h.
- Mean delay: 87.64 seconds.
- Maximum queue: 3,051.82 m.
- Signal adaptations: 106.
- Estimated CO2: 284.7 kg.
- CSV aggregate over 600 rows: mean active queue 166.275 vehicles, maximum observed active queue 469.5 vehicles, mean throughput 2,679.08 vehicles/hour.

These are SUMO scenario outputs, not field-measured traffic accuracy metrics.

## Planner evaluation

- Grounding golden set: 123/123 passed.
- Non-pollution regression: 20/20 passed.
- Advice, LLM-on: 15/15 passed.
- Advice, forced rule fallback: 60/60 passed.
- Advice, reasoning-false baseline match: 60/60 passed.

## Training-status boundary

The pollution GRU/GAT candidates are locally trained models. Chronos-2 is a pretrained foundation model used with covariates. Weather is a provider-ingestion service with a deterministic fallback; energy is a deterministic hybrid profile model; traffic and simulation use SUMO plus rule-based demand/signal logic. The paper therefore does not claim that every domain component was trained as a supervised ML model.
