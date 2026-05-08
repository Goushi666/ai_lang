"""多层记忆中需落库的部分：情景、感知。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.agent_memory_layers import AgentEpisodicMemory, AgentPerceptualMemory


class AgentMemoryRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append_episode(
        self,
        conversation_id: str,
        *,
        kind: str,
        summary: str,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        import json

        now = datetime.utcnow()
        detail_json = json.dumps(detail, ensure_ascii=False) if detail else None
        row = AgentEpisodicMemory(
            conversation_id=conversation_id,
            kind=(kind or "event")[:64],
            summary=summary or "",
            detail_json=detail_json,
            created_at=now,
        )
        async with self._session_factory() as sess:
            sess.add(row)
            await sess.commit()

    async def list_recent_episodes(
        self, conversation_id: str, *, limit: int = 12
    ) -> List[Dict[str, Any]]:
        limit = max(1, min(limit, 50))
        async with self._session_factory() as sess:
            stmt = (
                select(AgentEpisodicMemory)
                .where(AgentEpisodicMemory.conversation_id == conversation_id)
                .order_by(AgentEpisodicMemory.created_at.desc())
                .limit(limit)
            )
            rows = list((await sess.execute(stmt)).scalars().all())
        rows.reverse()
        return [
            {
                "kind": r.kind,
                "summary": r.summary,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in rows
        ]

    async def append_perceptual(
        self,
        conversation_id: str,
        *,
        modality: str,
        ref: str,
        summary: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        import json

        now = datetime.utcnow()
        row = AgentPerceptualMemory(
            conversation_id=conversation_id,
            modality=(modality or "unknown")[:32],
            ref=(ref or "")[:1024],
            summary=summary or "",
            extra_json=json.dumps(extra, ensure_ascii=False) if extra else None,
            created_at=now,
        )
        async with self._session_factory() as sess:
            sess.add(row)
            await sess.commit()

    async def list_recent_perceptual(
        self, conversation_id: str, *, limit: int = 8
    ) -> List[Dict[str, Any]]:
        limit = max(1, min(limit, 30))
        async with self._session_factory() as sess:
            stmt = (
                select(AgentPerceptualMemory)
                .where(AgentPerceptualMemory.conversation_id == conversation_id)
                .order_by(AgentPerceptualMemory.created_at.desc())
                .limit(limit)
            )
            rows = list((await sess.execute(stmt)).scalars().all())
        rows.reverse()
        return [
            {
                "modality": r.modality,
                "ref": r.ref,
                "summary": r.summary,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in rows
        ]

    async def delete_by_conversation(self, conversation_id: str) -> None:
        async with self._session_factory() as sess:
            await sess.execute(
                delete(AgentEpisodicMemory).where(
                    AgentEpisodicMemory.conversation_id == conversation_id
                )
            )
            await sess.execute(
                delete(AgentPerceptualMemory).where(
                    AgentPerceptualMemory.conversation_id == conversation_id
                )
            )
            await sess.commit()
