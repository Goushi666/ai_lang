"""库内 naive 时间与 MQTT 无时区 ISO 的统一解释（避免东八区与 UTC 混用差 8 小时）。"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.core.config import settings


def _naive_wall_means_tzname() -> str | None:
    """
    仅用于 **读库** ``utc_aware_from_db_naive``：历史误把东八区墙钟写入 naive 列时填 Asia/Shanghai。

    **禁止**用于 MQTT/Unix 入库路径，否则会把「已是 UTC 的库内数字」再按上海解释，与写入叠成约 8 小时偏差。
    """
    tzname = (settings.SQLITE_NAIVE_MEANS_TIMEZONE or "").strip()
    if not tzname or tzname.upper() == "UTC":
        return None
    return tzname


def to_utc_aware_instant(dt: datetime) -> datetime:
    """
    将任意 datetime 规范为带 ``timezone.utc`` 的同一瞬间（业务入参 / 入库前）。

    - 已带 tz：换算到 UTC。
    - naive：**一律视为 UTC 墙钟**（Unix epoch、MQTT 数值、本服务写入约定）。与 ``SQLITE_NAIVE_MEANS_TIMEZONE`` 无关。
    """
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    return dt.replace(tzinfo=timezone.utc)


def instant_to_sqlite_naive(dt: datetime) -> datetime:
    """
    写入 SQLite ``DateTime`` 列：**UTC 墙钟的 naive**。

    仅依赖 ``to_utc_aware_instant``（naive=UTC 墙钟）。``SQLITE_NAIVE_MEANS_TIMEZONE`` 只影响 **读出**，不参与本条。
    """
    return to_utc_aware_instant(dt).replace(tzinfo=None)


def iso_string_to_sqlite_naive(iso_str: str) -> datetime:
    """ISO / RFC3339 字符串（含 ``Z``/``z``、``±offset``）→ 存库用 UTC naive。"""
    s = (iso_str or "").strip()
    if not s:
        raise ValueError("empty ISO datetime string")
    if s.endswith("Z") or s.endswith("z"):
        s = f"{s[:-1]}+00:00"
    parsed = datetime.fromisoformat(s)
    return instant_to_sqlite_naive(parsed)


def utc_aware_from_db_naive(ts: datetime) -> datetime:
    """
    SQLite 中存的无时区时间戳：默认按 **UTC 墙钟** 理解（与当前入库逻辑一致）。

    若历史数据实为「东八区墙钟误写入 naive」，在 .env 设置
    ``SQLITE_NAIVE_MEANS_TIMEZONE=Asia/Shanghai``，读出时会先按该时区再换算为 UTC。
    """
    if ts.tzinfo is not None:
        return ts.astimezone(timezone.utc)
    tzname = _naive_wall_means_tzname()
    if tzname is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.replace(tzinfo=ZoneInfo(tzname)).astimezone(timezone.utc)


def attach_tz_for_mqtt_naive_iso(dt: datetime) -> datetime:
    """MQTT JSON 里无时区的 ISO 本地时间：按 ``MQTT_NAIVE_ISO_TIMEZONE`` 当作墙钟再转 UTC。"""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    tzname = (settings.MQTT_NAIVE_ISO_TIMEZONE or "Asia/Shanghai").strip()
    if not tzname or tzname.upper() == "UTC":
        return dt.replace(tzinfo=timezone.utc)
    return dt.replace(tzinfo=ZoneInfo(tzname)).astimezone(timezone.utc)


def format_instant_rfc3339_utc_z(dt: datetime) -> str:
    """
    将时刻序列化为带 ``Z`` 的 RFC3339 UTC 字符串。

    避免 ``+00:00`` / 无时区 ISO 在前端被误加东八区偏移，造成显示慢 8 小时。
    """
    if dt.tzinfo is None:
        aware = utc_aware_from_db_naive(dt)
    else:
        aware = dt.astimezone(timezone.utc)
    s = aware.isoformat(timespec="microseconds")
    if s.endswith("+00:00"):
        return s[:-6] + "Z"
    if s.endswith("-00:00"):
        return s[:-6] + "Z"
    return s
