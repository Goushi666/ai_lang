from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.schemas.vehicle import VehicleStatusResponse


@dataclass
class _VehicleStatus:
    mode: str
    speed: int
    left_speed: int
    right_speed: int
    connected: bool
    deviation: float | None
    correction: float | None
    timestamp: datetime


class VehicleRepository:
    """
    MVP：内存状态仓库。后续可替换 MQTT/设备反馈 + 持久化。
    """

    def __init__(self) -> None:
        self._status = _VehicleStatus(
            mode="manual",
            speed=0,
            left_speed=0,
            right_speed=0,
            connected=True,
            deviation=None,
            correction=None,
            timestamp=datetime.utcnow(),
        )

    async def get_status(self) -> VehicleStatusResponse:
        s = self._status
        return VehicleStatusResponse(
            mode=s.mode,  # type: ignore[arg-type]
            speed=s.speed,
            left_speed=s.left_speed,
            right_speed=s.right_speed,
            connected=s.connected,
            deviation=s.deviation,
            correction=s.correction,
            timestamp=s.timestamp,
        )

    async def send_control(self, action: str, speed: int) -> None:
        """
        MVP：模拟车辆执行（不做真实硬件控制）。

        action 映射到车辆状态：
        - forward/backward：速度正负号
        - left/right：左右轮速度差异
        - stop：速度清零
        """
        now = datetime.utcnow()
        if action in {"forward", "backward", "left", "right", "stop"}:
            if action == "stop":
                self._status.speed = 0
                self._status.left_speed = 0
                self._status.right_speed = 0
            elif action == "forward":
                self._status.speed = speed
                self._status.left_speed = speed
                self._status.right_speed = speed
            elif action == "backward":
                self._status.speed = -speed
                self._status.left_speed = -speed
                self._status.right_speed = -speed
            elif action == "left":
                self._status.speed = speed
                self._status.left_speed = 0
                self._status.right_speed = speed
            elif action == "right":
                self._status.speed = speed
                self._status.left_speed = speed
                self._status.right_speed = 0

        self._status.timestamp = now

