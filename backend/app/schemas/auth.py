"""认证与用户管理 API 模型。"""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

UserLevel = Literal["viewer", "operator", "admin"]


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)

    @field_validator("username")
    @classmethod
    def username_chars(cls, v: str) -> str:
        s = v.strip()
        if not s or len(s) > 64:
            raise ValueError("用户名长度不合法")
        for c in s:
            if not (c.isascii() and (c.isalnum() or c == "_")):
                raise ValueError("用户名仅允许英文字母、数字与下划线")
        return s


class LoginRequest(BaseModel):
    username: str
    password: str


class UserPublic(BaseModel):
    id: int
    username: str
    level: str
    is_active: bool = True

    model_config = {"from_attributes": True}


class UserListItem(BaseModel):
    id: int
    username: str
    level: str
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class UsersListResponse(BaseModel):
    items: List[UserListItem]


class UpdateUserLevelRequest(BaseModel):
    level: UserLevel
