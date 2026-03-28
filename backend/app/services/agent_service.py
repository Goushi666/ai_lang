"""智能 Agent：框架占位，不调用外部 LLM 与工具。"""

import uuid
from typing import List, Optional

from app.schemas.agent import ChatMessage, ChatResponse


class AgentService:
    async def chat(
        self,
        *,
        messages: List[ChatMessage],
        session_id: Optional[str] = None,
    ) -> ChatResponse:
        _ = messages
        sid = session_id or str(uuid.uuid4())
        return ChatResponse(
            content=(
                "【智能助手 · 框架占位】尚未接入大模型与工具调用。"
                "后续将在此连接 LLM，并通过工具访问传感器、告警、车辆状态与环境分析接口。"
            ),
            session_id=sid,
            framework=True,
        )
