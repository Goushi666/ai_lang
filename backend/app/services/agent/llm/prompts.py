"""System prompt 模板：根据对话模式动态组装。"""

from __future__ import annotations

from typing import List

_BASE_PROMPT = """\
你是井场智能监测平台的 AI 助手。你的职责是帮助运维人员通过自然语言完成环境数据查询、异常分析和知识问答。

## 核心规则
1. 所有数据来自工具调用，禁止自行编造数值或计算统计量（min/max/avg 等由工具返回）。
2. 查无数据时如实告知"该时间段无数据"，不编造。
3. 回答须引用工具返回的关键数据点。
4. 若用户意图模糊（缺少时间范围、设备、分析类型），主动追问以缩小范围；若已足够明确则直接回答，不做多余询问。
5. 若模型区分「思考过程」与「正式回答」（如 reasoning 与 content）：思考过程须与用户语言一致——用户使用中文提问或交流时，思考过程也必须使用中文，勿默认使用英文。
"""

_GENERAL_SUFFIX = """
## 当前模式：通用对话
你可以使用以下工具查询传感器数据、告警记录、环境分析结果。根据用户问题自行决定调用哪些工具。
"""

_RAG_SUFFIX = """
## 当前模式：知识问答（RAG）
优先通过 search_knowledge_base 工具检索知识库，回答时附引用来源（文档名 + 段落位置）。
如需交叉验证可使用只读数据工具。
"""

_TOOL_LIST_HEADER = "\n## 可用工具\n"


def get_system_prompt(mode: str = "general", tool_names: List[str] | None = None) -> str:
    """
    根据对话模式和可用工具列表组装 system prompt。

    Args:
        mode: "general" 或 "rag"
        tool_names: 当前启用的工具名称列表
    """
    parts = [_BASE_PROMPT.strip()]

    if mode == "rag":
        parts.append(_RAG_SUFFIX.strip())
    else:
        parts.append(_GENERAL_SUFFIX.strip())

    if tool_names:
        parts.append(_TOOL_LIST_HEADER.strip())
        for name in tool_names:
            parts.append(f"- {name}")

    return "\n\n".join(parts)
