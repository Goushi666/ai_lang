"""
写入约 6 小时、温度约 31℃ 附近的模拟传感器数据（温湿度 + 光照）。

用法（在 backend 目录下执行）：
  .venv\\Scripts\\python.exe scripts\\seed_sensor_6h_31c.py
  .venv\\Scripts\\python.exe scripts\\seed_sensor_6h_31c.py --device-id pi_demo --hours 6 --step-minutes 5
"""

from __future__ import annotations

import argparse
import asyncio
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone

from app.core.database import dispose_db, get_session_factory, init_db
from app.repositories.sensor_repo import SensorRepository


async def main() -> None:
    p = argparse.ArgumentParser(description="生成约 31℃、指定时长内的模拟环境采样并写入 sensor_data")
    p.add_argument("--device-id", type=str, default="demo_device", help="设备 ID，默认 demo_device")
    p.add_argument("--hours", type=float, default=6.0, help="时间跨度（小时），默认 6")
    p.add_argument("--step-minutes", type=float, default=5.0, dest="step_minutes", help="采样间隔（分钟），默认 5")
    p.add_argument("--seed", type=int, default=42, help="随机种子，默认 42")
    args = p.parse_args()

    random.seed(args.seed)
    await init_db()
    factory = get_session_factory()
    repo = SensorRepository(factory)

    now = datetime.now(timezone.utc)
    step = timedelta(minutes=args.step_minutes)
    total_seconds = args.hours * 3600.0
    n_steps = max(1, int(total_seconds / (args.step_minutes * 60.0)))

    samples: list[tuple[float, float, float, datetime]] = []
    for i in range(n_steps):
        ts = now - timedelta(seconds=total_seconds) + step * i
        # 温度：均值约 31℃，缓慢起伏 ±约 1℃ + 小幅噪声
        phase = (i / max(n_steps - 1, 1)) * 2 * math.pi
        temp = 31.0 + 0.85 * math.sin(phase) + 0.35 * math.sin(phase * 2.3)
        temp += random.uniform(-0.25, 0.25)
        # 湿度：与温度略负相关，45%～58%
        hum = 52.0 - (temp - 31.0) * 1.2 + random.uniform(-2.0, 2.0)
        hum = max(40.0, min(65.0, hum))
        # 光照：6 小时内略变化（模拟环境光），约 280～720 lx
        light = 480.0 + 180.0 * math.sin(phase * 0.7) + random.uniform(-40.0, 40.0)
        light = max(50.0, light)
        samples.append((round(temp, 2), round(hum, 2), round(light, 2), ts))

    for temp, hum, lux, ts in samples:
        await repo.ingest_reading(args.device_id, temp, hum, lux, ts)

    t0, t1 = samples[0][3], samples[-1][3]
    print(
        f"已写入 {len(samples)} 条：device_id={args.device_id!r}，"
        f"约 {args.hours}h、间隔 {args.step_minutes}min，温度中心约 31℃"
    )
    print(f"时间范围（UTC）：{t0.isoformat()} ～ {t1.isoformat()}")
    await dispose_db()


if __name__ == "__main__":
    asyncio.run(main())
