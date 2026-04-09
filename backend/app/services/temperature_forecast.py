"""
温度预测（仅后端逻辑）：阻尼线性 24h 与可选 LSTM 自回归 24 步。

供环境分析 `temperature_forecast` 使用；监测页 2h 时间轴的拟合仍用本模块的 `linear_regression` / `aware_utc`。
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from app.core.config import settings
from app.core.timeutil import format_instant_rfc3339_utc_z
from app.schemas.analysis import ForecastHourPoint, TemperatureForecast
from app.schemas.sensor import SensorDataResponse

logger = logging.getLogger(__name__)


def aware_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def linear_regression(xs: List[float], ys: List[float]) -> Tuple[float, float]:
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


def _extract_hourly_temps(sorted_points: List[SensorDataResponse], n_hours: int) -> List[float]:
    """相对末条样本，最近 n_hours 个整点小时的平均温度（旧→新）。"""
    if not sorted_points:
        return []
    last_dt = aware_utc(sorted_points[-1].timestamp)
    hourly: dict[int, List[float]] = defaultdict(list)
    for p in reversed(sorted_points):
        ts = aware_utc(p.timestamp)
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


def temperature_forecast_damped_linear(
    sorted_filtered: List[SensorDataResponse],
) -> Optional[TemperatureForecast]:
    """最近若干点线性拟合 + 斜率限幅 + 相对末条实测的指数阻尼，输出 +1h…+24h。"""
    if not sorted_filtered:
        return None
    basis_n = min(len(sorted_filtered), settings.ANALYSIS_FORECAST_BASIS_POINTS)
    pts = sorted_filtered[-basis_n:]
    last_dt = aware_utc(pts[-1].timestamp)
    t0 = aware_utc(pts[0].timestamp).timestamp()
    xs = [aware_utc(p.timestamp).timestamp() - t0 for p in pts]
    ys = [p.temperature for p in pts]
    a, b = linear_regression(xs, ys)
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
        w = math.exp(-float(h) / tau)
        y_hat = last_temp + (y_linear - last_temp) * w
        hours.append(
            ForecastHourPoint(
                hours_after_last_sample=h,
                time_iso=format_instant_rfc3339_utc_z(future_dt),
                temperature_c=round(y_hat, 2),
            )
        )

    return TemperatureForecast(
        based_on_points=len(pts),
        anchor_time_iso=format_instant_rfc3339_utc_z(last_dt),
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


def temperature_forecast_lstm_rollout(
    sorted_filtered: List[SensorDataResponse],
) -> Optional[TemperatureForecast]:
    """LSTM 小时窗口 → 自回归 24 步；失败或数据不足则回退阻尼线性。"""
    if not sorted_filtered:
        return None

    window = settings.FORECAST_LSTM_WINDOW_HOURS
    hourly_temps = _extract_hourly_temps(sorted_filtered, window)

    if len(hourly_temps) < window:
        logger.info("LSTM: 小时级数据不足 %d/%d，回退线性回归", len(hourly_temps), window)
        return temperature_forecast_damped_linear(sorted_filtered)

    try:
        from ml.predictor import TemperaturePredictor

        predictor = TemperaturePredictor.get_instance(settings.FORECAST_LSTM_MODEL_PATH)
        temps_24 = predictor.predict_rollout(hourly_temps, steps=24)
    except Exception:
        logger.warning("LSTM 预测失败，回退线性回归", exc_info=True)
        return temperature_forecast_damped_linear(sorted_filtered)

    last_dt = aware_utc(sorted_filtered[-1].timestamp)
    hours_out: List[ForecastHourPoint] = []
    for h, temp_c in enumerate(temps_24, start=1):
        future_dt = last_dt + timedelta(hours=h)
        hours_out.append(
            ForecastHourPoint(
                hours_after_last_sample=h,
                time_iso=format_instant_rfc3339_utc_z(future_dt),
                temperature_c=temp_c,
            )
        )

    last_observed_temp = round(float(sorted_filtered[-1].temperature), 2)

    return TemperatureForecast(
        based_on_points=len(sorted_filtered),
        anchor_time_iso=format_instant_rfc3339_utc_z(last_dt),
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


def compute_temperature_forecast(
    sorted_filtered: List[SensorDataResponse],
) -> Optional[TemperatureForecast]:
    """
    环境分析唯一入口：按配置选择 LSTM 自回归或阻尼线性。

    入参须为按时间升序的传感器点（与窗口内最后一条为 anchor 一致）。
    """
    if not sorted_filtered:
        return None
    if settings.FORECAST_USE_LSTM:
        return temperature_forecast_lstm_rollout(sorted_filtered)
    return temperature_forecast_damped_linear(sorted_filtered)
