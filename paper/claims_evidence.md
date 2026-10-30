# Claims-Evidence Mapping for SUPADSP Paper

| Claim | Number/Statement | Source (file:line or command) | Verified | README Conflict |
|-------|-----------------|------------------------------|----------|-----------------|
| Deployed model name | TemporalGRU_KNNCovariate | unified_best_model_meta.json:2 | Yes | Yes — README calls it "Spatial-Temporal GRU" |
| 2-layer GRU | num_gru_layers=2 | unified_forecast/models.py:233 | Yes | No |
| 18 features (12 local + 6 covariates) | 7 pollutants + 5 meteo + 6 temporal = 18; +6 KNN covariates for KNN variant | unified_forecast/config.py:37-46 | Yes | No |
| 13 CAAQMS stations | NUM_STATIONS = 13 | unified_forecast/config.py:30 | Yes | No |
| Hidden dim 64 | hidden_dim=64 | unified_forecast/models.py:230 | Yes | No |
| Dropout 0.15 | dropout=0.15 | unified_forecast/models.py:236 | Yes | No |
| Forecast horizon 7 days | FORECAST_HORIZON = 7 | unified_forecast/config.py:49 | Yes | No |
| Context length 14 days | CONTEXT_LENGTH = 14 | unified_forecast/config.py:50 | Yes | No |
| CV MAE Chronos-2: 8.87 | MAE_mean: 8.87 | unified_best_model_meta.json:185 | Yes | No |
| CV MAE Persistence: 9.74 | MAE_mean: 9.74 | unified_best_model_meta.json:237 | Yes | No |
| CV MAE KNN GRU: 10.79 | MAE_mean: 10.79 | unified_best_model_meta.json:133 | Yes | No |
| CV MAE TemporalOnly: 10.98 | MAE_mean: 10.98 | unified_best_model_meta.json:29 | Yes | No |
| CV MAE GAT+GRU: 11.79 | MAE_mean: 11.79 | unified_best_model_meta.json:81 | Yes | No |
| CV MAE SeasonalNaive: 12.07 | MAE_mean: 12.07 | unified_best_model_meta.json:289 | Yes | No |
| Test MAE KNN GRU: 11.38 | AQI_MAE: 11.38 | unified_best_model_meta.json:369 | Yes | No |
| Test MAE TemporalOnly: 11.76 | AQI_MAE: 11.76 | unified_best_model_meta.json:343 | Yes | No |
| Test MAE Persistence: 12.21 | AQI_MAE: 12.21 | unified_best_model_meta.json:395 | Yes | No |
| Test MAE Chronos-2: 12.22 | AQI_MAE: 12.22 | unified_best_model_meta.json:382 | Yes | No |
| Test MAE GAT+GRU: 13.32 | AQI_MAE: 13.32 | unified_best_model_meta.json:356 | Yes | No |
| Test MAE SeasonalNaive: 13.89 | AQI_MAE: 13.89 | unified_best_model_meta.json:408 | Yes | No |
| Validation-to-test gap KNN: 0.59 | gap: 0.59 | unified_best_model_meta.json:556 | Yes | No |
| D1 MAE: 8.76 | AQI_MAE: 8.76 | unified_best_model_meta.json:437 | Yes | No |
| D3 directional accuracy: 23.53% | directional_accuracy_pct: 23.53 | unified_best_model_meta.json:461 | Yes | No |
| D1 directional accuracy: 40.0% | directional_accuracy_pct: 40.0 | unified_best_model_meta.json:443 | Yes | No |
| PM2.5 test MAE: 6.98, R2: 0.1024 | MAE: 6.98, R2: 0.1024 | unified_best_model_meta.json:502-505 | Yes | No |
| NO2 R2: -0.8365 | R2: -0.8365 | unified_best_model_meta.json:516 | Yes | No |
| CPCB cross-check 4/12 exact | 4 exact matches | VERIFICATION_CPCB.md:20 | Yes | No |
| CPCB 7/12 within ±2 | 7 stations | VERIFICATION_CPCB.md:21 | Yes | No |
| 100% prominent pollutant concordance | 12/12 | VERIFICATION_CPCB.md:23 | Yes | No |
| 7 CPCB pollutants (no Pb) | BREAKPOINTS dict has 7 keys | aqi_engine.py:19-76 | Yes | No |
| Golden set 123/123 passed | total_passed: 123 | eval/eval_scorecard.json:3 | Yes | No |
| Non-pollution regression 20/20 | regression.passed: 20 | eval/eval_scorecard.json:57 | Yes | No |
| Advice eval 60/60 rule fallback | mode2_llm_forced_timeout.passed: 60 | eval/advice_eval_scorecard.json:5 | Yes | No |
| Advice eval 15/15 LLM-on | mode1_llm_on.passed: 15 | eval/advice_eval_scorecard.json:78 | Yes | No |
| 14-day live switchover | MIN_LIVE_DAYS_FOR_FORECAST = 14 | pollution_agent/config.py:88 | Yes | No |
| 3-hour OpenAQ stale threshold | OPENAQ_STALE_HOURS = 3 | pollution_agent/config.py:92 | Yes | No |
| 180s weather cache TTL | CACHE_TTL_SECONDS = 180.0 | weather_agent/main.py:27 | Yes | No |
| Diurnal blend 85/15 | 0.85 * empirical + 0.15 * Gaussian | load_calculator.py:52 | Yes | No |
| HVAC base coefficient 0.020 | multiplier = 1.0 + (0.020 * delta_t) | load_calculator.py:89 | Yes | Yes — README says 0.020 for all; code uses 0.025 above heatwave threshold |
| HVAC heatwave coefficient 0.025 | multiplier = 1.0 + (0.025 * delta_t) + 0.015*(T-38) | load_calculator.py:87 | Yes | Yes — README formula uses 0.020 base, code uses 0.025 |
| EV 0.030 MW/vehicle | ev_mw += (ev_fleet_count * 0.030) | load_calculator.py:109 | Yes | No |
| Congestion 1.5 MW/% above 60 | ev_mw += ((occupancy - 60.0) * 1.5) | load_calculator.py:113 | Yes | No |
| Solar 12% of capacity | solar_peak_mw = capacity_mw * 0.12 | load_calculator.py:63 | Yes | No |
| Severity ≥85% CRITICAL | if load_pct >= 85.0: CRITICAL | load_calculator.py:126 | Yes | No |
| Severity ≥75% HIGH | elif load_pct >= 75.0: HIGH | load_calculator.py:128 | Yes | No |
| 15 substations | SUBSTATIONS_DB in substations.py | substations.py (15 entries) | Yes | No |
| Energy test split chronological | split_idx = int(len(df) * 0.70); test_df = df.iloc[split_idx:] | evaluate_energy_model.py:71-72 | Yes | No |
| Hourly weights from ALL data | hourly_means = df.groupby('Hour')['Global_active_power'].mean() computed on full df | dataset_loader.py:78 | Yes | Yes — leakage not disclosed in README |
| Pollution port 8002 | POLLUTION_AGENT_PORT = 8002 | pollution_agent/config.py:23 | Yes | No |
| Weather Agent: NO Open-Meteo | No Open-Meteo code in weather_agent/main.py | weather_agent/main.py (entire file) | Yes | Yes — README says dual-source |
| Weather Agent: NO Magnus-Tetens | No Magnus formula in weather_agent/ | grep search returns 0 results | Yes | Yes — README describes Magnus formula |
| Weather Agent: NO provider.py | Only main.py and __init__.py in weather_agent/ | ls weather_agent/ | Yes | Yes — README describes provider.py |
| Weather Agent: NO alerts.py | File does not exist | ls weather_agent/ | Yes | Yes — README describes alerts.py |
| Weather Agent: NO chat.py | File does not exist | ls weather_agent/ | Yes | Yes — README describes chat.py |
| Weather Agent: NO schemas.py | File does not exist | ls weather_agent/ | Yes | Yes — README describes schemas.py |
| Fold 1 train end 2024-06-30 | train_end: 2024-06-30 | unified_best_model_meta.json:8 | Yes | No |
| Fold 2 Winter Inversion | name: Fold 2: Winter Inversion Peak | unified_best_model_meta.json:14 | Yes | No |
| Test period Oct-Dec 2025 | TEST_START_DATE = 2025-10-01, TEST_END_DATE = 2025-12-31 | unified_forecast/config.py:57-58 | Yes | No |
| Random seed 42 | RANDOM_SEED = 42 | unified_forecast/config.py:61 | Yes | No |
| Gaussian sigma 12 km | sigma_km: float = 12.0 | unified_forecast/models.py:49 | Yes | No |
| Max distance 25 km | max_dist_km: float = 25.0 | unified_forecast/models.py:50 | Yes | No |
| KNN k=3 | k_nearest: int = 3 | unified_forecast/models.py:51 | Yes | No |
| GAT 4 heads | num_gat_heads: int = 4 | unified_forecast/models.py:173 | Yes | No |
