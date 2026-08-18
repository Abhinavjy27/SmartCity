"""
SUPADSP Specialist Agent — Energy Grid Intelligence
Handles substation telemetry, grid load prediction, peak load shaving, and renewable integration.
"""

from fastapi import FastAPI

app = FastAPI(title="SUPADSP Energy Agent", version="2.0.0")

@app.get("/health")
def health():
    return {"agent": "Energy Agent", "status": "ONLINE"}

@app.get("/api/v1/energy/grid-status")
def get_grid_status():
    return {
        "current_load_mw": 4820,
        "capacity_mw": 6150,
        "load_pct": 78.4,
        "solar_generation_mw": 620,
        "substations": [
            {"id": "SUB_01", "name": "Madhapur 220kV", "load_pct": 86.2, "status": "HIGH"},
            {"id": "SUB_02", "name": "Gachibowli 132kV", "load_pct": 74.1, "status": "NORMAL"},
            {"id": "SUB_03", "name": "Kondapur 132kV", "load_pct": 68.9, "status": "NORMAL"}
        ]
    }
