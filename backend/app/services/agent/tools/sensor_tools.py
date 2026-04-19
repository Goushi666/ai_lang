"""传感器数据 Tool：封装 SensorService / SensorRepository 的原子操作。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.repositories.sensor_repo import SensorRepository
from app.services.sensor_service import SensorService

from .base import BaseTool, ToolResult


class GetSensorLatest(BaseTool):
    """获取最新一条传感器读数。"""

    name = "get_sensor_latest"
    description = "获取最新的传感器读数（温度、湿度、光照），返回最近一条采样数据。"
    parameters = {
        "type": "object",
        "properties": {
            "device_id": {
                "type": "string",
                "description": "设备 ID（可选，不传则返回全局最新）",
            },
        },
        "required": [],
    }

    def __init__(self, sensor_service: SensorService):
        self._service = sensor_service

    async def execute(self, **kwargs: Any) -> ToolResult:
        latest = await self._service.get_latest()
        if latest is None:
            return ToolResult(data={"message": "暂无传感器数据"})
        return ToolResult(data={
            "device_id": latest.device_id,
            "temperature": latest.temperature,
            "humidity": latest.humidity,
            "light": latest.light,
            "timestamp": latest.timestamp.isoformat(),
        })


class GetSensorHistory(BaseTool):
    """查询历史传感器采样数据。"""

    name = "get_sensor_history"
    description = "查询指定时间范围内的传感器历史数据（温度、湿度、光照时序）。"
    parameters = {
        "type": "object",
        "properties": {
            "start_time": {
                "type": "string",
                "description": "起始时间，ISO 8601 格式（如 2024-01-01T00:00:00Z）",
            },
            "end_time": {
                "type": "string",
                "description": "结束时间，ISO 8601 格式",
            },
            "device_id": {
                "type": "string",
                "description": "设备 ID（可选）",
            },
            "limit": {
                "type": "integer",
                "description": "最大返回条数（默认 100）",
            },
        },
        "required": ["start_time", "end_time"],
    }

    def __init__(self, sensor_service: SensorService):
        self._service = sensor_service

    async def execute(self, **kwargs: Any) -> ToolResult:
        start_str = kwargs.get("start_time", "")
        end_str = kwargs.get("end_time", "")
        limit = kwargs.get("limit", 100)

        try:
            start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError) as e:
            return ToolResult(error=f"时间格式错误: {e}")

        history = await self._service.get_history(start, end)
        if limit:
            history = history[:limit]

        return ToolResult(data={
            "count": len(history),
            "records": [
                {
                    "device_id": r.device_id,
                    "temperature": r.temperature,
                    "humidity": r.humidity,
                    "light": r.light,
                    "timestamp": r.timestamp.isoformat(),
                }
                for r in history
            ],
        })
