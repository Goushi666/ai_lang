import logging
from datetime import datetime
from typing import FrozenSet, List, Optional

from app.core.timeutil import format_instant_rfc3339_utc_z, to_utc_aware_instant
from app.repositories.alarm_repo import AlarmRepository
from app.repositories.environment_anomaly_repo import EnvironmentAnomalyRepository
from app.schemas.alarm import AlarmConfig, AlarmHistoryPage, AlarmResponse
from app.schemas.analysis import AnomalyItem
from app.schemas.sensor import SensorDataResponse
from app.websocket.manager import websocket_manager

logger = logging.getLogger(__name__)

_EDGE_RULE_IDS = {
    "temperature": "temp_streak_high",
    "humidity": "humidity_streak_high",
    "light": "light_streak_high",
}


class AlarmService:
    """
    告警业务服务（Service 层）。

    职责边界：
    - REST：告警历史、标记已读、告警配置
    - WebSocket：在传感器读数超阈（边沿）时推送；同一次采样内多条合并为一条 WS 消息，避免连弹窗。
    - SQLite environment_anomalies：与弹窗同次的边沿告警写入一条，避免仅打开「环境监测」分析后才落库。
    """

    def __init__(
        self,
        repo: AlarmRepository,
        *,
        environment_anomaly_repo: Optional[EnvironmentAnomalyRepository] = None,
    ) -> None:
        self._repo = repo
        self._environment_anomaly_repo = environment_anomaly_repo

    async def get_history(
        self,
        start_time: datetime,
        end_time: datetime,
        *,
        metric: Optional[str] = None,
        level: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> AlarmHistoryPage:
        total, items = await self._repo.get_history(
            start_time,
            end_time,
            metric=metric,
            level=level,
            page=page,
            page_size=page_size,
        )
        return AlarmHistoryPage(total=total, items=items)

    async def mark_read(self, alarm_id: str) -> bool:
        return await self._repo.mark_read(alarm_id)

    async def get_config(self) -> AlarmConfig:
        return await self._repo.get_config()

    async def update_config(self, config: AlarmConfig) -> None:
        await self._repo.update_config(config)

    async def evaluate_sensor_reading(
        self,
        data: SensorDataResponse,
        *,
        metrics_to_evaluate: Optional[FrozenSet[str]] = None,
    ) -> None:
        """
        根据当前阈值判定是否由正常变为超阈；满足则写入历史并合并广播一次。

        ``metrics_to_evaluate``：仅 MQTT 分 topic 上报时使用，只判本包出现的指标；
        为 ``None`` 时判三项（模拟采样等全量行）。
        """
        cfg = await self._repo.get_config()
        created: List[AlarmResponse] = []
        anomaly_items: List[AnomalyItem] = []
        checks = [
            ("temperature", cfg.temperature_threshold, "温度", "℃", data.temperature),
            ("humidity", cfg.humidity_threshold, "湿度", "%RH", data.humidity),
            ("light", cfg.light_threshold, "光照", "lx", data.light),
        ]
        for metric, threshold, metric_zh, unit, value in checks:
            if metrics_to_evaluate is not None and metric not in metrics_to_evaluate:
                continue
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
                rule_id = _EDGE_RULE_IDS.get(metric)
                if self._environment_anomaly_repo is not None and rule_id is not None:
                    ts_iso = format_instant_rfc3339_utc_z(to_utc_aware_instant(data.timestamp))
                    detail = (
                        f"设备「{data.device_id}」{metric_zh}超阈（实时）：读数 {alarm.value:.2f}{unit}，"
                        f"阈值 {alarm.threshold:.2f}{unit}。"
                    )
                    anomaly_items.append(
                        AnomalyItem(
                            device_id=data.device_id,
                            metric=metric,  # type: ignore[arg-type]
                            rule_id=rule_id,
                            start_time=ts_iso,
                            end_time=ts_iso,
                            peak=alarm.value,
                            threshold=alarm.threshold,
                            detail_zh=detail,
                        )
                    )

        if anomaly_items and self._environment_anomaly_repo is not None:
            try:
                await self._environment_anomaly_repo.persist_items(anomaly_items)
            except Exception:
                logger.exception("environment_anomalies 边沿告警落库失败")

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
