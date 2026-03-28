"""智能 Agent API 的请求/响应模型。"""

from typing import List, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., description="user | assistant | system")
    content: str


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    messages: List[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    content: str
    session_id: Optional[str] = None
    framework: bool = Field(True, description="为 True 表示未接入真实 LLM")
