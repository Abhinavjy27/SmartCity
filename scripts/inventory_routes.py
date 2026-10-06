import inspect
import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.supervisor.main import app

routes = []
seen = {}
duplicates = []

def extract_routes(route_list, prefix=""):
    extracted = []
    for r in route_list:
        if hasattr(r, "routes"):
            new_prefix = prefix + (getattr(r, "path", "") or "")
            extracted.extend(extract_routes(r.routes, new_prefix))
        elif hasattr(r, "original_router") and hasattr(r.original_router, "routes"):
            new_prefix = prefix + (getattr(r, "path", "") or "")
            extracted.extend(extract_routes(r.original_router.routes, new_prefix))
        elif hasattr(r, "path") and hasattr(r, "endpoint"):
            extracted.append((prefix + r.path, r))
        elif hasattr(r, "path_format") and hasattr(r, "endpoint"):
            extracted.append((prefix + r.path_format, r))
    return extracted

all_raw = extract_routes(app.routes)

for path, r in all_raw:
    methods = sorted(list(r.methods)) if hasattr(r, 'methods') and r.methods else ['*']
    methods = [m for m in methods if m not in ('HEAD', 'OPTIONS')]
    if not methods:
        continue
    endpoint = getattr(r, 'endpoint', None)
    if endpoint:
        try:
            file_ = inspect.getsourcefile(endpoint)
            try:
                rel_file = Path(file_).relative_to(Path.cwd()).as_posix()
            except Exception:
                rel_file = file_
            lines, start_line = inspect.getsourcelines(endpoint)
            loc = f"{rel_file}:{start_line}"
        except Exception:
            loc = "unknown"
        tags = getattr(r, 'tags', [])
        name = getattr(endpoint, '__name__', str(endpoint))
    else:
        loc = "unknown"
        tags = []
        name = "none"

    owner = "Supervisor"
    if tags:
        owner = ", ".join(tags)
    elif "pollution" in path or "pollution_agent" in loc:
        owner = "Specialist Agent - Pollution"
    elif "traffic" in path or "traffic_agent" in loc:
        owner = "Specialist Agent - Traffic"
    elif "weather" in path or "weather_agent" in loc:
        owner = "Specialist Agent - Weather"
    elif "energy" in path or "energy_agent" in loc:
        owner = "Specialist Agent - Energy"
    elif "simulation" in path or "simulation_agent" in loc:
        owner = "Specialist Agent - Simulation"
    elif "planner" in path or "planner_agent" in loc:
        owner = "Planner Agent"

    for m in methods:
        key = (m, path)
        if key in seen:
            prev = seen[key]
            duplicates.append({
                "method": m,
                "path": path,
                "current_name": name,
                "current_loc": loc,
                "previous_name": prev["name"],
                "previous_loc": prev["loc"],
            })
        else:
            seen[key] = {"name": name, "loc": loc, "owner": owner}

        routes.append({
            "method": m,
            "path": path,
            "name": name,
            "location": loc,
            "owner": owner,
        })

print(f"TOTAL_ROUTES={len(routes)}")
print(f"TOTAL_DUPLICATES={len(duplicates)}")
print("\n--- DUPLICATES ---")
for d in duplicates:
    print(f"DUPLICATE: {d['method']} {d['path']} | Registered: {d['current_name']} ({d['current_loc']}) | Shadows: {d['previous_name']} ({d['previous_loc']})")

output_path = Path("docs/route_inventory_raw.json")
output_path.parent.mkdir(parents=True, exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    json.dump({"total": len(routes), "duplicates": duplicates, "routes": routes}, f, indent=2)
print(f"\nSaved {len(routes)} routes to {output_path}")
