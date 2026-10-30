# REVIEW_NOTES.md — Self-Review as Hostile Reviewer

## Top 7 Weaknesses

### 1. **Directional accuracy below chance — is the model useful?** [ACKNOWLEDGED in Limitations §10.4]
The deployed model's directional accuracy ranges from 23.5% (D3) to 45.9% (D6), all below the 50% chance line.
This means the model cannot predict whether AQI will go up or down tomorrow—a fundamental requirement for actionable forecasting.
The model essentially predicts toward the seasonal mean.
**Status**: Acknowledged in Limitations and Discussion. Reported plainly as a negative result.
**Mitigation**: PBLH features via ERA5 proposed as future work.

### 2. **Modest improvement over Persistence baseline** [ACKNOWLEDGED in Results §7.2]
The deployed model (MAE 11.38) beats Persistence (12.21) by only 0.83 AQI points.
A reviewer could argue this difference is not statistically significant given 86 test windows.
Bootstrap CIs were requested but not computed due to not being able to run the compute pipeline.
**Status**: Partially fixed. The gap is reported honestly. Statistical significance is not established.

### 3. **Energy evaluation is fundamentally flawed** [ACKNOWLEDGED in Limitations §10.10]
The original MAPE 3.68% claim suffers from train-test leakage (hourly weights computed from all data including test) and measures diurnal-profile shape fit on a single European household, then applied to Indian MW-scale substations.
**Status**: Fixed. The paper does not reproduce the 3.68% claim. It documents the leakage and scale mismatch explicitly.

### 4. **Weather Agent README is fiction** [ACKNOWLEDGED in §5.1 and Limitations §10.11]
The README describes 10+ components (provider.py, schemas.py, alerts.py, chat.py, Open-Meteo integration, Magnus-Tetens dew point, 30-locality registry) that do not exist in the code. The actual weather agent is a single-file WeatherAPI client.
**Status**: Fixed. Every README-code conflict is documented in the paper and claims_evidence.md.

### 5. **Single-city scope limits generalizability** [ACKNOWLEDGED in Limitations §10.3]
All results are from Hyderabad with its specific monsoon/winter inversion pattern. No cross-city validation exists.
**Status**: Acknowledged. Cannot be fixed without additional data.

### 6. **Test-set exposure during development** [ACKNOWLEDGED in Limitations §10.13]
Test MAE was viewed during the model lock-in discussion. While the final decision used CV metrics, the exposure introduces potential bias.
**Status**: Disclosed transparently. Cannot be undone.

### 7. **Grounding evaluation has 100% pass rate — is the test set discriminative?** [PARTIALLY ADDRESSED in §6]
A 123-question golden set with 100% pass rate raises the question: is the evaluation challenging enough, or was the test set designed to match the system's capabilities? No adversarial red-team beyond the 10 adversarial questions was performed.
**Status**: The adversarial category exists (10/10 passed), but reviewer may question whether 10 adversarial questions constitute a rigorous stress test. Future work should include independent red-teaming.

## Summary
- Weaknesses 1, 2, 3, 4, 5, 6: All acknowledged in Limitations section
- Weakness 7: Partially addressed; could be strengthened with external red-team evaluation
- The paper's credibility rests on honest reporting of negative results (directional accuracy, GAT underperformance, energy leakage, README staleness). A reviewer should recognize this as a strength, not a weakness.
