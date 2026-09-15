"""
SUPADSP Specialist Agent — Energy Grid Intelligence
Handles substation telemetry, grid load prediction, peak load shaving, and renewable integration.
"""

from fastapi import FastAPI, APIRouter
from typing import Dict, Any
import datetime

app = FastAPI(title="SUPADSP Energy Agent", version="2.0.0")
router = APIRouter()

@app.get("/health")
def health():
    return {"agent": "Energy Agent", "status": "ONLINE"}

@router.get("/api/v1/energy/grid-status")
def get_grid_status():
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return {
        "source": "Live Energy Agent API",
        "timestamp": now_utc,
        "current_load_mw": 4820,
        "capacity_mw": 6150,
        "load_pct": 78.4,
        "solar_generation_mw": 620,
        "total_consumption_mwh": 1821,
        "efficiency_score_pct": 87.2,
        "substations": [
            {"id": "SUB_01", "name": "Madhapur 220kV", "load_pct": 86.2, "status": "HIGH"},
            {"id": "SUB_02", "name": "Gachibowli 132kV", "load_pct": 74.1, "status": "NORMAL"},
            {"id": "SUB_03", "name": "Kondapur 132kV", "load_pct": 68.9, "status": "NORMAL"}
        ],
        "hourly_load": [
            {"h": "00:00", "load": 48, "capacity": 92},
            {"h": "01:00", "load": 45, "capacity": 92},
            {"h": "02:00", "load": 42, "capacity": 92},
            {"h": "03:00", "load": 40, "capacity": 92},
            {"h": "04:00", "load": 42, "capacity": 92},
            {"h": "05:00", "load": 46, "capacity": 92},
            {"h": "06:00", "load": 54, "capacity": 92},
            {"h": "07:00", "load": 62, "capacity": 92},
            {"h": "08:00", "load": 71, "capacity": 92},
            {"h": "09:00", "load": 78, "capacity": 92},
            {"h": "10:00", "load": 82, "capacity": 92},
            {"h": "11:00", "load": 86, "capacity": 92},
            {"h": "12:00", "load": 89, "capacity": 92},
            {"h": "13:00", "load": 91, "capacity": 92},
            {"h": "14:00", "load": 92, "capacity": 92},
            {"h": "15:00", "load": 88, "capacity": 92},
            {"h": "16:00", "load": 85, "capacity": 92},
            {"h": "17:00", "load": 82, "capacity": 92},
            {"h": "18:00", "load": 79, "capacity": 92},
            {"h": "19:00", "load": 84, "capacity": 92},
            {"h": "20:00", "load": 86, "capacity": 92},
            {"h": "21:00", "load": 76, "capacity": 92},
            {"h": "22:00", "load": 65, "capacity": 92},
            {"h": "23:00", "load": 55, "capacity": 92},
        ],
        "zone_data": [
            {"zone": "HITECH City", "consumption": 342, "peak": 89, "color": "#00f0ff"},
            {"zone": "Gachibowli", "consumption": 285, "peak": 82, "color": "#8b5cf6"},
            {"zone": "Secunderabad", "consumption": 428, "peak": 91, "color": "#f43f5e"},
            {"zone": "Kukatpally", "consumption": 312, "peak": 78, "color": "#f59e0b"},
            {"zone": "Old City", "consumption": 256, "peak": 72, "color": "#10b981"},
            {"zone": "LB Nagar", "consumption": 198, "peak": 65, "color": "#3b82f6"},
        ],
        "recommendations": [
            {"title": "Shift non-critical loads to off-peak hours (22:00–06:00)", "impact": "12% reduction", "priority": "HIGH"},
            {"title": "Activate demand response program for HITECH City zone", "impact": "8% reduction", "priority": "HIGH"},
            {"title": "Optimize street lighting dimming schedule based on traffic volume", "impact": "15% savings", "priority": "MEDIUM"},
            {"title": "Deploy solar-assisted power at 12 government buildings", "impact": "20% offset", "priority": "MEDIUM"},
        ]
    }

app.include_router(router)
