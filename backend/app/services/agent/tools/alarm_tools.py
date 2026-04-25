"""告警 Tool：封装 AlarmRepository / AlarmService 的原子操作。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.repositories.alarm_repo import AlarmRepository

from .base import BaseTool, ToolResult


class GetAlarmsHistory(BaseTool):
    """查询历史告警记录。"""

    name = "get_alarms_history"
    description = "查询指定时间范围内的告警历史记录，支持按告警级别过滤。"
    parameters = {
        "type": "object",
        "properties": {
            "start_time": {
                "type": "string",
                "description": "起始时间，ISO 8601 格式（可选，默认最近 24 小时）",
            },
            "end_time": {
                "type": "string",
                "description": "结束时间，ISO 8601 格式（可选，默认当前）",
            },
            "level": {
                "type": "string",
                "description": "告警级别过滤：urgent / high / medium（可选）",
            },
            "limit": {
                "type": "integer",
                "description": "最大返回条数（默认 200，上限 500）；结果含 total 为命中总数，records 为本页。",
            },
        },
        "required": [],
    }

    def __init__(self, alarm_repo: AlarmRepository):
        self._repo = alarm_repo

    async def execute(self, **kwargs: Any) -> ToolResult:
        now = datetime.now(timezone.utc)
        start_str = kwargs.get("start_time")
        end_str = kwargs.get("end_time")
        level = kwargs.get("level")
        raw_limit = kwargs.get("limit", 200)
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            limit = 200
        limit = max(1, min(limit, 500))

        try:
            start = (
                datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                if start_str
                else now - timedelta(hours=24)
            )
            end = (
                datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                if end_str
                else now
            )
        except (ValueError, AttributeError) as e:
            return ToolResult(error=f"时间格式错误: {e}")

        total, alarms = await self._repo.get_history(
            start, end, level=level, page=1, page_size=limit,
        )

        return ToolResult(data={
            "total": total,
            "records": [
                {
                    "id": a.id,
                    "type": a.type,
                    "level": a.level,
                    "message": a.message,
                    "value": a.value,
                    "threshold": a.threshold,
                    "read": a.read,
                    "timestamp": a.timestamp.isoformat(),
                }
                for a in alarms
            ],
        })


class GetAlarmConfig(BaseTool):
    """获取当前告警阈值配置。"""

    name = "get_alarm_config"
    description = "获取当前告警阈值配置（温度、湿度、光照的告警阈值）。"
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def __init__(self, alarm_repo: AlarmRepository):
        self._repo = alarm_repo

    async def execute(self, **kwargs: Any) -> ToolResult:
        config = await self._repo.get_config()
        return ToolResult(data={
            "temperature_threshold": config.temperature_threshold,
            "humidity_threshold": config.humidity_threshold,
            "light_threshold": config.light_threshold,
        })
