"""Agent Tool：将结构化行数据导出为 CSV 文件（UTF-8 BOM，便于 Excel 打开中文）。"""

from __future__ import annotations

import csv
import io
import json
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from app.repositories.alarm_repo import AlarmRepository
from app.services.sensor_service import SensorService

from .base import BaseTool, ToolResult

_FILENAME_SAFE = re.compile(r"[^\w\-\.]+")


def _sanitize_filename(name: str) -> str:
    base = Path(str(name).strip()).name
    if not base:
        base = f"export_{uuid.uuid4().hex[:10]}"
    base = _FILENAME_SAFE.sub("_", base).strip("._") or "export"
    if not base.lower().endswith(".csv"):
        base = f"{base}.csv"
    return base[:120]


def _fieldnames(rows: List[Dict[str, Any]], headers: Optional[Sequence[str]]) -> List[str]:
    if headers:
        seen = set()
        out: List[str] = []
        for h in headers:
            k = str(h).strip()
            if not k or k in seen:
                continue
            seen.add(k)
            out.append(k)
        if out:
            return out
    keys: List[str] = []
    seen2 = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        for k in row.keys():
            ks = str(k)
            if ks not in seen2:
                seen2.add(ks)
                keys.append(ks)
    return keys


def _resolve_export_path(export_root: Path, sanitized_filename: str) -> Path:
    """在 export_root 下得到可写入路径；重名则加随机后缀。"""
    export_root.mkdir(parents=True, exist_ok=True)
    root_res = export_root.resolve()
    target = (export_root / sanitized_filename).resolve()
    try:
        target.relative_to(root_res)
    except ValueError as e:
        raise ValueError("非法文件名") from e
    if target.exists():
        stem = target.stem
        suffix = target.suffix
        target = (export_root / f"{stem}_{uuid.uuid4().hex[:8]}{suffix}").resolve()
        try:
            target.relative_to(root_res)
        except ValueError as e:
            raise ValueError("非法文件名") from e
    return target


def _export_write_result(export_root: Path, target: Path, rows_written: int) -> ToolResult:
    root_res = export_root.resolve()
    try:
        size = target.stat().st_size
    except OSError:
        size = -1
    rel = str(target.relative_to(root_res))
    return ToolResult(
        data={
            "message": "CSV 已写入服务器",
            "filename": target.name,
            "relative_path": rel,
            "directory": str(export_root.resolve()),
            "rows_written": rows_written,
            "bytes": size,
        },
    )


def _parse_iso_datetime(s: Any) -> datetime:
    if s is None or not str(s).strip():
        raise ValueError("缺少时间")
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


class ExportCsvFile(BaseTool):
    """
    将多行对象数据写入服务器本地 CSV 文件。
    路径限制在 export_root 下，禁止 LLM 传入绝对路径或 ``..`` 逃逸。
    """

    name = "export_csv_file"
    description = (
        "将小量表格（建议 **≤200 行**）导出为 CSV：入参为文件名与 rows 对象数组。"
        "**禁止**把传感器全量或上千行告警塞进 rows（会极慢且易超时）；"
        "大量时段数据请改用 ``export_sensor_history_csv`` 或 ``export_alarms_history_csv``，由服务端直连数据库写文件。"
        "保存目录为服务器临时路径，前端会提供「保存到电脑」下载链接。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "导出文件名，如 alarms_jan.csv（勿含路径；非 .csv 将自动补后缀）",
            },
            "rows": {
                "type": "array",
                "description": "行数据，每项为 JSON 对象，键为列名、值为单元格（将转为字符串）",
                "items": {"type": "object"},
            },
            "headers": {
                "type": "array",
                "description": "可选；列顺序。不传则按首行及后续行出现过的键顺序合并",
                "items": {"type": "string"},
            },
        },
        "required": ["filename", "rows"],
    }

    def __init__(self, export_root: Path, max_rows: int = 50_000) -> None:
        self._root = export_root
        self._max_rows = max(1, int(max_rows))

    async def execute(self, **kwargs: Any) -> ToolResult:
        filename = _sanitize_filename(str(kwargs.get("filename", "export.csv")))
        raw_rows = kwargs.get("rows")
        headers_in = kwargs.get("headers")

        if not isinstance(raw_rows, list):
            return ToolResult(error="rows 必须为数组")
        if len(raw_rows) == 0:
            return ToolResult(error="rows 不能为空")
        if len(raw_rows) > min(self._max_rows, 500):
            return ToolResult(
                error=(
                    f"行数 {len(raw_rows)} 过多；export_csv_file 仅适合小表。"
                    "请改用 export_sensor_history_csv 或 export_alarms_history_csv，或缩小行数至 500 以内。"
                ),
            )
        if len(raw_rows) > self._max_rows:
            return ToolResult(error=f"行数超过上限 {self._max_rows}，请分批导出或缩小范围")

        rows: List[Dict[str, Any]] = []
        for i, item in enumerate(raw_rows):
            if not isinstance(item, dict):
                return ToolResult(error=f"rows[{i}] 必须为对象")
            rows.append({str(k): v for k, v in item.items()})

        headers: Optional[List[str]] = None
        if isinstance(headers_in, list) and headers_in:
            headers = [str(h) for h in headers_in if str(h).strip()]

        fieldnames = _fieldnames(rows, headers)
        if not fieldnames:
            return ToolResult(error="无法推断列名：请提供非空 rows 或 headers")

        try:
            target = _resolve_export_path(self._root, filename)
        except ValueError as e:
            return ToolResult(error=str(e))
        except OSError as e:
            return ToolResult(error=f"无法创建导出目录: {e}")

        def _cell(v: Any) -> str:
            if v is None:
                return ""
            if isinstance(v, (dict, list)):
                return json.dumps(v, ensure_ascii=False)
            return str(v)

        try:
            with target.open("w", newline="", encoding="utf-8-sig") as fp:
                w = csv.DictWriter(fp, fieldnames=fieldnames, extrasaction="ignore")
                w.writeheader()
                for row in rows:
                    w.writerow({k: _cell(row.get(k)) for k in fieldnames})
        except OSError as e:
            return ToolResult(error=f"写入失败: {e}")

        return _export_write_result(self._root, target, len(rows))


class ExportSensorHistoryCsv(BaseTool):
    """服务端按时间窗从数据库拉取传感器历史并写 CSV，避免模型在 tool 参数里传上万行 JSON。"""

    name = "export_sensor_history_csv"
    description = (
        "从数据库直接导出指定时间范围内的**传感器历史**为 CSV（与 REST 导出格式一致，UTF-8 BOM）。"
        "仅需文件名与时间范围，**勿**把采样行塞进 export_csv_file；适合全量或大量数据，速度快。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "如 sensor_2026-01-01.csv（勿含路径）"},
            "start_time": {"type": "string", "description": "起始时间 ISO 8601"},
            "end_time": {"type": "string", "description": "结束时间 ISO 8601"},
        },
        "required": ["filename", "start_time", "end_time"],
    }

    def __init__(self, export_root: Path, sensor_service: SensorService) -> None:
        self._root = export_root
        self._sensor = sensor_service

    async def execute(self, **kwargs: Any) -> ToolResult:
        filename = _sanitize_filename(str(kwargs.get("filename", "sensor_history.csv")))
        try:
            start = _parse_iso_datetime(kwargs.get("start_time"))
            end = _parse_iso_datetime(kwargs.get("end_time"))
        except (ValueError, TypeError) as e:
            return ToolResult(error=f"时间格式错误: {e}")
        if end < start:
            return ToolResult(error="end_time 不能早于 start_time")
        if (end - start) > timedelta(days=366):
            return ToolResult(error="时间范围超过 366 天，请分段导出")

        try:
            csv_text = await self._sensor.export_csv(start, end)
        except Exception as e:
            return ToolResult(error=f"读取或生成 CSV 失败: {e}")

        try:
            target = _resolve_export_path(self._root, filename)
            target.write_text(csv_text, encoding="utf-8")
        except ValueError as e:
            return ToolResult(error=str(e))
        except OSError as e:
            return ToolResult(error=f"写入失败: {e}")

        lines = csv_text.count("\n")
        data_rows = max(0, lines - 1) if lines else 0
        return _export_write_result(self._root, target, data_rows)


class ExportAlarmsHistoryCsv(BaseTool):
    """合并 alarms + environment_anomalies 历史，服务端分页拉齐后写 CSV。"""

    name = "export_alarms_history_csv"
    description = (
        "从数据库直接导出指定时间范围内的**告警历史**（与 get_alarms_history 同源：含 environment_anomalies）为 CSV。"
        "仅需文件名与时间范围，勿用 export_csv_file 逐行拼装大量告警。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "如 alarms_export.csv（勿含路径）"},
            "start_time": {"type": "string", "description": "起始时间 ISO 8601"},
            "end_time": {"type": "string", "description": "结束时间 ISO 8601"},
            "level": {
                "type": "string",
                "description": "可选：urgent / high / medium，与 get_alarms_history 一致",
            },
            "metric": {
                "type": "string",
                "description": "可选：temperature / humidity / light",
            },
        },
        "required": ["filename", "start_time", "end_time"],
    }

    def __init__(self, export_root: Path, alarm_repo: AlarmRepository, max_rows: int = 50_000) -> None:
        self._root = export_root
        self._repo = alarm_repo
        self._max_rows = max(1, int(max_rows))

    async def execute(self, **kwargs: Any) -> ToolResult:
        filename = _sanitize_filename(str(kwargs.get("filename", "alarms_export.csv")))
        try:
            start = _parse_iso_datetime(kwargs.get("start_time"))
            end = _parse_iso_datetime(kwargs.get("end_time"))
        except (ValueError, TypeError) as e:
            return ToolResult(error=f"时间格式错误: {e}")
        if end < start:
            return ToolResult(error="end_time 不能早于 start_time")

        level = kwargs.get("level")
        if level is not None:
            level = str(level).strip() or None
        metric = kwargs.get("metric")
        if metric is not None:
            metric = str(metric).strip() or None

        page = 1
        page_size = 500
        all_rows: List[List[Any]] = []
        max_pages = 500

        while len(all_rows) < self._max_rows and page <= max_pages:
            _total, batch = await self._repo.get_history(
                start,
                end,
                metric=metric,
                level=level,
                page=page,
                page_size=page_size,
            )
            if not batch:
                break
            for a in batch:
                all_rows.append(
                    [
                        a.id,
                        a.type,
                        a.level,
                        a.message,
                        a.value,
                        a.threshold,
                        a.read,
                        a.timestamp.isoformat(),
                    ],
                )
                if len(all_rows) >= self._max_rows:
                    break
            if len(batch) < page_size:
                break
            page += 1

        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["id", "type", "level", "message", "value", "threshold", "read", "timestamp_iso"])
        w.writerows(all_rows)
        body = "\ufeff" + buf.getvalue()

        try:
            target = _resolve_export_path(self._root, filename)
            target.write_text(body, encoding="utf-8")
        except ValueError as e:
            return ToolResult(error=str(e))
        except OSError as e:
            return ToolResult(error=f"写入失败: {e}")

        return _export_write_result(self._root, target, len(all_rows))
