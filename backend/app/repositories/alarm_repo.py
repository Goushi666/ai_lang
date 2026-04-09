from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


def _to_utc_aware(dt: datetime) -> datetime:
    """与 FastAPI Query 解析出的带时区时间可比；历史里 naive 一律视为 UTC。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

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


# 高报滞回：需回落到 threshold - hyst 以下才解除「已告警」态，避免在阈值附近抖动反复边沿落库
_ALARM_CLEAR_HYSTERESIS: dict[str, float] = {
    "temperature": 0.6,
    "humidity": 2.0,
    "light": 20.0,
}


def _level_for_excess(value: float, threshold: float) -> str:
    """超阈越明显，级别越高（与前端 urgent/high/medium 一致）。"""
    if threshold <= 0:
        return "high"
    delta = value - threshold
    ratio = delta / threshold if threshold else 0.0
    if delta >= 5 or ratio >= 0.15:
        return "urgent"
    if delta >= 2 or ratio >= 0.05:
        return "high"
    return "medium"


class AlarmRepository:
    """
    告警数据仓库（MVP 内存实现）。

    温度/湿度/光照告警仅在采样**从正常变为超阈**时写入一条（边沿触发），
    持续超阈不重复刷屏；需回落到阈值减滞回量以下才解除告警态，再超阈才再次记录。
    """

    def __init__(self) -> None:
        self._alarms: List[_AlarmRow] = []
        self._metric_alarm_active: Dict[Tuple[str, str], bool] = {}

        self._config = AlarmConfig(
            temperature_threshold=30.0,
            humidity_threshold=60.0,
            light_threshold=350.0,
        )

        self._config_store: dict[str, AlarmConfig] = {"default": self._config}

    async def get_history(
        self,
        start_time: datetime,
        end_time: datetime,
        *,
        metric: Optional[str] = None,
        level: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[int, List[AlarmResponse]]:
        st = _to_utc_aware(start_time)
        et = _to_utc_aware(end_time)
        rows = [
            a
            for a in self._alarms
            if st <= _to_utc_aware(a.timestamp) <= et
        ]
        if metric:
            rows = [a for a in rows if a.type == metric]
        if level:
            rows = [a for a in rows if a.level == level]
        rows.sort(key=lambda x: _to_utc_aware(x.timestamp), reverse=True)
        total = len(rows)
        p = max(1, page)
        ps = max(1, min(page_size, 500))
        start_idx = (p - 1) * ps
        page_rows = rows[start_idx : start_idx + ps]
        return total, [
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
            for r in page_rows
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

    def _next_id(self) -> str:
        return f"alarm_{len(self._alarms):06d}"

    async def try_append_threshold_alarm(
        self,
        *,
        device_id: str,
        metric: str,
        metric_zh: str,
        unit: str,
        value: float,
        threshold: float,
    ) -> Optional[AlarmResponse]:
        """
        边沿检测：value > threshold 且上一状态为未告警时落库一条；
        解除告警态需 value <= threshold - hyst，避免在阈值附近小幅波动反复触发。
        """
        key = (device_id, metric)
        hyst = _ALARM_CLEAR_HYSTERESIS.get(metric, 0.0)
        release = threshold - hyst
        was_active = self._metric_alarm_active.get(key, False)

        if value <= release:
            if was_active:
                self._metric_alarm_active[key] = False
            return None

        if value <= threshold:
            return None

        if was_active:
            return None

        self._metric_alarm_active[key] = True
        ts = datetime.now(timezone.utc)
        level = _level_for_excess(value, threshold)
        alarm_id = self._next_id()
        message = (
            f"设备「{device_id}」{metric_zh}异常：当前 {value:.2f}{unit}，阈值 {threshold:.2f}{unit}"
        )
        row = _AlarmRow(
            id=alarm_id,
            type=metric,
            level=level,
            message=message,
            value=round(float(value), 4),
            threshold=round(float(threshold), 4),
            read=False,
            timestamp=ts,
        )
        self._alarms.append(row)
        if len(self._alarms) > 2000:
            self._alarms = self._alarms[-2000:]

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
