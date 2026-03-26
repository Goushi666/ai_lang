"""
全局配置（MVP 阶段通过环境变量读取）。

文档技术选型提到：Pydantic 用于数据验证与配置管理。
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "ai_lang-backend"
    API_PREFIX: str = "/api"

    # MVP：先放宽跨域与鉴权，后续再收紧
    CORS_ALLOW_ORIGINS: list[str] = ["*"]

    # JWT
    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"

    # SQLite (MVP) / MySQL (未来)
    SQLITE_URL: str = "sqlite+aiosqlite:///./app.db"


settings = Settings()

