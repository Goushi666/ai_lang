"""LangGraph 状态定义（内存运行，不启用持久化 checkpoint）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from typing_extensions import NotRequired


class AgentGraphState(TypedDict):
    """单次对话 run 的共享状态；各节点返回部分字段合并。

    ``ainvoke`` / ``astream`` 入口必须提供前五项；其余字段由节点逐步写入，
    类型上为 ``NotRequired``，在节点内通过 ``assert key in state`` 收窄后再下标访问。
    """

    # --- 输入（invoke 时注入，必填）---
    session: Any
    request_messages: List[Any]
    mode: str
    user_level: str
    max_tool_rounds: int

    # --- ingest / clarify ---
    last_user: NotRequired[str]
    clarification_question: NotRequired[Optional[str]]
    clarification_options: NotRequired[List[Dict[str, str]]]
    clarification_allow_custom: NotRequired[bool]
    needs_clarification: NotRequired[bool]

    # --- 主链路 ---
    system_prompt: NotRequired[str]
    llm_messages: NotRequired[List[Dict[str, Any]]]
    tool_declarations: NotRequired[Optional[List[Dict[str, Any]]]]
    last_response: NotRequired[Any]  # LLMResponse，非序列化；仅内存图
    llm_turn: NotRequired[int]
    collected_exports: NotRequired[List[Dict[str, str]]]
    hit_tool_limit: NotRequired[bool]

    # --- 工业安全：审计 / 反思 ---
    audit_result: NotRequired[Dict[str, Any]]
    audit_blocked: NotRequired[bool]
    audit_requires_human_confirm: NotRequired[bool]
    reflection_result: NotRequired[Dict[str, Any]]

    # --- 输出 ---
    clarification: NotRequired[Any]
    final_content: NotRequired[str]
    final_reasoning: NotRequired[Optional[str]]
    usage: NotRequired[Dict[str, int]]
    conversation_title: NotRequired[Optional[str]]
    framework: NotRequired[bool]
