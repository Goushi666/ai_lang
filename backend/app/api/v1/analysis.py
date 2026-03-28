from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.deps import analysis_service_dep
from app.schemas.analysis import EnvironmentSummaryResponse
from app.services.analysis_service import AnalysisService

router = APIRouter()


def _normalize_bucket(bucket: Optional[str]) -> Optional[str]:
    if bucket is None or bucket == "" or bucket == "none":
        return None
    if bucket == "1h":
        return "1h"
    raise HTTPException(status_code=400, detail="分桶仅支持：不分桶、或按小时（1h）")


def _check_window(start_time: datetime, end_time: datetime) -> None:
    if start_time > end_time:
        raise HTTPException(status_code=400, detail="开始时间不能晚于结束时间")


@router.get(
    "/environment/summary",
    response_model=EnvironmentSummaryResponse,
    summary="环境分析（统计、曲线点、异常区间、24小时温度预测）",
)
async def get_environment_summary(
    start_time: datetime = Query(..., description="开始时间 ISO8601"),
    end_time: datetime = Query(..., description="结束时间 ISO8601"),
    device_id: Optional[str] = Query(None, description="只分析某台设备时填写；不填则合并所有设备"),
    bucket: Optional[str] = Query(None, description="按小时统计填 1h，否则不传或 none"),
    service: AnalysisService = Depends(analysis_service_dep),
):
    _check_window(start_time, end_time)
    b = _normalize_bucket(bucket)
    return await service.get_environment_summary(
        start_time=start_time,
        end_time=end_time,
        device_id=device_id,
        bucket=b,
    )


@router.post(
    "/environment/run",
    response_model=EnvironmentSummaryResponse,
    summary="重新计算（与 GET 相同）",
)
async def run_environment_analysis(
    start_time: datetime = Query(..., description="开始时间 ISO8601"),
    end_time: datetime = Query(..., description="结束时间 ISO8601"),
    device_id: Optional[str] = Query(None),
    bucket: Optional[str] = Query(None),
    service: AnalysisService = Depends(analysis_service_dep),
):
    _check_window(start_time, end_time)
    b = _normalize_bucket(bucket)
    return await service.run_environment_analysis(
        start_time=start_time,
        end_time=end_time,
        device_id=device_id,
        bucket=b,
    )


@router.get(
    "/environment/export",
    summary="导出：JSON 或 CSV；范围可选仅异常 / 全部",
    response_class=Response,
)
async def export_environment(
    start_time: datetime = Query(..., description="开始时间 ISO8601"),
    end_time: datetime = Query(..., description="结束时间 ISO8601"),
    device_id: Optional[str] = Query(None),
    export_format: Literal["json", "csv"] = Query(
        alias="format",
        description="json 或 csv",
    ),
    scope: Literal["anomalies", "full"] = Query(
        description="anomalies=仅异常；full=全部（JSON 为结构化全文，CSV 为时段内每条原始采样）",
    ),
    service: AnalysisService = Depends(analysis_service_dep),
):
    _check_window(start_time, end_time)
    body, media_type, suffix = await service.export_unified(
        start_time=start_time,
        end_time=end_time,
        device_id=device_id,
        export_format=export_format,
        scope=scope,
    )
    return Response(
        content=body.encode("utf-8"),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{suffix}"',
        },
    )


@router.get(
    "/environment/anomalies/export",
    summary="仅导出异常 CSV（兼容旧链接）",
    response_class=Response,
)
async def export_anomalies_legacy(
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    device_id: Optional[str] = Query(None),
    service: AnalysisService = Depends(analysis_service_dep),
):
    _check_window(start_time, end_time)
    csv_text = await service.export_anomalies_csv(
        start_time=start_time,
        end_time=end_time,
        device_id=device_id,
    )
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="environment_anomalies.csv"',
        },
    )
