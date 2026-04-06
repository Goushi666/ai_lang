from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


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

    文档前端使用 action + speed + timestamp。
    """
    action: str
    speed: int
    timestamp: int

