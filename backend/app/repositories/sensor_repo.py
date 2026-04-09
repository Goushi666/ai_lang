from __future__ import annotations

from datetime import datetime, timezone
import random
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.timeutil import (
    format_instant_rfc3339_utc_z,
    instant_to_sqlite_naive,
    to_utc_aware_instant,
    utc_aware_from_db_naive,
)
from app.models.sensor import SensorData
from app.schemas.sensor import SensorDataResponse


def _row_to_response(row: SensorData) -> SensorDataResponse:
    ts = utc_aware_from_db_naive(row.timestamp)
    return SensorDataResponse(
        device_id=row.device_id,
        temperature=row.temperature,
        humidity=row.humidity,
        light=row.light,
        timestamp=ts,
    )


async def _same_second_row_or_none(
    session: AsyncSession, device_id: str, ts_naive: datetime
) -> SensorData | None:
    """
    同一 device 同一秒应只有一行；若历史数据有多条，保留 id 最小的一条并删除其余，
    避免 scalar_one_or_none 在重复行上抛 MultipleResultsFound。
    """
    stmt = (
        select(SensorData)
        .where(SensorData.device_id == device_id, SensorData.timestamp == ts_naive)
        .order_by(SensorData.id.asc())
    )
    rows = list((await session.execute(stmt)).scalars().all())
    if not rows:
        return None
    keeper = rows[0]
    for dup in rows[1:]:
        await session.delete(dup)
    return keeper


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
        start_naive = instant_to_sqlite_naive(start_time)
        end_naive = instant_to_sqlite_naive(end_time)

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
                f"{format_instant_rfc3339_utc_z(row.timestamp)},"
                f"{row.device_id},{row.temperature},{row.humidity},{row.light}"
            )
        return "\n".join(lines)

    async def simulate_tick(self) -> Optional[SensorDataResponse]:
        """
        基于库内最新一条做小幅扰动并插入；无数据时插入种子记录。
        时间戳对齐到 **UTC 整秒**，同一 device 同一秒仅一条（与 MQTT 入库一致）。
        """
        async with self._session_factory() as session:
            stmt = select(SensorData).order_by(SensorData.timestamp.desc()).limit(1)
            result = await session.execute(stmt)
            last = result.scalar_one_or_none()

            ts_utc = datetime.now(timezone.utc).replace(microsecond=0)
            ts_naive = ts_utc.replace(tzinfo=None)

            if last is None:
                # 无历史数据时插入种子记录
                next_temp, next_hum, next_light = 25.0, 50.0, 300.0
                device_id = "device_001"
            else:
                next_temp = round(last.temperature + random.uniform(-0.3, 0.3), 2)
                next_hum = round(last.humidity + random.uniform(-0.5, 0.5), 2)
                next_light = round(last.light + random.uniform(-20.0, 20.0), 2)
                device_id = last.device_id

            same = await _same_second_row_or_none(session, device_id, ts_naive)
            if same is not None:
                same.temperature = next_temp
                same.humidity = next_hum
                same.light = next_light
                await session.commit()
                await session.refresh(same)
                return _row_to_response(same)

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
            return _row_to_response(row)

    async def ingest_reading(
        self,
        device_id: str,
        temperature: float | None,
        humidity: float | None,
        light: float | None,
        timestamp: datetime,
    ) -> SensorDataResponse:
        """
        写入一条采样（按 **UTC 整秒** 去重）：同一 ``device_id`` + 同一秒内只保留一行，
        后续 MQTT 包（如 dht / light 分开发）在同秒内 **更新** 该行并合并字段。

        同一秒内：缺失字段沿用本秒已写入行。跨到新一秒时：温湿度仍可沿用上一行（常见仅 DHT 包）；
        **光照**若本包未携带则**不**沿用上一秒（记 0），避免 light 独立 topic 时旧值被复制到每一秒导致峰值/曲线失真。
        """
        ts_aware = to_utc_aware_instant(timestamp).replace(microsecond=0)
        ts_naive = ts_aware.replace(tzinfo=None)

        async with self._session_factory() as session:
            same = await _same_second_row_or_none(session, device_id, ts_naive)

            prev_stmt = (
                select(SensorData)
                .where(SensorData.device_id == device_id)
                .order_by(SensorData.timestamp.desc())
                .limit(1)
            )
            prev = (await session.execute(prev_stmt)).scalars().first()

            merge_src = same if same is not None else prev

            def _pick(new: float | None, old: float | None) -> float:
                if new is not None:
                    return new
                if old is not None:
                    return old
                return 0.0

            final_temp = _pick(temperature, merge_src.temperature if merge_src else None)
            final_hum = _pick(humidity, merge_src.humidity if merge_src else None)
            if same is not None:
                final_light = _pick(light, merge_src.light if merge_src else None)
            else:
                final_light = _pick(light, None)

            if same is not None:
                same.temperature = final_temp
                same.humidity = final_hum
                same.light = final_light
                await session.commit()
                await session.refresh(same)
                return _row_to_response(same)

            row = SensorData(
                device_id=device_id,
                temperature=final_temp,
                humidity=final_hum,
                light=final_light,
                timestamp=ts_naive,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return _row_to_response(row)

    async def delete_older_than(self, cutoff: datetime) -> int:
        """删除严格早于 cutoff（UTC naive 存库）的记录，返回删除行数。"""
        cutoff_naive = instant_to_sqlite_naive(cutoff)
        async with self._session_factory() as session:
            result = await session.execute(delete(SensorData).where(SensorData.timestamp < cutoff_naive))
            await session.commit()
        return result.rowcount or 0

    async def delete_all(self) -> int:
        """删除全部采样记录。"""
        async with self._session_factory() as session:
            result = await session.execute(delete(SensorData))
            await session.commit()
        return result.rowcount or 0
