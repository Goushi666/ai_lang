from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, Path

from app.deps import alarm_service_dep
from app.schemas.alarm import AlarmConfig, AlarmHistoryPage
from app.services.alarm_service import AlarmService


router = APIRouter()

"""
告警相关 API（REST）。

与 Web 端设计文档对齐：
- `GET /api/alarms/history`
- `PUT /api/alarms/{id}/read`
- `GET /api/alarms/config`
- `PUT /api/alarms/config`
"""


@router.get("/history", response_model=AlarmHistoryPage)
async def get_history(
    start_time: datetime = Query(..., description="开始时间（含）"),
    end_time: datetime = Query(..., description="结束时间（含）"),
    metric: Optional[Literal["temperature", "humidity", "light"]] = Query(
        None,
        description="仅温度/湿度/光照；不传为全部",
    ),
    level: Optional[Literal["low", "medium", "high", "urgent"]] = Query(
        None,
        description="告警级别；不传为全部",
    ),
    page: int = Query(1, ge=1, description="页码，从 1 起"),
    page_size: int = Query(20, ge=1, le=500, description="每页条数"),
    service: AlarmService = Depends(alarm_service_dep),
):
    """历史告警分页查询，按触发时间倒序（最新在前）。"""
    return await service.get_history(
        start_time,
        end_time,
        metric=metric,
        level=level,
        page=page,
        page_size=page_size,
    )


@router.put("/{alarm_id}/read")
async def mark_read(
    alarm_id: str = Path(...),
    service: AlarmService = Depends(alarm_service_dep),
):
    """标记告警为已读（仅更新 read 状态）"""
    ok = await service.mark_read(alarm_id)
    return {"ok": ok}


@router.get("/config", response_model=AlarmConfig)
async def get_config(service: AlarmService = Depends(alarm_service_dep)):
    """获取告警配置（阈值）"""
    return await service.get_config()


@router.put("/config")
async def update_config(
    config: AlarmConfig,
    service: AlarmService = Depends(alarm_service_dep),
):
    """更新告警配置（阈值）"""
    await service.update_config(config)
    return {"ok": True}

