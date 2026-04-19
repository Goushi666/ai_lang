"""Tool 注册表：管理所有可用 Tool 的声明与执行。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

__all__ = ["ToolRegistry", "BaseTool", "ToolResult"]


class ToolRegistry:
    """
    工具注册表。

    负责收集所有 BaseTool 实例，对外提供：
    - 按名称获取工具
    - 生成 LLM function-calling 声明列表
    - 按名称 + 参数执行工具
    """

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            logger.warning("Tool '%s' 重复注册，已覆盖", tool.name)
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_names(self) -> List[str]:
        return list(self._tools.keys())

    def list_declarations(self) -> List[Dict[str, Any]]:
        """返回所有工具的 OpenAI function-calling 声明。"""
        return [t.declaration() for t in self._tools.values()]

    async def execute(self, name: str, **kwargs: Any) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(error=f"未知工具: {name}")
        try:
            return await tool.execute(**kwargs)
        except Exception as exc:
            logger.exception("Tool '%s' 执行异常", name)
            return ToolResult(error=str(exc))
