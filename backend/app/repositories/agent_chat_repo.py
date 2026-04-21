"""智能助手对话 SQLite 持久化。"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.agent_chat import AgentConversation, AgentMessage
from app.services.agent.context.session import Message, Session


def _dt_to_ts(dt: Optional[datetime]) -> Optional[float]:
    if dt is None:
        return None
    return dt.timestamp()


def _ts_to_dt(ts: float) -> datetime:
    return datetime.utcfromtimestamp(ts)


class AgentChatRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_summaries(self, limit: int = 50) -> List[Dict[str, Any]]:
        limit = max(1, min(limit, 200))
        async with self._session_factory() as sess:
            stmt = (
                select(AgentConversation)
                .order_by(AgentConversation.updated_at.desc())
                .limit(limit)
            )
            rows = list((await sess.execute(stmt)).scalars().all())
        return [
            {
                "session_id": r.id,
                "title": r.title or "新对话",
                "mode": r.mode or "general",
                "updated_at": _dt_to_ts(r.updated_at),
                "created_at": _dt_to_ts(r.created_at),
            }
            for r in rows
        ]

    async def delete_conversation(self, conversation_id: str) -> bool:
        async with self._session_factory() as sess:
            row = await sess.get(AgentConversation, conversation_id)
            if row is None:
                return False
            await sess.delete(row)
            await sess.commit()
        return True

    async def persist_session_snapshot(
        self,
        session: Session,
        title: Optional[str] = None,
        *,
        infer_title_from_messages: bool = True,
    ) -> str:
        """用当前内存会话覆盖 SQLite 中同 ID 记录。返回最终写入的标题。"""
        now = datetime.utcnow()
        async with self._session_factory() as sess:
            conv = await sess.get(AgentConversation, session.id)
            t = (title or "").strip() or None
            can_infer_user = conv is None or not (
                conv.title and conv.title.strip() and conv.title != "新对话"
            )
            # 显式传入标题时仅用该标题，勿再用首条用户消息覆盖（首轮归纳标题）
            if not t and infer_title_from_messages and can_infer_user:
                for m in session.messages:
                    if m.role == "user" and m.content.strip():
                        raw = m.content.strip()
                        t = raw[:80] + ("…" if len(raw) > 80 else "")
                        break
            if not t:
                if conv is not None and conv.title:
                    t = conv.title
                else:
                    t = "新对话"
            if conv is None:
                conv = AgentConversation(
                    id=session.id,
                    title=t,
                    mode=session.mode,
                    created_at=now,
                    updated_at=now,
                )
                sess.add(conv)
            else:
                conv.title = t
                conv.mode = session.mode
                conv.updated_at = now
            await sess.execute(
                delete(AgentMessage).where(AgentMessage.conversation_id == session.id)
            )
            for i, m in enumerate(session.messages):
                if m.role not in ("user", "assistant", "system"):
                    continue
                sess.add(
                    AgentMessage(
                        conversation_id=session.id,
                        role=m.role,
                        content=m.content or "",
                        reasoning=m.reasoning if m.role == "assistant" else None,
                        seq=i,
                        created_at=now,
                    )
                )
            await sess.commit()
        return t

    async def load_session(self, conversation_id: str) -> Optional[Session]:
        """从库组装 Session（仅 user/assistant/system，供恢复上下文）。"""
        async with self._session_factory() as sess:
            conv = await sess.get(AgentConversation, conversation_id)
            if conv is None:
                return None
            stmt = (
                select(AgentMessage)
                .where(AgentMessage.conversation_id == conversation_id)
                .order_by(AgentMessage.seq.asc())
            )
            rows = list((await sess.execute(stmt)).scalars().all())
        msgs: List[Message] = []
        for r in rows:
            if r.role == "assistant":
                msgs.append(
                    Message(
                        role=r.role,
                        content=r.content or "",
                        reasoning=r.reasoning,
                        timestamp=r.created_at.timestamp() if r.created_at else time.time(),
                    )
                )
            else:
                msgs.append(
                    Message(
                        role=r.role,
                        content=r.content or "",
                        timestamp=r.created_at.timestamp() if r.created_at else time.time(),
                    )
                )
        s = Session(
            id=conv.id,
            mode=conv.mode or "general",
            messages=msgs,
            created_at=_dt_to_ts(conv.created_at) or time.time(),
            updated_at=_dt_to_ts(conv.updated_at) or time.time(),
            conversation_title_done=True,
        )
        return s
