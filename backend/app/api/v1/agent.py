from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.deps import agent_service_dep
from app.schemas.agent import ChatRequest, ChatResponse
from app.services.agent_service import AgentService

router = APIRouter()


@router.get("/health", summary="Agent 模块是否启用（框架）")
async def agent_health():
    return {
        "enabled": settings.AGENT_ENABLED,
        "framework": True,
        "message": "未接入 LLM，仅返回占位回复" if settings.AGENT_ENABLED else "Agent 已关闭",
    }


@router.post("/chat", response_model=ChatResponse, summary="对话（框架占位）")
async def agent_chat(
    body: ChatRequest,
    service: AgentService = Depends(agent_service_dep),
):
    if not settings.AGENT_ENABLED:
        raise HTTPException(status_code=503, detail="Agent 功能已关闭（AGENT_ENABLED=false）")
    return await service.chat(messages=body.messages, session_id=body.session_id)
