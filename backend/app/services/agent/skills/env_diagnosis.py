"""环境诊断 Skill：编排 sensor + alarm + analysis 多个 Tool 完成环境分析。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .base import BaseSkill, SkillResult


class EnvDiagnosisSkill(BaseSkill):
    """
    环境诊断 Skill（框架占位）。

    完整流程（后续实现）：
    1. 解析用户意图 → 提取时间范围、设备、关注指标
    2. [如信息不足] → 生成 clarification 返回前端
    3. [信息充足] → 并行调用所需 Tool：
       - get_sensor_latest（如需实时值）
       - get_environment_analysis（如需统计/异常）
       - get_alarms_history（如涉及告警上下文）
    4. 整合 Tool 返回的结构化数据
    5. 由 LLM 组织为自然语言回答
    """

    name = "env_diagnosis"
    description = "环境诊断：综合传感器数据、告警记录、环境分析，给出环境状况的完整诊断。"
    required_tools = [
        "get_sensor_latest",
        "get_sensor_history",
        "get_environment_analysis",
        "get_alarms_history",
        "get_alarm_config",
    ]

    async def run(
        self,
        tool_registry: Any,
        user_intent: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> SkillResult:
        # TODO: 实现完整的 env_diagnosis 编排逻辑
        # MVP 阶段由 LLM 自行决定调用哪些 Tool，Skill 层暂不介入
        return SkillResult(
            content="[env_diagnosis Skill 框架占位] 后续将编排多个 Tool 调用完成环境诊断。",
        )
