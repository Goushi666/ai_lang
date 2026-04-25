"""
应用主入口模块。

负责创建 FastAPI 应用实例，完成以下初始化工作：
- 注册 CORS 中间件
- 挂载各业务 API 路由（传感器、告警、车辆、设备、环境分析、Agent）
- 配置 WebSocket 端点用于实时数据推送
- 启动后台任务（模拟传感器数据采集；超阈告警由采样链路边沿触发）
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.admin import router as admin_router
from app.api.v1.agent import router as agent_router
from app.api.v1.alarms import router as alarms_router
from app.api.v1.analysis import router as analysis_router
from app.api.v1.monitoring import router as monitoring_router
from app.api.v1.sensors import router as sensors_router
from app.api.v1.vehicles import router as vehicles_router
from app.api.v1.devices import router as devices_router
from app.api.v1.video import router as video_router
from app.middleware.cors import cors_middleware
from app.websocket.manager import websocket_manager
from app.repositories.agent_chat_repo import AgentChatRepository
from app.repositories.alarm_repo import AlarmRepository
from app.repositories.environment_anomaly_repo import EnvironmentAnomalyRepository
from app.repositories.sensor_repo import SensorRepository
from app.services.alarm_service import AlarmService
from app.repositories.vehicle_repo import VehicleRepository
from app.services.sensor_service import SensorService
from app.services.vehicle_service import VehicleService
from app.core.config import settings
from app.core.database import dispose_db, get_session_factory, init_db
from app.core.mqtt import mqtt_client, parse_json_payload
from app.services.agent import AgentService
from app.services.agent.context import SessionManager
from app.services.agent.tools import ToolRegistry
from app.services.agent.tools.sensor_tools import GetSensorLatest, GetSensorHistory
from app.services.agent.tools.alarm_tools import GetAlarmsHistory, GetAlarmConfig
from app.services.agent.tools.analysis_tools import GetEnvironmentAnalysis
from app.services.agent.tools.knowledge_tools import SearchKnowledgeBase
from app.services.agent.tools.csv_export_tools import (
    ExportAlarmsHistoryCsv,
    ExportCsvFile,
    ExportSensorHistoryCsv,
)
from app.services.agent.tools.time_tools import GetCurrentTime
from app.services.agent.tools.vehicle_tools import (
    ControlArmJoints,
    ControlVehicle,
    GetVehicleStatus,
)
from app.services.agent.skills import SkillRegistry
from app.services.agent.skills.env_diagnosis import EnvDiagnosisSkill
from app.services.agent.llm import LLMClient
from app.services.agent.clarifier import Clarifier

logger = logging.getLogger(__name__)


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
    app.include_router(analysis_router, prefix="/api/analysis", tags=["analysis"])  # 环境分析（框架）
    app.include_router(monitoring_router, prefix="/api/monitoring", tags=["monitoring"])  # 环境监测页
    app.include_router(agent_router, prefix="/api/agent", tags=["agent"])          # 智能 Agent（框架）
    app.include_router(video_router, prefix="/api/video", tags=["video"])        # 车载 MJPEG / HLS 配置与代理
    app.include_router(admin_router, prefix="/api/admin", tags=["admin"])       # 数据维护（清空表等）

    # ---------- 健康检查端点 ----------
    @app.get("/api/health")
    async def health():
        """健康检查接口，用于监控服务是否正常运行。"""
        return {"ok": True}

    # ---------- WebSocket 端点 ----------
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """
        WebSocket 连接入口。

        客户端连接后进入消息循环，支持心跳保活等消息处理。
        连接断开时自动从管理器中移除。

        注意：首参必须标注为 ``WebSocket``。若写成 ``async def f(ws)`` 且无类型注解，
        FastAPI 会把 ``ws`` 当成**查询参数**校验，握手失败，Uvicorn 日志里会表现为 ``WebSocket /ws 403``。
        """
        await websocket_manager.connect(websocket)
        try:
            while True:
                # 接收客户端消息（如心跳 ping）
                data = await websocket.receive_text()
                await websocket_manager.handle_client_message(websocket, data)
        finally:
            # 连接断开时清理
            await websocket_manager.disconnect(websocket)

    # ---------- 应用生命周期事件 ----------
    @app.on_event("startup")
    async def _startup() -> None:
        """
        应用启动时执行：创建后台定时任务。

        MVP 阶段使用模拟数据驱动 WebSocket 推送链路，
        后续替换为真实 MQTT 设备数据接入。
        """
        await init_db()
        session_factory = get_session_factory()
        agent_chat_repo = AgentChatRepository(session_factory)
        app.state.agent_chat_repo = agent_chat_repo
        sensor_repo = SensorRepository(session_factory)
        app.state.sensor_repo = sensor_repo
        env_anomaly_repo = EnvironmentAnomalyRepository(session_factory)
        app.state.environment_anomaly_repo = env_anomaly_repo
        alarm_repo = AlarmRepository(
            session_factory,
            environment_anomaly_repo=env_anomaly_repo,
        )
        app.state.alarm_repo = alarm_repo
        alarm_service = AlarmService(
            repo=alarm_repo,
            environment_anomaly_repo=env_anomaly_repo,
        )
        sensor_service = SensorService(repo=sensor_repo, alarm_service=alarm_service)
        app.state.sensor_service = sensor_service

        vehicle_repo = VehicleRepository()
        app.state.vehicle_repo = vehicle_repo
        app.state.vehicle_service = VehicleService(repo=vehicle_repo)

        # ---------- 智能 Agent 初始化 ----------
        session_manager = SessionManager(
            max_sessions=200,
            ttl=settings.AGENT_SESSION_TTL,
            max_messages=settings.AGENT_SESSION_MAX_MESSAGES,
        )
        tool_registry = ToolRegistry()
        tool_registry.register(GetCurrentTime(display_timezone=settings.AGENT_TIME_DISPLAY_TZ))
        _backend_root = Path(__file__).resolve().parent.parent
        _csv_export_dir = (_backend_root / settings.AGENT_CSV_EXPORT_DIR.replace("\\", "/").lstrip("./")).resolve()
        tool_registry.register(
            ExportCsvFile(_csv_export_dir, max_rows=settings.AGENT_CSV_EXPORT_MAX_ROWS),
        )
        tool_registry.register(ExportSensorHistoryCsv(_csv_export_dir, sensor_service))
        tool_registry.register(
            ExportAlarmsHistoryCsv(
                _csv_export_dir,
                alarm_repo,
                max_rows=settings.AGENT_CSV_EXPORT_MAX_ROWS,
            ),
        )
        tool_registry.register(GetSensorLatest(sensor_service))
        tool_registry.register(GetSensorHistory(sensor_service))
        tool_registry.register(GetAlarmsHistory(alarm_repo))
        tool_registry.register(GetAlarmConfig(alarm_repo))
        # AnalysisService 需要 sensor_repo + alarm_service；按需构建（复用 analysis_service_dep 的模式）
        if settings.ANALYSIS_ENABLED:
            from app.services.analysis_service import AnalysisService as _AS
            _analysis_svc = _AS(sensor_repo=sensor_repo, alarm_service=alarm_service)
            tool_registry.register(GetEnvironmentAnalysis(_analysis_svc))

        tool_registry.register(ControlArmJoints(app.state.vehicle_service))
        tool_registry.register(ControlVehicle(app.state.vehicle_service))
        tool_registry.register(GetVehicleStatus(app.state.vehicle_service))

        app.state.knowledge_service = None
        try:
            from app.services.knowledge import KnowledgeService as _KnowledgeService

            _ks = _KnowledgeService(settings)
            app.state.knowledge_service = _ks
            if settings.AGENT_RAG_ENABLED:
                tool_registry.register(
                    SearchKnowledgeBase(_ks, top_k=settings.AGENT_RAG_TOP_K),
                )
            logger.info(
                "知识库已初始化(FTS) path=%s rag_tool=%s",
                _ks.db_path,
                settings.AGENT_RAG_ENABLED,
            )
        except Exception:
            logger.exception("知识库初始化失败，入库 API 与 RAG 检索将不可用")

        skill_registry = SkillRegistry()
        skill_registry.register(EnvDiagnosisSkill())

        llm_client = LLMClient(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            model=settings.LLM_MODEL,
        )
        clarifier = Clarifier(
            enabled=settings.AGENT_CLARIFICATION_ENABLED,
            llm_client=llm_client,
            min_clarity=settings.AGENT_CLARIFICATION_MIN_CLARITY,
            judge_timeout_sec=settings.AGENT_CLARIFICATION_JUDGE_TIMEOUT_SEC,
            clarify_timeout_sec=settings.AGENT_CLARIFICATION_CLARIFY_TIMEOUT_SEC,
            max_options=settings.AGENT_CLARIFICATION_MAX_OPTIONS,
        )

        app.state.agent_csv_export_dir = _csv_export_dir
        app.state.agent_service = AgentService(
            session_manager=session_manager,
            tool_registry=tool_registry,
            skill_registry=skill_registry,
            llm_client=llm_client,
            clarifier=clarifier,
            max_tool_rounds=settings.AGENT_MAX_TOOL_ROUNDS,
            chat_repo=agent_chat_repo,
        )

        # ---------- MQTT 接入（sensor/data 等，见 settings.MQTT_SUBSCRIBE_TOPICS）----------
        def on_mqtt_message(topic: str, payload: str) -> None:
            """
            在 asyncio 事件循环线程中执行（由 mqtt_client 通过 call_soon_threadsafe 投递）。

            将 JSON 解析为 dict 后写入 SensorService，内部会：
            - 更新内存仓库（REST 可读到最新值）
            - 按前端协议广播 type=sensor_data
            """
            parsed = parse_json_payload(payload)

            async def _handle() -> None:
                if isinstance(parsed, dict):
                    try:
                        await sensor_service.ingest_mqtt_payload_dict(parsed)
                    except Exception:
                        logger.exception("处理 MQTT 传感器消息失败 topic=%s", topic)
                else:
                    logger.debug("MQTT 非 object JSON，跳过传感器入库 topic=%s", topic)

            asyncio.create_task(_handle())

        if settings.MQTT_ENABLED:
            mqtt_client.set_message_handler(on_mqtt_message)
            await mqtt_client.start()

        async def sensor_loop() -> None:
            """传感器数据模拟循环：每 5 秒生成一条数据并广播给前端。"""
            while True:
                try:
                    await sensor_service.push_sensor_data()
                except Exception:
                    # 避免单次异常导致整个后台任务退出
                    pass
                await asyncio.sleep(5)

        anomaly_repo = app.state.environment_anomaly_repo

        async def apply_data_retention() -> None:
            days = settings.SENSOR_HISTORY_RETENTION_DAYS
            if days <= 0:
                return
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            try:
                n_s = await sensor_repo.delete_older_than(cutoff)
                n_a = await anomaly_repo.delete_recorded_before(cutoff)
                if n_s or n_a:
                    logger.info(
                        "数据保留策略删除 sensor_data=%s environment_anomalies=%s（早于 %s）",
                        n_s,
                        n_a,
                        cutoff.isoformat(),
                    )
            except Exception:
                logger.exception("数据保留清理失败")

        async def retention_loop() -> None:
            while True:
                await asyncio.sleep(3600)
                await apply_data_retention()

        # 将后台任务挂载到 app.state，方便关闭时取消
        if settings.MQTT_DISABLE_SENSOR_SIM:
            app.state._sensor_task = None
        else:
            app.state._sensor_task = asyncio.create_task(sensor_loop())
        if settings.SENSOR_HISTORY_RETENTION_DAYS > 0:
            await apply_data_retention()
            app.state._retention_task = asyncio.create_task(retention_loop())
        else:
            app.state._retention_task = None

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        """应用关闭时执行：取消所有后台定时任务。"""
        for attr in ("_sensor_task", "_retention_task"):
            task = getattr(app.state, attr, None)
            if task:
                task.cancel()
        if settings.MQTT_ENABLED:
            await mqtt_client.stop()
        # 关闭 LLM httpx 客户端
        agent_svc = getattr(app.state, "agent_service", None)
        if agent_svc and hasattr(agent_svc, "_llm"):
            await agent_svc._llm.close()
        await dispose_db()

    return app


# 创建全局应用实例，供 uvicorn 启动使用
app = create_app()
