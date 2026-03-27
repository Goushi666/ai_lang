from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import random
from typing import List, Optional

from app.schemas.sensor import SensorDataResponse


@dataclass
class _SensorSnapshot:
    device_id: str
    temperature: float
    humidity: float
    light: float
    timestamp: datetime


class SensorRepository:
    """
    MVP 数据仓库：先用内存实现，保持 Service/接口不变，后续再替换 SQLite/MySQL。
    """

    def __init__(self) -> None:
        self._data: List[_SensorSnapshot] = []

    async def get_latest(self) -> Optional[SensorDataResponse]:
        if not self._data:
            return None
        latest = max(self._data, key=lambda x: x.timestamp)
        return SensorDataResponse(**latest.__dict__)

    async def get_history(self, start_time: datetime, end_time: datetime) -> List[SensorDataResponse]:
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        else:
            start_time = start_time.astimezone(timezone.utc)

        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        else:
            end_time = end_time.astimezone(timezone.utc)

        rows = [
            x
            for x in self._data
            if start_time <= x.timestamp <= end_time
        ]
        rows.sort(key=lambda x: x.timestamp)
        return [SensorDataResponse(**x.__dict__) for x in rows]

    async def export_csv(self, start_time: datetime, end_time: datetime) -> str:
        history = await self.get_history(start_time, end_time)
        lines = ["timestamp,device_id,temperature,humidity,light"]
        for row in history:
            lines.append(
                f"{row.timestamp.isoformat()},{row.device_id},{row.temperature},{row.humidity},{row.light}"
            )
        return "\n".join(lines)

    async def simulate_tick(self) -> Optional[SensorDataResponse]:
        """
        MVP：模拟设备产生一条新采样，用于联调 WebSocket 实时推送链路。

        无历史数据时不生成占位值，返回 None（由调用方跳过广播）。
        """
        if not self._data:
            return None

        last = max(self._data, key=lambda x: x.timestamp)
        ts = datetime.now(timezone.utc)

        # 小幅扰动生成新值
        next_temp = round(last.temperature + random.uniform(-0.3, 0.3), 2)
        next_hum = round(last.humidity + random.uniform(-0.5, 0.5), 2)
        next_light = round(last.light + random.uniform(-20.0, 20.0), 2)

        self._data.append(
            _SensorSnapshot(
                device_id=last.device_id,
                temperature=next_temp,
                humidity=next_hum,
                light=next_light,
                timestamp=ts,
            )
        )

        # 避免内存无限增长
        if len(self._data) > 500:
            self._data = self._data[-500:]

        return SensorDataResponse(
            device_id=last.device_id,
            temperature=next_temp,
            humidity=next_hum,
            light=next_light,
            timestamp=ts,
        )

    async def ingest_reading(
        self,
        device_id: str,
        temperature: float,
        humidity: float,
        light: float,
        timestamp: datetime,
    ) -> SensorDataResponse:
        """写入一条来自 MQTT 等外部来源的传感器采样，供 REST latest/history 与 WebSocket 一致。"""
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = timestamp.astimezone(timezone.utc)

        self._data.append(
            _SensorSnapshot(
                device_id=device_id,
                temperature=temperature,
                humidity=humidity,
                light=light,
                timestamp=timestamp,
            )
        )
        if len(self._data) > 500:
            self._data = self._data[-500:]

        return SensorDataResponse(
            device_id=device_id,
            temperature=temperature,
            humidity=humidity,
            light=light,
            timestamp=timestamp,
        )

