"""
依赖注入（Dependency Injection, DI）层。

文档里建议后端使用：`API路由层 -> Service -> Repository`。
这里把 Service 需要的 Repository 组合好，并提供“可选鉴权”的依赖函数（MVP 用）。
"""

from typing import Optional

from fastapi import Depends, Request

from app.core.security import get_optional_current_user
from app.repositories.alarm_repo import AlarmRepository
from app.repositories.sensor_repo import SensorRepository
from app.repositories.vehicle_repo import VehicleRepository
from app.services.alarm_service import AlarmService
from app.services.sensor_service import SensorService
from app.services.vehicle_service import VehicleService


def sensor_service_dep() -> SensorService:
    # MVP：直接 new Repository（后续可替换成单例/连接池/DI 容器）
    repo = SensorRepository()
    return SensorService(repo=repo)


def alarm_service_dep() -> AlarmService:
    # MVP：告警历史/配置先用内存仓库
    repo = AlarmRepository()
    return AlarmService(repo=repo)


def vehicle_service_dep() -> VehicleService:
    # MVP：车辆状态先用内存仓库
    repo = VehicleRepository()
    return VehicleService(repo=repo)


def optional_user_dep(request: Request) -> Optional[str]:
    # MVP：token 缺失/无效不强制拦截
    # 返回值：None 或 user_id（当前实现里用 payload 的 sub/user 字段）
    return get_optional_current_user(request)

