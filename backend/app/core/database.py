"""
异步 SQLite（aiosqlite）引擎与会话工厂。

供 SensorRepository 与各依赖注入共用；启动时 create_all，关闭时 dispose。
"""

from __future__ import annotations

from sqlalchemy import event, inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


def _migrate_environment_anomalies_schema(sync_conn) -> None:
    """
    旧表含 start_time/end_time；新表仅 recorded_at。一次性复制后删旧表（SQLite）。
    """
    insp = inspect(sync_conn)
    names = insp.get_table_names()
    if "environment_anomalies" not in names:
        return
    col_names = {c["name"] for c in insp.get_columns("environment_anomalies")}
    if "start_time" not in col_names:
        return
    sync_conn.execute(
        text(
            """
            CREATE TABLE environment_anomalies__new (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                device_id VARCHAR(50) NOT NULL,
                metric VARCHAR(20) NOT NULL,
                rule_id VARCHAR(64) NOT NULL,
                peak FLOAT,
                threshold FLOAT,
                detail_zh TEXT NOT NULL DEFAULT '',
                recorded_at DATETIME NOT NULL
            )
            """
        )
    )
    sync_conn.execute(
        text(
            """
            INSERT INTO environment_anomalies__new
                (id, device_id, metric, rule_id, peak, threshold, detail_zh, recorded_at)
            SELECT
                id,
                device_id,
                metric,
                rule_id,
                peak,
                threshold,
                COALESCE(detail_zh, ''),
                COALESCE(recorded_at, end_time, start_time, CURRENT_TIMESTAMP)
            FROM environment_anomalies
            """
        )
    )
    sync_conn.execute(text("DROP TABLE environment_anomalies"))
    sync_conn.execute(text("ALTER TABLE environment_anomalies__new RENAME TO environment_anomalies"))
    sync_conn.execute(
        text("CREATE INDEX ix_env_anomaly_recorded_at ON environment_anomalies (recorded_at)")
    )
    sync_conn.execute(
        text(
            "CREATE INDEX ix_env_anomaly_device_recorded "
            "ON environment_anomalies (device_id, recorded_at)"
        )
    )


def _migrate_agent_messages_reasoning(sync_conn) -> None:
    """旧库仅有 content 等列；新版本增加 reasoning（思考过程）。"""
    insp = inspect(sync_conn)
    names = insp.get_table_names()
    if "agent_messages" not in names:
        return
    col_names = {c["name"] for c in insp.get_columns("agent_messages")}
    if "reasoning" in col_names:
        return
    sync_conn.execute(text("ALTER TABLE agent_messages ADD COLUMN reasoning TEXT"))


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
    from app.models.agent_chat import AgentConversation, AgentMessage  # noqa: F401
    from app.models.environment_anomaly import EnvironmentAnomaly  # noqa: F401
    from app.models.sensor import SensorData  # noqa: F401

    engine = _create_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_environment_anomalies_schema)
        await conn.run_sync(_migrate_agent_messages_reasoning)


async def dispose_db() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
