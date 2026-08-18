"""
Test download of verified Telangana GeoJSON
"""
import urllib.request
import os

url = "https://raw.githubusercontent.com/gpavanb1/Telangana-Visualisation/master/data/Telangana.geojson"
dest = "datasets/raw/gis/telangana_districts.geojson"

req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as resp, open(dest, 'wb') as f:
    f.write(resp.read())

print(f"Successfully downloaded Telangana GeoJSON ({os.path.getsize(dest)/1024:.2f} KB) to {dest}")
