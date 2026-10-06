"""
Verification Agent
Evaluates proposed municipal interventions for safety, logistical feasibility, and side effects.
"""

import json
from fastapi import FastAPI, APIRouter, HTTPException
from backend.schemas import VerificationRequest, VerificationResponse, VerificationStatus

try:
    from backend.utils.llm import get_llm_provider
except ImportError:
    # Stub for the LLM utility requested by user
    def get_llm_provider():
        class MockLLM:
            def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
                return {}
        return MockLLM()

app = FastAPI(title="Verification Agent", version="1.0.0")
router = APIRouter()

@app.get("/health")
def health():
    return {"agent": "Verification Agent", "status": "ONLINE"}

@router.post("/agents/verification/verify", response_model=VerificationResponse)
def verify_interventions(request: VerificationRequest):
    system_prompt = (
        "You are a strict municipal safety and policy auditor. "
        "Your task is to evaluate proposed municipal interventions for public safety risks, "
        "logistical feasibility, and potential negative secondary effects (e.g., extreme traffic gridlock). "
        "You must determine if the proposals are safe to proceed. If any intervention is deemed unsafe or illegal, "
        "safe_to_proceed MUST be false, and status MUST be REJECTED. "
        "Return a JSON object strictly matching the requested schema."
    )
    
    user_prompt = (
        f"Domain: {request.domain}\n"
        f"Location: {request.location}\n"
        f"Proposed Interventions: {json.dumps(request.proposed_interventions)}\n"
        "Evaluate these interventions and provide a strict safety and feasibility verdict in JSON format."
    )
    
    try:
        llm = get_llm_provider()
        llm_response = llm.generate_json(system_prompt, user_prompt)
        
        # Safe extraction with fallbacks
        safe_to_proceed = llm_response.get("safe_to_proceed", False)
        status_raw = llm_response.get("status", "REJECTED").upper()
        
        # Ensure status is a valid enum value
        valid_statuses = [e.value for e in VerificationStatus]
        if status_raw not in valid_statuses:
            status_raw = "REJECTED"
            safe_to_proceed = False
            
        auditor_feedback = llm_response.get("auditor_feedback", "No feedback provided.")
        
        return VerificationResponse(
            safe_to_proceed=safe_to_proceed,
            status=VerificationStatus(status_raw),
            auditor_feedback=auditor_feedback
        )
        
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"LLM API Error: {str(e)}")

app.include_router(router)
