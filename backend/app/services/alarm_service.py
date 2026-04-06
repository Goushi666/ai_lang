from datetime import datetime
from typing import List

from app.repositories.alarm_repo import AlarmRepository
from app.schemas.alarm import AlarmConfig, AlarmResponse
from app.schemas.sensor import SensorDataResponse
from app.websocket.manager import websocket_manager


class AlarmService:
    """
    告警业务服务（Service 层）。

    职责边界：
    - REST：告警历史、标记已读、告警配置
    - WebSocket：在传感器读数超阈（边沿）时推送；同一次采样内多条合并为一条 WS 消息，避免连弹窗。
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

    async def evaluate_sensor_reading(self, data: SensorDataResponse) -> None:
        """根据当前阈值判定温度/湿度/光照是否由正常变为超阈；满足则写入历史并合并广播一次。"""
        cfg = await self._repo.get_config()
        created: List[AlarmResponse] = []
        checks = [
            ("temperature", cfg.temperature_threshold, "温度", "℃", data.temperature),
            ("humidity", cfg.humidity_threshold, "湿度", "%RH", data.humidity),
            ("light", cfg.light_threshold, "光照", "lx", data.light),
        ]
        for metric, threshold, metric_zh, unit, value in checks:
            alarm = await self._repo.try_append_threshold_alarm(
                device_id=data.device_id,
                metric=metric,
                metric_zh=metric_zh,
                unit=unit,
                value=float(value),
                threshold=float(threshold),
            )
            if alarm is not None:
                created.append(alarm)

        if not created:
            return

        ts_ms = max(int(a.timestamp.timestamp() * 1000) for a in created)
        await websocket_manager.broadcast(
            {
                "type": "alarm",
                "payload": {
                    "alarms": [
                        {
                            "id": a.id,
                            "type": a.type,
                            "level": a.level,
                            "message": a.message,
                            "value": a.value,
                            "threshold": a.threshold,
                            "read": a.read,
                            "timestamp": int(a.timestamp.timestamp() * 1000),
                        }
                        for a in created
                    ]
                },
                "timestamp": ts_ms,
            }
        )
