"""注册、登录、JWT（密码 bcrypt）。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
from fastapi import HTTPException
from jose import jwt

from app.core.config import settings
from app.core.security import jwt_secret
from app.repositories.user_repo import UserRepository
from app.schemas.auth import UserPublic


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("ascii"))
    except Exception:
        return False


def create_access_token(*, user_id: int, username: str, level: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "level": level,
        "exp": expire,
    }
    return jwt.encode(payload, jwt_secret(), algorithm=settings.JWT_ALGORITHM)


class AuthService:
    def __init__(self, repo: UserRepository):
        self._repo = repo

    async def register(self, username: str, password: str) -> UserPublic:
        existing = await self._repo.get_by_username(username)
        if existing is not None:
            raise HTTPException(status_code=400, detail="用户名已存在")
        n = await self._repo.count()
        level = "admin" if n == 0 else "viewer"
        row = await self._repo.create(
            username=username,
            password_hash=hash_password(password),
            level=level,
        )
        return UserPublic.model_validate(row)

    async def login(self, username: str, password: str) -> tuple[str, UserPublic]:
        row = await self._repo.get_by_username(username)
        if row is None or not row.is_active:
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        if not verify_password(password, row.password_hash):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        token = create_access_token(user_id=row.id, username=row.username, level=row.level)
        return token, UserPublic.model_validate(row)

    async def get_user(self, user_id: int) -> Optional[UserPublic]:
        row = await self._repo.get_by_id(user_id)
        if row is None or not row.is_active:
            return None
        return UserPublic.model_validate(row)
