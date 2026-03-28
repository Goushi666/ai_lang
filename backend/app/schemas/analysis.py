"""环境分析 API：统计、图表、预测与导出（含 Agent 用 JSON 结构）。"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class AggregateMetric(BaseModel):
    count: int = 0
    min: Optional[float] = None
    max: Optional[float] = None
    avg: Optional[float] = None
    median: Optional[float] = None


class TimeWindow(BaseModel):
    start: str
    end: str


MetricName = Literal["temperature", "humidity", "light"]


class ThresholdSnapshot(BaseModel):
    temperature_c: float = Field(description="温度阈值 ℃")
    humidity_percent: float = Field(description="湿度阈值 %RH")
    light_lux: float = Field(description="光照阈值 lx")


class AnomalyItem(BaseModel):
    device_id: str
    metric: MetricName
    rule_id: str
    start_time: str
    end_time: str
    peak: Optional[float] = None
    threshold: Optional[float] = None
    detail_zh: str = Field(default="")


class BucketSeries(BaseModel):
    bucket_start: str
    aggregate: dict[str, AggregateMetric]


class ChartPoint(BaseModel):
    """折线图用：毫秒时间戳 + 三指标。"""

    time_ms: int
    time_iso: str
    temperature: float
    humidity: float
    light: float


class ChartAnomalyBand(BaseModel):
    """图上阴影区间（与异常片段一致）。"""

    start_ms: int
    end_ms: int
    label_zh: str
    metric: MetricName


class ForecastHourPoint(BaseModel):
    hours_after_last_sample: int = Field(ge=1, le=24)
    time_iso: str
    temperature_c: float


class TemperatureForecast(BaseModel):
    """未来多步温度：可能为线性阻尼外推或 LSTM（含自回归滚动），见 method 与 method_zh。"""

    based_on_points: int
    method: str = Field(description="机器可读，如 linear_regression_on_time")
    method_zh: str
    disclaimer_zh: str
    hours: list[ForecastHourPoint] = Field(default_factory=list)
    anchor_time_iso: str = Field(
        description="推算时间轴基准：时段内用于外推的「最后一条采样」时刻（UTC ISO）"
    )
    last_observed_temperature_c: float = Field(
        description="anchor 时刻的实测温度 ℃，与 hours[0]（+1h）对照"
    )
    horizon_hours: int = Field(
        default=24,
        ge=1,
        description="共给出多少步；每步相对上一时刻间隔 1 小时，第 1 步 = anchor + 1h",
    )


class EnvironmentSummaryResponse(BaseModel):
    device_id: str
    window: TimeWindow
    aggregate: dict[str, AggregateMetric]
    buckets: list[BucketSeries] = Field(default_factory=list)
    anomalies: list[AnomalyItem] = Field(default_factory=list)

    summary_code: str
    summary_label: str
    summary_hints: list[str] = Field(default_factory=list)
    lines_plain: list[str] = Field(default_factory=list)

    thresholds: Optional[ThresholdSnapshot] = None
    sample_count_in_window: int = 0
    sample_count_used: int = 0
    streak_points_required: int = 0

    chart_points: list[ChartPoint] = Field(
        default_factory=list,
        description="时段内曲线（已限制点数，便于前端绘图）",
    )
    chart_anomaly_bands: list[ChartAnomalyBand] = Field(default_factory=list)
    temperature_forecast: Optional[TemperatureForecast] = None

    downsampled: bool = False
    framework: bool = False
