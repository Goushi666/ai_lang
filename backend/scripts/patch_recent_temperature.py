"""
批量修改「最近若干小时」内传感器采样中的温度字段（SQLite sensor_data）。

用法（在 backend 目录下执行，与 app.db 路径一致）：
  .venv\\Scripts\\python.exe scripts\\patch_recent_temperature.py --mode fixed --value 26.5
  .venv\\Scripts\\python.exe scripts\\patch_recent_temperature.py --mode add --delta 2
  .venv\\Scripts\\python.exe scripts\\patch_recent_temperature.py --mode linear --linear-from 20 --linear-to 28
  .venv\\Scripts\\python.exe scripts\\patch_recent_temperature.py --hours 6 --device-id demo_device --dry-run --mode fixed --value 25

可选：与主应用相同的环境变量，默认 SQLITE_URL=sqlite+aiosqlite:///./app.db
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.database import dispose_db, get_session_factory, init_db
from app.models.sensor import SensorData


def _utc_cutoff_naive(hours: float) -> datetime:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return cutoff.replace(tzinfo=None)


async def main() -> None:
    p = argparse.ArgumentParser(description="修改最近若干小时内的温度采样")
    p.add_argument("--hours", type=float, default=6.0, help="回溯时长（小时），默认 6")
    p.add_argument("--device-id", type=str, default="", help="只改该设备；不填则改窗口内全部设备")
    p.add_argument("--dry-run", action="store_true", help="只打印将影响的行数与示例，不写库")
    p.add_argument(
        "--mode",
        choices=("fixed", "add", "linear"),
        required=True,
        help="fixed=设为同一值；add=在原有温度上加减；linear=按时间顺序从 linear-from 插值到 linear-to",
    )
    p.add_argument("--value", type=float, default=None, help="mode=fixed 时的目标温度 ℃")
    p.add_argument("--delta", type=float, default=None, help="mode=add 时在原值上加的增量 ℃")
    p.add_argument("--linear-from", type=float, default=None, dest="linear_from", help="mode=linear 起点 ℃")
    p.add_argument("--linear-to", type=float, default=None, dest="linear_to", help="mode=linear 终点 ℃")
    args = p.parse_args()

    if args.mode == "fixed" and args.value is None:
        p.error("mode=fixed 时必须提供 --value")
    if args.mode == "add" and args.delta is None:
        p.error("mode=add 时必须提供 --delta")
    if args.mode == "linear" and (args.linear_from is None or args.linear_to is None):
        p.error("mode=linear 时必须同时提供 --linear-from 与 --linear-to")

    await init_db()
    factory = get_session_factory()
    cutoff = _utc_cutoff_naive(args.hours)

    async with factory() as session:
        stmt = select(SensorData).where(SensorData.timestamp >= cutoff)
        if args.device_id.strip():
            stmt = stmt.where(SensorData.device_id == args.device_id.strip())
        stmt = stmt.order_by(SensorData.timestamp.asc())

        result = await session.execute(stmt)
        rows = list(result.scalars().all())

        if not rows:
            print(f"未找到数据：timestamp >= {cutoff.isoformat()}（UTC naive 存库）")
            await dispose_db()
            return

        n = len(rows)
        print(f"将处理 {n} 条（最近 {args.hours} 小时内" + (f"，device_id={args.device_id!r}" if args.device_id.strip() else "，全部设备") + "）")

        if args.mode == "fixed":
            for r in rows:
                r.temperature = round(float(args.value), 4)
        elif args.mode == "add":
            for r in rows:
                r.temperature = round(float(r.temperature) + float(args.delta), 4)
        else:
            lo, hi = float(args.linear_from), float(args.linear_to)
            if n == 1:
                rows[0].temperature = round(hi, 4)
            else:
                for i, r in enumerate(rows):
                    t = lo + (hi - lo) * (i / (n - 1))
                    r.temperature = round(t, 4)

        sample = rows[0]
        sample_last = rows[-1]
        print(
            f"示例：首条 id={sample.id} t={sample.timestamp.isoformat()} "
            f"device={sample.device_id!r} temp -> {sample.temperature} ℃"
        )
        print(
            f"示例：末条 id={sample_last.id} t={sample_last.timestamp.isoformat()} "
            f"device={sample_last.device_id!r} temp -> {sample_last.temperature} ℃"
        )

        if args.dry_run:
            await session.rollback()
            print("dry-run：已回滚，未写入数据库。")
        else:
            await session.commit()
            print("已提交。")

    await dispose_db()


if __name__ == "__main__":
    asyncio.run(main())
