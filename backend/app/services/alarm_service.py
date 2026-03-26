from datetime import datetime
from typing import List

from app.repositories.alarm_repo import AlarmRepository
from app.schemas.alarm import AlarmConfig, AlarmResponse
from app.websocket.manager import websocket_manager


class AlarmService:
    """
    告警业务服务（Service 层）。

    职责边界：
    - REST：告警历史、标记已读、告警配置
    - WebSocket：在 MVP/设备触发后推送告警消息（push_alarm）
    """

    def __init__(self, repo: AlarmRepository) -> None:
        self._repo = repo

    async def get_history(self, start_time: datetime, end_time: datetime) -> List[AlarmResponse]:
        return await self._repo.get_history(start_time, end_time)

    async def mark_read(self, alarm_id: str) -> bool:
        return await self._repo.mark_read(alarm_id)

    async def get_config(self) -> AlarmConfig:
        return await self._repo.get_config()

    async def update_config(self, config: AlarmConfig) -> None:
        await self._repo.update_config(config)

    async def push_alarm(self) -> None:
        """
        MVP：模拟生成告警并推送给前端。
        """
        alarm: AlarmResponse = await self._repo.simulate_alarm_trigger()
        ts_ms = int(alarm.timestamp.timestamp() * 1000)

        await websocket_manager.broadcast(
            {
                "type": "alarm",
                "payload": {
                    "id": alarm.id,
                    "level": alarm.level,
                    "message": alarm.message,
                    "value": alarm.value,
                    "threshold": alarm.threshold,
                    "read": alarm.read,
                    "timestamp": ts_ms,
                },
                "timestamp": ts_ms,
            }
        )

