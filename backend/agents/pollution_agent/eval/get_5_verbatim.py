import os
import sys
import json
from pathlib import Path

# Force UTF-8 on Windows
sys.stdout.reconfigure(encoding='utf-8')

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.agents.pollution_agent.grounding.handler import handle_pollution_chat

questions = [
    "how to reduce aqi in kapra",
    "what can be done about PM10 at Bollaram",
    "why is Nacharam high and what should we do",
    "suggest measures to improve Hyderabad air quality",
    "is it safe to jog at Zoo Park now"
]

results = {}
for q in questions:
    print(f"Running: {q}...", flush=True)
    resp = handle_pollution_chat(q)
    results[q] = resp

out_path = Path(__file__).resolve().parent / "verbatim_5_answers.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"Saved to {out_path}")
