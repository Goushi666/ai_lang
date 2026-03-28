"""环境监测页：2 小时温度时间轴（实测 + LSTM/线性推算）。"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.core.config import settings
from app.repositories.sensor_repo import SensorRepository
from app.schemas.monitoring import (
    MonitoringTemperatureTimelineResponse,
    TimelineBandPoint,
    TimelinePoint,
)
from app.schemas.sensor import SensorDataResponse
from app.services.analysis_service import _aware_utc, _linear_regression

logger = logging.getLogger(__name__)


def extract_hourly_temps_before_anchor(
    sorted_points: List[SensorDataResponse], n_hours: int, anchor: datetime
) -> List[float]:
    """相对 anchor 时刻之前 n 个小时桶的均值温度（与 LSTM 训练口径一致）。"""
    anchor = _aware_utc(anchor)
    hourly: dict[int, List[float]] = defaultdict(list)
    for p in reversed(sorted_points):
        ts = _aware_utc(p.timestamp)
        if ts > anchor:
            continue
        hours_ago = (anchor - ts).total_seconds() / 3600.0
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


def _fill_none_forward_backward(vals: List[Optional[float]]) -> List[float]:
    n = len(vals)
    out: List[Optional[float]] = list(vals)
    last: Optional[float] = None
    for i in range(n):
        if out[i] is not None:
            last = out[i]
        elif last is not None:
            out[i] = last
    last = None
    for i in range(n - 1, -1, -1):
        if out[i] is not None:
            last = out[i]
        elif last is not None:
            out[i] = last
    default = 20.0
    for i in range(n):
        if out[i] is None:
            out[i] = default
    return [float(x) for x in out]


def _cubic_bezier_scalar(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    u = 1.0 - t
    return u**3 * p0 + 3 * u**2 * t * p1 + 3 * u * t**2 * p2 + t**3 * p3


def _std_past_actual_temps(past_actual: List[TimelinePoint]) -> float:
    if len(past_actual) < 2:
        return 0.28
    ys = [p.temperature_c for p in past_actual]
    m = sum(ys) / len(ys)
    v = sum((y - m) ** 2 for y in ys) / len(ys)
    return math.sqrt(v)


def _future_hour_temperatures(
    n_points: int,
    v_start: float,
    v_end: float,
    roll_future: List[float],
    past_actual: List[TimelinePoint],
) -> List[float]:
    """
    未来 1 小时网格上的温度序列。
    - LSTM 可用且有多步 rollout 时：三次贝塞尔，端点为 v_start 与第一步预测，控制点吸收第 2、3 小时趋势。
    - 否则：端点线性插值 + 基于近 1h 实测波动的阻尼正弦（端点仍为 v_start / v_end）。
    """
    if n_points <= 1:
        return [round(float(v_start), 2)]
    if len(roll_future) >= 2:
        p0 = float(v_start)
        p3 = float(v_end)
        r1 = float(roll_future[1])
        r2 = float(roll_future[2]) if len(roll_future) > 2 else r1
        seg = p3 - p0
        d12 = r1 - p3
        d23 = r2 - r1
        st = seg / 3.0
        p1 = p0 + st + 0.28 * d12
        p2 = p3 - st + 0.32 * d23 + 0.1 * d12
        out: List[float] = []
        for i in range(n_points):
            t = i / (n_points - 1)
            out.append(round(_cubic_bezier_scalar(p0, p1, p2, p3, t), 2))
        return out
    std_a = _std_past_actual_temps(past_actual)
    amp = min(0.55, max(0.1, std_a * 0.5))
    span = abs(v_end - v_start)
    if span > 0.4:
        amp *= max(0.2, 1.0 - min(1.0, span / 3.5))
    out2: List[float] = []
    for i in range(n_points):
        alpha = i / (n_points - 1)
        lin = v_start + (v_end - v_start) * alpha
        out2.append(round(lin + amp * math.sin(math.pi * alpha), 2))
    return out2


def build_two_hour_temperature_timeline(
    sorted_points: List[SensorDataResponse], now: datetime
) -> MonitoringTemperatureTimelineResponse:
    now = _aware_utc(now)
    window = settings.FORECAST_LSTM_WINDOW_HOURS
    t_from = now - timedelta(hours=1)

    past_actual: List[TimelinePoint] = []
    for p in sorted_points:
        ts = _aware_utc(p.timestamp)
        if t_from <= ts <= now:
            past_actual.append(
                TimelinePoint(
                    time_ms=int(ts.timestamp() * 1000),
                    temperature_c=round(float(p.temperature), 2),
                )
            )

    n_grid = 13
    past_grid_ms: List[int] = []
    for i in range(n_grid):
        x = t_from + timedelta(seconds=i * (3600.0 / (n_grid - 1)))
        if x > now:
            x = now
        past_grid_ms.append(int(x.timestamp() * 1000))

    predictor_ok = False
    predictor = None
    if settings.FORECAST_USE_LSTM:
        try:
            from ml.predictor import TemperaturePredictor

            predictor = TemperaturePredictor.get_instance(
                settings.FORECAST_LSTM_MODEL_PATH
            )
            predictor_ok = True
        except Exception:
            logger.debug("监测时间轴：LSTM 未加载", exc_info=True)
            predictor_ok = False

    lstm_slots: List[Optional[float]] = [None] * n_grid
    for idx, x_ms in enumerate(past_grid_ms):
        x = datetime.fromtimestamp(x_ms / 1000.0, tz=timezone.utc)
        anchor = x - timedelta(hours=1)
        hourly = extract_hourly_temps_before_anchor(sorted_points, window, anchor)
        if predictor_ok and len(hourly) >= window:
            try:
                lstm_slots[idx] = round(float(predictor.predict(hourly)), 2)
            except Exception:
                pass

    lstm_hits = sum(1 for v in lstm_slots if v is not None)
    if lstm_hits >= max(6, n_grid // 2):
        filled = _fill_none_forward_backward(lstm_slots)
        past_predicted = [
            TimelinePoint(time_ms=past_grid_ms[i], temperature_c=filled[i])
            for i in range(n_grid)
        ]
        past_tag = "lstm"
        past_zh = "过去一小时推算温度为 LSTM 逐步回溯（锚点 = 目标时刻前 1 小时）；不足格已前后填补。"
    else:
        past_predicted = []
        if len(past_actual) >= 2:
            ap = sorted(
                [(p.time_ms / 1000.0, p.temperature_c) for p in past_actual],
                key=lambda z: z[0],
            )
            xs = [z[0] for z in ap]
            ys = [z[1] for z in ap]
            t0 = xs[0]
            a0, b0 = _linear_regression([x - t0 for x in xs], ys)
            past_predicted = [
                TimelinePoint(
                    time_ms=g,
                    temperature_c=round(a0 + b0 * (g / 1000.0 - t0), 2),
                )
                for g in past_grid_ms
            ]
        elif len(past_actual) == 1:
            v = past_actual[0].temperature_c
            past_predicted = [
                TimelinePoint(time_ms=g, temperature_c=v) for g in past_grid_ms
            ]
        past_tag = "linear_fallback"
        past_zh = "过去一小时推算温度为基于实测的线性拟合（LSTM 数据不足）。"

    future_grid_ms: List[int] = []
    for i in range(n_grid):
        x = now + timedelta(seconds=i * (3600.0 / (n_grid - 1)))
        future_grid_ms.append(int(x.timestamp() * 1000))

    v_start: Optional[float] = None
    if past_predicted:
        v_start = past_predicted[-1].temperature_c
    elif past_actual:
        v_start = past_actual[-1].temperature_c

    v_end: Optional[float] = None
    roll_future: List[float] = []
    hourly_now = extract_hourly_temps_before_anchor(sorted_points, window, now)
    if predictor_ok and len(hourly_now) >= window and predictor is not None:
        try:
            roll_future = [
                round(float(x), 2) for x in predictor.predict_rollout(list(hourly_now), 3)
            ]
            if roll_future:
                v_end = roll_future[0]
        except Exception:
            roll_future = []
            v_end = None
        if v_end is None:
            try:
                v_end = round(float(predictor.predict(hourly_now)), 2)
            except Exception:
                v_end = None

    if v_end is None and v_start is not None:
        ap = sorted(past_actual, key=lambda q: q.time_ms)
        if len(ap) >= 2:
            dt_sec = (ap[-1].time_ms - ap[-2].time_ms) / 1000.0
            if dt_sec > 1:
                slope = (ap[-1].temperature_c - ap[-2].temperature_c) / dt_sec
                v_end = round(v_start + slope * 3600.0, 2)
            else:
                v_end = v_start
        else:
            v_end = v_start
    if v_end is not None and v_start is None:
        v_start = v_end

    future_predicted: List[TimelinePoint] = []
    if v_start is not None and v_end is not None:
        nf = len(future_grid_ms)
        ftemps = _future_hour_temperatures(
            nf, v_start, v_end, roll_future, past_actual
        )
        future_predicted = [
            TimelinePoint(time_ms=future_grid_ms[i], temperature_c=ftemps[i])
            for i in range(nf)
        ]

    future_vals = [p.temperature_c for p in future_predicted]
    future_is_uniform = False
    future_hint_zh = ""
    future_band: List[TimelineBandPoint] = []
    band_scale = 0.55
    if predictor_ok and predictor is not None:
        try:
            band_scale = max(0.45, float(predictor.std) * 0.12)
        except Exception:
            band_scale = 0.55

    if len(future_vals) >= 2:
        lo_f, hi_f = min(future_vals), max(future_vals)
        if hi_f - lo_f < 0.15:
            future_is_uniform = True
            future_hint_zh = (
                "未来一小时推算沿多步趋势平滑过渡；若整体仍近似水平，说明模型多步变化也较小。"
                "绿色浅带为按模型尺度给出的参考波动范围。"
            )
            for p in future_predicted:
                future_band.append(
                    TimelineBandPoint(
                        time_ms=p.time_ms,
                        low_c=round(p.temperature_c - band_scale, 2),
                        high_c=round(p.temperature_c + band_scale, 2),
                    )
                )
    elif len(future_vals) == 1:
        future_is_uniform = True
        future_hint_zh = "未来推算仅一个时间点，仅供参考。"
        p0 = future_predicted[0]
        future_band.append(
            TimelineBandPoint(
                time_ms=p0.time_ms,
                low_c=round(p0.temperature_c - band_scale, 2),
                high_c=round(p0.temperature_c + band_scale, 2),
            )
        )

    if past_tag == "lstm" and v_end is not None and predictor_ok:
        method = "lstm"
        method_zh = (
            past_zh
            + " 未来一小时为 LSTM 自回归多步趋势经三次贝塞尔贴合起点与第 1 步终点"
            + "（步数越多不确定性越大）；无多步时退化为端点插值加小幅波动。"
        )
    elif future_predicted:
        method = "linear_fallback"
        method_zh = past_zh + " 未来一小时为端点插值并叠加近 1h 实测波动形的小幅修正（非 LSTM 多步）。"
    else:
        method = "insufficient"
        method_zh = "数据不足，无法绘制完整 2 小时推算曲线。"

    if future_hint_zh:
        method_zh = method_zh + " " + future_hint_zh

    return MonitoringTemperatureTimelineResponse(
        now_iso=now.isoformat(),
        method=method,
        method_zh=method_zh,
        past_actual=past_actual,
        past_predicted=past_predicted,
        future_predicted=future_predicted,
        future_is_uniform=future_is_uniform,
        future_hint_zh=future_hint_zh,
        future_band=future_band,
    )


class MonitoringService:
    def __init__(self, sensor_repo: SensorRepository) -> None:
        self._sensor_repo = sensor_repo

    async def get_temperature_timeline(
        self, *, device_id: Optional[str] = None
    ) -> MonitoringTemperatureTimelineResponse:
        now = datetime.now(timezone.utc)
        raw = await self._sensor_repo.get_history(now - timedelta(hours=10), now)
        if device_id and device_id.strip():
            d = device_id.strip()
            raw = [p for p in raw if p.device_id == d]
        sorted_pts = sorted(raw, key=lambda p: p.timestamp)
        return build_two_hour_temperature_timeline(sorted_pts, now)
