import urllib.request
import json
import time
import os
import sys

sys.path.insert(0, os.path.abspath("."))
from backend.agents.pollution_agent.grounding.handler import _analyze_question

questions = [
    "how to reduce aqi in kapra",
    "what is the aqi in kapra",
    "why is the air quality bad in kapra",
    "what can the city do to improve air quality in hyderabad",
    "which pollutant is dominant in kapra and how do we lower it",
]

audit_file = "backend/agents/pollution_agent/logs/pollution_answer_audit.jsonl"

for idx, q in enumerate(questions, 1):
    print(f"=== REPRO #{idx}: \"{q}\" ===", flush=True)
    analysis = _analyze_question(q)
    active_analysis = {k: v for k, v in analysis.items() if v}
    print(f"Detected Analysis: {json.dumps(active_analysis)}", flush=True)

    t0 = time.time()
    payload = json.dumps({"question": q}).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/planning/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elapsed = time.time() - t0
            print(f"Elapsed: {elapsed:.2f}s | HTTP {resp.status}", flush=True)
            print(f"Full JSON: {json.dumps(data)}", flush=True)
    except Exception as e:
        elapsed = time.time() - t0
        print(f"Error ({elapsed:.2f}s): {e}", flush=True)

    if os.path.exists(audit_file):
        with open(audit_file, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
            if lines:
                print(f"Matching Audit Line: {lines[-1]}", flush=True)
    print("", flush=True)
