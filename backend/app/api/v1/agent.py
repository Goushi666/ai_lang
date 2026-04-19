"""智能 Agent API 路由。"""

from __future__ import annotations

import asyncio
import json
import uuid
from functools import partial
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.deps import agent_chat_repo_dep, agent_service_dep, knowledge_service_dep
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
from app.services.knowledge import KnowledgeService

router = APIRouter()

_BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _check_enabled() -> None:
    if not settings.AGENT_ENABLED:
        raise HTTPException(status_code=503, detail="Agent 功能已关闭（AGENT_ENABLED=false）")


# ------------------------------------------------------------------
# 健康检查
# ------------------------------------------------------------------

@router.get("/health", summary="Agent 模块状态")
async def agent_health(request: Request):
    llm_ok = bool(settings.LLM_API_KEY and settings.LLM_BASE_URL and settings.LLM_MODEL)
    if not settings.AGENT_ENABLED:
        msg = "Agent 已关闭"
    elif llm_ok:
        msg = f"已接入 LLM（{settings.LLM_MODEL}）"
    else:
        msg = "未配置 LLM（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL）"
    ks: Optional[KnowledgeService] = getattr(request.app.state, "knowledge_service", None)
    kb_chunks = 0
    if ks is not None:
        try:
            kb_chunks = int(ks.status().get("total_chunks", 0))
        except Exception:
            kb_chunks = 0
    rag_tool = bool(settings.AGENT_RAG_ENABLED and ks is not None)
    return {
        "enabled": settings.AGENT_ENABLED,
        "llm_configured": llm_ok,
        "message": msg,
        "rag_enabled": settings.AGENT_RAG_ENABLED,
        "stream_enabled": settings.AGENT_STREAM_ENABLED,
        "knowledge_ready": ks is not None,
        "knowledge_chunks": kb_chunks,
        "rag_retrieval_ready": rag_tool,
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

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
async def knowledge_ingest(
    body: KnowledgeIngestRequest,
    ks: KnowledgeService = Depends(knowledge_service_dep),
):
    _check_enabled()
    if body.file_path:
        p = Path(body.file_path)
        if not p.is_absolute():
            p = (_BACKEND_ROOT / p).resolve()
        n = await asyncio.to_thread(partial(ks.ingest_file, p, replace=body.replace))
        return {"ok": True, "chunks": n, "source": p.name}
    if body.content is not None and str(body.content).strip():
        sid = (body.source_id or "").strip() or f"paste_{uuid.uuid4().hex[:12]}"
        n = await asyncio.to_thread(
            partial(
                ks.ingest_text,
                text=body.content,
                source=sid,
                replace=body.replace,
            ),
        )
        return {"ok": True, "chunks": n, "source": sid}
    raise HTTPException(status_code=422, detail="请提供 file_path 或 content")


@router.get("/knowledge/status", response_model=KnowledgeStatusResponse, summary="查询知识库状态")
async def knowledge_status(request: Request):
    _check_enabled()
    svc: Optional[KnowledgeService] = getattr(request.app.state, "knowledge_service", None)
    if svc is None:
        return KnowledgeStatusResponse(
            status="not_initialized",
            total_chunks=0,
            total_documents=0,
        )
    st = svc.status()
    return KnowledgeStatusResponse(
        status=st.get("status", "ok"),
        total_chunks=st.get("total_chunks", 0),
        total_documents=st.get("total_documents", 0),
        collection=st.get("collection"),
        db_path=st.get("db_path"),
    )


@router.delete("/knowledge/{doc_id}", summary="按 source 标识删除文档块")
async def knowledge_delete(
    doc_id: str,
    ks: KnowledgeService = Depends(knowledge_service_dep),
):
    _check_enabled()
    removed = await asyncio.to_thread(ks.delete_by_source, doc_id)
    return {"ok": True, "removed_chunks": removed, "source": doc_id}
