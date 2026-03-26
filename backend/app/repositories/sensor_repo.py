from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import random
from typing import List

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

        # 初始化一些模拟数据，方便前端联调
        now = datetime.utcnow()
        for i in range(30):
            ts = now - timedelta(minutes=5 * i)
            self._data.append(
                _SensorSnapshot(
                    device_id="dev_001",
                    temperature=25.0 + (i % 5) * 0.2,
                    humidity=60.0 + (i % 7) * 0.3,
                    light=300.0 + (i % 9) * 10.0,
                    timestamp=ts,
                )
            )

    async def get_latest(self) -> SensorDataResponse:
        latest = max(self._data, key=lambda x: x.timestamp)
        return SensorDataResponse(**latest.__dict__)

    async def get_history(self, start_time: datetime, end_time: datetime) -> List[SensorDataResponse]:
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

    async def simulate_tick(self) -> SensorDataResponse:
        """
        MVP：模拟设备产生一条新采样，用于联调 WebSocket 实时推送链路。

        说明：
        - 返回字段与 `schemas/sensor.py` 的 `SensorDataResponse` 对齐
        - 内存列表会截断到最大长度，避免无限增长
        """
        if not self._data:
            # 理论上不会发生（初始化时已填充），兜底即可
            self._data.append(
                _SensorSnapshot(
                    device_id="dev_001",
                    temperature=25.0,
                    humidity=60.0,
                    light=300.0,
                    timestamp=datetime.utcnow(),
                )
            )

        last = max(self._data, key=lambda x: x.timestamp)
        ts = datetime.utcnow()

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

