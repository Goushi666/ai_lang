"""
JWT 与 Bearer 解析。

- 可选鉴权：无效/缺失 token 时部分依赖仍返回 None。
- 强制鉴权：使用 deps 中的 get_current_user。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Request
from jose import JWTError, jwt

from app.core.config import settings


def jwt_secret() -> str:
    """与签发令牌使用同一密钥；未配置时使用仅适用于开发的占位值。"""
    return (settings.JWT_SECRET_KEY or "").strip() or "dev-insecure-secret"


def extract_bearer_token(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    if not auth:
        return None
    if not auth.lower().startswith("bearer "):
        return None
    return auth.split(" ", 1)[1].strip()


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, jwt_secret(), algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


def get_optional_current_user(request: Request) -> Optional[str]:
    token = extract_bearer_token(request)
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    sub = payload.get("sub") or payload.get("user")
    return str(sub) if sub is not None else None
