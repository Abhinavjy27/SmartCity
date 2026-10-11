"""
Unit and integration tests for the SUPADSP Weather Agent using standard unittest.
"""

import unittest
from fastapi.testclient import TestClient
from backend.agents.weather_agent.main import app
from backend.agents.weather_agent.provider import resolve_location, wmo_code_to_condition


class WeatherAgentTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_check(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["agent"], "Weather Agent")
        self.assertEqual(data["status"], "ONLINE")

    def test_get_current_weather(self):
        resp = self.client.get("/api/v1/weather/current")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("temperature_c", data)
        self.assertIn("humidity_pct", data)
        self.assertIn("wind_speed_kmh", data)
        self.assertIn("condition", data)
        self.assertIn("forecast_7d", data)
        self.assertIsInstance(data["forecast_7d"], list)

    def test_get_current_weather_locality(self):
        resp = self.client.get("/api/v1/weather/current?location=Gachibowli")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["city"], "Gachibowli")
        self.assertIn("temperature_c", data)

    def test_get_forecast(self):
        resp = self.client.get("/api/v1/weather/forecast?location=Hyderabad")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("forecast_7d", data)
        self.assertGreater(len(data["forecast_7d"]), 0)

    def test_get_alerts(self):
        resp = self.client.get("/api/v1/weather/alerts?location=Hyderabad")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("alerts", data)
        self.assertIn("risk_level", data)
        self.assertIn("air_comfort", data)

    def test_analyze_weather(self):
        resp = self.client.post("/api/v1/weather/analyze", json={"location": "Begumpet"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("cross_domain_impacts", data)
        self.assertIn("traffic_impact", data["cross_domain_impacts"])
        self.assertIn("energy_impact", data["cross_domain_impacts"])
        self.assertIn("pollution_impact", data["cross_domain_impacts"])
        self.assertIn("recommendations", data)

    def test_resolve_location(self):
        name, lat, lon = resolve_location("Begumpet")
        self.assertEqual(name, "Begumpet")
        self.assertEqual(lat, 17.4440)

        name, lat, lon = resolve_location("Unknown Place")
        self.assertEqual(name, "Hyderabad")

    def test_wmo_code_mapping(self):
        cond, icon = wmo_code_to_condition(0)
        self.assertEqual(cond, "Clear Sky")
        self.assertEqual(icon, "Sun")

        cond, icon = wmo_code_to_condition(95)
        self.assertEqual(cond, "Thunderstorm")
        self.assertEqual(icon, "CloudLightning")

    def test_weather_chat_endpoint_rain(self):
        resp = self.client.post(
            "/api/v1/weather/chat",
            json={"question": "Is it going to rain in Narayanguda today?"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("text", data)
        self.assertIn("Narayanguda", data["text"])
        self.assertIn("insights", data)
        self.assertIn("suggestions", data)
        self.assertIn("data", data)
        self.assertEqual(data["data"]["locality"], "Narayanguda")

    def test_weather_chat_endpoint_temperature_gachibowli(self):
        resp = self.client.post(
            "/api/v1/weather/chat",
            json={"question": "What is the temperature in Gachibowli right now?"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("text", data)
        self.assertIn("Gachibowli", data["text"])
        self.assertIn("°C", data["text"])
        self.assertIsInstance(data["insights"], list)

    def test_weather_chat_endpoint_alerts(self):
        resp = self.client.post(
            "/api/v1/weather/chat",
            json={"question": "Are there any thunderstorm or severe weather alerts for Begumpet?"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("text", data)
        self.assertIn("Begumpet", data["text"])


if __name__ == "__main__":
    unittest.main()
