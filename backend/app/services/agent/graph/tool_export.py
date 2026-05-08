"""工具导出链接解析（与 AgentService 逻辑一致）。"""

from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import quote

from app.services.agent.tools.base import ToolResult

_EXPORT_DOWNLOAD_TOOL_NAMES = frozenset(
    {"export_csv_file", "export_sensor_history_csv", "export_alarms_history_csv"},
)


def export_download_from_tool_result(tool_name: str, result: ToolResult) -> Optional[Dict[str, str]]:
    if tool_name not in _EXPORT_DOWNLOAD_TOOL_NAMES or not result.ok:
        return None
    data = result.data or {}
    fn = data.get("filename")
    if not isinstance(fn, str) or not fn.strip():
        return None
    fn = fn.strip()
    return {
        "filename": fn,
        "download_path": f"/api/agent/export-download?filename={quote(fn, safe='')}",
    }
