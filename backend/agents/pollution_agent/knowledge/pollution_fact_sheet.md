# SUPADSP Air Quality Domain Fact Sheet
(Generated dynamically by generate_jsons.py from verified codebase and model artifacts)

## 1. Deployed Forecasting Model & Checksum
- **Deployed Model Architecture**: TemporalGRU_KNNCovariate
- **Artifact Path**: `backend/agents/pollution_agent/unified_forecast/artifacts/unified_best_model.pt`
- **Model Checksum (SHA-256)**: `9E033DFFE56522B97DC7CCBE7E9A1827E91E6EF5B3AF91C84C5E140E6A0F1DA9`
- **Test Window**: 2025-10-01 to 2025-12-31 (held-out test set)
- **Overall Performance**: MAE = 11.38 AQI points, RMSE = 14.18 AQI points
- **Per-Horizon Metrics (MAE & Directional Accuracy)**:
  - **Day 1**: MAE = 8.76 AQI points, Directional Accuracy = 40.0%
  - **Day 2**: MAE = 10.4 AQI points, Directional Accuracy = 36.47%
  - **Day 3**: MAE = 11.49 AQI points, Directional Accuracy = 23.53%
  - **Day 4**: MAE = 11.94 AQI points, Directional Accuracy = 36.47%
  - **Day 5**: MAE = 12.0 AQI points, Directional Accuracy = 36.47%
  - **Day 6**: MAE = 12.44 AQI points, Directional Accuracy = 45.88%
  - **Day 7**: MAE = 12.63 AQI points, Directional Accuracy = 42.35%

## 2. Known Model Limitations
- **Flat 7-Day Trajectory**: Model exhibits smoothing across Days 2-7, tending to regress toward seasonal means rather than capturing sharp spikes.
- **Directional Accuracy**: Day 1 to Day 7 directional accuracy ranges from 40.0% to 42.4% (at or below random chance 50%), meaning daily swing direction must not be treated as high confidence.
- **Winter-Inversion Weakness**: Struggles with sudden winter temperature inversion peaks where nocturnal boundary layers trap particulates.
- **No Boundary Layer Height (PBLH)**: Model does not ingest boundary layer height or dynamic vertical mixing telemetry, limiting peak inversion prediction accuracy.

## 3. CPCB National AQI (NAQI) Methodology & Engine Invariants
- **Governing Standard**: Central Pollution Control Board (CPCB) India National Air Quality Index.
- **Sufficiency Rule**: Minimum of 3 pollutant sub-indices required to compute an overall AQI.
- **Particulate Mandate**: At least one of the 3 pollutants MUST be a particulate matter (either PM2.5 or PM10). If neither is present, AQI is mathematically undefined ("unavailable").
- **Overall AQI Rule**: Overall AQI is defined as the maximum (worst) sub-index among all qualifying pollutants (`AQI = max(I_p)`). The pollutant with this maximum sub-index is designated the **Dominant Pollutant**.
- **Linear Interpolation**: Sub-index computed via CPCB piecewise linear interpolation: `I = I_lo + (I_hi - I_lo) * (C - B_lo) / (B_hi - B_lo)`.
- **Engine Fix 1 (SO2 Breakpoint Fix)**: Corrected SO2 breakpoint table from erroneous 0-40 ug/m3 Good category to authentic CPCB 0-40/41-80 standard.
- **Engine Fix 2 (Sub-Index & Rounding Fix)**: Enforced exact integer truncation/half-up standards and strict non-negative clamping before determining dominant pollutant.

## 4. AQI Categories & Health Impacts
- **Good (0 - 50)**: Minimal impact.
- **Satisfactory (51 - 100)**: Minor breathing discomfort to sensitive people.
- **Moderate (101 - 200)**: Breathing discomfort to people with lungs, asthma, and heart diseases.
- **Poor (201 - 300)**: Breathing discomfort to most people on prolonged exposure.
- **Very Poor (301 - 400)**: Respiratory illness on prolonged exposure.
- **Severe (401 - 500)**: Affects healthy people and seriously impacts those with existing diseases.

## 5. Data Provenance, Switchover & Ingestion Pipeline
- **Historical Archive**: Spans 2024-01-01 through 2025-12-31 from Telangana State / CPCB CAAQMS stations.
- **Live Provider**: OpenAQ REST API (`OpenAQLiveProvider`) ingesting live observations for Hyderabad/Telangana CPCB/TSPCB stations.
- **Forecast Input Window**: Model requires a strict 14-consecutive-day input window to predict a 7-day output trajectory (14 days input vs 7 days output).
- **14-Day Switchover Rule**: The forecast model switches its input window from the historical archive to live accumulated data IF AND ONLY IF 14 consecutive days of complete live data exist with ZERO missing days. Until then, forecasts use the historical archive, with zero synthetic data fabrication.
- **Averaging Window**: CPCB standard defines 24-hour window from 16:00 IST to 16:00 IST (4 PM to 4 PM) for PM2.5, PM10, NO2, SO2, NH3, and 8-hour rolling maximum for CO and O3.

## 6. Staleness Rules & Thresholds
- **Freshness Threshold (`OPENAQ_STALE_HOURS`)**: 3 hours.
- **Station-Level Staleness**: Any individual station reading older than 3 hours is excluded from real-time city aggregation when fresh stations are present.
- **All-Stale Fallback**: When all live stations are older than 3 hours, the system returns the latest available data with explicit staleness metadata: `status: "success"`, `is_stale: true`, `data_age_hours`, and human-readable `last_updated_label`. It NEVER fabricates zero or null values when historical or last-known data exists.

## 7. Monitoring Network & Stations
Covers 13-15 continuous monitoring stations across Greater Hyderabad:
- **Bollaram Industrial** (Area: Bollaram): Aliases: Bollaram Industrial, Bollaram Industrial Area
- **Central University** (Area: Gachibowli): Aliases: Central University
- **ECIL Kapra** (Area: Kapra): Aliases: ECIL Kapra, Ecil Kapra
- **ICRISAT Patancheru** (Area: Patancheru): Aliases: ICRISAT Patancheru, Icrisat Patancheru
- **IDA Pashamylaram** (Area: Pashamylaram): Aliases: IDA Pashamylaram, Ida Pashamylaram
- **Kokapet** (Area: Kokapet): Aliases: Kokapet
- **Kompally Municipal** (Area: Kompally): Aliases: Kompally Municipal, Kompally Municipal Office
- **Nacharam TSIIC** (Area: Nacharam): Aliases: Nacharam TSIIC, Nacharam_Tsiic Iala
- **New Malakpet** (Area: Malakpet): Aliases: New Malakpet
- **Ramachandrapuram** (Area: Ramachandrapuram): Aliases: Ramachandrapuram
- **Sanathnagar** (Area: Sanathnagar): Aliases: Sanathnagar
- **Somajiguda** (Area: Somajiguda): Aliases: Somajiguda
- **Zoo Park** (Area: Zoo Park): Aliases: Zoo Park
