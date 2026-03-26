from datetime import datetime
from typing import List

from app.repositories.sensor_repo import SensorRepository
from app.schemas.sensor import SensorDataResponse
from app.websocket.manager import websocket_manager


class SensorService:
    """
    传感器业务服务（Service 层）。

    职责边界：
    - 从 Repository 获取数据（REST 历史/最新/导出）
    - 在 MVP 中产生模拟数据并通过 WebSocket 推送（push_sensor_data）
    """

    def __init__(self, repo: SensorRepository) -> None:
        self._repo = repo

    async def get_latest(self) -> SensorDataResponse:
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
        data: SensorDataResponse = await self._repo.simulate_tick()
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

