"""环境分析：统计（含中位数）、异常、折线图数据、24h 温度预测、导出。"""

from __future__ import annotations

import csv
import io
import json
import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from itertools import groupby
from typing import Any, List, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)
from app.repositories.sensor_repo import SensorRepository
from app.schemas.alarm import AlarmConfig
from app.schemas.analysis import (
    AggregateMetric,
    AnomalyItem,
    BucketSeries,
    ChartAnomalyBand,
    ChartPoint,
    EnvironmentSummaryResponse,
    ForecastHourPoint,
    TemperatureForecast,
    ThresholdSnapshot,
    TimeWindow,
)
from app.schemas.sensor import SensorDataResponse
from app.services.alarm_service import AlarmService

_METRIC_ZH = {
    "temperature": "温度",
    "humidity": "湿度",
    "light": "光照",
}


def _aware_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _iso_to_ms(iso_str: str) -> int:
    s = iso_str.replace("Z", "+00:00") if iso_str.endswith("Z") else iso_str
    dt = datetime.fromisoformat(s)
    dt = _aware_utc(dt)
    return int(dt.timestamp() * 1000)


def _uniform_downsample(
    points: List[SensorDataResponse], max_n: int
) -> Tuple[List[SensorDataResponse], bool]:
    if len(points) <= max_n:
        return points, False
    n = len(points)
    m = max(2, min(max_n, n))
    indices = sorted({int(round(i * (n - 1) / (m - 1))) for i in range(m)})
    return [points[i] for i in indices], True


def _median(vals: List[float]) -> Optional[float]:
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    if n % 2:
        return round(s[mid], 4)
    return round((s[mid - 1] + s[mid]) / 2, 4)


def _agg_floats(values: List[float]) -> AggregateMetric:
    if not values:
        return AggregateMetric(count=0, min=None, max=None, avg=None, median=None)
    return AggregateMetric(
        count=len(values),
        min=round(min(values), 2),
        max=round(max(values), 2),
        avg=round(sum(values) / len(values), 4),
        median=_median(values),
    )


def _aggregate_points(points: List[SensorDataResponse]) -> dict[str, AggregateMetric]:
    if not points:
        return {
            "temperature": AggregateMetric(),
            "humidity": AggregateMetric(),
            "light": AggregateMetric(),
        }
    return {
        "temperature": _agg_floats([p.temperature for p in points]),
        "humidity": _agg_floats([p.humidity for p in points]),
        "light": _agg_floats([p.light for p in points]),
    }


def _hour_bucket_start_iso(ts: datetime) -> str:
    ts = _aware_utc(ts)
    floored = ts.replace(minute=0, second=0, microsecond=0)
    return floored.isoformat()


def _build_hourly_buckets(points: List[SensorDataResponse]) -> List[BucketSeries]:
    groups: dict[str, List[SensorDataResponse]] = defaultdict(list)
    for p in points:
        groups[_hour_bucket_start_iso(p.timestamp)].append(p)
    out: List[BucketSeries] = []
    for key in sorted(groups.keys()):
        out.append(
            BucketSeries(bucket_start=key, aggregate=_aggregate_points(groups[key]))
        )
    return out


def _fmt_ts_short(dt: datetime) -> str:
    dt = _aware_utc(dt)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _streak_anomalies_for_device(
    device_id: str,
    sorted_points: List[SensorDataResponse],
    *,
    cfg: AlarmConfig,
    k: int,
) -> List[AnomalyItem]:
    anomalies: List[AnomalyItem] = []
    specs = [
        ("temperature", cfg.temperature_threshold, "temp_streak_high", "℃"),
        ("humidity", cfg.humidity_threshold, "humidity_streak_high", "%RH"),
        ("light", cfg.light_threshold, "light_streak_high", "lx"),
    ]

    for attr, threshold, rule_id, unit in specs:
        i = 0
        n = len(sorted_points)
        while i < n:
            v = getattr(sorted_points[i], attr)
            if v <= threshold:
                i += 1
                continue
            j = i
            while j < n and getattr(sorted_points[j], attr) > threshold:
                j += 1
            length = j - i
            if length >= k:
                seg = sorted_points[i:j]
                vals = [getattr(p, attr) for p in seg]
                start_t = _aware_utc(seg[0].timestamp)
                end_t = _aware_utc(seg[-1].timestamp)
                peak_v = max(vals)
                mzh = _METRIC_ZH[attr]
                detail = (
                    f"设备「{device_id}」{_fmt_ts_short(start_t)} 至 {_fmt_ts_short(end_t)}："
                    f"{mzh}连续{length}个点高于阈值 {threshold}{unit}，"
                    f"这段里最高读数 {round(peak_v, 2)}{unit}。"
                )
                anomalies.append(
                    AnomalyItem(
                        device_id=device_id,
                        metric=attr,  # type: ignore[arg-type]
                        rule_id=rule_id,
                        start_time=start_t.isoformat(),
                        end_time=end_t.isoformat(),
                        peak=round(peak_v, 4),
                        threshold=threshold,
                        detail_zh=detail,
                    )
                )
            i = j
    return anomalies


def _collect_anomalies(
    points: List[SensorDataResponse], cfg: AlarmConfig, k: int
) -> List[AnomalyItem]:
    if not points:
        return []
    ordered = sorted(points, key=lambda p: (p.device_id, p.timestamp))
    all_a: List[AnomalyItem] = []
    for device_id, grp in groupby(ordered, key=lambda p: p.device_id):
        dev_list = list(grp)
        dev_list.sort(key=lambda p: p.timestamp)
        all_a.extend(
            _streak_anomalies_for_device(device_id, dev_list, cfg=cfg, k=k)
        )
    return all_a


def _derive_summary_code(
    insufficient: bool, anomalies: List[AnomalyItem]
) -> Tuple[str, str]:
    if insufficient:
        return "insufficient_data", "数据条数不够"
    if not anomalies:
        return "stable", "未发现连续超阈"
    types = {a.rule_id for a in anomalies}
    if len(types) == 1:
        r = next(iter(types))
        if r == "temp_streak_high":
            return "temp_spike", "温度曾连续超阈"
        if r == "humidity_streak_high":
            return "humidity_high", "湿度曾连续超阈"
        if r == "light_streak_high":
            return "light_high", "光照曾连续超阈"
    return "mixed", "多项指标曾连续超阈"


def _build_lines_plain(
    *,
    out_device: str,
    start_time: datetime,
    end_time: datetime,
    sample_in: int,
    sample_used: int,
    agg: dict[str, AggregateMetric],
    cfg: AlarmConfig,
    k: int,
    insufficient: bool,
    min_required: int,
    summary_label: str,
) -> List[str]:
    dev_txt = "全部设备合并统计" if out_device == "all" else f"仅设备「{out_device}」"
    lines = [
        f"查询时段：{start_time.isoformat()} ～ {end_time.isoformat()}（与接口入参一致）。",
        f"统计范围：{dev_txt}。",
        f"该时段从数据库读到 {sample_in} 条记录；参与计算 {sample_used} 条。",
    ]

    t, h, l_ = agg["temperature"], agg["humidity"], agg["light"]
    if t.count:
        med_t = t.median if t.median is not None else "—"
        lines.append(
            f"温度（℃）：最低 {t.min}，最高 {t.max}，平均 {t.avg}，中位数 {med_t}，共 {t.count} 个点。"
        )
    else:
        lines.append("温度（℃）：该时段无数据。")
    if h.count:
        med_h = h.median if h.median is not None else "—"
        lines.append(
            f"湿度（%RH）：最低 {h.min}，最高 {h.max}，平均 {h.avg}，中位数 {med_h}，共 {h.count} 个点。"
        )
    else:
        lines.append("湿度（%RH）：该时段无数据。")
    if l_.count:
        med_l = l_.median if l_.median is not None else "—"
        lines.append(
            f"光照（lx）：最低 {l_.min}，最高 {l_.max}，平均 {l_.avg}，中位数 {med_l}，共 {l_.count} 个点。"
        )
    else:
        lines.append("光照（lx）：该时段无数据。")

    lines.append(
        "判定规则（与当前告警阈值配置一致）："
        f"温度高于 {cfg.temperature_threshold}℃，"
        f"或湿度高于 {cfg.humidity_threshold}%RH，"
        f"或光照高于 {cfg.light_threshold}lx，"
        f"且连续至少 {k} 个采样点，则记为下方「异常片段」中的一段。"
    )

    if insufficient:
        lines.append(
            f"因参与计算的点数少于 {min_required} 条，本次不做「连续超阈」判定。"
            f"结论：{summary_label}。"
        )
    else:
        lines.append(f"结论摘要：{summary_label}。")

    return lines


def _build_chart_points(
    filtered_sorted: List[SensorDataResponse],
) -> List[ChartPoint]:
    if not filtered_sorted:
        return []
    capped, _ = _uniform_downsample(
        filtered_sorted, settings.ANALYSIS_CHART_MAX_POINTS
    )
    out: List[ChartPoint] = []
    for p in capped:
        ts = _aware_utc(p.timestamp)
        out.append(
            ChartPoint(
                time_ms=int(ts.timestamp() * 1000),
                time_iso=ts.isoformat(),
                temperature=round(p.temperature, 4),
                humidity=round(p.humidity, 4),
                light=round(p.light, 4),
            )
        )
    return out


def _build_chart_bands(anomalies: List[AnomalyItem]) -> List[ChartAnomalyBand]:
    bands: List[ChartAnomalyBand] = []
    for a in anomalies:
        bands.append(
            ChartAnomalyBand(
                start_ms=_iso_to_ms(a.start_time),
                end_ms=_iso_to_ms(a.end_time),
                label_zh=f"{_METRIC_ZH[a.metric]}偏高",
                metric=a.metric,
            )
        )
    return bands


def _linear_regression(xs: List[float], ys: List[float]) -> Tuple[float, float]:
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    var_x = sum((x - mx) ** 2 for x in xs)
    if var_x < 1e-12:
        return my, 0.0
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = cov / var_x
    a = my - b * mx
    return a, b


def _temperature_forecast(
    sorted_filtered: List[SensorDataResponse],
) -> Optional[TemperatureForecast]:
    if not sorted_filtered:
        return None
    basis_n = min(len(sorted_filtered), settings.ANALYSIS_FORECAST_BASIS_POINTS)
    pts = sorted_filtered[-basis_n:]
    last_dt = _aware_utc(pts[-1].timestamp)
    t0 = _aware_utc(pts[0].timestamp).timestamp()
    xs = [_aware_utc(p.timestamp).timestamp() - t0 for p in pts]
    ys = [p.temperature for p in pts]
    a, b = _linear_regression(xs, ys)
    # b 为 ℃/秒；限制为约 ±ANALYSIS_FORECAST_MAX_SLOPE_C_PER_HOUR ℃/小时
    b_max = settings.ANALYSIS_FORECAST_MAX_SLOPE_C_PER_HOUR / 3600.0
    if b > b_max:
        b = b_max
    elif b < -b_max:
        b = -b_max
    a = sum(ys) / len(ys) - b * (sum(xs) / len(xs))

    last_temp = float(ys[-1])
    tau = max(1.0, settings.ANALYSIS_FORECAST_DAMPING_TAU_HOURS)

    hours: List[ForecastHourPoint] = []
    for h in range(1, 25):
        future_dt = last_dt + timedelta(hours=h)
        x_future = future_dt.timestamp() - t0
        y_linear = a + b * x_future
        # 直线外推在物理上不可靠：越远越削弱与「最后实测」的偏差，避免 24 小时单调暴涨/暴跌
        w = math.exp(-float(h) / tau)
        y_hat = last_temp + (y_linear - last_temp) * w
        hours.append(
            ForecastHourPoint(
                hours_after_last_sample=h,
                time_iso=future_dt.isoformat(),
                temperature_c=round(y_hat, 2),
            )
        )

    return TemperatureForecast(
        based_on_points=len(pts),
        anchor_time_iso=last_dt.isoformat(),
        last_observed_temperature_c=round(last_temp, 2),
        horizon_hours=len(hours),
        method="linear_regression_damped",
        method_zh=(
            "先用最近若干条数据拟合温度随时间的变化趋势，再限制每小时升降幅度；"
            f"越远时刻越减弱该趋势，使预测逐渐靠近最后一次实测（约 {tau:.0f} 小时衰减尺度），避免直线无限延伸。"
        ),
        disclaimer_zh=(
            "此为极简数学外推，不是天气预报；若历史段本身在升温，前几小时可能仍偏高，"
            "但远期会被拉回最后实测附近，不代表一定会一直上升或下降。"
        ),
        hours=hours,
    )


def _extract_hourly_temps(
    sorted_points: List[SensorDataResponse], n_hours: int
) -> List[float]:
    """从传感器数据中提取最近 n_hours 个整小时的平均温度。"""
    if not sorted_points:
        return []
    last_dt = _aware_utc(sorted_points[-1].timestamp)
    hourly: dict[int, List[float]] = defaultdict(list)
    for p in reversed(sorted_points):
        ts = _aware_utc(p.timestamp)
        hours_ago = (last_dt - ts).total_seconds() / 3600.0
        if hours_ago > n_hours:
            break
        bucket = int(hours_ago)
        if bucket < n_hours:
            hourly[bucket].append(p.temperature)
    result: List[float] = []
    for h in range(n_hours - 1, -1, -1):
        if h in hourly:
            result.append(sum(hourly[h]) / len(hourly[h]))
    return result


def _temperature_forecast_lstm(
    sorted_filtered: List[SensorDataResponse],
) -> Optional[TemperatureForecast]:
    """使用 LSTM 模型预测下 1 小时温度，失败时回退到线性回归。"""
    if not sorted_filtered:
        return None

    window = settings.FORECAST_LSTM_WINDOW_HOURS
    hourly_temps = _extract_hourly_temps(sorted_filtered, window)

    if len(hourly_temps) < window:
        logger.info("LSTM: 小时级数据不足 %d/%d，回退线性回归", len(hourly_temps), window)
        return _temperature_forecast(sorted_filtered)

    try:
        from ml.predictor import TemperaturePredictor

        predictor = TemperaturePredictor.get_instance(
            settings.FORECAST_LSTM_MODEL_PATH
        )
        temps_24 = predictor.predict_rollout(hourly_temps, steps=24)
    except Exception:
        logger.warning("LSTM 预测失败，回退线性回归", exc_info=True)
        return _temperature_forecast(sorted_filtered)

    last_dt = _aware_utc(sorted_filtered[-1].timestamp)
    hours_out: List[ForecastHourPoint] = []
    for h, temp_c in enumerate(temps_24, start=1):
        future_dt = last_dt + timedelta(hours=h)
        hours_out.append(
            ForecastHourPoint(
                hours_after_last_sample=h,
                time_iso=future_dt.isoformat(),
                temperature_c=temp_c,
            )
        )

    last_observed_temp = round(float(sorted_filtered[-1].temperature), 2)

    return TemperatureForecast(
        based_on_points=len(sorted_filtered),
        anchor_time_iso=last_dt.isoformat(),
        last_observed_temperature_c=last_observed_temp,
        horizon_hours=len(hours_out),
        method="lstm",
        method_zh=(
            f"基于与训练一致的 LSTM（窗口 {window} 小时、与 ml_training/config 中 "
            f"WINDOW_SIZE/HIDDEN_SIZE/NUM_LAYERS 对齐），先把时段内采样聚合为相对末条样本的逐小时均值，"
            f"再对下一步做推理；第 2～24 小时在模型外以自回归方式滚动，越远不确定性越大。"
        ),
        disclaimer_zh=(
            "模型在 Open-Meteo 历史气温上训练，与现场传感器分布可能不同；"
            "自回归多步仅供参考，不能替代天气预报。"
        ),
        hours=hours_out,
    )


class AnalysisService:
    def __init__(
        self,
        *,
        sensor_repo: SensorRepository,
        alarm_service: AlarmService,
    ) -> None:
        self._sensor_repo = sensor_repo
        self._alarm_service = alarm_service

    async def get_environment_summary(
        self,
        *,
        start_time: datetime,
        end_time: datetime,
        device_id: Optional[str] = None,
        bucket: Optional[str] = None,
    ) -> EnvironmentSummaryResponse:
        raw = await self._sensor_repo.get_history(start_time, end_time)
        if device_id:
            filtered = [p for p in raw if p.device_id == device_id]
            out_device = device_id
        else:
            filtered = raw
            out_device = "all"

        filtered_sorted = sorted(filtered, key=lambda p: p.timestamp)
        sample_in = len(filtered_sorted)

        working, downsampled = _uniform_downsample(
            filtered_sorted, settings.ANALYSIS_MAX_POINTS
        )
        sample_used = len(working)

        agg = _aggregate_points(working)
        point_count = agg["temperature"].count

        buckets: List[BucketSeries] = []
        if bucket == "1h" and working:
            buckets = _build_hourly_buckets(working)

        cfg = await self._alarm_service.get_config()
        k = max(1, settings.ANALYSIS_STREAK_POINTS)
        min_required = settings.ANALYSIS_MIN_POINTS

        insufficient = point_count < min_required
        anomalies: List[AnomalyItem] = []
        if not insufficient:
            anomalies = _collect_anomalies(working, cfg, k)

        summary_code, summary_label = _derive_summary_code(insufficient, anomalies)

        lines_plain = _build_lines_plain(
            out_device=out_device,
            start_time=start_time,
            end_time=end_time,
            sample_in=sample_in,
            sample_used=sample_used,
            agg=agg,
            cfg=cfg,
            k=k,
            insufficient=insufficient,
            min_required=min_required,
            summary_label=summary_label,
        )
        if downsampled:
            lines_plain.insert(
                3,
                f"说明：从 {sample_in} 条里均匀抽取 {sample_used} 条参与计算，"
                f"下面的最低/最高/平均/中位数与异常判定都基于抽取后的数据。",
            )

        summary_hints = [
            lines_plain[2],
            lines_plain[3] if len(lines_plain) > 3 else "",
            lines_plain[-1],
        ]
        summary_hints = [x for x in summary_hints if x]

        thresholds = ThresholdSnapshot(
            temperature_c=cfg.temperature_threshold,
            humidity_percent=cfg.humidity_threshold,
            light_lux=cfg.light_threshold,
        )

        chart_points = _build_chart_points(filtered_sorted)
        chart_bands = (
            [] if insufficient else _build_chart_bands(anomalies)
        )
        if settings.FORECAST_USE_LSTM:
            forecast = _temperature_forecast_lstm(filtered_sorted)
        else:
            forecast = _temperature_forecast(filtered_sorted)

        return EnvironmentSummaryResponse(
            device_id=out_device,
            window=TimeWindow(start=start_time.isoformat(), end=end_time.isoformat()),
            aggregate=agg,
            buckets=buckets,
            anomalies=[] if insufficient else anomalies,
            summary_code=summary_code,
            summary_label=summary_label,
            summary_hints=summary_hints,
            lines_plain=lines_plain,
            thresholds=thresholds,
            sample_count_in_window=sample_in,
            sample_count_used=sample_used,
            streak_points_required=k,
            chart_points=chart_points,
            chart_anomaly_bands=chart_bands,
            temperature_forecast=forecast,
            downsampled=downsampled,
            framework=False,
        )

    async def run_environment_analysis(
        self,
        *,
        start_time: datetime,
        end_time: datetime,
        device_id: Optional[str] = None,
        bucket: Optional[str] = None,
    ) -> EnvironmentSummaryResponse:
        return await self.get_environment_summary(
            start_time=start_time,
            end_time=end_time,
            device_id=device_id,
            bucket=bucket,
        )

    def build_anomalies_csv(self, summary: EnvironmentSummaryResponse) -> str:
        lines = [
            "rule_id,metric,start_time,end_time,peak,threshold,device_id,detail_zh",
        ]
        for a in summary.anomalies:
            peak = "" if a.peak is None else str(a.peak)
            thr = "" if a.threshold is None else str(a.threshold)
            detail = (a.detail_zh or "").replace('"', '""')
            lines.append(
                f"{a.rule_id},{a.metric},{a.start_time},{a.end_time},"
                f"{peak},{thr},{a.device_id},\"{detail}\""
            )
        return "\n".join(lines)

    def build_full_series_csv(self, rows: List[SensorDataResponse]) -> str:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["时间(ISO)", "设备编号", "温度℃", "湿度%RH", "光照lx"])
        for p in sorted(rows, key=lambda x: x.timestamp):
            ts = _aware_utc(p.timestamp)
            w.writerow(
                [
                    ts.isoformat(),
                    p.device_id,
                    p.temperature,
                    p.humidity,
                    p.light,
                ]
            )
        return buf.getvalue()

    def build_full_export_json(self, summary: EnvironmentSummaryResponse) -> str:
        def metric_block(m: AggregateMetric) -> dict[str, Any]:
            return {
                "sample_count": m.count,
                "min": m.min,
                "max": m.max,
                "mean": m.avg,
                "median": m.median,
            }

        agg = summary.aggregate
        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "kind": "environment_analysis_full",
            "time_range": {
                "start": summary.window.start,
                "end": summary.window.end,
            },
            "device_scope": summary.device_id,
            "metrics": {
                "temperature_c": metric_block(agg["temperature"]),
                "humidity_percent": metric_block(agg["humidity"]),
                "light_lux": metric_block(agg["light"]),
            },
            "thresholds": summary.thresholds.model_dump() if summary.thresholds else None,
            "anomalies": [a.model_dump() for a in summary.anomalies],
            "temperature_forecast_24h": (
                summary.temperature_forecast.model_dump()
                if summary.temperature_forecast
                else None
            ),
            "chart_series_sample": [p.model_dump() for p in summary.chart_points],
            "flags": {
                "downsampled_for_stats": summary.downsampled,
                "internal_summary_code": summary.summary_code,
            },
            "display_zh": {
                "headline": summary.summary_label,
                "lines": summary.lines_plain,
            },
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def build_anomalies_only_json(
        self, summary: EnvironmentSummaryResponse
    ) -> str:
        payload = {
            "schema_version": "1.0",
            "kind": "environment_anomalies_only",
            "time_range": {
                "start": summary.window.start,
                "end": summary.window.end,
            },
            "device_scope": summary.device_id,
            "anomalies": [a.model_dump() for a in summary.anomalies],
            "display_zh": {
                "headline": summary.summary_label,
            },
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    async def export_anomalies_csv(
        self,
        *,
        start_time: datetime,
        end_time: datetime,
        device_id: Optional[str] = None,
    ) -> str:
        summary = await self.get_environment_summary(
            start_time=start_time,
            end_time=end_time,
            device_id=device_id,
            bucket=None,
        )
        rows = summary.anomalies[: settings.ANALYSIS_MAX_ANOMALY_EXPORT_ROWS]
        slim = summary.model_copy(update={"anomalies": rows})
        return self.build_anomalies_csv(slim)

    async def export_unified(
        self,
        *,
        start_time: datetime,
        end_time: datetime,
        device_id: Optional[str] = None,
        export_format: str,
        scope: str,
    ) -> Tuple[str, str, str]:
        """
        Returns (body, media_type, filename_suffix).
        export_format: json | csv
        scope: anomalies | full
        """
        raw = await self._sensor_repo.get_history(start_time, end_time)
        if device_id:
            filtered = [p for p in raw if p.device_id == device_id]
        else:
            filtered = raw

        summary = await self.get_environment_summary(
            start_time=start_time,
            end_time=end_time,
            device_id=device_id,
            bucket=None,
        )

        if export_format == "json":
            if scope == "anomalies":
                body = self.build_anomalies_only_json(summary)
                return body, "application/json; charset=utf-8", "env_anomalies_only.json"
            body = self.build_full_export_json(summary)
            return body, "application/json; charset=utf-8", "env_analysis_full.json"

        if scope == "anomalies":
            rows = summary.anomalies[: settings.ANALYSIS_MAX_ANOMALY_EXPORT_ROWS]
            slim = summary.model_copy(update={"anomalies": rows})
            body = self.build_anomalies_csv(slim)
            return body, "text/csv; charset=utf-8", "env_anomalies.csv"
        body = self.build_full_series_csv(filtered)
        return body, "text/csv; charset=utf-8", "env_all_samples.csv"
