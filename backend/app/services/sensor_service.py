from datetime import datetime
from typing import TYPE_CHECKING, Any, List, Optional

from app.repositories.sensor_repo import SensorRepository
from app.schemas.sensor import SensorDataResponse
from app.websocket.manager import websocket_manager

if TYPE_CHECKING:
    from app.services.alarm_service import AlarmService


class SensorService:
    """
    传感器业务服务（Service 层）。

    职责边界：
    - 从 Repository 获取数据（REST 历史/最新/导出）
    - 在 MVP 中产生模拟数据并通过 WebSocket 推送（push_sensor_data）
    """

    def __init__(self, repo: SensorRepository, alarm_service: Optional["AlarmService"] = None) -> None:
        self._repo = repo
        self._alarm_service = alarm_service

    async def get_latest(self) -> Optional[SensorDataResponse]:
        return await self._repo.get_latest()

    async def get_history(self, start_time: datetime, end_time: datetime) -> List[SensorDataResponse]:
        return await self._repo.get_history(start_time, end_time)

    async def export_csv(self, start_time: datetime, end_time: datetime) -> str:
        return await self._repo.export_csv(start_time, end_time)

    async def push_sensor_data(self) -> None:
        """
        MVP：产生一条传感器数据并通过 WebSocket 广播给前端。

        推送消息格式（与 Web 端一致）：
        {
          "type": "sensor_data",
          "payload": { deviceId, temperature, humidity, light, timestamp },
          "timestamp": <ms>
        }
        """
        data = await self._repo.simulate_tick()
        if data is None:
            return
        await self.broadcast_sensor_record(data)

    async def broadcast_sensor_record(self, data: SensorDataResponse) -> None:
        """将已持久化（内存）的采样按前端协议广播（与 push_sensor_data 的 WebSocket 结构一致）。"""
        ts_ms = int(data.timestamp.timestamp() * 1000)
        await websocket_manager.broadcast(
            {
                "type": "sensor_data",
                "payload": {
                    "deviceId": data.device_id,
                    "temperature": data.temperature,
                    "humidity": data.humidity,
                    "light": data.light,
                    "timestamp": ts_ms,
                },
                "timestamp": ts_ms,
            }
        )
        if self._alarm_service:
            await self._alarm_service.evaluate_sensor_reading(data)

    async def ingest_mqtt_payload_dict(self, data: dict[str, Any]) -> Optional[SensorDataResponse]:
        """
        将 MQTT JSON（已解析为 dict）规范化后写入仓库并广播。

        字段兼容常见别名：deviceId/device_id/deviceName、temp、temperature、hum、humidity、lux、light 等。
        """
        from app.core.mqtt import normalize_sensor_dict

        normalized = normalize_sensor_dict(data)
        if not normalized:
            return None

        rec = await self._repo.ingest_reading(
            device_id=normalized["device_id"],
            temperature=normalized["temperature"],
            humidity=normalized["humidity"],
            light=normalized["light"],
            timestamp=normalized["timestamp"],
        )
        await self.broadcast_sensor_record(rec)
        return rec

