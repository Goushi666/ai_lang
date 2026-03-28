"""环境监测页：2 小时温度时间轴、近期异常列表。"""

from pydantic import BaseModel, Field

from app.schemas.analysis import AnomalyItem


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
