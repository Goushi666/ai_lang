"""环境分析 Tool：封装 AnalysisService 的原子操作。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .base import BaseTool, ToolResult


class GetEnvironmentAnalysis(BaseTool):
    """获取环境分析摘要（聚合统计、异常、趋势）。"""

    name = "get_environment_analysis"
    description = (
        "获取指定时间范围内的环境分析摘要，包含温度/湿度/光照的统计值"
        "（最小、最大、平均、中位数）、检测到的异常列表、以及温度预测。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "start_time": {
                "type": "string",
                "description": "起始时间，ISO 8601 格式",
            },
            "end_time": {
                "type": "string",
                "description": "结束时间，ISO 8601 格式",
            },
            "device_id": {
                "type": "string",
                "description": "设备 ID（可选）",
            },
        },
        "required": ["start_time", "end_time"],
    }

    def __init__(self, analysis_service: Any):
        self._service = analysis_service

    async def execute(self, **kwargs: Any) -> ToolResult:
        start_str = kwargs.get("start_time", "")
        end_str = kwargs.get("end_time", "")
        device_id = kwargs.get("device_id")

        try:
            start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError) as e:
            return ToolResult(error=f"时间格式错误: {e}")

        try:
            summary = await self._service.get_environment_summary(
                start_time=start,
                end_time=end,
                device_id=device_id,
            )
        except Exception as e:
            return ToolResult(error=f"分析服务调用失败: {e}")

        # 将 Pydantic 响应转为 dict
        result: dict[str, Any] = {}

        if summary.time_window:
            result["time_window"] = {
                "start": summary.time_window.start,
                "end": summary.time_window.end,
                "sample_count": summary.time_window.sample_count,
            }

        if summary.aggregate:
            agg = {}
            for metric in summary.aggregate:
                agg[metric.metric] = {
                    "min": metric.min,
                    "max": metric.max,
                    "avg": metric.avg,
                    "median": metric.median,
                    "unit": metric.unit,
                }
            result["aggregate"] = agg

        if summary.anomalies:
            result["anomalies"] = [
                {
                    "metric": a.metric,
                    "type": a.type,
                    "message": a.message,
                    "peak_value": a.peak_value,
                    "threshold": a.threshold,
                    "start_time": a.start_time,
                    "end_time": a.end_time,
                    "count": a.count,
                }
                for a in summary.anomalies
            ]
        else:
            result["anomalies"] = []

        if summary.thresholds:
            result["thresholds"] = {
                "temperature": summary.thresholds.temperature,
                "humidity": summary.thresholds.humidity,
                "light": summary.thresholds.light,
            }

        return ToolResult(data=result)
