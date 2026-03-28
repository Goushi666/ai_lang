"""环境分析 API 的 Pydantic 模型（框架阶段字段已对齐设计文档，数值可为占位）。"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class AggregateMetric(BaseModel):
    count: int = 0
    min: Optional[float] = None
    max: Optional[float] = None
    avg: Optional[float] = None


class TimeWindow(BaseModel):
    start: str
    end: str


class EnvironmentSummaryResponse(BaseModel):
    device_id: str
    window: TimeWindow
    aggregate: dict[str, AggregateMetric]
    buckets: list[Any] = Field(default_factory=list)
    summary_code: str
    summary_hints: list[str] = Field(default_factory=list)
    framework: bool = Field(
        True,
        description="为 True 表示当前为占位实现，未做真实聚合",
    )
