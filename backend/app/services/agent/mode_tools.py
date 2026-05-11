"""按对话模式裁剪「暴露给 LLM 的工具列表」，缩短 function 声明与 system 中的工具枚举。"""

from __future__ import annotations

from typing import List

# vehicle：具身控制为主；不包含传感器/导出/知识库，显著减小 prefill
VEHICLE_LLM_TOOL_ORDER: tuple[str, ...] = (
    "get_current_time",
    "control_vehicle",
    "control_arm_joints",
    "get_vehicle_status",
)


def vehicle_tool_names_for_llm(registered_names: List[str]) -> List[str]:
    reg = set(registered_names)
    return [n for n in VEHICLE_LLM_TOOL_ORDER if n in reg]
