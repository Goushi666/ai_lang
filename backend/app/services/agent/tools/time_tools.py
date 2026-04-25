"""与时间相关的 Agent Tool。"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from .base import BaseTool, ToolResult

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9
    ZoneInfo = None  # type: ignore[misc, assignment]


class GetCurrentTime(BaseTool):
    """返回服务器当前 UTC 与业务默认时区（东八区）时间，供推算查询窗口。"""

    name = "get_current_time"
    description = (
        "获取当前服务器时间：UTC ISO、配置的展示时区本地 ISO、Unix 秒时间戳。"
        "在本轮需要调用任何其它工具时，必须先调用本工具一次（且须为第一个工具调用），"
        "用返回结果推算时间窗口或写明「截至……」，禁止猜测当前日期。"
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def __init__(self, display_timezone: str = "Asia/Shanghai") -> None:
        self._tz_name = (display_timezone or "Asia/Shanghai").strip() or "Asia/Shanghai"

    async def execute(self, **kwargs: Any) -> ToolResult:
        utc_now = datetime.now(timezone.utc)
        utc_iso = utc_now.isoformat().replace("+00:00", "Z")
        unix_ts = int(time.time())

        local_iso = utc_iso
        if ZoneInfo is not None:
            try:
                tz = ZoneInfo(self._tz_name)
                local_iso = utc_now.astimezone(tz).isoformat()
            except Exception:
                pass

        return ToolResult(
            data={
                "utc_iso": utc_iso,
                "local_iso": local_iso,
                "display_timezone": self._tz_name,
                "unix_timestamp": unix_ts,
            },
        )
