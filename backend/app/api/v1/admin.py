"""维护接口：清空 SQLite 业务表（MVP 无鉴权，生产请加权限或关闭路由）。"""

from fastapi import APIRouter, Request

from app.schemas.admin import PurgeDataRequest

router = APIRouter()


@router.post(
    "/purge-data",
    summary="一键清空库内业务表（sensor_data / environment_anomalies）",
)
async def purge_data(body: PurgeDataRequest, request: Request):
    n_sensor = 0
    n_anomaly = 0
    if body.sensor_data:
        n_sensor = await request.app.state.sensor_repo.delete_all()
    if body.environment_anomalies:
        n_anomaly = await request.app.state.environment_anomaly_repo.delete_all()
    return {
        "ok": True,
        "sensor_data_deleted": n_sensor,
        "environment_anomalies_deleted": n_anomaly,
    }
