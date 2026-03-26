import asyncio
import json
from typing import Any

from fastapi import WebSocket


class WebSocketManager:
    """
    WebSocket 连接管理器（MVP）。

    职责：
    - 接收连接 / 断开
    - 统一广播消息（按文档消息协议：{type, payload, timestamp}）
    - 处理简单的客户端心跳：收到 {"type":"ping"} 保持连接活跃

    后续可扩展：
    - 权限校验（按 JWT）
    - 按 type/主题订阅（消息分组）
    - 心跳回 pong / 超时清理
    """
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        # 接受连接并加入客户端集合
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, message: dict[str, Any]) -> None:
        # 广播消息给所有已连接客户端
        data = json.dumps(message, ensure_ascii=False)
        stale: list[WebSocket] = []

        async with self._lock:
            clients = list(self._clients)

        for ws in clients:
            try:
                await ws.send_text(data)
            except Exception:
                stale.append(ws)

        if stale:
            async with self._lock:
                for ws in stale:
                    self._clients.discard(ws)

    async def handle_client_message(self, ws: WebSocket, raw_text: str) -> None:
        """
        MVP：目前只处理心跳 ping。

        客户端（前端 utils/websocket.js）会定时发送：{"type":"ping"}
        """
        try:
            data = json.loads(raw_text)
        except Exception:
            return

        msg_type = data.get("type")
        if msg_type == "ping":
            # 可选：回 pong 或仅维持连接
            # await ws.send_text(json.dumps({"type":"pong","payload":{},"timestamp":data.get("timestamp")}))
            return


websocket_manager = WebSocketManager()

