from fastapi import APIRouter, Body, Depends

from app.deps import vehicle_service_dep
from app.schemas.vehicle import VehicleControlRequest, VehicleStatusResponse
from app.services.vehicle_service import VehicleService


router = APIRouter()

"""
车辆控制 API（REST）。

与 Web 端设计文档对齐：
- `POST /api/vehicle/control`：发送控制指令
- `GET /api/vehicle/status`：获取车辆实时状态
"""

@router.post("/control")
async def send_control(
    payload: VehicleControlRequest = Body(...),
    service: VehicleService = Depends(vehicle_service_dep),
):
    """
    发送车辆控制指令（MVP）。

    Web 前端会传：
    - action：forward/backward/left/right/stop
    - speed：速度
    - timestamp：时间戳
    """
    await service.send_control(action=payload.action, speed=payload.speed)
    return {"ok": True}


@router.get("/status", response_model=VehicleStatusResponse)
async def get_status(service: VehicleService = Depends(vehicle_service_dep)):
    """获取车辆状态（MVP：内存状态）"""
    return await service.get_status()

