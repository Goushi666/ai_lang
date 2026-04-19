"""Tool 层基类：每个 Tool 封装一个后端服务的原子操作。"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ToolResult:
    """Tool 执行结果。"""

    data: Any = None
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_message_content(self) -> str:
        """序列化为可注入 LLM messages 的字符串。"""
        if self.error:
            return json.dumps({"error": self.error}, ensure_ascii=False)
        return json.dumps(self.data, ensure_ascii=False, default=str)


class BaseTool(ABC):
    """
    Tool 抽象基类。

    每个子类需声明 ``name``、``description``、``parameters``，
    并实现 ``execute()``。LLM 通过 JSON Schema 声明感知可用工具，
    Agent 通过 ``execute()`` 调用后端服务获取结构化结果。
    """

    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行工具并返回结构化结果。"""
        ...

    def declaration(self) -> Dict[str, Any]:
        """返回 OpenAI function-calling 兼容的 tool 声明。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
