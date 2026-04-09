"""库内 naive 时间与 MQTT 无时区 ISO 的统一解释（避免东八区与 UTC 混用差 8 小时）。"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.core.config import settings


def _sqlite_naive_wall_zoneinfo() -> ZoneInfo | None:
    """
    若配置 ``SQLITE_NAIVE_WALL_CLOCK_ZONE``（如 Asia/Shanghai），则 naive 列按该时区墙钟存取；
    空或 UTC 则列内存 UTC 墙钟（默认）。
    """
    name = (settings.SQLITE_NAIVE_WALL_CLOCK_ZONE or "").strip()
    if not name or name.upper() == "UTC":
        return None
    return ZoneInfo(name)


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
    写入 SQLite ``DateTime`` 列的无时区值。

    - 默认（未配 ``SQLITE_NAIVE_WALL_CLOCK_ZONE``）：**UTC 墙钟** naive。
    - 若配 ``Asia/Shanghai``：**北京时间墙钟** naive（与 Navicat 本地观感一致；API 仍通过 ``utc_aware_from_db_naive`` 换算为 UTC）。
    """
    aware = to_utc_aware_instant(dt)
    zi = _sqlite_naive_wall_zoneinfo()
    if zi is None:
        return aware.replace(tzinfo=None)
    return aware.astimezone(zi).replace(tzinfo=None)


def iso_string_to_sqlite_naive(iso_str: str) -> datetime:
    """ISO / RFC3339 字符串（含 ``Z``/``z``、``±offset``）→ 存库用 naive（按 ``SQLITE_NAIVE_WALL_CLOCK_ZONE``）。"""
    s = (iso_str or "").strip()
    if not s:
        raise ValueError("empty ISO datetime string")
    if s.endswith("Z") or s.endswith("z"):
        s = f"{s[:-1]}+00:00"
    parsed = datetime.fromisoformat(s)
    return instant_to_sqlite_naive(parsed)


def utc_aware_from_db_naive(ts: datetime) -> datetime:
    """
    将 SQLite naive 列还原为 UTC aware。

    优先 ``SQLITE_NAIVE_WALL_CLOCK_ZONE``（与写入一致）；未配置时默认列内为 UTC 墙钟；
    若仅做历史误存修复可再设 ``SQLITE_NAIVE_MEANS_TIMEZONE``（与 WALL_CLOCK 二选一即可，勿混两套语义）。
    """
    if ts.tzinfo is not None:
        return ts.astimezone(timezone.utc)
    zi = _sqlite_naive_wall_zoneinfo()
    if zi is not None:
        return ts.replace(tzinfo=zi).astimezone(timezone.utc)
    tzname = _naive_wall_means_tzname()
    if tzname is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.replace(tzinfo=ZoneInfo(tzname)).astimezone(timezone.utc)


def attach_tz_for_mqtt_naive_iso(dt: datetime) -> datetime:
    """MQTT JSON 里无时区的 ISO：按 ``MQTT_NAIVE_ISO_TIMEZONE``（默认 UTC）当作墙钟再换算为 UTC。"""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    tzname = (settings.MQTT_NAIVE_ISO_TIMEZONE or "UTC").strip()
    if not tzname or tzname.upper() == "UTC":
        return dt.replace(tzinfo=timezone.utc)
    return dt.replace(tzinfo=ZoneInfo(tzname)).astimezone(timezone.utc)


def format_instant_beijing_wall_csv(dt: datetime) -> str:
    """
    北京时间墙钟 ``YYYY-MM-DD HH:mm:ss``（无时区后缀）。

    用于传感器等 CSV 导出，与告警中心前端 ``formatDateTimeZh`` 观感一致。
    REST / WebSocket 仍应使用 ``format_instant_rfc3339_utc_z`` 表示 UTC 瞬间。
    """
    if dt.tzinfo is None:
        aware = utc_aware_from_db_naive(dt)
    else:
        aware = dt.astimezone(timezone.utc)
    sh = aware.astimezone(ZoneInfo("Asia/Shanghai"))
    return sh.strftime("%Y-%m-%d %H:%M:%S")


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
