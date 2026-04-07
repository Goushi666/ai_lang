"""
依赖注入（Dependency Injection, DI）层。

文档里建议后端使用：`API路由层 -> Service -> Repository`。
这里把 Service 需要的 Repository 组合好，并提供“可选鉴权”的依赖函数（MVP 用）。
"""

from typing import Optional

from fastapi import Depends, HTTPException, Request

from app.core.config import settings
from app.core.security import get_optional_current_user
from app.services.agent_service import AgentService
from app.services.alarm_service import AlarmService
from app.services.analysis_service import AnalysisService
from app.services.sensor_service import SensorService
from app.services.vehicle_service import VehicleService


def sensor_service_dep(request: Request) -> SensorService:
    return request.app.state.sensor_service


def alarm_service_dep(request: Request) -> AlarmService:
    # 与 startup 共用同一内存仓库，否则每次请求新建会导致阈值保存无效
    return AlarmService(repo=request.app.state.alarm_repo)


def vehicle_service_dep(request: Request) -> VehicleService:
    # 与 lifespan 共用同一内存仓库，保证状态与 MQTT 发布一致
    return request.app.state.vehicle_service


def analysis_service_dep(request: Request) -> AnalysisService:
    if not settings.ANALYSIS_ENABLED:
        raise HTTPException(status_code=503, detail="环境分析已关闭")
    return AnalysisService(
        sensor_repo=request.app.state.sensor_repo,
        alarm_service=AlarmService(repo=request.app.state.alarm_repo),
    )


def agent_service_dep() -> AgentService:
    return AgentService()


def optional_user_dep(request: Request) -> Optional[str]:
    # MVP：token 缺失/无效不强制拦截
    # 返回值：None 或 user_id（当前实现里用 payload 的 sub/user 字段）
    return get_optional_current_user(request)

