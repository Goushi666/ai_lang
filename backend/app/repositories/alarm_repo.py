from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List
import random

from app.schemas.alarm import AlarmConfig, AlarmResponse


@dataclass
class _AlarmRow:
    id: str
    type: str
    level: str
    message: str
    value: float
    threshold: float
    read: bool
    timestamp: datetime


class AlarmRepository:
    """
    告警数据仓库（MVP 内存实现）。

    在接入真实硬件/MQTT 后，这里会：
    - 从数据流中完成告警判定
    - 把告警持久化到数据库
    - 维护告警 read 状态
    """
    def __init__(self) -> None:
        now = datetime.utcnow()
        self._alarms: List[_AlarmRow] = [
            _AlarmRow(
                id=f"alarm_{i:03d}",
                type="temperature",
                level=["low", "medium", "high", "urgent"][i % 4],
                message="MVP 模拟告警（温度相关）",
                value=35.0 + i * 0.2,
                threshold=30.0,
                read=(i % 3 == 0),
                timestamp=now - timedelta(minutes=20 * i),
            )
            for i in range(15)
        ]

        self._config = AlarmConfig(
            temperature_threshold=30.0,
            humidity_threshold=60.0,
            light_threshold=350.0,
        )

        self._config_store: Dict[str, AlarmConfig] = {"default": self._config}

    async def get_history(self, start_time: datetime, end_time: datetime) -> List[AlarmResponse]:
        rows = [a for a in self._alarms if start_time <= a.timestamp <= end_time]
        rows.sort(key=lambda x: x.timestamp)
        return [
            AlarmResponse(
                id=r.id,
                type=r.type,
                level=r.level,
                message=r.message,
                value=r.value,
                threshold=r.threshold,
                read=r.read,
                timestamp=r.timestamp,
            )
            for r in rows
        ]

    async def mark_read(self, alarm_id: str) -> bool:
        for row in self._alarms:
            if row.id == alarm_id:
                row.read = True
                return True
        return False

    async def get_config(self) -> AlarmConfig:
        return self._config_store["default"]

    async def update_config(self, config: AlarmConfig) -> None:
        self._config_store["default"] = config.model_copy(deep=True)

    async def simulate_alarm_trigger(self) -> AlarmResponse:
        """
        MVP：模拟告警触发，用于联调 WebSocket 推送链路。

        当前实现：
        - 读取 `AlarmConfig.temperature_threshold` 作为阈值
        - 根据阈值生成一个温度超阈值/临界告警
        """
        config = self._config_store["default"]
        ts = datetime.utcnow()

        # 用温度阈值生成一个“必触发”告警（也可扩展为多类型）
        threshold = float(config.temperature_threshold)
        value = round(threshold + random.uniform(0.5, 5.0), 2)
        level = "high" if value > threshold else "medium"

        next_index = len(self._alarms)
        alarm_id = f"alarm_{next_index:03d}"

        row = _AlarmRow(
            id=alarm_id,
            type="temperature",
            level=level,
            message="温度超过阈值（MVP 模拟）",
            value=value,
            threshold=threshold,
            read=False,
            timestamp=ts,
        )
        self._alarms.append(row)
        if len(self._alarms) > 500:
            self._alarms = self._alarms[-500:]

        return AlarmResponse(
            id=row.id,
            type=row.type,
            level=row.level,
            message=row.message,
            value=row.value,
            threshold=row.threshold,
            read=row.read,
            timestamp=row.timestamp,
        )

