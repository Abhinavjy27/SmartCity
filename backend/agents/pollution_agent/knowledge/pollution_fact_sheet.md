# Pollution Fact Sheet

[KB:ingestion]
Data is ingested from 13 CPCB CAAQMS stations in Greater Hyderabad. The `data_provider.py` module reads 15-minute resolution CSV data. Live data fetching via `PlaceholderLivePollutionProvider` is not active (mocked/disabled by team decision).

[KB:data_currency]
The dataset is a static archive spanning from 2024-01-01 to 2025-12-31. There is no live data for 2026. Data is not time-shifted to the present day; any gap to the server date is a result of observing historical bounds.

[KB:coverage]
Covers Greater Hyderabad via 13 stations (19 aliases/variants total). Supported domains: Air Quality (no water, noise, soil, or waste). Forecast covers 6 primary pollutants (PM2.5, PM10, NO2, SO2, CO, O3) but the AQI engine supports 7 including NH3. Lead (Pb) is not supported.

[KB:data_quality]
Validity ranges restrict observed values: PM2.5 (0-1000), PM10 (0-1500), NO (0-500), NO2 (0-600), NOx (0-800), NH3 (0-2400), CO (0-50), SO2 (0-2400), O3 (0-1000), Benzene (0-500), Toluene (0-500), Xylene (0-500). Out-of-bounds values are treated as missing data.

[KB:sufficiency_rules]
A valid 24h rolling average for PM2.5, PM10, NO2, SO2, NH3 requires >=16 valid hourly readings. A valid 8h rolling average for CO and O3 requires >=6 valid hourly readings.

[KB:aqi_method]
Uses the CPCB Indian National AQI. Requires at least 3 valid pollutant sub-indices, and one MUST be PM2.5 or PM10. Never forecast AQI directly; forecast concentration values and run them through the CPCB engine.

[KB:hotspots_alerts]
Alert thresholds: Sensitive >= 100, Poor >= 200, Very Poor >= 300, Severe >= 400. Rapid increase alert triggers when (current-previous)/previous * 100 >= 20%.

[KB:forecasting]
Forecast horizons: 7 days. Day 1 provides 24h granularity, Days 2-7 provide daily granularity. Directional swings tend to be smoothed out (under-reacted), especially during winter inversions.

[KB:deployed_model]
Deployed model class: TemporalGRU_KNNCovariate. Weights loaded from unified_best_model.pt with SHA-256: 9E033DFFE56522B97DC7CCBE7E9A1827E91E6EF5B3AF91C84C5E140E6A0F1DA9.

[KB:trend_rule]
A trend arrow (rising, falling, stable) is anchored to the observed AQI vs the Day-1 forecast. The threshold is a 3-point dead-band: changes >= 3 points or a category shift trigger 'rising'/'falling', else 'stable'.

[KB:endpoints]
The system serves data via FastAPI over ports 8000 (Supervisor/Planner) and 8002 (Pollution Agent direct). Key routes include /api/pollution/current, /forecast/daily, /forecast/7day, /alerts, /summary, /hotspots.

[KB:performance]
Test window: 2024-01-01 to 2025-12-31. Overall MAE: ~10.71-11.02. Day 1 MAE: 9.48. Day 7 MAE: 13.42. Directional accuracy decays heavily from 38.8% (Day 1) to chance or worse at longer horizons.

[KB:limitations]
No real-time data after 2025-12-31. No physical inversion layer (PBLH) feature logic exists, limiting winter peak prediction accuracy. Historical aggregation endpoints beyond spatial means are missing.
