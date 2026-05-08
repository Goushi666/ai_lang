"""工业/遥控场景：工具分级（审计是否走 LLM）、是否触发反思。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.config import settings

# 只读/低风险：工业模式下可跳过「审计 LLM」，直接执行（仍受 user_level 与工具自身校验约束）
LOW_RISK_TOOL_NAMES = frozenset(
    {
        "get_sensor_latest",
        "get_sensor_history",
        "get_alarms_history",
        "get_alarm_config",
        "get_environment_analysis",
        "get_current_time",
        "get_vehicle_status",
        "search_knowledge_base",
    }
)

# 写操作 / 导出 / 控制：必须经安全审计 LLM（若未关闭总开关）
MUTATION_OR_CONTROL_TOOL_NAMES = frozenset(
    {
        "control_vehicle",
        "control_arm_joints",
        "export_sensor_history_csv",
        "export_alarms_history_csv",
        "export_csv_file",
    }
)


def _tool_names_from_calls(tool_calls: Optional[List[Dict[str, Any]]]) -> List[str]:
    names: List[str] = []
    for tc in tool_calls or []:
        fn = (tc or {}).get("function") or {}
        n = (fn.get("name") or "").strip()
        if n:
            names.append(n)
    return names


def tool_calls_need_llm_audit(tool_calls: Optional[List[Dict[str, Any]]]) -> bool:
    """
    本轮拟执行的工具是否需要走完整审计 LLM。
    - 关闭分级：恒为 True（只要工业模式且本轮有 tool_calls，由上游保证）。
    - 开启分级：仅当存在控制/导出/未知工具名时为 True；纯只读列表为 False。
    """
    if not getattr(settings, "AGENT_INDUSTRIAL_AUDIT_TIERED", True):
        return True
    names = _tool_names_from_calls(tool_calls)
    if not names:
        return False
    for n in names:
        if n in MUTATION_OR_CONTROL_TOOL_NAMES:
            return True
        if n not in LOW_RISK_TOOL_NAMES:
            return True
    return False


def llm_messages_had_tool_execution(llm_messages: Optional[List[Dict[str, Any]]]) -> bool:
    """本轮对话构造的 messages 里是否已出现过 tool 结果（说明本 user 轮内至少跑过一批工具）。"""
    for m in llm_messages or []:
        if isinstance(m, dict) and m.get("role") == "tool":
            return True
    return False


def should_run_reflection(state: Dict[str, Any]) -> bool:
    """
    工业/遥控下是否调用反思 LLM（加速时可关或按条件触发）。
    """
    if not getattr(settings, "AGENT_INDUSTRIAL_REFLECTION_ENABLED", True):
        return False
    mode = (getattr(settings, "AGENT_INDUSTRIAL_REFLECTION_MODE", "conditional") or "conditional").strip().lower()
    if mode == "off":
        return False
    if mode == "always":
        return True

    # conditional
    lr = state.get("last_response")
    max_r = int(state.get("max_tool_rounds", 10))
    turn = int(state.get("llm_turn", 0))
    msgs = state.get("llm_messages") or []

    if lr is None:
        return True

    tool_calls = getattr(lr, "tool_calls", None) or None
    hit_limit = bool(tool_calls and turn >= max_r)
    if hit_limit:
        return True
    if llm_messages_had_tool_execution(msgs):
        return True

    if getattr(settings, "AGENT_INDUSTRIAL_REFLECTION_ON_TEXT_ONLY", False):
        return True
    return False
