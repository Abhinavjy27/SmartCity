# Assistant Flow Notes

## Tracing Real Requests
The `Planning.jsx` frontend does not currently send chat messages to the backend. The chat interaction is completely mocked.
- **How domain is chosen:** In the current mocked UI, there is no domain routing. In the actual backend `PlannerAgent` (`backend/agents/planner_agent/planner.py`), `detect_domain_from_text()` selects the domain based on keyword presence (e.g., "pollution", "aqi").
- **How chips reach the Planner:** Currently, they do not. `Planning.jsx` uses hardcoded strings. The backend `Supervisor` receives `PlannerPlanRequest` with `objective` and `location`, but the UI chips are not transmitted to the backend.
- **Which agents/tools run:** None are currently executed by the frontend chat because it uses `setTimeout()` to inject fake AI responses.
- **Which prompt is used:** The backend uses `PLANNER_SYSTEM_PROMPT` in `prompts.py` for general routing and `PLANNER_EVALUATION_SYSTEM_PROMPT` for result evaluation, but this is separated from the UI chat.
- **Response Schema:** The frontend expects an AI message object with `text`, `insights` (an array of bullets), and `suggestions` (an array of follow-up chips).
- **Off-topic Questions:** In the backend `PlannerAgent`, `is_out_of_scope_query()` catches general knowledge and coding queries using regex. In the UI mock, off-topic questions simply return default traffic insights.
