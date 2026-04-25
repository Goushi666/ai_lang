"""车辆与机械臂控制 Tool：供具身智能对话模式调用。"""

from __future__ import annotations

from typing import Any

from app.services.vehicle_service import VehicleService

from .base import BaseTool, ToolResult


class ControlArmJoints(BaseTool):
    """控制机械臂关节角度。"""

    name = "control_arm_joints"
    description = (
        "控制机械臂关节角度。可同时设置 1~6 个关节（joint_0 到 joint_5），"
        "每个关节角度范围 0~180°，未指定的关节保持不变。"
        "复位姿态参考：[110, 180, 170, 150, 90, 90]。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "joint_0_angle": {
                "type": "integer",
                "minimum": 0,
                "maximum": 180,
                "description": "关节0（底座旋转）目标角度",
            },
            "joint_1_angle": {
                "type": "integer",
                "minimum": 0,
                "maximum": 180,
                "description": "关节1 目标角度",
            },
            "joint_2_angle": {
                "type": "integer",
                "minimum": 0,
                "maximum": 180,
                "description": "关节2 目标角度",
            },
            "joint_3_angle": {
                "type": "integer",
                "minimum": 0,
                "maximum": 180,
                "description": "关节3 目标角度",
            },
            "joint_4_angle": {
                "type": "integer",
                "minimum": 0,
                "maximum": 180,
                "description": "关节4 目标角度",
            },
            "joint_5_angle": {
                "type": "integer",
                "minimum": 0,
                "maximum": 180,
                "description": "关节5（末端执行器）目标角度",
            },
            "speed": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "转动速度（0~100），默认 50",
            },
        },
        "required": [],
    }

    def __init__(self, vehicle_service: VehicleService):
        self._svc = vehicle_service

    async def execute(self, **kwargs: Any) -> ToolResult:
        angle_keys = [f"joint_{i}_angle" for i in range(6)]
        angles = {k: kwargs[k] for k in angle_keys if k in kwargs and kwargs[k] is not None}
        if not angles:
            return ToolResult(error="至少需要指定一个关节角度")
        speed = kwargs.get("speed")
        try:
            await self._svc.send_arm_joints_mqtt(**angles, speed=speed)
        except Exception as e:
            return ToolResult(error=f"机械臂控制失败: {e}")
        sent = [int(k.split("_")[1]) for k in angles]
        return ToolResult(data={
            "ok": True,
            "joints_sent": sent,
            "angles": {f"J{k.split('_')[1]}": v for k, v in angles.items()},
            "speed": speed if speed is not None else 50,
        })


class ControlVehicle(BaseTool):
    """控制巡检车移动。"""

    name = "control_vehicle"
    description = (
        "控制巡检车移动方向。action 可选：forward（前进）、backward（后退）、"
        "left（左转）、right（右转）、stop（停止）。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["forward", "backward", "left", "right", "stop"],
                "description": "移动方向",
            },
            "speed": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "行驶速度（0~100），默认 50",
            },
            "duration": {
                "type": "integer",
                "minimum": 0,
                "description": "持续时间（秒），0 表示持续到下一条指令",
            },
        },
        "required": ["action"],
    }

    def __init__(self, vehicle_service: VehicleService):
        self._svc = vehicle_service

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action", "")
        if action not in ("forward", "backward", "left", "right", "stop"):
            return ToolResult(error=f"无效动作: {action}")
        speed = kwargs.get("speed", 50)
        duration = kwargs.get("duration", 0)
        try:
            await self._svc.send_control(action=action, speed=speed, duration=duration)
        except Exception as e:
            return ToolResult(error=f"车辆控制失败: {e}")
        return ToolResult(data={"ok": True, "action": action, "speed": speed})


class GetVehicleStatus(BaseTool):
    """获取巡检车当前状态。"""

    name = "get_vehicle_status"
    description = "获取巡检车当前状态，包括连接状态、运行模式、行驶策略、速度等。"
    parameters = {"type": "object", "properties": {}, "required": []}

    def __init__(self, vehicle_service: VehicleService):
        self._svc = vehicle_service

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            s = await self._svc.get_status()
        except Exception as e:
            return ToolResult(error=f"获取状态失败: {e}")
        return ToolResult(data={
            "mode": s.mode,
            "drive_mode": s.drive_mode,
            "speed": s.speed,
            "left_speed": s.left_speed,
            "right_speed": s.right_speed,
            "connected": s.connected,
            "timestamp": s.timestamp.isoformat() if s.timestamp else None,
        })
