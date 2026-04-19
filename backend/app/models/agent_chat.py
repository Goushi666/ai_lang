"""智能助手会话与消息（SQLite 持久化）。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AgentConversation(Base):
    __tablename__ = "agent_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    mode: Mapped[str] = mapped_column(String(32), default="general")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True)

    messages: Mapped[list["AgentMessage"]] = relationship(
        "AgentMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AgentMessage.seq",
    )


class AgentMessage(Base):
    __tablename__ = "agent_messages"
    __table_args__ = (Index("ix_agent_msg_conv_seq", "conversation_id", "seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_conversations.id", ondelete="CASCADE"),
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text, default="")
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))

    conversation: Mapped["AgentConversation"] = relationship(
        "AgentConversation", back_populates="messages"
    )
