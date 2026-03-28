from __future__ import annotations

from datetime import datetime, timedelta, timezone
import random
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.sensor import SensorData
from app.schemas.sensor import SensorDataResponse


def _to_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.replace(tzinfo=None)


def _row_to_response(row: SensorData) -> SensorDataResponse:
    ts = row.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)
    return SensorDataResponse(
        device_id=row.device_id,
        temperature=row.temperature,
        humidity=row.humidity,
        light=row.light,
        timestamp=ts,
    )


class SensorRepository:
    """
    传感器数据：SQLite（aiosqlite）持久化，与 REST / MQTT 共用同一 session_factory。
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_latest(self) -> Optional[SensorDataResponse]:
        async with self._session_factory() as session:
            stmt = select(SensorData).order_by(SensorData.timestamp.desc()).limit(1)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return _row_to_response(row)

    async def get_history(self, start_time: datetime, end_time: datetime) -> List[SensorDataResponse]:
        start_naive = _to_naive_utc(start_time)
        end_naive = _to_naive_utc(end_time)

        async with self._session_factory() as session:
            stmt = (
                select(SensorData)
                .where(SensorData.timestamp >= start_naive, SensorData.timestamp <= end_naive)
                .order_by(SensorData.timestamp.asc())
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [_row_to_response(r) for r in rows]

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
        基于库内最新一条做小幅扰动并插入；无数据时插入种子记录。
        """
        async with self._session_factory() as session:
            stmt = select(SensorData).order_by(SensorData.timestamp.desc()).limit(1)
            result = await session.execute(stmt)
            last = result.scalar_one_or_none()

            ts = datetime.now(timezone.utc)
            ts_naive = _to_naive_utc(ts)

            if last is None:
                # 无历史数据时插入种子记录
                next_temp, next_hum, next_light = 25.0, 50.0, 300.0
                device_id = "device_001"
            else:
                next_temp = round(last.temperature + random.uniform(-0.3, 0.3), 2)
                next_hum = round(last.humidity + random.uniform(-0.5, 0.5), 2)
                next_light = round(last.light + random.uniform(-20.0, 20.0), 2)
                device_id = last.device_id

            row = SensorData(
                device_id=device_id,
                temperature=next_temp,
                humidity=next_hum,
                light=next_light,
                timestamp=ts_naive,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return SensorDataResponse(
                device_id=row.device_id,
                temperature=row.temperature,
                humidity=row.humidity,
                light=row.light,
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
        ts_aware = timestamp
        if ts_aware.tzinfo is None:
            ts_aware = ts_aware.replace(tzinfo=timezone.utc)
        else:
            ts_aware = ts_aware.astimezone(timezone.utc)
        ts_naive = _to_naive_utc(ts_aware)

        async with self._session_factory() as session:
            row = SensorData(
                device_id=device_id,
                temperature=temperature,
                humidity=humidity,
                light=light,
                timestamp=ts_naive,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return SensorDataResponse(
                device_id=row.device_id,
                temperature=row.temperature,
                humidity=row.humidity,
                light=row.light,
                timestamp=ts_aware,
            )

    async def delete_older_than(self, cutoff: datetime) -> int:
        """删除严格早于 cutoff（UTC naive 存库）的记录，返回删除行数。"""
        cutoff_naive = _to_naive_utc(cutoff)
        async with self._session_factory() as session:
            result = await session.execute(delete(SensorData).where(SensorData.timestamp < cutoff_naive))
            await session.commit()
        return result.rowcount or 0
