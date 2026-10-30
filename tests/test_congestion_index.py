import asyncio
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.congestion_service import (
    CongestionDB,
    CongestionService,
    get_level,
)


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_congestion.db"
    return CongestionDB(db_path=db_file)


class TestCongestionFormula:
    def test_clamp_normal_flow(self, temp_db):
        async def _test():
            service = CongestionService(db=temp_db)
            sem = asyncio.Semaphore(5)

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "flowSegmentData": {
                    "currentSpeed": 30,
                    "freeFlowSpeed": 60,
                    "confidence": 0.9,
                    "roadClosure": False,
                }
            }
            client = AsyncMock()
            client.get.return_value = mock_resp

            val = await service.fetch_point_congestion(client, sem, {"lat": 17.4, "lon": 78.4}, "key")
            assert val == pytest.approx(0.5)

        asyncio.run(_test())

    def test_clamp_overspeed_clamps_to_zero(self, temp_db):
        async def _test():
            service = CongestionService(db=temp_db)
            sem = asyncio.Semaphore(5)

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "flowSegmentData": {
                    "currentSpeed": 70,
                    "freeFlowSpeed": 60,
                    "confidence": 0.9,
                    "roadClosure": False,
                }
            }
            client = AsyncMock()
            client.get.return_value = mock_resp

            val = await service.fetch_point_congestion(client, sem, {"lat": 17.4, "lon": 78.4}, "key")
            assert val == 0.0

        asyncio.run(_test())

    def test_road_closure_gives_1_0(self, temp_db):
        async def _test():
            service = CongestionService(db=temp_db)
            sem = asyncio.Semaphore(5)

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "flowSegmentData": {
                    "roadClosure": True,
                    "currentSpeed": 0,
                    "freeFlowSpeed": 50,
                    "confidence": 0.5,
                }
            }
            client = AsyncMock()
            client.get.return_value = mock_resp

            val = await service.fetch_point_congestion(client, sem, {"lat": 17.4, "lon": 78.4}, "key")
            assert val == 1.0

        asyncio.run(_test())

    def test_low_confidence_discard(self, temp_db):
        async def _test():
            service = CongestionService(db=temp_db)
            sem = asyncio.Semaphore(5)

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "flowSegmentData": {
                    "currentSpeed": 30,
                    "freeFlowSpeed": 60,
                    "confidence": 0.59,
                    "roadClosure": False,
                }
            }
            client = AsyncMock()
            client.get.return_value = mock_resp

            val = await service.fetch_point_congestion(client, sem, {"lat": 17.4, "lon": 78.4}, "key")
            assert val is None

        asyncio.run(_test())

    def test_invalid_free_flow_speed_discard(self, temp_db):
        async def _test():
            service = CongestionService(db=temp_db)
            sem = asyncio.Semaphore(5)

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "flowSegmentData": {
                    "currentSpeed": 30,
                    "freeFlowSpeed": 0,
                    "confidence": 0.95,
                    "roadClosure": False,
                }
            }
            client = AsyncMock()
            client.get.return_value = mock_resp

            val = await service.fetch_point_congestion(client, sem, {"lat": 17.4, "lon": 78.4}, "key")
            assert val is None

        asyncio.run(_test())


class TestValidityRule:
    def test_under_60_percent_validity_marks_stale_or_null(self, temp_db):
        async def _test():
            service = CongestionService(db=temp_db)
            service.points = [{"lat": 17.0, "lon": 78.0, "name": f"P{i}"} for i in range(10)]

            with patch.object(service, "_get_api_key", return_value="valid_key"):
                readings = [0.2, 0.3, 0.4, 0.5, 0.6, None, None, None, None, None] * 2
                with patch.object(service, "fetch_point_congestion", side_effect=readings):
                    res = await service.poll_cycle()
                    assert res["status"] == "stale"
                    assert res["value_pct"] is None

                    service._latest_result["value_pct"] = 28.5
                    service._latest_result["status"] = "live"

                    res2 = await service.poll_cycle()
                    assert res2["status"] == "stale"
                    assert res2["value_pct"] == 28.5

        asyncio.run(_test())



class TestBaselineWindowDelta:
    def test_baseline_calculation_in_window(self, temp_db):
        now = datetime.now(timezone.utc)
        target_24h_ago = now - timedelta(hours=24)

        ts1 = (target_24h_ago - timedelta(minutes=10)).isoformat()
        temp_db.insert_snapshot(ts1, 30.0, 20, 21)

        ts2 = (target_24h_ago + timedelta(minutes=15)).isoformat()
        temp_db.insert_snapshot(ts2, 40.0, 20, 21)

        ts3 = (target_24h_ago - timedelta(minutes=45)).isoformat()
        temp_db.insert_snapshot(ts3, 90.0, 20, 21)

        baseline, available = temp_db.get_baseline_for(now)
        assert available is True
        assert baseline == 35.0

    def test_no_baseline_snapshots(self, temp_db):
        now = datetime.now(timezone.utc)
        baseline, available = temp_db.get_baseline_for(now)
        assert available is False
        assert baseline is None


class TestLevelThresholds:
    def test_level_bins(self):
        assert get_level(None) is None
        assert get_level(14.9) == "light"
        assert get_level(15.0) == "moderate"
        assert get_level(29.9) == "moderate"
        assert get_level(30.0) == "heavy"
        assert get_level(49.9) == "heavy"
        assert get_level(50.0) == "severe"
        assert get_level(85.2) == "severe"


class TestQuotaGuardAndNoKey:
    def test_startup_quota_guard_warning(self, temp_db):
        service = CongestionService(db=temp_db)
        service.points = [{"lat": 17.0, "lon": 78.0} for _ in range(100)]
        service.poll_interval = 60
        service.daily_quota = 2500

        with patch("backend.services.congestion_service.logger.warning") as mock_warn:
            service.startup_guard()
            mock_warn.assert_called_once()
            assert "STARTUP QUOTA GUARD" in mock_warn.call_args[0][0]

    def test_no_key_unavailable_path(self, temp_db):
        async def _test():
            service = CongestionService(db=temp_db)
            with patch.object(service, "_get_api_key", return_value=""):
                res = await service.poll_cycle()
                assert res["status"] == "unavailable"
                assert res["value_pct"] is None

                current = service.get_current_metrics()
                assert current["status"] == "unavailable"
                assert current["value_pct"] is None

        asyncio.run(_test())
