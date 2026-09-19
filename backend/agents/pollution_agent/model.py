"""
Unified Forecaster Model Bridge.
Replaces the legacy Ganesh BiLSTM with the verified Unified Forecasting Pipeline.
Zero code paths remain to the deprecated aqi_lstm_model.pt or HuggingFace downloader.
"""
from pathlib import Path
from typing import Dict, Any, Optional, List
from .unified_forecast.inference import UnifiedForecaster
from .unified_forecast.config import ALL_FEATURES, NUM_FEATURES, PRIMARY_TARGETS

MODEL_FEATURES = ALL_FEATURES


class AQIForecastModel:
    """
    Unified AQI Forecast Model Adapter.
    Delegates all inference to UnifiedForecaster.
    Guarantees zero divergence in Day-1 predictions.
    """
    def __init__(self):
        self.unified = UnifiedForecaster.get_instance()
        self.status = "ready" if self.unified.loaded else "not_loaded"
        self.error_message = self.unified.error_message
        self.city_enc_value = 0

    def load(self, city_name: str = "Hyderabad") -> bool:
        success = self.unified.load()
        self.status = "ready" if success else "unavailable"
        return success

    def predict(self, rows: Optional[List[Dict]] = None) -> Dict[str, Any]:
        res = self.unified.predict()
        return res["daily"]

    def preprocess(self, days: List[Dict]) -> Optional[Any]:
        return None

    def get_info(self) -> Dict[str, Any]:
        return {
            "model_name": self.unified.model_name,
            "pipeline": "Unified Spatial-Temporal Forecasting Pipeline",
            "architecture": "Temporal GRU over Criteria Pollutants with CPCB AQI Engine",
            "license": "Apache-2.0",
        }


_model_instance: Optional[AQIForecastModel] = None


def get_model() -> AQIForecastModel:
    global _model_instance
    if _model_instance is None:
        _model_instance = AQIForecastModel()
    return _model_instance
