"""工业 / 遥控场景：安全审计与反思（Reflection）的提示与结果规范化。"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .state import AgentGraphState

AUDIT_SYSTEM = """\
你是工业与遥控场景下的**安全审计员**，与「提出工具调用的执行模型」职责分离。
你只根据给定的用户意图摘要、用户级别、以及**拟执行的工具调用列表**做合规与风险评估。
禁止编造传感器或设备实时数值；不得假设未提供的证据。

**重要**：字段 ``user_level`` 由**服务端根据登录 JWT 注入**，必须采信：
- ``operator`` / ``admin``：在参数合理、无显式作死指令（如超速、超限角度、访客冒充）时，对常规巡检车/机械臂控制应优先 ``allow``。
- ``viewer``：控制类工具倾向 ``require_human_confirm`` 或 ``deny`` 并说明权限。
- ``guest``（未登录）：控制类工具倾向 ``deny`` 或 ``require_human_confirm``。

你必须只输出**一个 JSON 对象**（不要 Markdown 围栏），字段如下：
- decision: 字符串，必须是 "allow" | "deny" | "require_human_confirm" 之一
- risk_tier: 字符串，"low" | "medium" | "high"
- policy_hits: 字符串数组，若无则 []
- rationale: 字符串，简短中文理由（给用户或运维阅读）
- remediation: 字符串或 null；当 decision 为 deny 或 require_human_confirm 时给出可执行说明；allow 时为 null

裁决指引（摘要）：
- 明显危险或未授权的高风险动作（如未确认的高速移动、大角度机械臂在未知环境下盲调）：倾向 deny 或 require_human_confirm
- 访客/观察员级别尝试控制类工具：应 deny 或 require_human_confirm 并说明权限
- 信息查询类、只读类工具：通常 allow
- 无法判断时：require_human_confirm 优于贸然 allow
"""

REFLECT_SYSTEM = """\
你是**质量反思**模块：在助手即将回复用户之前，检查本轮推理与答复是否合理。
禁止编造工具未返回的数据；仅根据摘要判断一致性、证据充分性、是否答非所问。

只输出**一个 JSON 对象**（不要 Markdown 围栏），字段：
- verdict: "ok" | "revise" | "escalate"
- issues: 字符串数组，具体问题列表；无则 []
- revised_summary: 字符串或 null；verdict 为 revise 时给出简短修订建议（中文）；其它为 null
- rationale: 字符串，简短说明

指引：
- 若答复明显缺乏依据却断言事实：verdict 倾向 revise 或 escalate
- 若涉及安全/控制且表述与审计结论冲突：escalate
- 小问题可 revise；整体可接受则 ok
"""


def industrial_safety_enabled(state: AgentGraphState) -> bool:
    """与 PRD 工业巡检一致：`industrial` 与 `vehicle` 均走审计 + 反思。"""
    m = (state.get("mode") or "").strip().lower()
    return m in ("industrial", "vehicle")


def build_audit_user_message(state: AgentGraphState) -> str:
    lr = state.get("last_response")
    tool_calls = getattr(lr, "tool_calls", None) if lr is not None else None
    payload = {
        "user_level": state.get("user_level"),
        "last_user": state.get("last_user", ""),
        "proposed_tool_calls": tool_calls or [],
    }
    return (
        "请对以下拟执行工具调用做安全审计，仅输出 JSON。\n"
        + json.dumps(payload, ensure_ascii=False, default=str)
    )


def build_reflect_user_message(state: AgentGraphState) -> str:
    lr = state.get("last_response")
    content = (getattr(lr, "content", None) or "") if lr is not None else ""
    reasoning = (getattr(lr, "reasoning", None) or "") if lr is not None else ""
    max_r = int(state.get("max_tool_rounds", 10))
    turn = int(state.get("llm_turn", 0))
    had_tools = bool(getattr(lr, "tool_calls", None)) if lr is not None else False
    hit_limit = bool(had_tools and turn >= max_r)

    tail: List[Dict[str, Any]] = []
    lmsgs = state.get("llm_messages")
    if isinstance(lmsgs, list) and lmsgs:
        for m in lmsgs[-6:]:
            if isinstance(m, dict):
                role = m.get("role")
                if role == "tool":
                    tail.append(
                        {
                            "role": "tool",
                            "tool_call_id": m.get("tool_call_id"),
                            "content_preview": (str(m.get("content") or ""))[:500],
                        }
                    )
                elif role == "assistant" and m.get("tool_calls"):
                    tail.append(
                        {
                            "role": "assistant",
                            "tool_calls_preview": json.dumps(
                                m.get("tool_calls"), ensure_ascii=False, default=str
                            )[:800],
                        }
                    )

    payload = {
        "user_level": state.get("user_level"),
        "last_user": state.get("last_user", ""),
        "assistant_content_preview": (content or "")[:2000],
        "assistant_reasoning_preview": (reasoning or "")[:1500],
        "hit_tool_round_limit": hit_limit,
        "recent_tool_trace": tail,
        "audit_result": state.get("audit_result"),
    }
    return (
        "请对本轮助手答复做反思评估，仅输出 JSON。\n"
        + json.dumps(payload, ensure_ascii=False, default=str)
    )


def normalize_audit(raw: Dict[str, Any]) -> Dict[str, Any]:
    d = (raw.get("decision") or "allow").strip().lower()
    if d not in ("allow", "deny", "require_human_confirm"):
        d = "require_human_confirm"
    risk = (raw.get("risk_tier") or "medium").strip().lower()
    if risk not in ("low", "medium", "high"):
        risk = "medium"
    hits = raw.get("policy_hits")
    if not isinstance(hits, list):
        hits = []
    hits = [str(x) for x in hits if str(x).strip()]
    return {
        "decision": d,
        "risk_tier": risk,
        "policy_hits": hits,
        "rationale": str(raw.get("rationale") or "").strip() or None,
        "remediation": str(raw.get("remediation") or "").strip() or None,
    }


def normalize_reflect(raw: Dict[str, Any]) -> Dict[str, Any]:
    v = (raw.get("verdict") or "ok").strip().lower()
    if v not in ("ok", "revise", "escalate"):
        v = "ok"
    issues = raw.get("issues")
    if not isinstance(issues, list):
        issues = []
    issues = [str(x) for x in issues if str(x).strip()]
    return {
        "verdict": v,
        "issues": issues,
        "revised_summary": str(raw.get("revised_summary") or "").strip() or None,
        "rationale": str(raw.get("rationale") or "").strip() or None,
    }


def stub_audit_allow() -> Dict[str, Any]:
    return normalize_audit(
        {
            "decision": "allow",
            "risk_tier": "low",
            "policy_hits": [],
            "rationale": "LLM 未配置，开发占位跳过安全审计。",
            "remediation": None,
        }
    )


def stub_reflect_ok() -> Dict[str, Any]:
    return normalize_reflect(
        {
            "verdict": "ok",
            "issues": [],
            "revised_summary": None,
            "rationale": "LLM 未配置，跳过反思。",
        }
    )
