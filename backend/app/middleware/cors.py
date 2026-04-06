"""
跨域（CORS）中间件配置。

文档强调前后端需要通过 HTTP 调用与 WebSocket 通信。
开发阶段通常允许跨域以便前端与后端端口不同。
"""

from __future__ import annotations

import json

from app.core.config import settings


def parse_cors_allow_origins(raw: str) -> list[str]:
    """
    将 .env 中的 CORS_ALLOW_ORIGINS 转为列表。
    支持：*、逗号分隔、JSON 数组字符串（如 [\"http://localhost:5173\"]）。
    """
    s = (raw or "*").strip()
    if not s or s == "*":
        return ["*"]
    if s.startswith("["):
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError:
            return ["*"]
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
        return ["*"]
    return [p.strip() for p in s.split(",") if p.strip()]


def cors_middleware() -> dict:
    """
    返回传给 ``CORSMiddleware`` 的关键字参数。

    注意（与 WebSocket 403 相关）：
    Starlette 的 CORS 中间件在校验 WebSocket 握手时，若同时设置
    ``allow_origins=["*"]`` 与 ``allow_credentials=True``，会违反浏览器 CORS 规则组合，
    结果常常是 **WebSocket 连接被拒绝并记录为 403**，而普通 GET/POST 仍可能返回 200。

    因此：使用通配来源时，必须关闭 ``allow_credentials``；若需要携带 Cookie 等凭证，
    请改为显式列出前端 Origin（例如 ``http://localhost:5173``）。
    """
    origins = parse_cors_allow_origins(settings.CORS_ALLOW_ORIGINS)
    wildcard_only = origins == ["*"] or origins == ["*", ""]

    # 通配 * 时不能带 credentials=True，否则浏览器/Starlette 对 WebSocket 会 403
    allow_credentials = not wildcard_only

    return {
        "allow_origins": origins,
        "allow_credentials": allow_credentials,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }

