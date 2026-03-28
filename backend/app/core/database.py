"""
异步 SQLite（aiosqlite）引擎与会话工厂。

供 SensorRepository 与各依赖注入共用；启动时 create_all，关闭时 dispose。
"""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """全局 ORM 基类；传感器等表均挂在此 metadata 上。"""

    pass


_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _create_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.SQLITE_URL,
            echo=False,
            pool_pre_ping=True,
        )

        @event.listens_for(_engine.sync_engine, "connect")
        def _sqlite_wal(dbapi_connection, connection_record):  # noqa: ARG001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        engine = _create_engine()
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def init_db() -> None:
    """创建缺失的 ORM 表。"""
    from app.models.sensor import SensorData  # noqa: F401

    engine = _create_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_db() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
