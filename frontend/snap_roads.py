import re
import ast
import json
import urllib.request

file_path = "c:/Users/lenovo/Downloads/Smart_City/SmartCity/frontend/src/services/map/hyderabadGeoData.js"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

start_idx = content.find("export const REAL_TRAFFIC_FLOWS = {")
end_idx = content.find("export const REAL_ENERGY_SUBSTATIONS")

traffic_flows_text = content[start_idx:end_idx]

# Find coordinates arrays inside geometry blocks
# A robust regex for an array of arrays of floats
pattern = r"coordinates:\s*(\[\s*(?:\[\s*[-+]?[0-9]*\.?[0-9]+,\s*[-+]?[0-9]*\.?[0-9]+\s*\],\s*)*\[\s*[-+]?[0-9]*\.?[0-9]+,\s*[-+]?[0-9]*\.?[0-9]+\s*\]\s*,?\s*\])"
matches = re.finditer(pattern, traffic_flows_text)

new_text = traffic_flows_text

def fetch_osrm_route(coords):
    # OSRM expects lon,lat;lon,lat
    coord_string = ";".join([f"{c[0]},{c[1]}" for c in coords])
    url = f"http://router.project-osrm.org/route/v1/driving/{coord_string}?geometries=geojson&overview=full"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            if data.get("code") == "Ok":
                return data["routes"][0]["geometry"]["coordinates"]
    except Exception as e:
        print(f"Error fetching OSRM: {e}")
    return coords

for match in matches:
    original_str = match.group(1)
    
    try:
        # evaluate string as python list
        coords_list = ast.literal_eval(original_str.strip())
        # ast might return tuple if trailing comma, let's cast to list
        if isinstance(coords_list, tuple):
            coords_list = list(coords_list)
            
        print(f"Matched coordinates block with {len(coords_list)} points")
        
        precise_coords = fetch_osrm_route(coords_list)
        print(f" -> Snapped to {len(precise_coords)} points")
        
        new_coords_str = "[\n"
        for c in precise_coords:
            new_coords_str += f"          [{c[0]:.5f}, {c[1]:.5f}],\n"
        new_coords_str += "        ]"
        
        new_text = new_text.replace(original_str, new_coords_str)
        
    except Exception as e:
        print(f"Error parsing: {e}")

new_content = content[:start_idx] + new_text + content[end_idx:]
with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)
print("Done!")
