"""
依赖注入（Dependency Injection, DI）层。

文档里建议后端使用：`API路由层 -> Service -> Repository`。
这里把 Service 需要的 Repository 组合好，并提供“可选鉴权”的依赖函数（MVP 用）。
"""

from typing import Optional

from fastapi import Depends, HTTPException, Request

from app.services.knowledge import KnowledgeService

from app.core.config import settings
from app.core.security import decode_access_token, extract_bearer_token, get_optional_current_user
from app.services.agent import AgentService
from app.services.alarm_service import AlarmService
from app.services.analysis_service import AnalysisService
from app.services.sensor_service import SensorService
from app.repositories.agent_chat_repo import AgentChatRepository
from app.services.vehicle_service import VehicleService
from app.repositories.user_repo import UserRepository
from app.schemas.auth import UserPublic
from app.services.auth_service import AuthService


def sensor_service_dep(request: Request) -> SensorService:
    return request.app.state.sensor_service


def alarm_service_dep(request: Request) -> AlarmService:
    # 与 startup 共用同一内存仓库；environment_anomalies 与边沿告警共用同一 SQLite 仓库
    return AlarmService(
        repo=request.app.state.alarm_repo,
        environment_anomaly_repo=request.app.state.environment_anomaly_repo,
    )


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


def agent_service_dep(request: Request) -> AgentService:
    svc = getattr(request.app.state, "agent_service", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="Agent 服务未初始化")
    return svc


def agent_chat_repo_dep(request: Request) -> AgentChatRepository:
    repo = getattr(request.app.state, "agent_chat_repo", None)
    if repo is None:
        raise HTTPException(status_code=503, detail="Agent 对话库未初始化")
    return repo


def optional_user_dep(request: Request) -> Optional[str]:
    # MVP：token 缺失/无效不强制拦截
    # 返回值：None 或 user_id（当前实现里用 payload 的 sub/user 字段）
    return get_optional_current_user(request)


def knowledge_service_dep(request: Request) -> KnowledgeService:
    svc = getattr(request.app.state, "knowledge_service", None)
    if svc is None:
        raise HTTPException(
            status_code=503,
            detail="知识库未初始化：请查看后端启动日志（KnowledgeService 构造失败）",
        )
    return svc


def user_repo_dep(request: Request) -> UserRepository:
    repo = getattr(request.app.state, "user_repo", None)
    if repo is None:
        raise HTTPException(status_code=503, detail="用户模块未初始化")
    return repo


def auth_service_dep(request: Request) -> AuthService:
    svc = getattr(request.app.state, "auth_service", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="认证服务未初始化")
    return svc


async def get_current_user(request: Request) -> UserPublic:
    token = extract_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="未登录")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    try:
        uid = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="令牌无效")
    svc: AuthService = auth_service_dep(request)
    user = await svc.get_user(uid)
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")
    return user


def require_admin_user(user: UserPublic = Depends(get_current_user)) -> UserPublic:
    if user.level != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


async def agent_user_level_dep(request: Request) -> str:
    """供 Agent 注入：guest | viewer | operator | admin（未登录或无效令牌为 guest）。"""
    token = extract_bearer_token(request)
    if not token:
        return "guest"
    payload = decode_access_token(token)
    if not payload:
        return "guest"
    try:
        uid = int(payload.get("sub"))
    except (TypeError, ValueError):
        return "guest"
    svc: AuthService = auth_service_dep(request)
    user = await svc.get_user(uid)
    if user is None:
        return "guest"
    return user.level if user.level in ("viewer", "operator", "admin") else "guest"

