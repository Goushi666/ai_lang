"""多层记忆聚合：拼装注入 system 的附录，并写入情景/感知。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from app.core.config import Settings

from .working import WorkingMemoryStore

if TYPE_CHECKING:
    from app.repositories.agent_memory_repo import AgentMemoryRepository
    from app.services.knowledge.service import KnowledgeService

logger = logging.getLogger(__name__)


class AgentMemoryService:
    """
    - WorkingMemory：进程内 TTL 槽位
    - Episodic / Perceptual：SQLite（可选，无 repo 时仅工作+语义）
    - Semantic：复用 KnowledgeService.search（与 RAG 工具同源，轻量 top_k）
    """

    def __init__(
        self,
        *,
        settings: Settings,
        working: WorkingMemoryStore,
        repo: Optional["AgentMemoryRepository"] = None,
        knowledge: Optional["KnowledgeService"] = None,
    ) -> None:
        self._settings = settings
        self._working = working
        self._repo = repo
        self._knowledge = knowledge

    def touch_user_turn(self, session_id: str, last_user: str) -> None:
        """每轮用户话后刷新工作记忆锚点。"""
        if not getattr(self._settings, "AGENT_MEMORY_LAYERS_ENABLED", True):
            return
        u = (last_user or "").strip()
        if not u:
            return
        ttl = float(getattr(self._settings, "AGENT_MEMORY_WORKING_TTL_SEC", 600.0))
        self._working.set(session_id, "last_user_turn", u[:4000], ttl_sec=ttl)
        self._working.set(
            session_id,
            "turn_anchor_ts",
            str(int(__import__("time").time())),
            ttl_sec=ttl,
        )

    async def build_system_appendix(
        self,
        *,
        conversation_id: str,
        last_user: str,
        mode: str,
    ) -> str:
        """返回追加到 system 的 Markdown 块；无内容则返回空串。"""
        if not getattr(self._settings, "AGENT_MEMORY_LAYERS_ENABLED", True):
            return ""

        parts: List[str] = []
        budget = int(getattr(self._settings, "AGENT_MEMORY_INJECT_MAX_CHARS", 6000))
        used = 0

        def add_block(title: str, body: str) -> None:
            nonlocal used
            b = (body or "").strip()
            if not b:
                return
            chunk = f"## {title}\n{b}"
            if used + len(chunk) > budget:
                remain = max(0, budget - used - 50)
                if remain < 80:
                    return
                chunk = chunk[:remain] + "…"
            parts.append(chunk)
            used += len(chunk)

        # --- 工作记忆 ---
        lines = self._working.snapshot_lines(conversation_id)
        if lines:
            body = "\n".join(f"- **{k}**：{v[:1200]}" for k, v in lines)
            add_block("工作记忆（本会话短期上下文，TTL）", body)

        # --- 情景记忆 ---
        if self._repo:
            try:
                eps = await self._repo.list_recent_episodes(conversation_id, limit=10)
            except Exception as exc:
                logger.debug("list_recent_episodes: %s", exc)
                eps = []
            if eps:
                body = "\n".join(
                    f"- [{e.get('created_at', '')}] ({e.get('kind', '')}) {e.get('summary', '')}"
                    for e in eps
                )
                add_block("情景记忆（本会话近期事件时间线）", body)

        # --- 语义记忆（轻量检索；rag 模式已由专用 RAG 注入，避免重复堆叠）---
        if (
            mode != "rag"
            and getattr(self._settings, "AGENT_MEMORY_SEMANTIC_IN_GENERAL", True)
            and self._knowledge
        ):
            q = (last_user or "").strip()
            if q:
                try:
                    top = int(getattr(self._settings, "AGENT_MEMORY_SEMANTIC_TOP_K", 3))
                    hits = self._knowledge.search(q, top_k=max(1, min(top, 8)))
                except Exception as exc:
                    logger.debug("semantic search: %s", exc)
                    hits = []
                if hits:
                    lines = []
                    for i, h in enumerate(hits, 1):
                        src = h.get("source") or "?"
                        tx = (h.get("text") or "").strip().replace("\n", " ")
                        if len(tx) > 420:
                            tx = tx[:419] + "…"
                        lines.append(f"{i}. （{src}）{tx}")
                    add_block("语义记忆（知识库摘要命中，非 RAG 全量）", "\n".join(lines))

        # --- 感知记忆 ---
        if self._repo:
            try:
                perc = await self._repo.list_recent_perceptual(conversation_id, limit=6)
            except Exception as exc:
                logger.debug("list_recent_perceptual: %s", exc)
                perc = []
            if perc:
                body = "\n".join(
                    f"- [{p.get('modality', '')}] {p.get('summary', '')} `ref={p.get('ref', '')}`"
                    for p in perc
                )
                add_block("感知记忆（多模态引用摘要）", body)

        if not parts:
            return ""
        return (
            "\n\n---\n\n# 多层记忆上下文\n"
            + "\n\n".join(parts)
            + "\n\n以上由系统自动注入，请与工具返回的实时数据区分；无实时数据时勿编造。"
        )

    async def record_tool_episode(
        self,
        conversation_id: str,
        *,
        tool_names: List[str],
        ok: bool,
    ) -> None:
        if not self._repo or not getattr(self._settings, "AGENT_MEMORY_LAYERS_ENABLED", True):
            return
        names = [n for n in tool_names if n]
        if not names:
            return
        summary = f"工具批：{', '.join(names)} → {'ok' if ok else '含失败'}"
        try:
            await self._repo.append_episode(
                conversation_id,
                kind="tool_batch",
                summary=summary[:2000],
                detail={"tools": names, "ok": ok},
            )
        except Exception as exc:
            logger.debug("record_tool_episode: %s", exc)

    async def record_perceptual(
        self,
        conversation_id: str,
        *,
        modality: str,
        ref: str,
        summary: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self._repo or not getattr(self._settings, "AGENT_MEMORY_LAYERS_ENABLED", True):
            return
        try:
            await self._repo.append_perceptual(
                conversation_id,
                modality=modality,
                ref=ref,
                summary=summary[:4000],
                extra=extra,
            )
        except Exception as exc:
            logger.debug("record_perceptual: %s", exc)

    async def delete_session(self, conversation_id: str) -> None:
        self._working.clear_session(conversation_id)
        if self._repo:
            try:
                await self._repo.delete_by_conversation(conversation_id)
            except Exception as exc:
                logger.debug("memory delete_session: %s", exc)
