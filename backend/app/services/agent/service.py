"""AgentService：Agent 模块的门面，编排 LLM、Tool、Skill、Session。"""

from __future__ import annotations

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

    async def _persist(self, session: Session) -> None:
        if self._chat_repo is None:
            return
        await self._chat_repo.persist_session_snapshot(session)

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
            await self._persist(session)
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
            )

        # 组装 system prompt
        system_prompt = get_system_prompt(
            mode=session.mode,
            tool_names=self._tools.list_names() or None,
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
        await self._persist(session)

        return ChatResponse(
            content=final_content,
            session_id=session.id,
            framework=not self._llm.is_configured,
            reasoning=final_reasoning,
            usage=usage or None,
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
            await self._persist(session)
            yield {
                "type": "clarification",
                "session_id": session.id,
                "question": cq.question,
                "options": [{"label": o.label, "value": o.value} for o in cq.options],
                "allow_custom": cq.allow_custom,
            }
            yield {"type": "done", "session_id": session.id}
            return

        system_prompt = get_system_prompt(
            mode=session.mode,
            tool_names=self._tools.list_names() or None,
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
                            yield {"type": "delta", "reasoning": ev["reasoning"]}
                        if ev.get("content"):
                            yield {"type": "delta", "content": ev["content"]}
                    elif ev.get("kind") == "final":
                        llm_resp = ev["response"]
                if llm_resp is None:
                    msg = "抱歉，未能获取模型响应。"
                    session.add_message(Message(role="assistant", content=msg))
                    await self._persist(session)
                    yield {
                        "type": "done",
                        "session_id": session.id,
                        "usage": usage,
                        "reasoning": None,
                        "content": msg,
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
                await self._persist(session)
                yield {
                    "type": "done",
                    "session_id": session.id,
                    "usage": usage,
                    "reasoning": final_reasoning,
                    "content": final_content,
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
            await self._persist(session)
            yield {
                "type": "done",
                "session_id": session.id,
                "usage": usage,
                "reasoning": None,
                "content": msg,
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
