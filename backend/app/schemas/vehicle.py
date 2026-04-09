from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


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
    摄像头云台（MQTT `arm/control`）：关节 6、7；可只传本次变动的项，未传关节不下发 MQTT。
    仅调 speed 时需同时带 joint_6_angle、joint_7_angle（当前角度），以便各发一条带新 speed 的报文。
    """

    joint_6_angle: Optional[int] = Field(default=None, ge=0, le=180, description="6 号关节目标角度")
    joint_7_angle: Optional[int] = Field(default=None, ge=0, le=90, description="7 号关节目标角度（超过 90° 易卡舵机）")
    speed: Optional[int] = Field(default=None, ge=0, le=100, description="转动速度 0~100；缺省时按 50")

    @model_validator(mode="after")
    def _gimbal_some_field(self):
        has6 = self.joint_6_angle is not None
        has7 = self.joint_7_angle is not None
        sp = self.speed is not None
        if not has6 and not has7 and not sp:
            raise ValueError("至少需要 joint_6_angle、joint_7_angle、speed 之一")
        if sp and not has6 and not has7:
            raise ValueError("仅调整 speed 时请同时提供 joint_6_angle 与 joint_7_angle")
        return self


class ArmJointsControlRequest(BaseModel):
    """
    机械臂（MQTT `arm/control`）：关节 0~5；可只传本次拖动的关节。
    仅调 speed 时需带齐 6 个关节角；未传关节不下发对应 MQTT。
    """

    joint_0_angle: Optional[int] = Field(default=None, ge=0, le=180)
    joint_1_angle: Optional[int] = Field(default=None, ge=0, le=180)
    joint_2_angle: Optional[int] = Field(default=None, ge=0, le=180)
    joint_3_angle: Optional[int] = Field(default=None, ge=0, le=180)
    joint_4_angle: Optional[int] = Field(default=None, ge=0, le=180)
    joint_5_angle: Optional[int] = Field(default=None, ge=0, le=180)
    speed: Optional[int] = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def _arm_some_field(self):
        angles = [
            self.joint_0_angle,
            self.joint_1_angle,
            self.joint_2_angle,
            self.joint_3_angle,
            self.joint_4_angle,
            self.joint_5_angle,
        ]
        n = sum(1 for a in angles if a is not None)
        sp = self.speed is not None
        if n == 0 and not sp:
            raise ValueError("至少需要某一关节角度或 speed")
        if sp and n == 0:
            raise ValueError("仅调整 speed 时请同时提供 joint_0_angle～joint_5_angle")
        return self


class VehicleControlRequest(BaseModel):
    """
    车辆控制请求模型（由前端 InspectionVehicle.vue 提交）。

    与 MQTT 手册 `car/control` 一致：action、speed、duration（秒，0=持续至 stop）。
    """
    action: Literal["forward", "backward", "left", "right", "stop"]
    speed: int = Field(ge=0, le=100)
    timestamp: int
    duration: int = Field(default=0, ge=0, description="持续时间（秒），0 表示持续执行直到收到 stop")

