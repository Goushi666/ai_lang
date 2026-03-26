"""
应用主入口模块。

负责创建 FastAPI 应用实例，完成以下初始化工作：
- 注册 CORS 中间件
- 挂载各业务 API 路由（传感器、告警、车辆、设备）
- 配置 WebSocket 端点用于实时数据推送
- 启动后台任务（模拟传感器数据采集 & 告警生成）
"""

import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.alarms import router as alarms_router
from app.api.v1.sensors import router as sensors_router
from app.api.v1.vehicles import router as vehicles_router
from app.api.v1.devices import router as devices_router
from app.middleware.cors import cors_middleware
from app.websocket.manager import websocket_manager
from app.repositories.alarm_repo import AlarmRepository
from app.repositories.sensor_repo import SensorRepository
from app.services.alarm_service import AlarmService
from app.services.sensor_service import SensorService


def create_app() -> FastAPI:
    """
    创建并配置 FastAPI 应用实例。

    Returns:
        FastAPI: 完整配置的应用实例
    """
    app = FastAPI(title="ai_lang-backend", version="0.1.0")

    # ---------- 中间件 ----------
    # 挂载 CORS 跨域中间件，允许前端跨域访问
    app.add_middleware(CORSMiddleware, **cors_middleware())

    # ---------- REST API 路由 ----------
    app.include_router(sensors_router, prefix="/api/sensors", tags=["sensors"])   # 传感器数据接口
    app.include_router(alarms_router, prefix="/api/alarms", tags=["alarms"])      # 告警管理接口
    app.include_router(vehicles_router, prefix="/api/vehicle", tags=["vehicle"])   # 车辆控制接口
    app.include_router(devices_router, prefix="/api/devices", tags=["devices"])    # 设备管理接口

    # ---------- 健康检查端点 ----------
    @app.get("/api/health")
    async def health():
        """健康检查接口，用于监控服务是否正常运行。"""
        return {"ok": True}

    # ---------- WebSocket 端点 ----------
    @app.websocket("/ws")
    async def websocket_endpoint(ws):
        """
        WebSocket 连接入口。

        客户端连接后进入消息循环，支持心跳保活等消息处理。
        连接断开时自动从管理器中移除。
        """
        await websocket_manager.connect(ws)
        try:
            while True:
                # 接收客户端消息（如心跳 ping）
                data = await ws.receive_text()
                await websocket_manager.handle_client_message(ws, data)
        finally:
            # 连接断开时清理
            await websocket_manager.disconnect(ws)

    # ---------- 应用生命周期事件 ----------
    @app.on_event("startup")
    async def _startup() -> None:
        """
        应用启动时执行：创建后台定时任务。

        MVP 阶段使用模拟数据驱动 WebSocket 推送链路，
        后续替换为真实 MQTT 设备数据接入。
        """
        sensor_service = SensorService(repo=SensorRepository())
        alarm_service = AlarmService(repo=AlarmRepository())

        async def sensor_loop() -> None:
            """传感器数据模拟循环：每 5 秒生成一条数据并广播给前端。"""
            while True:
                try:
                    await sensor_service.push_sensor_data()
                except Exception:
                    # 避免单次异常导致整个后台任务退出
                    pass
                await asyncio.sleep(5)

        async def alarm_loop() -> None:
            """告警模拟循环：每 20 秒生成一条告警并广播给前端。"""
            while True:
                try:
                    await alarm_service.push_alarm()
                except Exception:
                    pass
                await asyncio.sleep(20)

        # 将后台任务挂载到 app.state，方便关闭时取消
        app.state._sensor_task = asyncio.create_task(sensor_loop())
        app.state._alarm_task = asyncio.create_task(alarm_loop())

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        """应用关闭时执行：取消所有后台定时任务。"""
        for attr in ("_sensor_task", "_alarm_task"):
            task = getattr(app.state, attr, None)
            if task:
                task.cancel()

    return app


# 创建全局应用实例，供 uvicorn 启动使用
app = create_app()
