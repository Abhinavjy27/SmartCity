from pydantic import BaseModel
from typing import List, Dict, Any
from enum import Enum

class VerificationRequest(BaseModel):
    domain: str
    location: str
    proposed_interventions: List[Dict[str, Any]]

class VerificationStatus(str, Enum):
    PASSED = "PASSED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"

class VerificationResponse(BaseModel):
    safe_to_proceed: bool
    status: VerificationStatus
    auditor_feedback: str
