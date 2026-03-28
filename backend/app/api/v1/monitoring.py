"""环境监测页 API（并入原「环境分析」能力子集）。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from app.schemas.monitoring import MonitoringAnomaliesResponse, MonitoringTemperatureTimelineResponse
from app.services.alarm_service import AlarmService
from app.services.analysis_service import AnalysisService
from app.services.monitoring_service import MonitoringService


router = APIRouter()


def _monitoring_service(request: Request) -> MonitoringService:
    return MonitoringService(request.app.state.sensor_repo)


def _analysis_for_monitoring(request: Request) -> AnalysisService:
    """监测页异常列表不依赖 ANALYSIS_ENABLED，与独立分析路由解耦。"""
    return AnalysisService(
        sensor_repo=request.app.state.sensor_repo,
        alarm_service=AlarmService(repo=request.app.state.alarm_repo),
    )


@router.get(
    "/temperature-timeline",
    response_model=MonitoringTemperatureTimelineResponse,
    summary="2 小时温度：过去 1h 实测+推算，未来 1h 推算",
)
async def temperature_timeline(
    device_id: Optional[str] = Query(None, description="仅某设备；不传则合并全部"),
    service: MonitoringService = Depends(_monitoring_service),
):
    return await service.get_temperature_timeline(device_id=device_id)


@router.get(
    "/anomalies",
    response_model=MonitoringAnomaliesResponse,
    summary="过去 24 小时内环境异常片段（与告警阈值一致）",
)
async def monitoring_anomalies(
    hours: float = Query(24, ge=1, le=24, description="回溯小时数，最大 24"),
    device_id: Optional[str] = Query(None),
    service: AnalysisService = Depends(_analysis_for_monitoring),
):
    return await service.get_monitoring_anomalies_recent(hours=hours, device_id=device_id)
