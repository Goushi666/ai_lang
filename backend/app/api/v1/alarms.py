from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, Query, Path

from app.deps import alarm_service_dep
from app.schemas.alarm import AlarmConfig, AlarmResponse
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


@router.get("/history", response_model=List[AlarmResponse])
async def get_history(
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    service: AlarmService = Depends(alarm_service_dep),
):
    return await service.get_history(start_time, end_time)


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

