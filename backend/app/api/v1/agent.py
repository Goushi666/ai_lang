"""智能 Agent API 路由。"""

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.deps import agent_chat_repo_dep, agent_service_dep
from app.repositories.agent_chat_repo import AgentChatRepository
from app.schemas.agent import (
    ChatRequest,
    ChatResponse,
    KnowledgeIngestRequest,
    KnowledgeStatusResponse,
    SessionListItem,
    SessionListResponse,
    SessionResponse,
)
from app.services.agent import AgentService

router = APIRouter()


def _check_enabled() -> None:
    if not settings.AGENT_ENABLED:
        raise HTTPException(status_code=503, detail="Agent 功能已关闭（AGENT_ENABLED=false）")


# ------------------------------------------------------------------
# 健康检查
# ------------------------------------------------------------------

@router.get("/health", summary="Agent 模块状态")
async def agent_health():
    llm_ok = bool(settings.LLM_API_KEY and settings.LLM_BASE_URL and settings.LLM_MODEL)
    if not settings.AGENT_ENABLED:
        msg = "Agent 已关闭"
    elif llm_ok:
        msg = f"已接入 LLM（{settings.LLM_MODEL}）"
    else:
        msg = "未配置 LLM（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL）"
    return {
        "enabled": settings.AGENT_ENABLED,
        "llm_configured": llm_ok,
        "message": msg,
        "rag_enabled": settings.AGENT_RAG_ENABLED,
        "stream_enabled": settings.AGENT_STREAM_ENABLED,
    }


# ------------------------------------------------------------------
# 对话
# ------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse, summary="对话主接口")
async def agent_chat(
    body: ChatRequest,
    service: AgentService = Depends(agent_service_dep),
):
    _check_enabled()
    return await service.chat(
        messages=body.messages,
        session_id=body.session_id,
        mode=body.mode,
        stream=body.stream,
    )


@router.post("/chat/stream", summary="对话流式（SSE，思考与正文分 delta 推送）")
async def agent_chat_stream(
    body: ChatRequest,
    service: AgentService = Depends(agent_service_dep),
):
    """``data:`` 每行为 JSON：``clarification`` | ``delta`` | ``done``。"""
    _check_enabled()
    if not settings.AGENT_STREAM_ENABLED:
        raise HTTPException(status_code=503, detail="流式输出已关闭（AGENT_STREAM_ENABLED=false）")

    async def event_gen():
        async for ev in service.chat_sse_events(
            messages=body.messages,
            session_id=body.session_id,
            mode=body.mode,
        ):
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


# ------------------------------------------------------------------
# 会话管理
# ------------------------------------------------------------------

@router.get("/sessions", response_model=SessionListResponse, summary="会话列表（SQLite）")
async def list_agent_sessions(
    limit: int = 50,
    repo: AgentChatRepository = Depends(agent_chat_repo_dep),
):
    _check_enabled()
    rows = await repo.list_summaries(limit=limit)
    return SessionListResponse(
        items=[
            SessionListItem(
                session_id=r["session_id"],
                title=r["title"],
                mode=r["mode"],
                updated_at=r.get("updated_at"),
                created_at=r.get("created_at"),
            )
            for r in rows
        ]
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse, summary="获取会话历史")
async def get_session(
    session_id: str,
    service: AgentService = Depends(agent_service_dep),
):
    _check_enabled()
    data = await service.get_session(session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")
    return SessionResponse(**data)


@router.delete("/sessions/{session_id}", summary="清除会话")
async def delete_session(
    session_id: str,
    service: AgentService = Depends(agent_service_dep),
):
    _check_enabled()
    deleted = await service.delete_session(session_id)
    return {"ok": deleted, "session_id": session_id}


# ------------------------------------------------------------------
# 工具列表（调试用）
# ------------------------------------------------------------------

@router.get("/tools", summary="查询当前可用的 Tool 列表")
async def list_tools(
    service: AgentService = Depends(agent_service_dep),
):
    _check_enabled()
    return {"tools": service.list_tools()}


# ------------------------------------------------------------------
# 知识库管理（P0 接口骨架，实际实现待 RAG 集成）
# ------------------------------------------------------------------

@router.post("/knowledge/ingest", summary="导入文档到知识库")
async def knowledge_ingest(body: KnowledgeIngestRequest):
    _check_enabled()
    raise HTTPException(status_code=501, detail="RAG 知识库尚未实现，敬请期待")


@router.get("/knowledge/status", response_model=KnowledgeStatusResponse, summary="查询知识库状态")
async def knowledge_status():
    _check_enabled()
    return KnowledgeStatusResponse()


@router.delete("/knowledge/{doc_id}", summary="删除文档索引")
async def knowledge_delete(doc_id: str):
    _check_enabled()
    raise HTTPException(status_code=501, detail="RAG 知识库尚未实现，敬请期待")
