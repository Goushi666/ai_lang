from fastapi import APIRouter, Body, Depends, HTTPException

from app.core.config import settings
from app.deps import vehicle_service_dep
from app.schemas.vehicle import (
    ArmJointsControlRequest,
    GimbalControlRequest,
    TrackModeRequest,
    VehicleControlRequest,
    VehicleStatusResponse,
)
from app.services.vehicle_service import VehicleService


router = APIRouter()

"""
车辆控制 API（REST）。

与 Web 端设计文档对齐：
- `POST /api/vehicle/control`：发送控制指令（循迹模式下拒绝，需先 `POST /api/vehicle/track` 切回 normal）
- `POST /api/vehicle/track`：循迹模式切换（MQTT `car/control/track`）
- `POST /api/vehicle/gimbal`：摄像头云台（MQTT arm/control，joint 6/7；循迹模式下拒绝）
- `POST /api/vehicle/arm`：机械臂（MQTT arm/control，joint 0~5）
- `GET /api/vehicle/status`：获取车辆实时状态
"""

@router.post("/gimbal")
async def send_gimbal(
    payload: GimbalControlRequest = Body(...),
    service: VehicleService = Depends(vehicle_service_dep),
):
    """向 MQTT `arm/control` 发布云台关节；仅对请求体中出现的关节各发一条（QoS 1）。"""
    if not settings.MQTT_ENABLED or not (settings.MQTT_TOPIC_ARM_CONTROL or "").strip():
        raise HTTPException(
            status_code=503,
            detail="MQTT 未启用或未配置 MQTT_TOPIC_ARM_CONTROL，无法下发云台",
        )
    cur = await service.get_status()
    if cur.drive_mode == "track":
        raise HTTPException(
            status_code=409,
            detail="当前为循迹模式，云台由车端接管；请先切换为「普通模式」后再调云台。",
        )
    try:
        await service.send_gimbal_mqtt(
            joint_6_angle=payload.joint_6_angle,
            joint_7_angle=payload.joint_7_angle,
            speed=payload.speed,
        )
    except Exception:
        raise HTTPException(status_code=503, detail="云台 MQTT 下发失败") from None
    return {"ok": True}


@router.post("/arm")
async def send_arm_joints(
    payload: ArmJointsControlRequest = Body(...),
    service: VehicleService = Depends(vehicle_service_dep),
):
    """向 MQTT `arm/control` 发布机械臂关节；仅对请求体中出现的关节各发一条（QoS 1）。"""
    if not settings.MQTT_ENABLED or not (settings.MQTT_TOPIC_ARM_CONTROL or "").strip():
        raise HTTPException(
            status_code=503,
            detail="MQTT 未启用或未配置 MQTT_TOPIC_ARM_CONTROL，无法下发机械臂",
        )
    try:
        await service.send_arm_joints_mqtt(
            joint_0_angle=payload.joint_0_angle,
            joint_1_angle=payload.joint_1_angle,
            joint_2_angle=payload.joint_2_angle,
            joint_3_angle=payload.joint_3_angle,
            joint_4_angle=payload.joint_4_angle,
            joint_5_angle=payload.joint_5_angle,
            speed=payload.speed,
        )
    except Exception:
        raise HTTPException(status_code=503, detail="机械臂 MQTT 下发失败") from None
    return {"ok": True}


@router.post("/track")
async def set_track_mode(
    payload: TrackModeRequest = Body(...),
    service: VehicleService = Depends(vehicle_service_dep),
):
    """
    下发 MQTT `car/control/track`：``{"mode":"normal"|"track","timestamp":<unix秒>}``（QoS 1）。
    MQTT 已启用时须配置 ``MQTT_TOPIC_CAR_TRACK`` 且发布成功后才更新服务端状态。
    """
    if settings.MQTT_ENABLED and not (settings.MQTT_TOPIC_CAR_TRACK or "").strip():
        raise HTTPException(
            status_code=503,
            detail="已启用 MQTT 但未配置 MQTT_TOPIC_CAR_TRACK，无法下发循迹模式切换",
        )
    try:
        await service.send_track_mode(mode=payload.mode, timestamp=payload.timestamp)
    except Exception:
        raise HTTPException(status_code=503, detail="循迹模式 MQTT 下发失败") from None
    return {"ok": True, "mode": payload.mode}


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
    cur = await service.get_status()
    if cur.drive_mode == "track":
        raise HTTPException(
            status_code=409,
            detail="当前为循迹模式，手动方向控制已锁定；请先切换为「普通模式」后再使用本接口。",
        )
    await service.send_control(
        action=payload.action,
        speed=payload.speed,
        duration=payload.duration,
    )
    return {"ok": True}


@router.get("/status", response_model=VehicleStatusResponse)
async def get_status(service: VehicleService = Depends(vehicle_service_dep)):
    """获取车辆状态（MVP：内存状态）"""
    return await service.get_status()

