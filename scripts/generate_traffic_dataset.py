"""
Vectorized Hyderabad Traffic Sensor Speed & Flow Dataset Generator
Generates realistic multi-intersection spatio-temporal traffic sensor speed, volume, and adjacency matrix
for SUPADSP Hyderabad Smart City Traffic Module.
"""

import os
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAFFIC_DIR = os.path.join(BASE_DIR, "datasets", "raw", "traffic")
os.makedirs(TRAFFIC_DIR, exist_ok=True)

INTERSECTIONS = [
    {"id": "SENSOR_01", "name": "Gachibowli Flyover", "lat": 17.4401, "lon": 78.3489, "capacity": 3500, "free_flow_speed": 65.0},
    {"id": "SENSOR_02", "name": "HITECH City Mindspace", "lat": 17.4435, "lon": 78.3772, "capacity": 4000, "free_flow_speed": 60.0},
    {"id": "SENSOR_03", "name": "Jubilee Hills Checkpost", "lat": 17.4319, "lon": 78.4073, "capacity": 3800, "free_flow_speed": 55.0},
    {"id": "SENSOR_04", "name": "Punjagutta Junction", "lat": 17.4265, "lon": 78.4511, "capacity": 4200, "free_flow_speed": 50.0},
    {"id": "SENSOR_05", "name": "Begumpet Airport Flyover", "lat": 17.4447, "lon": 78.4664, "capacity": 3600, "free_flow_speed": 60.0},
    {"id": "SENSOR_06", "name": "Secunderabad Paradise Circle", "lat": 17.4416, "lon": 78.4871, "capacity": 3900, "free_flow_speed": 50.0},
    {"id": "SENSOR_07", "name": "Koti Women's College Circle", "lat": 17.3850, "lon": 78.4867, "capacity": 3200, "free_flow_speed": 45.0},
    {"id": "SENSOR_08", "name": "Charminar Madina Junction", "lat": 17.3616, "lon": 78.4747, "capacity": 2800, "free_flow_speed": 35.0},
    {"id": "SENSOR_09", "name": "LB Nagar Ring Road Circle", "lat": 17.3457, "lon": 78.5522, "capacity": 4500, "free_flow_speed": 65.0},
    {"id": "SENSOR_10", "name": "Kukatpally Y Junction", "lat": 17.4947, "lon": 78.3996, "capacity": 4100, "free_flow_speed": 55.0},
    {"id": "SENSOR_11", "name": "Miyapur Metro Station Junction", "lat": 17.4966, "lon": 78.3614, "capacity": 3700, "free_flow_speed": 60.0},
    {"id": "SENSOR_12", "name": "Mehdipatnam Bus Station Circle", "lat": 17.3956, "lon": 78.4382, "capacity": 3600, "free_flow_speed": 45.0},
    {"id": "SENSOR_13", "name": "Ameerpet Metro Interchange", "lat": 17.4375, "lon": 78.4482, "capacity": 4000, "free_flow_speed": 45.0},
    {"id": "SENSOR_14", "name": "Banjara Hills Road No 1", "lat": 17.4162, "lon": 78.4496, "capacity": 3300, "free_flow_speed": 50.0},
    {"id": "SENSOR_15", "name": "Toli Chowki Flyover", "lat": 17.4083, "lon": 78.4144, "capacity": 3400, "free_flow_speed": 55.0},
]

def generate_traffic_data():
    print("Generating Vectorized Hyderabad Traffic Sensor Time Series (2023)...")
    timestamps = pd.date_range(start="2023-01-01 00:00:00", end="2023-12-31 23:45:00", freq="15min")
    num_times = len(timestamps)
    num_sensors = len(INTERSECTIONS)
    
    np.random.seed(42)
    
    hours = timestamps.hour.to_numpy() + timestamps.minute.to_numpy() / 60.0
    day_of_week = timestamps.dayofweek.to_numpy()
    is_weekend = (day_of_week >= 5).astype(float)
    
    morning_rush = np.exp(-((hours - 9.0) ** 2) / 3.0)
    evening_rush = np.exp(-((hours - 18.5) ** 2) / 4.0)
    
    base_demand = 0.2 + 0.5 * morning_rush + 0.65 * evening_rush
    weekend_adjustment = 0.65 + 0.15 * np.exp(-((hours - 16.0) ** 2) / 8.0)
    
    demand = np.where(is_weekend > 0, base_demand * weekend_adjustment, base_demand)
    
    # Expand to shape (num_times, num_sensors)
    demand_matrix = np.tile(demand[:, None], (1, num_sensors))
    noise = np.random.normal(0, 0.05, size=(num_times, num_sensors))
    demand_matrix = np.clip(demand_matrix + noise, 0.05, 1.1)
    
    capacities = np.array([s["capacity"] for s in INTERSECTIONS])
    free_flows = np.array([s["free_flow_speed"] for s in INTERSECTIONS])
    lats = np.array([s["lat"] for s in INTERSECTIONS])
    lons = np.array([s["lon"] for s in INTERSECTIONS])
    s_ids = [s["id"] for s in INTERSECTIONS]
    s_names = [s["name"] for s in INTERSECTIONS]
    
    speed_matrix = free_flows[None, :] * (1.0 - 0.7 * (demand_matrix ** 1.5))
    speed_matrix += np.random.normal(0, 2.5, size=(num_times, num_sensors))
    speed_matrix = np.clip(speed_matrix, 5.0, free_flows[None, :])
    
    volume_matrix = (capacities[None, :] * demand_matrix).astype(int)
    occupancy_matrix = np.clip((volume_matrix / capacities[None, :]) * 85.0 + np.random.normal(0, 3.0, size=(num_times, num_sensors)), 2.0, 98.0)
    congestion_idx_matrix = np.clip((free_flows[None, :] - speed_matrix) / free_flows[None, :], 0.0, 1.0)
    
    # Flatten matrices
    ts_repeated = np.repeat(timestamps.to_numpy(), num_sensors)
    sensor_id_repeated = np.tile(s_ids, num_times)
    sensor_name_repeated = np.tile(s_names, num_times)
    lat_repeated = np.tile(lats, num_times)
    lon_repeated = np.tile(lons, num_times)
    
    df = pd.DataFrame({
        "timestamp": ts_repeated,
        "sensor_id": sensor_id_repeated,
        "location_name": sensor_name_repeated,
        "latitude": lat_repeated,
        "longitude": lon_repeated,
        "speed_kmh": np.round(speed_matrix.ravel(), 2),
        "volume_vph": volume_matrix.ravel(),
        "occupancy_pct": np.round(occupancy_matrix.ravel(), 2),
        "congestion_index": np.round(congestion_idx_matrix.ravel(), 3)
    })
    
    csv_path = os.path.join(TRAFFIC_DIR, "hyderabad_traffic_sensors_2023.csv")
    df.to_csv(csv_path, index=False)
    size_mb = os.path.getsize(csv_path) / (1024 * 1024)
    print(f"[SUCCESS] Saved Hyderabad Traffic Sensor Dataset ({size_mb:.2f} MB) with {len(df):,} rows to {csv_path}")

def generate_adjacency_matrix():
    print("Generating Sensor Spatial Distance & Adjacency Matrix...")
    n = len(INTERSECTIONS)
    adj_matrix = np.zeros((n, n))
    coords = np.array([[s["lat"], s["lon"]] for s in INTERSECTIONS])
    
    for i in range(n):
        for j in range(n):
            if i == j:
                adj_matrix[i, j] = 1.0
            else:
                lat1, lon1 = np.radians(coords[i])
                lat2, lon2 = np.radians(coords[j])
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
                c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
                dist_km = 6371.0 * c
                sigma = 5.0
                if dist_km <= 10.0:
                    adj_matrix[i, j] = np.exp(- (dist_km / sigma) ** 2)
                else:
                    adj_matrix[i, j] = 0.0
                    
    sensor_ids = [s["id"] for s in INTERSECTIONS]
    adj_df = pd.DataFrame(adj_matrix, index=sensor_ids, columns=sensor_ids)
    adj_path = os.path.join(TRAFFIC_DIR, "traffic_sensor_adjacency.csv")
    adj_df.to_csv(adj_path)
    print(f"[SUCCESS] Saved Sensor Spatial Adjacency Matrix to {adj_path}")

if __name__ == "__main__":
    generate_traffic_data()
    generate_adjacency_matrix()
    print("[COMPLETE] Traffic dataset generation completed successfully.")
