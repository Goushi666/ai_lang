"""知识库检索 Tool（RAG）。"""

from __future__ import annotations

import asyncio
from typing import Any

from app.services.knowledge import KnowledgeService

from .base import BaseTool, ToolResult


class SearchKnowledgeBase(BaseTool):
    """在本地知识库（SQLite FTS）中检索与问题相关的 Markdown 片段。"""

    name = "search_knowledge_base"
    description = (
        "检索井场系统知识库（Markdown 文档切片）。用于操作说明、模块能力、配置名词等事实性问题；"
        "返回若干文本片段及来源文件名，请在回答中引用来源。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "检索查询，使用与用户问题一致的语言关键词",
            },
        },
        "required": ["query"],
    }

    def __init__(self, knowledge: KnowledgeService, top_k: int = 5):
        self._knowledge = knowledge
        self._top_k = top_k

    async def execute(self, **kwargs: Any) -> ToolResult:
        query = str(kwargs.get("query") or "").strip()
        if not query:
            return ToolResult(error="query 不能为空")
        try:
            rows = await asyncio.to_thread(self._knowledge.search, query, self._top_k)
        except Exception as exc:
            return ToolResult(error=f"检索失败: {exc}")
        if not rows:
            return ToolResult(data={"message": "知识库中未找到相关片段", "hits": []})
        return ToolResult(
            data={
                "hits": rows,
                "hint": "请根据 hits[].text 作答，并注明来源 hits[].source",
            }
        )
