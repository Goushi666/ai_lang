from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_serializer


class SensorDataResponse(BaseModel):
    """
    传感器数据响应模型（给 REST + WebSocket 使用的字段集合）。
    """

    device_id: str
    temperature: float
    humidity: float
    light: float
    timestamp: datetime

    @field_serializer("timestamp", when_used="json")
    def _json_timestamp_utc_z(self, v: datetime) -> str:
        from app.core.timeutil import format_instant_rfc3339_utc_z

        return format_instant_rfc3339_utc_z(v)


class SensorHistoryQuery(BaseModel):
    """历史查询的参数模型（起止时间）"""
    start_time: datetime
    end_time: datetime

