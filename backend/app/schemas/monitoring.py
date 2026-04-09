"""环境监测页：2 小时温度时间轴、近期异常列表。"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.analysis import AnomalyItem

StoredMetricName = Literal["temperature", "humidity", "light"]


class EnvironmentAnomalyRecord(BaseModel):
    """SQLite 已落库异常（仅存落库时刻，无片段起止列）。"""

    id: int = Field(description="库内主键")
    device_id: str
    metric: StoredMetricName
    rule_id: str
    peak: float | None = None
    threshold: float | None = None
    detail_zh: str = ""
    recorded_at: str = Field(description="落库时间 ISO8601（UTC，Z）")


class EnvironmentAnomalyListResponse(BaseModel):
    total: int = Field(description="满足条件的总条数（不受分页截取影响）")
    items: list[EnvironmentAnomalyRecord] = Field(default_factory=list)


class BatchDeleteAnomalyRecordsBody(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=500, description="environment_anomalies 主键")

    @field_validator("ids", mode="before")
    @classmethod
    def coerce_ids(cls, v: object) -> list[int]:
        if not isinstance(v, list):
            raise ValueError("ids 须为非空数组")
        seen: set[int] = set()
        out: list[int] = []
        for x in v:
            try:
                n = int(x)  # JSON 数字 / 字符串 id 均可
            except (TypeError, ValueError):
                continue
            if n > 0 and n not in seen:
                seen.add(n)
                out.append(n)
        if not out:
            raise ValueError("ids 中无有效正整数主键")
        return out


class TimelinePoint(BaseModel):
    time_ms: int
    temperature_c: float


class TimelineBandPoint(BaseModel):
    """与未来推算同一时间点的浮动区间（℃）。"""

    time_ms: int
    low_c: float
    high_c: float


class MonitoringTemperatureTimelineResponse(BaseModel):
    """过去 1h 实测 + 过去 1h 推算 + 未来 1h 推算（均为 ℃）。"""

    now_iso: str
    method: str = Field(description="lstm | linear_fallback | insufficient")
    method_zh: str
    past_actual: list[TimelinePoint] = Field(default_factory=list)
    past_predicted: list[TimelinePoint] = Field(default_factory=list)
    future_predicted: list[TimelinePoint] = Field(default_factory=list)
    future_is_uniform: bool = Field(
        default=False,
        description="未来一小时推算近似水平线（端点温差过小）",
    )
    future_hint_zh: str = Field(
        default="",
        description="当 future_is_uniform 时给前端的说明",
    )
    future_band: list[TimelineBandPoint] = Field(
        default_factory=list,
        description="与未来点一一对应的上下界；非均匀时可为空",
    )


class MonitoringAnomaliesResponse(BaseModel):
    anomalies: list[AnomalyItem] = Field(default_factory=list)
    summary_label: str = ""
    summary_code: str = ""
