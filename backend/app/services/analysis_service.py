"""环境分析：统计（含中位数）、异常、折线图数据、24h 温度预测、导出。"""

from __future__ import annotations

import csv
import io
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from itertools import groupby
from typing import Any, List, Optional, Tuple

from app.core.config import settings
from app.core.timeutil import format_instant_beijing_wall_csv, format_instant_rfc3339_utc_z

logger = logging.getLogger(__name__)
from app.repositories.environment_anomaly_repo import EnvironmentAnomalyRepository
from app.repositories.sensor_repo import SensorRepository
from app.schemas.alarm import AlarmConfig
from app.schemas.analysis import (
    AggregateMetric,
    AnomalyItem,
    BucketSeries,
    ChartAnomalyBand,
    ChartPoint,
    EnvironmentSummaryResponse,
    ThresholdSnapshot,
    TimeWindow,
)
from app.schemas.sensor import SensorDataResponse
from app.services.alarm_service import AlarmService
from app.services.temperature_forecast import compute_temperature_forecast

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
    return format_instant_rfc3339_utc_z(floored)


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


def _peak_in_range_full_series(
    full_series: List[SensorDataResponse],
    *,
    attr: str,
    t_start: datetime,
    t_end: datetime,
) -> Optional[float]:
    """在完整序列中取 [t_start, t_end] 内该指标最大值（与 downsample 后的 streak 时段对齐）。"""
    a0 = _aware_utc(t_start)
    a1 = _aware_utc(t_end)
    best: Optional[float] = None
    for p in full_series:
        ts = _aware_utc(p.timestamp)
        if ts < a0 or ts > a1:
            continue
        v = float(getattr(p, attr))
        if best is None or v > best:
            best = v
    return best


def _streak_anomalies_for_device(
    device_id: str,
    sorted_points: List[SensorDataResponse],
    *,
    cfg: AlarmConfig,
    k: int,
    full_series: Optional[List[SensorDataResponse]] = None,
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
                if full_series:
                    refined = _peak_in_range_full_series(
                        full_series,
                        attr=attr,
                        t_start=seg[0].timestamp,
                        t_end=seg[-1].timestamp,
                    )
                    if refined is not None:
                        peak_v = refined
                mzh = _METRIC_ZH[attr]
                detail = (
                    f"设备「{device_id}」{mzh}连续{length}个点高于阈值 {threshold}{unit}，"
                    f"这段里最高读数 {round(peak_v, 2)}{unit}。"
                )
                anomalies.append(
                    AnomalyItem(
                        device_id=device_id,
                        metric=attr,  # type: ignore[arg-type]
                        rule_id=rule_id,
                        start_time=format_instant_rfc3339_utc_z(start_t),
                        end_time=format_instant_rfc3339_utc_z(end_t),
                        peak=round(peak_v, 4),
                        threshold=threshold,
                        detail_zh=detail,
                    )
                )
            i = j
    return anomalies


def _collect_anomalies(
    working: List[SensorDataResponse],
    cfg: AlarmConfig,
    k: int,
    *,
    full_sorted: List[SensorDataResponse],
) -> List[AnomalyItem]:
    """
    ``working`` 可能经均匀下采样，仅用于判定连续超阈；峰值在 ``full_sorted`` 同设备、
    与该 streak 起止时刻对齐的区间内取 max，避免落库峰值低于真实采样尖峰。
    """
    if not working:
        return []
    full_by_dev: dict[str, List[SensorDataResponse]] = defaultdict(list)
    for p in full_sorted:
        full_by_dev[p.device_id].append(p)
    for lst in full_by_dev.values():
        lst.sort(key=lambda p: p.timestamp)

    ordered = sorted(working, key=lambda p: (p.device_id, p.timestamp))
    all_a: List[AnomalyItem] = []
    for device_id, grp in groupby(ordered, key=lambda p: p.device_id):
        dev_list = list(grp)
        dev_list.sort(key=lambda p: p.timestamp)
        all_a.extend(
            _streak_anomalies_for_device(
                device_id,
                dev_list,
                cfg=cfg,
                k=k,
                full_series=full_by_dev.get(device_id),
            )
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
        f"查询时段：{format_instant_rfc3339_utc_z(start_time)} ～ {format_instant_rfc3339_utc_z(end_time)}（与接口入参一致）。",
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
                time_iso=format_instant_rfc3339_utc_z(ts),
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


class AnalysisService:
    def __init__(
        self,
        *,
        sensor_repo: SensorRepository,
        alarm_service: AlarmService,
        environment_anomaly_repo: Optional[EnvironmentAnomalyRepository] = None,
    ) -> None:
        self._sensor_repo = sensor_repo
        self._alarm_service = alarm_service
        self._environment_anomaly_repo = environment_anomaly_repo

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
            anomalies = _collect_anomalies(working, cfg, k, full_sorted=filtered_sorted)

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
        forecast = compute_temperature_forecast(filtered_sorted)

        # 不在此持久化 environment_anomalies：本方法在「环境监测」等拉取分析时频繁调用，
        # 连续超阈判定基于窗口内全量/抽样点，易与后台模拟采样或历史脏点形成伪 streak，每次进页误插入库。
        # 库表仅由 AlarmService 实时边沿超阈（与 WebSocket 弹窗同源）写入。

        return EnvironmentSummaryResponse(
            device_id=out_device,
            window=TimeWindow(
                start=format_instant_rfc3339_utc_z(start_time),
                end=format_instant_rfc3339_utc_z(end_time),
            ),
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

    async def get_monitoring_anomalies_recent(
        self,
        *,
        hours: float = 24.0,
        device_id: Optional[str] = None,
    ) -> "MonitoringAnomaliesResponse":
        """环境监测页：过去 24h 内（可缩短）异常片段列表。"""
        from app.schemas.monitoring import MonitoringAnomaliesResponse

        now = datetime.now(timezone.utc)
        h = min(max(hours, 1.0), 24.0)
        summary = await self.get_environment_summary(
            start_time=now - timedelta(hours=h),
            end_time=now,
            device_id=device_id if device_id and device_id.strip() else None,
            bucket=None,
        )
        return MonitoringAnomaliesResponse(
            anomalies=summary.anomalies,
            summary_label=summary.summary_label,
            summary_code=summary.summary_code,
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
        w.writerow(["时间(北京时间)", "设备编号", "温度℃", "湿度%RH", "光照lx"])
        for p in sorted(rows, key=lambda x: x.timestamp):
            ts = _aware_utc(p.timestamp)
            w.writerow(
                [
                    format_instant_beijing_wall_csv(ts),
                    p.device_id,
                    p.temperature,
                    p.humidity,
                    p.light,
                ]
            )
        return "\ufeff" + buf.getvalue()

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
