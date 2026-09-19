import pandas as pd
import numpy as np
from datetime import datetime

class PollutionCalculator:
    def __init__(self, dataset_path: str = "../../datasets/pollution_telemetry.csv"):
        self.dataset_path = dataset_path

    def _apply_dispersion_multiplier(self, base_val: float, hour: int) -> float:
        """
        Simplified deterministic dispersion physics model.
        Pollutants concentrate more heavily at night/early morning due to lower inversion layers
        and lower wind dispersion (approximated here by time-of-day).
        """
        # A sinusoidal multiplier where pollution is higher early morning and late night.
        # Peaks around 4 AM (1.3x), lowest around 4 PM (0.7x)
        time_factor = 1.0 + 0.3 * np.cos((hour - 4) * np.pi / 12)
        return float(base_val * time_factor)

    def calculate_metrics(self, location: str, hour: int = None) -> dict:
        try:
            df = pd.read_csv(self.dataset_path)
        except FileNotFoundError:
            return {}
        
        if 'location' not in df.columns:
            return {}
            
        df_filtered = df[df['location'].astype(str).str.lower() == location.lower()]
        if df_filtered.empty:
            return {}
            
        avg_aqi = df_filtered['aqi'].mean() if 'aqi' in df.columns else 0
        avg_pm25 = df_filtered['pm25'].mean() if 'pm25' in df.columns else 0.0
        avg_pm10 = df_filtered['pm10'].mean() if 'pm10' in df.columns else 0.0
        
        stations = []
        if 'station_name' in df.columns:
            stations = df_filtered['station_name'].dropna().unique().tolist()
            
        # Apply deterministic physics dispersion based on current hour
        if hour is None:
            hour = datetime.now().hour
            
        computed_aqi = int(self._apply_dispersion_multiplier(avg_aqi, hour)) if pd.notna(avg_aqi) else 0
        computed_pm25 = self._apply_dispersion_multiplier(avg_pm25, hour) if pd.notna(avg_pm25) else 0.0
        computed_pm10 = self._apply_dispersion_multiplier(avg_pm10, hour) if pd.notna(avg_pm10) else 0.0
        
        return {
            "city_avg_aqi": computed_aqi,
            "pm25": round(computed_pm25, 1),
            "pm10": round(computed_pm10, 1),
            "stations": stations
        }
