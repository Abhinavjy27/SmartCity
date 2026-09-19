import asyncio
import time
from datetime import datetime, timezone
from backend.agents.pollution_agent.main import (
    get_current, get_aqi_summary, get_hotspots, get_alerts,
    get_daily_forecast, get_7day_forecast, get_info
)
import backend.agents.pollution_agent.data_provider as dp

async def call_with_timeout_and_retry(func, *args, **kwargs):
    timeout = 8.0
    for attempt in range(2):
        try:
            # func could be async or sync; in our case FastAPI endpoint functions might be sync or async
            # Our endpoint functions are mostly defined as `async def` in main.py, but some are sync.
            # get_current, get_aqi_summary, get_hotspots etc are sync or async? 
            # In FastAPI, they can be either. We use asyncio.wait_for
            if asyncio.iscoroutinefunction(func):
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            else:
                # Run sync func in thread pool to allow timeout
                loop = asyncio.get_event_loop()
                return await asyncio.wait_for(loop.run_in_executor(None, lambda: func(*args, **kwargs)), timeout=timeout)
        except Exception as e:
            if attempt == 1:
                return {"error": str(e)}
            await asyncio.sleep(1)

def format_tool_response(name, data, data_type):
    now = datetime.now(timezone.utc).isoformat()
    resp = {
        "tool": name,
        "timestamp": now,
        "data_type": data_type,
        "data": data,
        "error": None,
        "data_mode": "historical",
        "is_live": False,
        "provider_name": "PlaceholderLivePollutionProvider"
    }
    
    if "error" in data:
        resp["error"] = data["error"]
        resp["data"] = None
        
    if data_type == "observed":
        resp["observation_timestamp"] = "2025-12-31T23:45:00Z"
    elif data_type == "predicted":
        resp["origin_date"] = "2025-12-31"
        
    return resp

class PollutionTools:
    @staticmethod
    async def get_latest_readings():
        res = await call_with_timeout_and_retry(get_current)
        return format_tool_response("get_latest_readings", res, "observed")

    @staticmethod
    async def get_aqi_summary_tool():
        res = await call_with_timeout_and_retry(get_aqi_summary)
        return format_tool_response("get_aqi_summary", res, "observed")
        
    @staticmethod
    async def get_hotspots_tool():
        res = await call_with_timeout_and_retry(get_hotspots)
        return format_tool_response("get_hotspots", res, "observed")
        
    @staticmethod
    async def get_alerts_tool():
        res = await call_with_timeout_and_retry(get_alerts)
        return format_tool_response("get_alerts", res, "observed")
        
    @staticmethod
    async def get_daily_forecast_tool():
        res = await call_with_timeout_and_retry(get_daily_forecast)
        return format_tool_response("get_daily_forecast", res, "predicted")
        
    @staticmethod
    async def get_7day_forecast_tool():
        res = await call_with_timeout_and_retry(get_7day_forecast)
        return format_tool_response("get_7day_forecast", res, "predicted")
        
    @staticmethod
    async def list_stations_tool():
        res = await call_with_timeout_and_retry(get_info)
        return format_tool_response("list_stations", res, "observed")
