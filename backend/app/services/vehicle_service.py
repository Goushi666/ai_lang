import json
import logging

from app.core.config import settings
from app.core.mqtt import mqtt_client
from app.repositories.vehicle_repo import VehicleRepository
from app.schemas.vehicle import VehicleStatusResponse
from app.websocket.manager import websocket_manager

logger = logging.getLogger(__name__)


class VehicleService:
    """
    车辆业务服务（Service 层）。

    MVP：
    - send_control：写入（内存）控制结果 → 向 MQTT `car/control` 发布 JSON（与手册一致，QoS 1）→ 广播 `vehicle_status`
    - send_gimbal_mqtt：向 `arm/control` 发布 joint 6、7（云台），QoS 1
    - get_status：读取当前车辆状态
    """

    def __init__(self, repo: VehicleRepository) -> None:
        self._repo = repo

    async def get_status(self) -> VehicleStatusResponse:
        return await self._repo.get_status()

    async def send_control(self, action: str, speed: int, duration: int = 0) -> None:
        await self._repo.send_control(action=action, speed=speed)

        car_topic = (settings.MQTT_TOPIC_CAR_CONTROL or "").strip()
        if settings.MQTT_ENABLED and car_topic:
            payload = json.dumps(
                {"action": action, "speed": int(speed), "duration": int(duration)},
                separators=(",", ":"),
            )
            try:
                await mqtt_client.publish(car_topic, payload, qos=1)
                logger.info("MQTT car/control published action=%s speed=%s", action, speed)
            except Exception:
                logger.exception("MQTT 发布小车控制失败 topic=%s", car_topic)

        # 推送车辆状态给前端（MVP：直接广播更新后的状态）
        status: VehicleStatusResponse = await self._repo.get_status()
        ts_ms = int(status.timestamp.timestamp() * 1000)
        await websocket_manager.broadcast(
            {
                "type": "vehicle_status",
                "payload": {
                    "mode": status.mode,
                    "speed": status.speed,
                    "leftSpeed": status.left_speed,
                    "rightSpeed": status.right_speed,
                    "connected": status.connected,
                    "timestamp": ts_ms,
                },
                "timestamp": ts_ms,
            }
        )

    async def send_gimbal_mqtt(self, joint_6_angle: int, joint_7_angle: int, speed: int) -> None:
        """手册 3.4：`{"joint","angle","speed"}`；云台仅下发 6、7 号关节各一条消息（QoS 1）。"""
        arm_topic = (settings.MQTT_TOPIC_ARM_CONTROL or "").strip()
        for joint, angle in ((6, joint_6_angle), (7, joint_7_angle)):
            payload = json.dumps(
                {"joint": joint, "angle": int(angle), "speed": int(speed)},
                separators=(",", ":"),
            )
            await mqtt_client.publish(arm_topic, payload, qos=1)
        logger.info(
            "MQTT arm/control published joints 6,7 angles=%s,%s speed=%s topic=%s",
            joint_6_angle,
            joint_7_angle,
            speed,
            arm_topic,
        )

