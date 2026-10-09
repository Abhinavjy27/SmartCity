# Shared Files Touched

The following files belonging to other domains must be patched using the provided `shared_hooks.patch`:

## 1. `backend/agents/planner_agent/planner.py`
- **Purpose**: Hooks the Planner Agent execution pipeline to dynamically route air quality questions to the Pollution Agent (`answer_pollution_question`) before hitting the default logic.
- **Affected Domains**: Planner core logic. Other domains (Traffic, Energy, Weather) are not affected, as the hook strictly falls back to the default `_detect_domain` path if the question is "not" pollution. In a "mixed" scenario, pollution context is generated and merged with the response via a new `pollution_card` field.

## 2. `frontend/src/pages/Planning.jsx`
- **Purpose**: Wires the existing mock UI to actually invoke the `POST /agents/planner/plan` backend when a message is sent.
- **Affected Domains**: Planning AI chat UI. Mock logic remains fully intact for non-pollution questions. It acts purely as a progressive enhancement. A fetch is initiated, and if a `pollution_card` is returned in the JSON payload, it natively renders the card component. Otherwise (or on timeout), it continues to the `setTimeout` mock as if nothing happened.
