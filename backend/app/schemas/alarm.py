from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AlarmResponse(BaseModel):
    """
    告警数据响应模型。

    Web 前端期望字段（在 WebSocket 中也会出现同名/同义字段）：
    - id / type / level / message
    - value / threshold
    - timestamp / read
    """

    id: str
    type: str
    level: str  # low, medium, high, urgent
    message: str
    value: float
    threshold: float
    timestamp: datetime
    read: bool


class AlarmConfig(BaseModel):
    """
    告警配置（阈值）。

    MVP：先用统一结构存储 temperature/humidity/light 阈值。
    """

    temperature_threshold: float
    humidity_threshold: float
    light_threshold: float

