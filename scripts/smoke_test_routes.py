import json
import time
import urllib.request
import urllib.error

# Load route inventory
with open("docs/route_inventory_raw.json", "r", encoding="utf-8") as f:
    inv = json.load(f)

routes = inv["routes"]
print(f"Total routes in inventory: {len(routes)}")

# Read-only GET routes and safe read-only POST routes
# We should test all GET endpoints without required path parameters or test with default params
results = []
skipped = []

SAFE_POST_PATHS = {
    "/agents/knowledge/search": {"query": "air quality Hyderabad"},
    "/agents/data-discovery/discover": {"query": "traffic data"},
    "/agents/data-retrieval/retrieve": {"source": "traffic"},
    "/models/traffic/analyze": {
        "request_id": "test_req_1",
        "location": "Gachibowli",
        "scenario": "peak_rush_hour",
        "inputs": {"current_speed": 20.0, "volume": 3000, "occupancy": 80.0}
    },
    "/models/flood/analyze": {
        "request_id": "test_req_2",
        "location": "Nacharam",
        "scenario": "rainfall_accumulation",
        "inputs": {"rainfall_mm": 20, "drainage_capacity_pct": 70}
    },
    "/models/energy/analyze": {
        "request_id": "test_req_3",
        "location": "Financial District",
        "scenario": "peak_load",
        "inputs": {"current_load_mw": 40.0, "capacity_mw": 50.0}
    },
    "/models/weather/analyze": {
        "request_id": "test_req_4",
        "location": "Hyderabad Central",
        "scenario": "dispersion",
        "inputs": {"wind_speed_kmh": 10.0, "temperature_c": 30.0, "humidity_pct": 60.0}
    },
    "/api/v1/traffic/analyze": {"corridor_id": "corr_begumpet"},
    "/api/v1/pollution/analyze": {"location": "Hyderabad"},
    "/api/planning/chat": {"question": "What is the current city AQI?"}
}

MUTATING_POST_PATTERNS = [
    "/planning/requests",
    "/agents/planner/plan",
    "/agents/planner/feedback",
    "/agents/planner/execute",
    "/alerts/", # acknowledge / dismiss
    "/simulations", # create
    "/agents/verification/verify",
    "/agents/fail-safe/check",
    "/recommendations/", # approve / reject / modify
    "/api/v1/traffic/optimize-signal",
    "/api/v1/energy/peak-shave",
    "/api/v1/energy/analyze",
    "/api/v1/simulation/run",
    "/api/pollution/predict"
]

def is_mutating(method, path):
    if method != "GET":
        if path in SAFE_POST_PATHS:
            return False
        return True
    return False

def make_request(url, method="GET", body=None, timeout=10):
    start = time.perf_counter()
    headers = {"Content-Type": "application/json"}
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = time.perf_counter() - start
            body_bytes = resp.read()
            status_code = resp.status
            try:
                parsed = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                parsed = body_bytes.decode("utf-8", errors="replace")
            return {
                "status_code": status_code,
                "elapsed": elapsed,
                "error": None,
                "body": parsed,
                "body_len": len(body_bytes)
            }
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - start
        err_body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = err_body
        return {
            "status_code": e.code,
            "elapsed": elapsed,
            "error": str(e),
            "body": parsed,
            "body_len": len(err_body)
        }
    except Exception as e:
        elapsed = time.perf_counter() - start
        return {
            "status_code": 0,
            "elapsed": elapsed,
            "error": str(e),
            "body": None,
            "body_len": 0
        }

for r in routes:
    m = r["method"]
    p = r["path"]
    
    # Check if mutating
    if is_mutating(m, p):
        skipped.append({"method": m, "path": p, "reason": "Mutating POST endpoint"})
        continue
    
    # Check if parameterized path
    test_path = p
    if "{" in p:
        if "{request_id}" in p:
            test_path = p.replace("{request_id}", "planreq_test")
        elif "{alert_id}" in p:
            test_path = p.replace("{alert_id}", "ALERT_01")
        elif "{simulation_id}" in p:
            test_path = p.replace("{simulation_id}", "sim_test")
        elif "{recommendation_id}" in p:
            test_path = p.replace("{recommendation_id}", "REC_01")
        elif "{location}" in p:
            test_path = p.replace("{location}", "Gachibowli")
        else:
            skipped.append({"method": m, "path": p, "reason": "Unhandled path parameter"})
            continue
            
    url = f"http://127.0.0.1:8000{test_path}"
    post_body = SAFE_POST_PATHS.get(p)
    
    # Cold test
    cold = make_request(url, method=m, body=post_body)
    # Warm test
    warm = make_request(url, method=m, body=post_body)
    
    body_data = warm["body"] if isinstance(warm["body"], dict) else {}
    body_status = body_data.get("status") if isinstance(body_data, dict) else None
    data_mode = body_data.get("data_mode") if isinstance(body_data, dict) else None
    data_source = body_data.get("data_source") if isinstance(body_data, dict) else None
    
    empty_body = (warm["body_len"] == 0 or warm["body"] is None or warm["body"] == {})
    
    res_entry = {
        "method": m,
        "path": p,
        "tested_url": url,
        "name": r["name"],
        "owner": r["owner"],
        "location": r["location"],
        "cold_ms": round(cold["elapsed"] * 1000, 2),
        "warm_ms": round(warm["elapsed"] * 1000, 2),
        "status_code": warm["status_code"],
        "body_status": body_status,
        "data_mode": data_mode,
        "data_source": data_source,
        "empty_body": empty_body,
        "flag_slow": warm["elapsed"] > 3.0,
        "flag_error": warm["status_code"] >= 400 or warm["status_code"] == 0,
        "flag_unavailable": body_status == "unavailable" or "unavailable" in str(body_data).lower() if isinstance(body_data, dict) else False
    }
    results.append(res_entry)
    print(f"[{m}] {p} -> HTTP {warm['status_code']} | cold: {res_entry['cold_ms']}ms | warm: {res_entry['warm_ms']}ms | status={body_status}")

out_data = {
    "tested_count": len(results),
    "skipped_count": len(skipped),
    "results": results,
    "skipped": skipped
}

with open("docs/smoke_test_results.json", "w", encoding="utf-8") as f:
    json.dump(out_data, f, indent=2)

print(f"\nDone. Tested {len(results)} routes, skipped {len(skipped)}. Saved to docs/smoke_test_results.json")
