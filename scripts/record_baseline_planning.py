import json
import time
import urllib.request
import urllib.error
from pathlib import Path

queries = [
    {"domain": "pollution", "question": "What is the current city AQI?"},
    {"domain": "weather", "question": "what's the weather in Hyderabad now"},
    {"domain": "traffic", "question": "how to reduce traffic along Begumpet"},
    {"domain": "energy", "question": "what is the power load status on the grid"}
]

out_dir = Path("eval")
out_dir.mkdir(parents=True, exist_ok=True)
out_file = out_dir / "baseline_planning.jsonl"

url = "http://127.0.0.1:8000/api/planning/chat"

print(f"Recording baseline planning questions to {out_file}...")

with open(out_file, "w", encoding="utf-8") as f:
    for q in queries:
        payload = json.dumps(q).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                elapsed = time.perf_counter() - start
                body = resp.read().decode("utf-8")
                parsed = json.loads(body)
                record = {
                    "domain": q["domain"],
                    "question": q["question"],
                    "status_code": resp.status,
                    "elapsed_ms": round(elapsed * 1000, 2),
                    "response": parsed
                }
        except urllib.error.HTTPError as e:
            elapsed = time.perf_counter() - start
            body = e.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = body
            record = {
                "domain": q["domain"],
                "question": q["question"],
                "status_code": e.code,
                "elapsed_ms": round(elapsed * 1000, 2),
                "error": str(e),
                "response": parsed
            }
        except Exception as e:
            elapsed = time.perf_counter() - start
            record = {
                "domain": q["domain"],
                "question": q["question"],
                "status_code": 0,
                "elapsed_ms": round(elapsed * 1000, 2),
                "error": str(e),
                "response": None
            }
        
        f.write(json.dumps(record) + "\n")
        f.flush()
        print(f"[{q['domain'].upper()}] {q['question']} -> HTTP {record['status_code']} ({record['elapsed_ms']}ms)")
        print(f"Response text: {record.get('response', {}).get('text') if record.get('response') else record.get('error')}\n")

print(f"Baseline saved to {out_file}")
