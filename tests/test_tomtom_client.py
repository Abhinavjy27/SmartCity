"""
tests/test_tomtom_client.py
============================
Unit tests for the TomTom service layer (backend/services/tomtom.py).
All external HTTP calls are mocked with httpx.MockTransport — no real
TomTom API is called during tests.

Run with:
    pytest tests/test_tomtom_client.py -v
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure TOMTOM_API_KEY is set before importing the service
# ---------------------------------------------------------------------------
os.environ.setdefault("TOMTOM_API_KEY", "TEST_KEY_MOCKED")
os.environ.setdefault("TRAFFIC_MODE", "live")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_flow_response(current_speed: float = 25.0, free_flow: float = 60.0) -> Dict[str, Any]:
    return {
        "flowSegmentData": {
            "currentSpeed": current_speed,
            "freeFlowSpeed": free_flow,
            "currentTravelTime": 240,
            "freeFlowTravelTime": 100,
            "confidence": 0.95,
            "roadClosure": False,
        }
    }


def _make_incidents_response(count: int = 3) -> Dict[str, Any]:
    incidents = []
    for i in range(count):
        incidents.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [78.38 + i * 0.01, 17.45]},
            "properties": {
                "iconCategory": 1,
                "magnitudeOfDelay": 3,
                "from": f"Location {i}",
                "to": f"Destination {i}",
                "delay": 300 + i * 60,
                "length": 200 + i * 50,
                "startTime": "2025-06-12T10:00:00Z",
                "endTime": "2025-06-12T12:00:00Z",
            }
        })
    return {"incidents": incidents}


# ---------------------------------------------------------------------------
# Tests: _TTLCache
# ---------------------------------------------------------------------------

class TestTTLCache:
    def test_get_returns_none_for_missing_key(self):
        from backend.services.tomtom import _TTLCache
        cache = _TTLCache()
        assert cache.get("missing") is None

    def test_set_and_get(self):
        from backend.services.tomtom import _TTLCache
        cache = _TTLCache()
        cache.set("k1", {"value": 42}, ttl=10.0)
        assert cache.get("k1") == {"value": 42}

    def test_expired_entry_returns_none(self):
        from backend.services.tomtom import _TTLCache
        cache = _TTLCache()
        cache.set("k_expire", "data", ttl=0.001)
        time.sleep(0.01)
        assert cache.get("k_expire") is None

    def test_request_count_increments(self):
        from backend.services.tomtom import _TTLCache
        cache = _TTLCache()
        initial = cache.request_count
        cache.set("x", 1, ttl=5.0)
        cache.increment_request_count()
        assert cache.request_count == initial + 2


# ---------------------------------------------------------------------------
# Tests: Helper functions
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_speed_to_status_free(self):
        from backend.services.tomtom import _speed_to_status
        assert _speed_to_status(55, 60) == "Free Flow"

    def test_speed_to_status_moderate(self):
        from backend.services.tomtom import _speed_to_status
        assert _speed_to_status(35, 60) == "Moderate"

    def test_speed_to_status_congested(self):
        from backend.services.tomtom import _speed_to_status
        assert _speed_to_status(20, 60) == "Congested"

    def test_speed_to_status_severe(self):
        from backend.services.tomtom import _speed_to_status
        assert _speed_to_status(8, 60) == "Severe"

    def test_speed_to_status_zero_free_flow_uses_default(self):
        from backend.services.tomtom import _speed_to_status
        # Should not divide by zero
        result = _speed_to_status(50, 0)
        assert result in ("Free Flow", "Moderate", "Congested", "Severe")

    def test_los_from_delay_a(self):
        from backend.services.tomtom import _los_from_delay
        assert _los_from_delay(5) == "A"

    def test_los_from_delay_f(self):
        from backend.services.tomtom import _los_from_delay
        assert _los_from_delay(100) == "F"

    def test_los_to_status_mapping(self):
        from backend.services.tomtom import _los_to_status
        assert _los_to_status("F") == "High Delay"
        assert _los_to_status("A") == "Good"
        assert _los_to_status("D") == "Moderate"

    def test_speed_to_geojson_status(self):
        from backend.services.tomtom import _speed_to_geojson_status
        assert _speed_to_geojson_status(60) == "free"
        assert _speed_to_geojson_status(40) == "moderate"
        assert _speed_to_geojson_status(20) == "congested"
        assert _speed_to_geojson_status(10) == "severe"


# ---------------------------------------------------------------------------
# Tests: fetch_flow_segment (live mode, mocked HTTP)
# ---------------------------------------------------------------------------

class TestFetchFlowSegment:
    @pytest.mark.asyncio
    async def test_returns_flow_data(self):
        from backend.services.tomtom import fetch_flow_segment, _cache

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_flow_response(25.0, 60.0)

        with patch("backend.services.tomtom._make_client") as mock_client_factory:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_factory.return_value = mock_client

            # Clear cache to force a live call
            _cache._store.pop("flow:test-corridor", None)

            result = await fetch_flow_segment(
                point=(78.38, 17.45),
                corridor_id="test-corridor",
                corridor_name="Test Corridor",
            )

        assert result.current_speed == 25.0
        assert result.free_flow_speed == 60.0
        assert result.road_closure is False
        assert result.confidence == 0.95
        # congestion_ratio = 1 - 25/60 ≈ 0.583
        assert 0.58 <= result.congestion_ratio <= 0.59
        assert result.status == "Congested"
        assert result.source == "TOMTOM_LIVE"

    @pytest.mark.asyncio
    async def test_403_raises_runtime_error(self):
        from backend.services.tomtom import fetch_flow_segment, _cache

        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch("backend.services.tomtom._make_client") as mock_client_factory:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_factory.return_value = mock_client

            _cache._store.pop("flow:test-403", None)

            with pytest.raises(RuntimeError, match="403"):
                await fetch_flow_segment(
                    point=(78.38, 17.45),
                    corridor_id="test-403",
                    corridor_name="Test 403",
                )

    @pytest.mark.asyncio
    async def test_429_raises_runtime_error(self):
        from backend.services.tomtom import fetch_flow_segment, _cache

        mock_response = MagicMock()
        mock_response.status_code = 429

        with patch("backend.services.tomtom._make_client") as mock_client_factory:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_factory.return_value = mock_client

            _cache._store.pop("flow:test-429", None)

            with pytest.raises(RuntimeError, match="429"):
                await fetch_flow_segment(
                    point=(78.38, 17.45),
                    corridor_id="test-429",
                    corridor_name="Test 429",
                )

    @pytest.mark.asyncio
    async def test_cache_hit_skips_http(self):
        from backend.services.tomtom import fetch_flow_segment, FlowSegmentData, _cache

        cached_data = FlowSegmentData(
            corridor_id="cached-corridor",
            corridor_name="Cached",
            current_speed=40.0,
            free_flow_speed=60.0,
            current_travel_time=100,
            free_flow_travel_time=80,
            congestion_ratio=0.333,
            road_closure=False,
            confidence=0.9,
            delay_seconds=20,
            status="Moderate",
            source="TOMTOM_LIVE",
        )
        _cache.set("flow:cached-corridor", cached_data, ttl=60.0)

        with patch("backend.services.tomtom._make_client") as mock_client_factory:
            result = await fetch_flow_segment(
                point=(78.38, 17.45),
                corridor_id="cached-corridor",
                corridor_name="Cached",
            )
            mock_client_factory.assert_not_called()

        assert result.current_speed == 40.0


# ---------------------------------------------------------------------------
# Tests: fetch_incidents (live mode, mocked HTTP)
# ---------------------------------------------------------------------------

class TestFetchIncidents:
    @pytest.mark.asyncio
    async def test_returns_geojson_feature_collection(self):
        from backend.services.tomtom import fetch_incidents, _cache

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_incidents_response(3)

        with patch("backend.services.tomtom._make_client") as mock_client_factory:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_factory.return_value = mock_client

            _cache._store.pop("incidents:hyderabad", None)

            result = await fetch_incidents()

        assert result.type == "FeatureCollection"
        assert len(result.features) == 3
        assert result.source == "TOMTOM_LIVE"

        # Verify incident properties are normalised
        f0 = result.features[0]
        assert f0.properties["type"] == "Accident"   # category 1
        assert f0.properties["severity"] == "High Impact"  # magnitude 3

    @pytest.mark.asyncio
    async def test_empty_incidents_returns_empty_collection(self):
        from backend.services.tomtom import fetch_incidents, _cache

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"incidents": []}

        with patch("backend.services.tomtom._make_client") as mock_client_factory:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_factory.return_value = mock_client

            _cache._store.pop("incidents:hyderabad", None)

            result = await fetch_incidents()

        assert len(result.features) == 0


# ---------------------------------------------------------------------------
# Tests: DEMO mode
# ---------------------------------------------------------------------------

class TestDemoMode:
    @pytest.mark.asyncio
    async def test_demo_flow_has_demo_source(self):
        import backend.services.tomtom as svc
        orig = svc.TRAFFIC_MODE
        svc.TRAFFIC_MODE = "demo"
        try:
            result = await svc.fetch_flow_segment(
                point=(78.38, 17.45),
                corridor_id="demo-test",
                corridor_name="Demo",
            )
            assert result.source == "DEMO_SIMULATED"
        finally:
            svc.TRAFFIC_MODE = orig

    @pytest.mark.asyncio
    async def test_demo_incidents_has_demo_source(self):
        import backend.services.tomtom as svc
        orig = svc.TRAFFIC_MODE
        svc.TRAFFIC_MODE = "demo"
        try:
            result = await svc.fetch_incidents()
            assert result.source == "DEMO_SIMULATED"
        finally:
            svc.TRAFFIC_MODE = orig

    @pytest.mark.asyncio
    async def test_demo_overview_has_demo_source(self):
        import backend.services.tomtom as svc
        orig = svc.TRAFFIC_MODE
        svc.TRAFFIC_MODE = "demo"
        try:
            result = await svc.fetch_traffic_overview()
            assert result.source == "DEMO_SIMULATED"
        finally:
            svc.TRAFFIC_MODE = orig


# ---------------------------------------------------------------------------
# Tests: get_usage
# ---------------------------------------------------------------------------

class TestGetUsage:
    def test_returns_usage_response(self):
        from backend.services.tomtom import get_usage
        result = get_usage()
        assert hasattr(result, "total_api_requests")
        assert hasattr(result, "mode")
        assert result.mode in ("live", "demo")


# ---------------------------------------------------------------------------
# Tests: proxy_tile
# ---------------------------------------------------------------------------

class TestProxyTile:
    @pytest.mark.asyncio
    async def test_basic_tile_proxied(self):
        from backend.services.tomtom import proxy_tile, _cache

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"PNG_BINARY_DATA"

        with patch("backend.services.tomtom._make_client") as mock_client_factory:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_factory.return_value = mock_client

            cache_key = "tile:basic:10:100:200"
            _cache._store.pop(cache_key, None)

            result = await proxy_tile("basic", 10, 100, 200)

        assert result == b"PNG_BINARY_DATA"

    @pytest.mark.asyncio
    async def test_unknown_layer_raises_value_error(self):
        from backend.services.tomtom import proxy_tile
        with pytest.raises(ValueError, match="Unknown tile layer"):
            await proxy_tile("unknown_layer", 10, 100, 200)

    @pytest.mark.asyncio
    async def test_tile_cached_after_fetch(self):
        from backend.services.tomtom import proxy_tile, _cache

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"CACHED_TILE"

        cache_key = "tile:flow:11:50:80"
        _cache._store.pop(cache_key, None)

        with patch("backend.services.tomtom._make_client") as mock_client_factory:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_factory.return_value = mock_client

            await proxy_tile("flow", 11, 50, 80)
            # Second call — should hit cache, not make HTTP call
            result = await proxy_tile("flow", 11, 50, 80)

        assert result == b"CACHED_TILE"
        # HTTP was called only once
        assert mock_client.get.call_count == 1
