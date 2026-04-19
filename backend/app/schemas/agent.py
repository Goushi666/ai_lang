"""智能 Agent API 的请求/响应模型。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# 对话
# ------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str = Field(..., description="user | assistant | system")
    content: str
    reasoning: Optional[str] = Field(
        None,
        description="assistant 的思考过程；多轮对话需原样回传以便服务端保留与落库",
    )


class ClarificationOption(BaseModel):
    label: str
    value: str


class ClarificationPayload(BaseModel):
    """追问载荷：前端收到后渲染选项供用户快捷选择。"""
    question: str
    options: List[ClarificationOption] = Field(default_factory=list)
    allow_custom: bool = True


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    messages: List[ChatMessage] = Field(default_factory=list)
    mode: str = Field("general", description="对话模式：general | rag")
    stream: bool = Field(False, description="是否启用 SSE 流式输出")


class ChatResponse(BaseModel):
    content: str
    session_id: Optional[str] = None
    framework: bool = Field(False, description="为 True 表示未接入真实 LLM")
    clarification: Optional[ClarificationPayload] = None
    reasoning: Optional[str] = Field(
        None,
        description="思考过程（推理模型如 DeepSeek-R1 返回的 reasoning_content，与 content 分离展示）",
    )
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    usage: Optional[Dict[str, int]] = None
    conversation_title: Optional[str] = Field(
        None,
        description="服务端根据首轮用户+助手对答归纳的会话标题（若有）",
    )


# ------------------------------------------------------------------
# 会话管理
# ------------------------------------------------------------------

class SessionMessageItem(BaseModel):
    role: str
    content: str
    timestamp: Optional[float] = None
    reasoning: Optional[str] = None


class SessionResponse(BaseModel):
    session_id: str
    mode: str = "general"
    messages: List[SessionMessageItem] = Field(default_factory=list)
    created_at: Optional[float] = None
    updated_at: Optional[float] = None


class SessionListItem(BaseModel):
    session_id: str
    title: str = "新对话"
    mode: str = "general"
    updated_at: Optional[float] = None
    created_at: Optional[float] = None


class SessionListResponse(BaseModel):
    items: List[SessionListItem] = Field(default_factory=list)


# ------------------------------------------------------------------
# 知识库管理（SQLite FTS5 + 入库 API）
# ------------------------------------------------------------------

class KnowledgeIngestRequest(BaseModel):
    file_path: Optional[str] = Field(None, description="服务端文档路径（相对 backend 根或绝对路径）")
    content: Optional[str] = Field(None, description="直接传入文本内容")
    source_id: Optional[str] = Field(
        None,
        description="入库文档标识，删除接口用；文本入库时必填或自动生成",
    )
    replace: bool = Field(True, description="是否先删除同 source 的旧块再写入")
    doc_type: str = Field("markdown", description="预留：markdown | txt")


class KnowledgeStatusResponse(BaseModel):
    total_documents: int = 0
    total_chunks: int = 0
    status: str = "not_initialized"
    collection: Optional[str] = None
    db_path: Optional[str] = None
