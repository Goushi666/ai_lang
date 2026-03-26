"""
认证授权（MVP stub）。

文档要求 JWT（python-jose）。在 MVP 中我们采用“可选鉴权”：
- token 缺失：不阻断接口调用
- token 无效：返回 None（不抛错）

等你需要“强制鉴权”时，再把可选逻辑收紧即可。
"""

from typing import Optional

from fastapi import Request
from jose import JWTError, jwt

from app.core.config import settings


def extract_bearer_token(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    if not auth:
        return None
    if not auth.lower().startswith("bearer "):
        return None
    return auth.split(" ", 1)[1].strip()


def get_optional_current_user(request: Request) -> Optional[str]:
    # 如果没有 Authorization: Bearer ...，直接返回 None
    token = extract_bearer_token(request)
    if not token:
        return None

    # MVP：token 无效也不阻断（可在后续改为 enforced）
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        # 约定：sub 作为用户标识（你后续可替换为实际字段）
        # 返回值目前用于“可选用户上下文”，MVP 暂不用于强制权限控制
        return payload.get("sub") or payload.get("user")  # type: ignore[return-value]
    except JWTError:
        return None

