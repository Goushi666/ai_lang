from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.timeutil import instant_to_sqlite_naive, utc_aware_from_db_naive
from app.models.alarm import Alarm as AlarmORM
from app.models.environment_anomaly import EnvironmentAnomaly
from app.schemas.alarm import AlarmConfig, AlarmResponse
from app.repositories.environment_anomaly_repo import EnvironmentAnomalyRepository


def _to_utc_aware(dt: datetime) -> datetime:
    """与 FastAPI Query 解析出的带时区时间可比；历史里 naive 一律视为 UTC。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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


def _orm_to_response(row: AlarmORM) -> AlarmResponse:
    return AlarmResponse(
        id=str(row.id),
        type=row.type,
        level=row.level,
        message=row.message,
        value=row.value,
        threshold=row.threshold,
        read=bool(row.read),
        timestamp=utc_aware_from_db_naive(row.timestamp),
    )


def _anomaly_to_alarm_response(row: EnvironmentAnomaly) -> AlarmResponse:
    peak = row.peak if row.peak is not None else 0.0
    thr = row.threshold if row.threshold is not None else 0.0
    lvl = _level_for_excess(float(peak), float(thr)) if thr > 0 else "medium"
    return AlarmResponse(
        id=f"ea-{row.id}",
        type=row.metric,
        level=lvl,
        message=(row.detail_zh or "")[:500],
        value=float(peak),
        threshold=float(thr),
        read=False,
        timestamp=utc_aware_from_db_naive(row.recorded_at),
    )


class AlarmRepository:
    """
    告警历史：``alarms`` 表（超阈边沿）+ ``environment_anomalies``（与告警中心页同源）。

    前端「告警中心」列表读的是 ``environment_anomalies``；此前仅内存的边沿告警只进了该表，
    若只查 ``alarms`` 会为空。合并后 Agent / REST 与界面一致。
    """

    _MERGE_FETCH_CAP = 5000

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        environment_anomaly_repo: Optional[EnvironmentAnomalyRepository] = None,
    ) -> None:
        self._session_factory = session_factory
        self._env_anomaly_repo = environment_anomaly_repo
        self._metric_alarm_active: Dict[tuple[str, str], bool] = {}
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
        start_naive = instant_to_sqlite_naive(st)
        end_naive = instant_to_sqlite_naive(et)

        a_conds = [
            AlarmORM.timestamp >= start_naive,
            AlarmORM.timestamp <= end_naive,
        ]
        if metric:
            a_conds.append(AlarmORM.type == metric)
        if level:
            a_conds.append(AlarmORM.level == level)

        p = max(1, page)
        ps = max(1, min(int(page_size), 500))

        async with self._session_factory() as session:
            cnt_a_stmt = select(func.count()).select_from(AlarmORM).where(and_(*a_conds))
            cnt_a = int((await session.execute(cnt_a_stmt)).scalar_one() or 0)

            a_stmt = (
                select(AlarmORM)
                .where(and_(*a_conds))
                .order_by(AlarmORM.timestamp.desc())
                .limit(self._MERGE_FETCH_CAP)
            )
            alarm_rows = list((await session.execute(a_stmt)).scalars().all())
            alarm_items = [_orm_to_response(r) for r in alarm_rows]

            merged: List[AlarmResponse] = list(alarm_items)

            if self._env_anomaly_repo is not None:
                ea_conds = [
                    EnvironmentAnomaly.recorded_at >= start_naive,
                    EnvironmentAnomaly.recorded_at <= end_naive,
                ]
                if metric:
                    ea_conds.append(EnvironmentAnomaly.metric == metric)
                cnt_e_stmt = (
                    select(func.count()).select_from(EnvironmentAnomaly).where(and_(*ea_conds))
                )
                cnt_e = int((await session.execute(cnt_e_stmt)).scalar_one() or 0)

                e_stmt = (
                    select(EnvironmentAnomaly)
                    .where(and_(*ea_conds))
                    .order_by(EnvironmentAnomaly.recorded_at.desc())
                    .limit(self._MERGE_FETCH_CAP)
                )
                ea_rows = list((await session.execute(e_stmt)).scalars().all())
                merged.extend(_anomaly_to_alarm_response(r) for r in ea_rows)
            else:
                cnt_e = 0

            merged.sort(key=lambda x: x.timestamp, reverse=True)

            if level:
                merged = [r for r in merged if r.level == level]

            truncated = (cnt_a > self._MERGE_FETCH_CAP) or (cnt_e > self._MERGE_FETCH_CAP)
            if truncated:
                total = len(merged)
            elif level:
                total = len(merged)
            else:
                total = cnt_a + cnt_e

            start_idx = (p - 1) * ps
            page_items = merged[start_idx : start_idx + ps]

        return total, page_items

    async def mark_read(self, alarm_id: str) -> bool:
        if str(alarm_id).startswith("ea-"):
            return False
        try:
            pk = int(str(alarm_id).strip())
        except ValueError:
            return False
        async with self._session_factory() as session:
            stmt = (
                update(AlarmORM)
                .where(AlarmORM.id == pk)
                .values(read=True)
                .returning(AlarmORM.id)
            )
            res = await session.execute(stmt)
            changed = res.scalar_one_or_none()
            await session.commit()
            return changed is not None

    async def get_config(self) -> AlarmConfig:
        return self._config_store["default"]

    async def update_config(self, config: AlarmConfig) -> None:
        self._config_store["default"] = config.model_copy(deep=True)

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
        ts_utc = datetime.now(timezone.utc)
        ts_naive = instant_to_sqlite_naive(ts_utc)
        level = _level_for_excess(value, threshold)
        message = (
            f"设备「{device_id}」{metric_zh}异常：当前 {value:.2f}{unit}，阈值 {threshold:.2f}{unit}"
        )

        async with self._session_factory() as session:
            row = AlarmORM(
                type=metric,
                level=level,
                message=message[:500],
                value=round(float(value), 4),
                threshold=round(float(threshold), 4),
                read=False,
                timestamp=ts_naive,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return _orm_to_response(row)
