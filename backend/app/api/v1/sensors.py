from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.deps import sensor_service_dep
from app.schemas.sensor import SensorDataResponse
from app.services.sensor_service import SensorService


router = APIRouter()

"""
传感器相关 API（REST）。

与 Web 端设计文档对齐：
- `GET /api/sensors/latest`
- `GET /api/sensors/history?start_time=...&end_time=...`
- `GET /api/sensors/export?start_time=...&end_time=...`（CSV）
"""


@router.get("/latest", response_model=SensorDataResponse)
async def get_latest_data(service: SensorService = Depends(sensor_service_dep)):
    """获取最新传感器数据；尚无上报时返回 404。"""
    data = await service.get_latest()
    if data is None:
        raise HTTPException(status_code=404, detail="暂无传感器数据，请等待设备上报")
    return data


@router.get("/history", response_model=List[SensorDataResponse])
async def get_history_data(
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    service: SensorService = Depends(sensor_service_dep),
):
    """
    查询历史数据（时间范围）。

    Parameters:
    - start_time: 起始时间（ISO 格式）
    - end_time: 结束时间（ISO 格式）
    """
    return await service.get_history(start_time, end_time)


@router.get("/export")
async def export_data(
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    service: SensorService = Depends(sensor_service_dep),
):
    """
    导出传感器历史 CSV。

    注意：
    - MVP 返回 `text/csv`，前端按 blob 方式接收即可。
    """
    csv_text = await service.export_csv(start_time, end_time)
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=sensor_history.csv"},
    )

