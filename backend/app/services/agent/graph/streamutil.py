"""SSE 与 LangGraph custom stream 的衔接。"""

from __future__ import annotations

from typing import Optional

from langchain_core.runnables import RunnableConfig


def sse_stream_enabled(config: Optional[RunnableConfig]) -> bool:
    """为 True 时节点通过 get_stream_writer 推送与前端约定一致的 SSE 载荷。"""
    if not config:
        return False
    return bool(config.get("configurable", {}).get("sse_stream"))
