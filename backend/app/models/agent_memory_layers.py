"""Agent 多层记忆：情景记忆、感知记忆（持久化）；工作记忆见内存实现。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentEpisodicMemory(Base):
    """情景记忆：带时间轴的事件摘要（工具批、关键轮次等）。"""

    __tablename__ = "agent_episodic_memory"
    __table_args__ = (Index("ix_agent_epi_conv_created", "conversation_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 与 agent 会话 id 对齐；不设 FK，避免会话尚未落库时写入失败
    conversation_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(64), default="event")
    summary: Mapped[str] = mapped_column(Text, default="")
    detail_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True)


class AgentPerceptualMemory(Base):
    """感知记忆：多模态引用与摘要（视频帧、图像、遥测快照等）。"""

    __tablename__ = "agent_perceptual_memory"
    __table_args__ = (Index("ix_agent_perc_conv_created", "conversation_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 与 agent 会话 id 对齐；不设 FK，避免会话尚未落库时写入失败
    conversation_id: Mapped[str] = mapped_column(String(36), index=True)
    modality: Mapped[str] = mapped_column(String(32), default="unknown")
    ref: Mapped[str] = mapped_column(String(1024), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    extra_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True)
