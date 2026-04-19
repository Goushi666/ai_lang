"""会话管理：内存 LRU 字典保存多轮对话上下文。"""

from __future__ import annotations

import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Message:
    """单条对话消息。"""

    role: str  # user | assistant | system | tool
    content: str
    reasoning: Optional[str] = None  # assistant 思考过程（推理模型）
    name: Optional[str] = None  # tool name (when role == "tool")
    tool_call_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class Session:
    """一次对话会话。"""

    id: str
    messages: List[Message] = field(default_factory=list)
    mode: str = "general"  # general | rag
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def add_message(self, msg: Message, max_messages: int = 50) -> None:
        self.messages.append(msg)
        self.updated_at = time.time()
        # 超过上限时截断最早的非 system 消息
        if len(self.messages) > max_messages:
            # 保留 system 消息 + 最近 max_messages 条
            system_msgs = [m for m in self.messages if m.role == "system"]
            non_system = [m for m in self.messages if m.role != "system"]
            self.messages = system_msgs + non_system[-max_messages:]

    def to_llm_messages(self) -> List[Dict[str, str]]:
        """转为 OpenAI messages 格式。"""
        result = []
        for m in self.messages:
            msg: Dict[str, Any] = {"role": m.role, "content": m.content}
            if m.name:
                msg["name"] = m.name
            if m.tool_call_id:
                msg["tool_call_id"] = m.tool_call_id
            result.append(msg)
        return result


class SessionManager:
    """
    内存会话管理器（MVP 阶段）。

    使用 OrderedDict 实现简易 LRU，超过容量时淘汰最早的会话。
    进程重启丢失可接受（PRD §7.1）。
    """

    def __init__(self, max_sessions: int = 200, ttl: int = 3600, max_messages: int = 50):
        self._sessions: OrderedDict[str, Session] = OrderedDict()
        self._max_sessions = max_sessions
        self._ttl = ttl
        self._max_messages = max_messages

    def get_or_create(self, session_id: Optional[str] = None, mode: str = "general") -> Session:
        now = time.time()

        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            # TTL 检查
            if now - session.updated_at > self._ttl:
                del self._sessions[session_id]
            else:
                # LRU: 移到末尾
                self._sessions.move_to_end(session_id)
                return session

        # 创建新会话
        sid = session_id or str(uuid.uuid4())
        session = Session(id=sid, mode=mode)
        self._sessions[sid] = session

        # 容量淘汰
        while len(self._sessions) > self._max_sessions:
            self._sessions.popitem(last=False)

        return session

    def get(self, session_id: str) -> Optional[Session]:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if time.time() - session.updated_at > self._ttl:
            del self._sessions[session_id]
            return None
        self._sessions.move_to_end(session_id)
        return session

    def delete(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def restore(self, session: Session) -> None:
        """从持久化载入的会话写回内存（用于 SQLite 恢复）。"""
        self._sessions[session.id] = session
        self._sessions.move_to_end(session.id)
        while len(self._sessions) > self._max_sessions:
            self._sessions.popitem(last=False)

    def add_message(self, session_id: str, msg: Message) -> None:
        session = self.get(session_id)
        if session:
            session.add_message(msg, self._max_messages)
