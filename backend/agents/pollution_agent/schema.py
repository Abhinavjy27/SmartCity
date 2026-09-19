from pydantic import BaseModel
from typing import List

class PollutionAnalyzeRequest(BaseModel):
    objective: str
    location: str

class PollutionIntervention(BaseModel):
    action_type: str
    description: str
    expected_impact_pct: float
    feasibility_score: float

class PollutionAnalyzeResponse(BaseModel):
    city_avg_aqi: int
    pm25: float
    pm10: float
    stations: List[str]
    suggested_interventions: List[PollutionIntervention]
