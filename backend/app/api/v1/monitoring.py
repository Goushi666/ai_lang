"""环境监测页 API（并入原「环境分析」能力子集）。"""

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request

from app.core.timeutil import format_instant_rfc3339_utc_z
from app.models.environment_anomaly import EnvironmentAnomaly
from app.schemas.monitoring import (
    BatchDeleteAnomalyRecordsBody,
    EnvironmentAnomalyListResponse,
    EnvironmentAnomalyRecord,
    MonitoringAnomaliesResponse,
    MonitoringTemperatureTimelineResponse,
)
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


def _row_to_env_record(row: EnvironmentAnomaly) -> EnvironmentAnomalyRecord:
    return EnvironmentAnomalyRecord(
        id=row.id,
        device_id=row.device_id,
        metric=row.metric,  # type: ignore[arg-type]
        rule_id=row.rule_id,
        peak=row.peak,
        threshold=row.threshold,
        detail_zh=row.detail_zh or "",
        recorded_at=format_instant_rfc3339_utc_z(row.recorded_at),
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
    "/anomalies/records",
    response_model=EnvironmentAnomalyListResponse,
    summary="查询已落库的环境异常（按落库时间落在查询时段内）",
)
async def list_stored_environment_anomalies(
    request: Request,
    start_time: datetime = Query(..., description="查询窗口开始 ISO8601（含，按落库时间筛选）"),
    end_time: datetime = Query(..., description="查询窗口结束 ISO8601（含，按落库时间筛选）"),
    device_id: Optional[str] = Query(None, description="仅某设备；不传则全部"),
    metric: Optional[Literal["temperature", "humidity", "light"]] = Query(
        None,
        description="仅温度/湿度/光照；不传为全部",
    ),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    if start_time > end_time:
        raise HTTPException(status_code=400, detail="开始时间不能晚于结束时间")
    repo = request.app.state.environment_anomaly_repo
    total, rows = await repo.list_overlapping_window(
        window_start=start_time,
        window_end=end_time,
        device_id=device_id,
        metric=metric,
        limit=limit,
        offset=offset,
    )
    return EnvironmentAnomalyListResponse(
        total=total,
        items=[_row_to_env_record(r) for r in rows],
    )


@router.post(
    "/anomalies/records/batch-delete",
    summary="按主键批量删除环境异常落库记录",
)
async def batch_delete_anomaly_records(
    request: Request,
    body: BatchDeleteAnomalyRecordsBody,
):
    repo = request.app.state.environment_anomaly_repo
    n = await repo.delete_by_ids(body.ids)
    return {"ok": True, "deleted": n, "requested": len(body.ids)}


@router.delete(
    "/anomalies/records/{record_id}",
    summary="按主键删除一条已落库的环境异常片段",
)
async def delete_stored_environment_anomaly(
    request: Request,
    record_id: int = Path(..., ge=1),
):
    repo = request.app.state.environment_anomaly_repo
    ok = await repo.delete_by_id(record_id)
    if not ok:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"ok": True}


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
