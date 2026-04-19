"""AgentService：Agent 模块的门面，编排 LLM、Tool、Skill、Session。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from app.core.config import settings

from app.schemas.agent import (
    ChatMessage,
    ChatResponse,
    ClarificationOption as SchemaClarificationOption,
    ClarificationPayload,
)

from .clarifier import Clarifier
from .context.session import Message, Session, SessionManager
from .llm.client import LLMClient, LLMResponse
from .llm.prompts import get_system_prompt
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
    2. 组装 MCP 上下文（system prompt + tool 声明 + 对话历史）
    3. 调用 LLM，解析 tool_calls，执行工具，循环直到产出最终回答
    4. 返回 ChatResponse
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
    ):
        self._sessions = session_manager
        self._tools = tool_registry
        self._skills = skill_registry
        self._llm = llm_client
        self._clarifier = clarifier
        self._max_tool_rounds = max_tool_rounds
        self._chat_repo = chat_repo

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
                # 推理模型常见：正文在流里尚未合并时 content 为空，仅有 reasoning
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
            line = a_text.replace("\n", " ").strip() or u_text.replace("\n", " ").strip()
            if len(line) > 22:
                line = line[:22] + "…"
            out = _clean(line)
            return out or "会话"

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
                        "你是会话标题生成器。根据【用户】首问与【助手】首轮回复，概括主题，"
                        "输出一条中文标题：10～22 个字；勿照抄用户原句；勿含「用户」「助手」等标签；"
                        "不要引号；只输出一行标题，不要解释。"
                    ),
                },
                {"role": "user", "content": f"【用户】\n{u_text[:600]}\n\n【助手】\n{a_text[:1200]}"},
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
        """写入 assistant 后：首轮对答归纳标题并落库；返回实际写入 DB 的标题（供前端同步侧栏）。"""
        prev_done = session.conversation_title_done
        suggested = await self._suggest_conversation_title(session)
        attempted = session.conversation_title_done and (not prev_done)
        infer = not attempted
        if suggested:
            written = await self._persist(
                session,
                title=suggested,
                infer_title_from_messages=True,
            )
            return written
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
    ) -> ChatResponse:
        """
        处理一次用户对话请求。

        当前为框架实现：
        - 管理 session
        - 组装 prompt
        - 调用 LLM（stub 模式下返回占位）
        - 未来：tool_calls 循环
        """
        session = self._sessions.get_or_create(session_id, mode=mode)
        session.mode = mode

        # 客户端每次携带完整 transcripts 时，用请求体覆盖内存会话，避免重复追加
        session.messages.clear()
        for msg in messages:
            session.add_message(
                Message(
                    role=msg.role,
                    content=msg.content,
                    reasoning=msg.reasoning if msg.role == "assistant" else None,
                )
            )

        # 仅对「本轮最后一条 user」做澄清（不额外调用大模型）
        last_user = ""
        for msg in reversed(messages):
            if msg.role == "user":
                last_user = msg.content or ""
                break
        cq = await self._clarifier.check(last_user, session_mode=session.mode)
        if cq is not None:
            session.add_message(Message(role="assistant", content=cq.question))
            conv_title = await self._finalize_title_and_persist(session)
            return ChatResponse(
                content=cq.question,
                session_id=session.id,
                framework=not self._llm.is_configured,
                clarification=ClarificationPayload(
                    question=cq.question,
                    options=[
                        SchemaClarificationOption(label=o.label, value=o.value)
                        for o in cq.options
                    ],
                    allow_custom=cq.allow_custom,
                ),
                reasoning=None,
                usage=None,
                conversation_title=conv_title,
            )

        # 组装 system prompt
        system_prompt = get_system_prompt(
            mode=session.mode,
            tool_names=self._tools.list_names() or None,
        )
        system_prompt = await self._append_rag_retrieval(
            mode=session.mode,
            last_user=last_user,
            system_prompt=system_prompt,
        )

        # 构建 LLM messages
        llm_messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]
        llm_messages.extend(session.to_llm_messages())

        # 获取 tool 声明
        tool_declarations = self._tools.list_declarations() or None

        # --- 调用 LLM（tool-call 循环） ---
        final_content = ""
        final_reasoning: Optional[str] = None
        usage: Dict[str, int] = {}

        for _round in range(self._max_tool_rounds):
            llm_resp: LLMResponse = await self._llm.chat_completion(
                messages=llm_messages,
                tools=tool_declarations,
            )

            if llm_resp.usage:
                usage = llm_resp.usage

            # 如果 LLM 返回纯文本（无 tool_calls），结束循环
            if not llm_resp.tool_calls:
                final_content = llm_resp.content or ""
                final_reasoning = llm_resp.reasoning
                break

            # --- 有 tool_calls：执行工具并将结果注入 messages ---
            # 先把 assistant 的 tool_calls 消息加入上下文
            llm_messages.append({
                "role": "assistant",
                "content": llm_resp.content or "",
                "tool_calls": llm_resp.tool_calls,
            })

            for tc in llm_resp.tool_calls:
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                try:
                    import json as _json
                    tool_args = _json.loads(func.get("arguments", "{}"))
                except Exception:
                    tool_args = {}

                result = await self._tools.execute(tool_name, **tool_args)

                llm_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": result.to_message_content(),
                })
        else:
            # 达到最大轮次
            final_content = final_content or "抱歉，分析过程超出了最大工具调用轮次限制。"

        # 将 assistant 回复写入 session
        session.add_message(
            Message(role="assistant", content=final_content, reasoning=final_reasoning)
        )
        conv_title = await self._finalize_title_and_persist(session)

        return ChatResponse(
            content=final_content,
            session_id=session.id,
            framework=not self._llm.is_configured,
            reasoning=final_reasoning,
            usage=usage or None,
            conversation_title=conv_title,
        )

    async def chat_sse_events(
        self,
        *,
        messages: List[ChatMessage],
        session_id: Optional[str] = None,
        mode: str = "general",
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        供 SSE 使用：澄清 / 工具循环与 chat() 一致；最终回复按配置输出 delta（思考与正文分离）。
        """
        session = self._sessions.get_or_create(session_id, mode=mode)
        session.mode = mode
        session.messages.clear()
        for msg in messages:
            session.add_message(
                Message(
                    role=msg.role,
                    content=msg.content,
                    reasoning=msg.reasoning if msg.role == "assistant" else None,
                )
            )

        last_user = ""
        for msg in reversed(messages):
            if msg.role == "user":
                last_user = msg.content or ""
                break
        cq = await self._clarifier.check(last_user, session_mode=session.mode)
        if cq is not None:
            session.add_message(Message(role="assistant", content=cq.question))
            conv_title = await self._finalize_title_and_persist(session)
            yield {
                "type": "clarification",
                "session_id": session.id,
                "question": cq.question,
                "options": [{"label": o.label, "value": o.value} for o in cq.options],
                "allow_custom": cq.allow_custom,
            }
            yield {"type": "done", "session_id": session.id, "conversation_title": conv_title}
            return

        system_prompt = get_system_prompt(
            mode=session.mode,
            tool_names=self._tools.list_names() or None,
        )
        system_prompt = await self._append_rag_retrieval(
            mode=session.mode,
            last_user=last_user,
            system_prompt=system_prompt,
        )
        llm_messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        llm_messages.extend(session.to_llm_messages())
        tool_declarations = self._tools.list_declarations() or None
        usage: Dict[str, int] = {}

        for _round in range(self._max_tool_rounds):
            llm_resp: Optional[LLMResponse] = None
            if settings.AGENT_STREAM_ENABLED:
                async for ev in self._llm.chat_completion_stream_round(
                    llm_messages,
                    tool_declarations,
                ):
                    if ev.get("kind") == "delta":
                        if ev.get("reasoning"):
                            async for out in _emit_sse_text_fragments(
                                "reasoning", ev["reasoning"]
                            ):
                                yield out
                        if ev.get("content"):
                            async for out in _emit_sse_text_fragments(
                                "content", ev["content"]
                            ):
                                yield out
                    elif ev.get("kind") == "final":
                        llm_resp = ev["response"]
                if llm_resp is None:
                    msg = "抱歉，未能获取模型响应。"
                    session.add_message(Message(role="assistant", content=msg))
                    conv_title = await self._finalize_title_and_persist(session)
                    yield {
                        "type": "done",
                        "session_id": session.id,
                        "usage": usage,
                        "reasoning": None,
                        "content": msg,
                        "conversation_title": conv_title,
                    }
                    return
            else:
                llm_resp = await self._llm.chat_completion(
                    messages=llm_messages,
                    tools=tool_declarations,
                )

            if llm_resp.usage:
                usage = llm_resp.usage

            if not llm_resp.tool_calls:
                final_reasoning = llm_resp.reasoning
                final_content = llm_resp.content or ""
                session.add_message(
                    Message(
                        role="assistant",
                        content=final_content,
                        reasoning=final_reasoning,
                    )
                )
                conv_title = await self._finalize_title_and_persist(session)
                yield {
                    "type": "done",
                    "session_id": session.id,
                    "usage": usage,
                    "reasoning": final_reasoning,
                    "content": final_content,
                    "conversation_title": conv_title,
                }
                return

            llm_messages.append({
                "role": "assistant",
                "content": llm_resp.content or "",
                "tool_calls": llm_resp.tool_calls,
            })
            for tc in llm_resp.tool_calls:
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                try:
                    import json as _json
                    tool_args = _json.loads(func.get("arguments", "{}"))
                except Exception:
                    tool_args = {}
                result = await self._tools.execute(tool_name, **tool_args)
                llm_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": result.to_message_content(),
                })
        else:
            msg = "抱歉，分析过程超出了最大工具调用轮次限制。"
            session.add_message(Message(role="assistant", content=msg))
            conv_title = await self._finalize_title_and_persist(session)
            yield {
                "type": "done",
                "session_id": session.id,
                "usage": usage,
                "reasoning": None,
                "content": msg,
                "conversation_title": conv_title,
            }

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
