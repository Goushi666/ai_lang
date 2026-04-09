from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.timeutil import instant_to_sqlite_naive
from app.models.environment_anomaly import EnvironmentAnomaly
from app.schemas.analysis import AnomalyItem


class EnvironmentAnomalyRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def persist_items(self, items: List[AnomalyItem]) -> int:
        """
        每条检测到的异常片段插入一行，仅写入 ``recorded_at=当前 UTC`` 作为时间依据；
        不写入片段起止时刻（起止仍存在于内存 AnomalyItem 供图表等使用）。
        """
        if not items:
            return 0
        now_naive = instant_to_sqlite_naive(datetime.now(timezone.utc))
        n = 0
        async with self._session_factory() as session:
            for item in items:
                session.add(
                    EnvironmentAnomaly(
                        device_id=item.device_id,
                        metric=item.metric,
                        rule_id=item.rule_id,
                        peak=item.peak,
                        threshold=item.threshold,
                        detail_zh=item.detail_zh or "",
                        recorded_at=now_naive,
                    )
                )
                n += 1
            await session.commit()
        return n

    async def list_overlapping_window(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
        device_id: Optional[str] = None,
        metric: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[int, List[EnvironmentAnomaly]]:
        """
        返回 ``recorded_at`` 落在 [window_start, window_end]（按 UTC 换算后的 naive）内的记录，
        按 ``recorded_at`` 降序。
        """
        ws = instant_to_sqlite_naive(window_start)
        we = instant_to_sqlite_naive(window_end)
        cond = and_(
            EnvironmentAnomaly.recorded_at >= ws,
            EnvironmentAnomaly.recorded_at <= we,
        )
        if device_id and device_id.strip():
            cond = and_(cond, EnvironmentAnomaly.device_id == device_id.strip())
        if metric and metric.strip():
            cond = and_(cond, EnvironmentAnomaly.metric == metric.strip())
        lim = min(max(1, limit), 500)
        off = max(0, offset)
        async with self._session_factory() as session:
            count_stmt = select(func.count()).select_from(EnvironmentAnomaly).where(cond)
            total = int((await session.execute(count_stmt)).scalar_one())
            stmt = (
                select(EnvironmentAnomaly)
                .where(cond)
                .order_by(EnvironmentAnomaly.recorded_at.desc())
                .offset(off)
                .limit(lim)
            )
            rows = list((await session.execute(stmt)).scalars().all())
            return total, rows

    async def delete_recorded_before(self, cutoff: datetime) -> int:
        """删除 ``recorded_at`` 严格早于 cutoff（UTC）的记录，与 sensor 保留策略对齐。"""
        cutoff_naive = instant_to_sqlite_naive(cutoff)
        async with self._session_factory() as session:
            result = await session.execute(
                delete(EnvironmentAnomaly).where(EnvironmentAnomaly.recorded_at < cutoff_naive)
            )
            await session.commit()
        return result.rowcount or 0

    async def delete_by_id(self, record_id: int) -> bool:
        async with self._session_factory() as session:
            row = await session.get(EnvironmentAnomaly, record_id)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
        return True

    async def delete_by_ids(self, ids: List[int]) -> int:
        clean_set: set[int] = set()
        for x in ids:
            try:
                n = int(x)
            except (TypeError, ValueError):
                continue
            if n > 0:
                clean_set.add(n)
        clean = sorted(clean_set)
        if not clean:
            return 0
        async with self._session_factory() as session:
            result = await session.execute(
                delete(EnvironmentAnomaly).where(EnvironmentAnomaly.id.in_(clean))
            )
            await session.commit()
        return result.rowcount or 0

    async def delete_all(self) -> int:
        async with self._session_factory() as session:
            result = await session.execute(delete(EnvironmentAnomaly))
            await session.commit()
        return result.rowcount or 0
