from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class VehicleStatusResponse(BaseModel):
    """
    车辆状态响应模型（MVP）。

    字段说明：
    - mode：manual/auto
    - speed：总体速度（整数）
    - left_speed/right_speed：左右轮速度
    - connected：连接状态
    """

    mode: Literal["manual", "auto"]
    speed: int
    left_speed: int
    right_speed: int
    connected: bool
    deviation: Optional[float] = None
    correction: Optional[float] = None
    timestamp: datetime


class VehicleControlRequest(BaseModel):
    """
    车辆控制请求模型（由前端 InspectionVehicle.vue 提交）。

    与 MQTT 手册 `car/control` 一致：action、speed、duration（秒，0=持续至 stop）。
    """
    action: Literal["forward", "backward", "left", "right", "stop"]
    speed: int = Field(ge=0, le=100)
    timestamp: int
    duration: int = Field(default=0, ge=0, description="持续时间（秒），0 表示持续执行直到收到 stop")

