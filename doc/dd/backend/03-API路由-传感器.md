# 后端设计 · API 路由（传感器）

路由前缀：`/api/sensors`（在 `main.py` 中挂载）。

## 代码结构示例

```python
from fastapi import APIRouter, Depends, Query
from typing import List
from datetime import datetime
from app.schemas.sensor import SensorDataResponse, SensorHistoryQuery
from app.services.sensor_service import SensorService

router = APIRouter()

@router.get("/latest", response_model=SensorDataResponse)
async def get_latest_data(
    service: SensorService = Depends()
):
    """获取最新传感器数据"""
    return await service.get_latest()

@router.get("/history", response_model=List[SensorDataResponse])
async def get_history_data(
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    service: SensorService = Depends()
):
    """查询历史数据"""
    return await service.get_history(start_time, end_time)

@router.get("/export")
async def export_data(
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    service: SensorService = Depends()
):
    """导出数据"""
    return await service.export_csv(start_time, end_time)
```

## 实现说明

- `latest` 在无数据时可返回 HTTP 404，避免响应体使用 `response_model` 伪造记录；具体以 `app/api/v1/sensors.py` 为准。
- `export` 返回 `text/csv` 与附件头，便于前端 Blob 下载。
