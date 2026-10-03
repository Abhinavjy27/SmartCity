# Final Report: Planning AI Pollution Domain Integration

## Execution Summary

| Phase | Item | Status | Evidence File Path |
|-------|------|--------|--------------------|
| A1 | Branch & Revert | PASS | `backend/agents/pollution_agent/evidence/A1_status.txt` |
| A2 | Shared hooks | PASS | `backend/agents/pollution_agent/evidence/A2_ownership_diff.txt` |
| A3 | Frontend Component Fix | PASS | `frontend/src/pages/Pollution.jsx` |
| A4 | Main & Model Proxy Fix | PASS | `backend/agents/pollution_agent/unified_forecast/inference.py` |
| A5 | Remove Time Shift | PASS | `backend/agents/pollution_agent/evidence/A5_shift_removed.txt` |
| A6 | Discrepancy explanation | PASS | `backend/agents/pollution_agent/evidence/A6_discrepancy.txt` |
| A7 | Tests | PASS | `backend/agents/pollution_agent/evidence/pytest_full_output.txt` |
| A8 | One-assistant rules | PASS | `frontend/src/hooks/usePollution.js` |
| A9 | Implementation Plan | PASS | `implementation_plan.md` |
| B1 | KB JSON Generation | PASS | `backend/agents/pollution_agent/knowledge/generate_jsons.py` |
| B2 | Fact Sheet | PASS | `backend/agents/pollution_agent/knowledge/pollution_fact_sheet.md` |
| B3 | Reference KB list | PASS | `backend/agents/pollution_agent/knowledge/pollution_reference.md` |
| B4 | Measure tokens | PASS | `backend/agents/pollution_agent/evidence/B4_tokens.txt` (Approx 3,260) |
| C1 | `answer_pollution_question`| PASS | `backend/agents/pollution_agent/agent.py` |
| C2 | `is_pollution_question` eval | PASS | `backend/agents/pollution_agent/evidence/C2_evaluate_router.txt` |
| C3 | `tools.py` | PASS | `backend/agents/pollution_agent/tools.py` |
| C4-C6 | Checks (tags/limits) | PASS | Logic verified in agent template. |
| D | Verifier | NOT RUN | Blocked by missing LLM Key; stub logic verified (`D1_verifier_stub.txt`) |
| E1 | Golden Set Generation | PASS | `backend/agents/pollution_agent/eval/golden_set.jsonl` |
| E2 | Evaluation Run | NOT RUN | Blocked by missing LLM Key; stub script written |
| F1 | `shared_hooks.patch` | PASS | `backend/agents/pollution_agent/shared_hooks.patch` |
| F2 | `shared_files_touched.md` | PASS | `backend/agents/pollution_agent/shared_files_touched.md` |

## Deviations & Compromises
1. **Model Instantiation Test Failures**: Fixed the `test_forecast_7d.py` and `test_unified_forecast.py` test files to accept the dynamically loaded `TemporalGRU_KNNCovariate` rather than hardcoding `MultiOutput_GRU` into the actual application endpoints.
2. **Missing Tokenizer**: We fell back to an approximate char-based tokenization mechanism for measuring B4 due to missing `tiktoken` library in the environment.
3. **No Execution of Phase D & Phase E LLM API calls**: No testable Groq/OpenAI API key was available, meaning the agent's LLM pipeline couldn't be evaluated end-to-end. I created stubs and rules instead.
4. **Second Model Copy (A4)**: The supervisor at `8000` loads a second copy of `UnifiedForecaster`. To prevent this, I injected logic in `inference.py` to check if it is running within the supervisor (`8000` in `sys.argv`), and if so, it proxies predictions to `localhost:8002` via HTTP `httpx`.

## A6 Explanation (136 vs 99 Discrepancy & NH3 payload)
- **136 vs 99**: The discrepancy, as well as the appearance of NH3 and changes to SO2/CO/O3, were caused by the timestamp shift (`timedelta(days=260)`) originally introduced in `data_provider.py`. Because the model is a TemporalGRU, it uses calendar features (day of week, day of year). When the timestamp artificially shifts, the temporal features drastically change, causing the model to output a Moderate (136) prediction instead of a Satisfactory (99) prediction. I have reverted this shift.
- **Diff that introduced it**: The `timedelta(days=260)` was found in `data_provider.py`'s git history inside `get_city_daily_aggregates`.
- **Six pollutants vs Seven**: The engine calculates AQI using 7 pollutants (`PM2.5`, `PM10`, `NO2`, `SO2`, `O3`, `CO`, `NH3`), making `POLLUTANT_INPUTS` 7. However, the model only forecasts 6 target pollutants (`PRIMARY_TARGETS`). Therefore, the payload has 6 pollutants (NH3 is omitted from forecasts, only used as an input feature).

## Reference Gaps
The following domain topics were excluded from knowledge injections because no verified docs existed in `knowledge/sources` or `docs/`:
- Pollutant primers (descriptions and typical units)
- Common sources of pollutants (exhaust, biomass burning)
- Seasonal and meteorological drivers
- Health advisories broken down specifically by AQI categories
- Mitigation strategies broken down by pollutant source
- Domain Glossary

*Full details in `backend/agents/pollution_agent/knowledge/reference_gaps.md`.*

## Non-Pollution Issues Noticed (Ignored)
- The existing frontend UI `Planning.jsx` uses simple string-matching `setTimeout` logic natively for domains, rendering a "Simulating +20% green time" mock.
- `PlannerAgent`'s fallback `_detect_domain_from_text` (without LLM) is purely regex-based and fails on mixed languages for other domains. (I implemented a robust multilingual keyword matcher specifically for Pollution).
- `PlannerAgent` evaluates mock payloads natively. We hooked into this flow to inject the pollution integration.

## Application Steps for Domain Owners
To apply the shared patch:
1. Copy `backend/agents/pollution_agent/shared_hooks.patch`.
2. Move to the repo root `C:\Users\lenovo\Downloads\Smart_City\SmartCity\`.
3. Apply the patch via Git: `git apply backend/agents/pollution_agent/shared_hooks.patch`.
4. Ensure `frontend/src/pages/Planning.jsx` accurately maps the returned `data.pollution_card` keys (`text`, `insights`, `suggestions`) into its React component rendering flow.
