"""
向 SQLite 写入若干条演示用传感器数据，便于无 MQTT 时联调 history / 环境分析。

用法（在 backend 目录下，与 app.db 路径一致）：
  .venv\\Scripts\\python.exe scripts\\seed_sensor_demo.py

可选环境变量：与主应用相同，默认使用 SQLITE_URL=sqlite+aiosqlite:///./app.db
"""

from __future__ import annotations

import asyncio
import os
import sys

# 保证以 backend 为 cwd 时能 import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone

from app.core.database import dispose_db, get_session_factory, init_db
from app.repositories.sensor_repo import SensorRepository


async def main() -> None:
    await init_db()
    factory = get_session_factory()
    repo = SensorRepository(factory)

    now = datetime.now(timezone.utc)
    device_id = "demo_device"
    # 过去 24 小时内：多数正常，中间一段连续高温（>30）便于触发 temp_spike
    samples: list[tuple[float, float, float, datetime]] = []
    for i in range(48):
        ts = now - timedelta(minutes=30 * (47 - i))
        if 20 <= i <= 24:
            temp = 32.0 + (i - 20) * 0.3
        else:
            temp = 22.0 + (i % 5) * 0.2
        hum = 48.0 + (i % 7)
        lux = 200.0 + i * 10
        samples.append((temp, hum, lux, ts))

    for temp, hum, lux, ts in samples:
        await repo.ingest_reading(device_id, temp, hum, lux, ts)

    print(f"已写入 {len(samples)} 条，device_id={device_id!r}，时间范围约过去 24h。")
    print("环境分析页：设备 ID 可填 demo_device，或留空（全设备）。")
    await dispose_db()


if __name__ == "__main__":
    asyncio.run(main())
