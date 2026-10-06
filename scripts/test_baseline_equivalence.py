import urllib.request
import json
import time

def test_chat(q, domain):
    payload = {"question": q, "domain": domain}
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/planning/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
        elapsed = time.time() - t0
        print(f"=== [{domain.upper()}] Q: {q} ({resp.status}, {elapsed:.2f}s) ===")
        print("Text:", data.get("text"))
        print("Insights:", data.get("insights"))
        print("Suggestions:", data.get("suggestions"))
        print()
        return data

if __name__ == "__main__":
    d_poll = test_chat("What is the current city AQI?", "pollution")
    d_weath = test_chat("what's the weather in Hyderabad now", "weather")
    d_traf = test_chat("how to reduce traffic along Begumpet", "traffic")
    d_ener = test_chat("what is the power load status on the grid", "energy")
