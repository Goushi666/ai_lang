from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.deps import analysis_service_dep
from app.schemas.analysis import EnvironmentSummaryResponse
from app.services.analysis_service import AnalysisService

router = APIRouter()


@router.get(
    "/environment/summary",
    response_model=EnvironmentSummaryResponse,
    summary="环境分析摘要（框架占位）",
)
async def get_environment_summary(
    start_time: datetime = Query(..., description="ISO8601 起始时间"),
    end_time: datetime = Query(..., description="ISO8601 结束时间"),
    device_id: Optional[str] = Query(None, description="可选设备 ID"),
    bucket: Optional[str] = Query(None, description="可选分桶，如 1h"),
    service: AnalysisService = Depends(analysis_service_dep),
):
    return await service.get_environment_summary(
        start_time=start_time,
        end_time=end_time,
        device_id=device_id,
        bucket=bucket,
    )


@router.post(
    "/environment/run",
    response_model=EnvironmentSummaryResponse,
    summary="触发环境分析（框架占位，与 GET 摘要等价）",
)
async def run_environment_analysis(
    start_time: datetime = Query(..., description="ISO8601 起始时间"),
    end_time: datetime = Query(..., description="ISO8601 结束时间"),
    device_id: Optional[str] = Query(None),
    bucket: Optional[str] = Query(None),
    service: AnalysisService = Depends(analysis_service_dep),
):
    return await service.run_environment_analysis(
        start_time=start_time,
        end_time=end_time,
        device_id=device_id,
        bucket=bucket,
    )
