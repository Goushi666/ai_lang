"""
跨域（CORS）中间件配置。

文档强调前后端需要通过 HTTP 调用与 WebSocket 通信。
开发阶段通常允许跨域以便前端与后端端口不同。
"""

from app.core.config import settings


def cors_middleware() -> dict:
    # MVP：允许所有来源（*），后续建议收紧到具体域名/端口
    return {
        "allow_origins": settings.CORS_ALLOW_ORIGINS,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }

