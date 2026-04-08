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


class GimbalControlRequest(BaseModel):
    """
    摄像头云台（MQTT `arm/control`）：仅使用关节 6、7，与手册 JSON 字段一致。
    """

    joint_6_angle: int = Field(ge=0, le=180, description="6 号关节目标角度")
    joint_7_angle: int = Field(ge=0, le=90, description="7 号关节目标角度（超过 90° 易卡舵机）")
    speed: int = Field(default=50, ge=0, le=100, description="转动速度 0~100")


class ArmJointsControlRequest(BaseModel):
    """
    机械臂关节（MQTT `arm/control`）：关节 0~5，与手册 `{"joint","angle","speed"}` 一致。
    """

    joint_0_angle: int = Field(ge=0, le=180, description="0 号关节目标角度")
    joint_1_angle: int = Field(ge=0, le=180, description="1 号关节目标角度")
    joint_2_angle: int = Field(ge=0, le=180, description="2 号关节目标角度")
    joint_3_angle: int = Field(ge=0, le=180, description="3 号关节目标角度")
    joint_4_angle: int = Field(ge=0, le=180, description="4 号关节目标角度")
    joint_5_angle: int = Field(ge=0, le=180, description="5 号关节目标角度")
    speed: int = Field(default=50, ge=0, le=100, description="转动速度 0~100")


class VehicleControlRequest(BaseModel):
    """
    车辆控制请求模型（由前端 InspectionVehicle.vue 提交）。

    与 MQTT 手册 `car/control` 一致：action、speed、duration（秒，0=持续至 stop）。
    """
    action: Literal["forward", "backward", "left", "right", "stop"]
    speed: int = Field(ge=0, le=100)
    timestamp: int
    duration: int = Field(default=0, ge=0, description="持续时间（秒），0 表示持续执行直到收到 stop")

