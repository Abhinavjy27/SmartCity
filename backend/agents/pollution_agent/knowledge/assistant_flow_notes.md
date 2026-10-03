# Planning AI Assistant Flow — Trace Notes

## STEP 1: Architecture Trace

### Frontend → Backend Flow (Current State)

**FINDING: The Planning AI chat is 100% frontend-only. No backend is involved.**

- **Frontend handler**: `Planning.jsx` → `handleSendMessage()` (line 276)
- **Request payload**: None — the function uses `setTimeout(() => { ... }, 900)` with
  hardcoded keyword-matching responses (lines 291-338). It never makes a fetch/axios call.
- **Backend route**: Does not exist. The chat input never reaches the backend.
- **LLM call**: None. Responses are templates.
- **Tools**: None.
- **Parsing**: Frontend directly sets `{ text, insights, suggestions }` via `setMessages`.

### Active Domain Chip

The "Active Domain" pill (line 389-394) displays `activeAlert.domain` which is derived from
the currently selected alert in the left panel (`activeAlerts[selectedAlertIndex].domain`).
It is **not** sent to any backend. It is purely cosmetic UI state.

**Test: Does chip drive routing?**
- Cannot test with 3 request/response pairs because no request is ever made.
- The chip value is never transmitted anywhere.
- Answer: **No**, the chip does not drive routing because there is no routing at all.

### Domain Classification

The backend planner (`planner.py` line 89-101) has `detect_domain_from_text()` which uses
keyword matching to classify questions into domains. The pollution keywords are:
`pollution, aqi, air quality, pm2.5, pm10, smoke, emission, pollutant, smog, carbon, particulate`

This function is called by the orchestrator flow (`/agents/orchestrator/execute`),
but the chat UI never triggers that flow.

### Insertion Points

1. **Frontend hook** (Planning.jsx `handleSendMessage`): Must be modified to call a backend
   endpoint instead of using `setTimeout`. This is the ONLY way to make the chat work.
   Without this change, the chat will NEVER use real data.

2. **Backend endpoint**: New endpoint at `/api/pollution/chat` under the pollution agent
   that receives the user's question and returns `{ text, insights, suggestions }`.

3. **Alternatively**: Add a new endpoint on the supervisor (`/api/planning/chat`) that
   the frontend calls, which routes to the pollution grounding when domain=pollution
   and falls back to the existing hardcoded logic for other domains.

### Chosen Approach

Since the frontend MUST be modified (the chat is entirely hardcoded), and the user allows
ONE hook of at most 10 lines in a shared file:

- **Hook location**: `Planning.jsx` `handleSendMessage()` — replace the `setTimeout` block
  with a `fetch()` call to `/api/planning/chat` on the supervisor.
- **Supervisor hook**: ONE route `/api/planning/chat` (≤10 lines) gated by
  `POLLUTION_GROUNDING=true`, delegating to the pollution grounding module.
- **Pollution grounding**: Full implementation under `backend/agents/pollution_agent/grounding/`.

### Shared-File Hook Required: YES

The frontend `Planning.jsx` is a shared file that MUST be modified because the chat
currently has zero backend integration. Without this change, no pollution grounding
can ever be surfaced to the user through the existing Planning AI chat.

The supervisor `main.py` needs a new endpoint `/api/planning/chat` to receive the
frontend's chat messages and route them.
