"""
SUPADSP Hyderabad & Benchmark Automated Dataset Downloader
Run this script via: python scripts/download_datasets.py
"""

import os
import urllib.request
import zipfile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "datasets", "raw")

def ensure_dirs():
    for d in ["weather", "pollution", "energy", "gis"]:
        path = os.path.join(RAW_DIR, d)
        os.makedirs(path, exist_ok=True)

def download_file(url, dest):
    print(f"Downloading from: {url}")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    with urllib.request.urlopen(req) as response, open(dest, 'wb') as out_file:
        out_file.write(response.read())
    size_mb = os.path.getsize(dest) / (1024 * 1024)
    print(f"[SUCCESS] Saved file ({size_mb:.2f} MB) to {dest}")

def download_weather():
    print("\n--- 1. Downloading Hyderabad Weather Data (2020 - 2024 Hourly) ---")
    url = (
        "https://archive-api.open-meteo.com/v1/archive?"
        "latitude=17.3850&longitude=78.4867&"
        "start_date=2020-01-01&end_date=2024-01-01&"
        "hourly=temperature_2m,relative_humidity_2m,dew_point_2m,apparent_temperature,"
        "precipitation,rain,surface_pressure,wind_speed_10m,wind_direction_10m,shortwave_radiation&"
        "format=csv"
    )
    dest = os.path.join(RAW_DIR, "weather", "hyderabad_weather_2020_2024.csv")
    download_file(url, dest)

def download_gis():
    print("\n--- 2. Downloading Telangana & Hyderabad GIS Spatial Data ---")
    url = "https://raw.githubusercontent.com/gpavanb1/Telangana-Visualisation/master/data/Telangana.geojson"
    dest = os.path.join(RAW_DIR, "gis", "telangana_districts.geojson")
    download_file(url, dest)

def download_energy():
    print("\n--- 3. Downloading UCI Energy Consumption Benchmark Dataset ---")
    url = "https://archive.ics.uci.edu/static/public/235/individual+household+electric+power+consumption.zip"
    zip_dest = os.path.join(RAW_DIR, "energy", "household_power.zip")
    try:
        download_file(url, zip_dest)
        print("Extracting ZIP archive...")
        with zipfile.ZipFile(zip_dest, 'r') as zip_ref:
            zip_ref.extractall(os.path.join(RAW_DIR, "energy"))
        os.remove(zip_dest)
        txt_path = os.path.join(RAW_DIR, "energy", "individual_household_electric+power_consumption.txt")
        print(f"[SUCCESS] Extracted energy dataset to {os.path.join(RAW_DIR, 'energy')}")
    except Exception as e:
        print(f"[!] UCI download encountered issue: {e}")

def download_pollution():
    print("\n--- 4. Downloading Hyderabad Air Quality & Pollution Dataset (2020 - 2024 Hourly) ---")
    url = (
        "https://air-quality-api.open-meteo.com/v1/air-quality?"
        "latitude=17.3850&longitude=78.4867&"
        "start_date=2020-01-01&end_date=2024-01-01&"
        "hourly=pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,us_aqi&"
        "format=csv"
    )
    dest = os.path.join(RAW_DIR, "pollution", "hyderabad_air_quality_2020_2024.csv")
    download_file(url, dest)

if __name__ == "__main__":
    ensure_dirs()
    download_weather()
    download_gis()
    download_energy()
    download_pollution()
    print("\n[COMPLETE] Download task completed.")


