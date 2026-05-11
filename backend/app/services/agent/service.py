"""AgentService：Agent 模块的门面，编排 LLM、Tool、Skill、Session。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Dict, List, Optional
from app.core.config import settings

from app.schemas.agent import (
    ChatMessage,
    ChatResponse,
    ClarificationPayload,
    ExportDownloadItem,
)

from .clarifier import Clarifier
from .context.session import Session, SessionManager
from .graph.build import build_agent_graph
from .graph.deps import AgentGraphDeps
from .llm.client import LLMClient
from .skills import SkillRegistry
from .tools import ToolRegistry

logger = logging.getLogger(__name__)


async def _emit_sse_text_fragments(
    field: str,
    piece: str,
) -> AsyncIterator[Dict[str, Any]]:
    """将上游可能较长的 delta 拆成更细的 SSE 事件，改善前端「逐字」观感。"""
    if not piece:
        return
    n = int(getattr(settings, "AGENT_STREAM_UI_CHUNK_SIZE", 0) or 0)
    tick = bool(getattr(settings, "AGENT_STREAM_YIELD_TO_LOOP", True))
    if n <= 0:
        yield {"type": "delta", field: piece}
        if tick:
            await asyncio.sleep(0)
        return
    step = max(1, n)
    for i in range(0, len(piece), step):
        yield {"type": "delta", field: piece[i : i + step]}
        if tick:
            await asyncio.sleep(0)


class AgentService:
    """
    智能 Agent 服务。

    职责：
    1. 维护对话会话（SessionManager）
    2. 编译并运行 LangGraph：澄清 → 构建上下文 → LLM ⟷ 工具 → 收尾
    3. ``chat`` 使用 ``ainvoke``；``chat_sse_events`` 使用 ``astream(custom)`` 与图内 ``get_stream_writer`` 对齐事件
    4. 组装 ``ChatResponse`` / SSE JSON 载荷
    """

    def __init__(
        self,
        session_manager: SessionManager,
        tool_registry: ToolRegistry,
        skill_registry: SkillRegistry,
        llm_client: LLMClient,
        clarifier: Clarifier,
        max_tool_rounds: int = 10,
        chat_repo: Any = None,
        memory_service: Any = None,
    ):
        self._sessions = session_manager
        self._tools = tool_registry
        self._skills = skill_registry
        self._llm = llm_client
        self._clarifier = clarifier
        self._max_tool_rounds = max_tool_rounds
        self._chat_repo = chat_repo
        self._memory_service = memory_service
        self._agent_graph = build_agent_graph(AgentGraphDeps(service=self))

    @staticmethod
    def _sync_conversation_title_done_flag(session: Session, transcript: List[ChatMessage]) -> None:
        """
        客户端每次用完整 transcript 覆盖内存会话后调用。
        若请求里仍只有一条 user（整会话的第一轮提问），重置标题标记，以便本轮结束后生成侧栏标题。
        多轮后 transcript 含多条 user 时保持原标记，避免每轮重复调用标题模型。
        """
        n_user = sum(1 for m in transcript if m.role == "user")
        if n_user == 1:
            session.conversation_title_done = False

    async def _persist(
        self,
        session: Session,
        title: Optional[str] = None,
        *,
        infer_title_from_messages: bool = True,
    ) -> Optional[str]:
        if self._chat_repo is None:
            return None
        return await self._chat_repo.persist_session_snapshot(
            session,
            title=title,
            infer_title_from_messages=infer_title_from_messages,
        )

    @staticmethod
    def _first_round_user_assistant(session: Session) -> tuple[str, str]:
        """时间序上第一条非空 user，及其后第一条 assistant 的正文。"""
        idx_u: Optional[int] = None
        u_text = ""
        for i, m in enumerate(session.messages):
            if m.role == "user" and (m.content or "").strip():
                idx_u = i
                u_text = (m.content or "").strip()
                break
        if idx_u is None:
            return "", ""
        for m in session.messages[idx_u + 1 :]:
            if m.role == "assistant":
                c0 = (m.content or "").strip()
                r0 = (m.reasoning or "").strip()
                # 起标题时须让模型看到思考+正文；仅有其一则单用
                if r0 and c0:
                    merged = f"{r0}\n\n{c0}"
                else:
                    merged = c0 or r0
                return u_text, merged
        return u_text, ""

    async def _suggest_conversation_title(self, session: Session) -> Optional[str]:
        if session.conversation_title_done:
            return None
        u_text, a_text = self._first_round_user_assistant(session)
        if not u_text or not a_text:
            return None
        session.conversation_title_done = True

        def _clean(raw: str) -> str:
            s = (raw or "").strip().split("\n")[0].strip()
            for ch in ('"', "'", "「", "」", "《", "》", "*", "#"):
                s = s.strip(ch).strip()
            if len(s) > 24:
                s = s[:23] + "…"
            return s

        def _fallback_round_title() -> str:
            """首轮命名：优先助手首答（含思考与正文合并后的摘要），其次用户首问。"""
            a_line = a_text.replace("\n", " ").strip()
            if len(a_line) > 22:
                a_line = a_line[:22] + "…"
            a_short = _clean(a_line)
            if a_short and len(a_short.replace("…", "")) >= 2:
                return a_short
            u_one = u_text.replace("\n", " ").strip()
            if len(u_one) > 22:
                u_one = u_one[:22] + "…"
            u_short = _clean(u_one)
            if u_short and len(u_short.replace("…", "")) >= 2:
                return u_short
            return "会话"

        try:
            if not self._llm.is_configured:
                if "框架占位" in a_text or "尚未配置 LLM" in a_text:
                    return "演示会话"
                line = a_text.replace("\n", " ").strip()
                if len(line) > 22:
                    line = line[:22] + "…"
                return _clean(line) or "演示会话"

            title_msgs: List[Dict[str, Any]] = [
                {
                    "role": "system",
                    "content": (
                        "你是会话标题生成器。请仅根据「第一轮对话」：用户首条提问 + 助手首条回复（其中助手块可能同时包含"
                        "「思考/推理过程」与「正式回答」，请综合二者提炼主题，不要只看正文而忽略思考里的关键意图）。"
                        "请先在心里完成简要归纳（不要写出该归纳过程），然后只输出侧栏用的一条中文标题。"
                        "要求：10～22 个字；紧扣用户首问；勿照抄原句；勿含「用户」「助手」等标签；不要引号；"
                        "除这一行标题外不要输出任何其他文字。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"【用户】\n{u_text[:600]}\n\n"
                        f"【助手】（以下为第一轮助手输出全文，含思考与正文时请一并参考）\n{a_text[:4000]}"
                    ),
                },
            ]
            try:
                resp = await asyncio.wait_for(
                    self._llm.chat_completion(
                        title_msgs,
                        None,
                        max_tokens=64,
                    ),
                    timeout=4.0,
                )
            except asyncio.TimeoutError:
                logger.warning("conversation title suggest timed out")
                return _fallback_round_title()
            got = _clean((resp.content or "").strip()) or None
            return got or _fallback_round_title()
        except Exception as exc:
            logger.warning("conversation title suggest failed: %s", exc)
            return _fallback_round_title()

    async def _finalize_title_and_persist(self, session: Session) -> Optional[str]:
        """写入 assistant 后：首轮对答归纳标题并落库；返回实际标题字符串（供 SSE/JSON 同步侧栏，无库时仍返回内存标题）。"""
        prev_done = session.conversation_title_done
        suggested = await self._suggest_conversation_title(session)
        attempted = session.conversation_title_done and (not prev_done)
        infer = not attempted
        if suggested:
            if self._chat_repo is None:
                return suggested
            written = await self._persist(
                session,
                title=suggested,
                infer_title_from_messages=False,
            )
            return written if written else suggested
        if self._chat_repo is None:
            u, _a = self._first_round_user_assistant(session)
            if u:
                one = u.replace("\n", " ").strip()
                return (one[:28] + "…") if len(one) > 28 else one
            return None
        written = await self._persist(session, title=None, infer_title_from_messages=infer)
        return written

    async def _append_rag_retrieval(
        self,
        *,
        mode: str,
        last_user: str,
        system_prompt: str,
    ) -> str:
        """知识问答：在调用主模型前自动检索 knowledge_docs 入库片段，写入 system。"""
        if mode != "rag":
            return system_prompt
        q = (last_user or "").strip()
        if not q:
            return system_prompt
        if self._tools.get("search_knowledge_base") is None:
            return (
                system_prompt
                + "\n\n## 知识库\n当前未挂载检索工具（知识服务未初始化或 AGENT_RAG_ENABLED=false）。"
                "请如实告知用户无法检索内置说明，勿编造手册内容。"
            )
        res = await self._tools.execute("search_knowledge_base", query=q)
        if not res.ok:
            return system_prompt + f"\n\n## 知识库检索失败\n{res.error}"
        hits = (res.data or {}).get("hits") or []
        if not hits:
            return (
                system_prompt
                + "\n\n## 已检索到的说明文档片段\n（无）与本次问题未匹配到已入库说明；"
                "请如实告知，并建议用户换关键词或联系管理员执行知识库入库脚本。"
            )
        parts: List[str] = []
        budget = 12000
        used = 0
        for i, h in enumerate(hits, 1):
            src = h.get("source") or "?"
            body = (h.get("text") or "").strip()
            if not body:
                continue
            chunk = f"### 片段{i}（来源：{src}）\n{body}"
            if used + len(chunk) > budget:
                remain = max(0, budget - used - 80)
                if remain > 200:
                    chunk = f"### 片段{i}（来源：{src}）\n{body[:remain]}…（已截断）"
                    parts.append(chunk)
                break
            parts.append(chunk)
            used += len(chunk)
        appendix = "\n\n".join(parts)
        return (
            system_prompt
            + "\n\n## 已检索到的说明文档片段（须优先据此回答）\n"
            + appendix
        )

    async def _append_memory_context(
        self,
        *,
        session_id: str,
        mode: str,
        last_user: str,
        system_prompt: str,
    ) -> str:
        """多层记忆：工作 / 情景 / 语义 / 感知 注入 system（在 RAG 等之后）。"""
        mem = self._memory_service
        if mem is None:
            return system_prompt
        try:
            appendix = await mem.build_system_appendix(
                conversation_id=session_id,
                last_user=last_user,
                mode=mode,
            )
        except Exception as exc:
            logger.warning("多层记忆注入失败: %s", exc)
            return system_prompt
        if not appendix:
            return system_prompt
        return system_prompt + "\n\n" + appendix

    def touch_working_memory(self, session_id: str, last_user: str) -> None:
        if self._memory_service is None:
            return
        try:
            self._memory_service.touch_user_turn(session_id, last_user)
        except Exception as exc:
            logger.debug("touch_working_memory: %s", exc)

    # ------------------------------------------------------------------
    # 对话主入口
    # ------------------------------------------------------------------

    async def chat(
        self,
        *,
        messages: List[ChatMessage],
        session_id: Optional[str] = None,
        mode: str = "general",
        stream: bool = False,
        user_level: str = "guest",
        clarification_user_enabled: Optional[bool] = None,
    ) -> ChatResponse:
        """
        处理一次用户对话请求（非流式）。

        编排由 LangGraph 完成：ingest → clarify → build_system → llm ⟷ tools → finalize。
        SSE 与 JSON 共用同一张编译图；SSE 通过 ``configurable.sse_stream`` + custom stream 推送增量。
        """
        del stream  # API 保留字段；非流式入口不使用
        session = self._sessions.get_or_create(session_id, mode=mode)
        result = await self._agent_graph.ainvoke(
            {
                "session": session,
                "request_messages": messages,
                "mode": mode,
                "user_level": user_level,
                "max_tool_rounds": self._max_tool_rounds,
                "clarification_user_enabled": clarification_user_enabled,
            }
        )
        clarification = result.get("clarification")
        exports_raw = result.get("collected_exports") or []
        clarification_model = (
            clarification if isinstance(clarification, ClarificationPayload) else None
        )
        return ChatResponse(
            content=result.get("final_content") or "",
            session_id=session.id,
            framework=bool(result.get("framework", not self._llm.is_configured)),
            clarification=clarification_model,
            reasoning=result.get("final_reasoning"),
            usage=result.get("usage") or None,
            conversation_title=result.get("conversation_title"),
            exports=[ExportDownloadItem(**x) for x in exports_raw],
            industrial_audit=result.get("audit_result"),
            industrial_reflection=result.get("reflection_result"),
        )

    async def chat_sse_events(
        self,
        *,
        messages: List[ChatMessage],
        session_id: Optional[str] = None,
        mode: str = "general",
        user_level: str = "guest",
        clarification_user_enabled: Optional[bool] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        供 SSE 使用：与 ``chat()`` 共用同一张 LangGraph。

        通过 ``astream(..., stream_mode=[\"custom\",\"values\"])`` 消费节点内
        ``get_stream_writer`` 推送的事件（delta / export_ready / clarification / done）。
        """
        session = self._sessions.get_or_create(session_id, mode=mode)
        initial: Dict[str, Any] = {
            "session": session,
            "request_messages": messages,
            "mode": mode,
            "user_level": user_level,
            "max_tool_rounds": self._max_tool_rounds,
            "clarification_user_enabled": clarification_user_enabled,
        }
        graph_config: Dict[str, Any] = {"configurable": {"sse_stream": True}}

        async for stream_mode, chunk in self._agent_graph.astream(
            initial,
            config=graph_config,
            stream_mode=["custom", "values"],
        ):
            if stream_mode != "custom":
                continue
            if not isinstance(chunk, dict):
                continue
            typ = chunk.get("type")
            if typ == "delta":
                field = chunk.get("field")
                text = chunk.get("text") or ""
                if text and field in ("reasoning", "content"):
                    async for out in _emit_sse_text_fragments(str(field), text):
                        yield out
                continue
            yield chunk

    # ------------------------------------------------------------------
    # 会话管理
    # ------------------------------------------------------------------

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = self._sessions.get(session_id)
        if session is None and self._chat_repo is not None:
            loaded = await self._chat_repo.load_session(session_id)
            if loaded is not None:
                self._sessions.restore(loaded)
                session = loaded
        if session is None:
            return None
        return {
            "session_id": session.id,
            "mode": session.mode,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp,
                    "reasoning": m.reasoning if m.role == "assistant" else None,
                }
                for m in session.messages
            ],
            "created_at": session.created_at,
            "updated_at": session.updated_at,
        }

    async def delete_session(self, session_id: str) -> bool:
        ok = self._sessions.delete(session_id)
        if self._memory_service is not None:
            try:
                await self._memory_service.delete_session(session_id)
            except Exception as exc:
                logger.debug("delete_session memory: %s", exc)
        if self._chat_repo is not None:
            db_ok = await self._chat_repo.delete_conversation(session_id)
            return ok or db_ok
        return ok

    # ------------------------------------------------------------------
    # 工具信息
    # ------------------------------------------------------------------

    def list_tools(self) -> List[Dict[str, Any]]:
        return self._tools.list_declarations()

    @property
    def is_llm_configured(self) -> bool:
        return self._llm.is_configured
