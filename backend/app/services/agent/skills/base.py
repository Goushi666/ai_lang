"""Skill 层基类：编排多个 Tool 完成复杂场景。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SkillResult:
    """Skill 执行结果。"""

    content: str = ""
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


class BaseSkill(ABC):
    """
    Skill 抽象基类。

    Skill 组合多个 Tool 调用完成一个复杂意图，
    包含前置条件判断、中间推理、结果整合。
    """

    name: str = ""
    description: str = ""
    required_tools: List[str] = []

    @abstractmethod
    async def run(
        self,
        tool_registry: Any,
        user_intent: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> SkillResult:
        """
        执行 Skill。

        Args:
            tool_registry: ToolRegistry 实例，用于按名称获取并执行 Tool。
            user_intent: 用户原始意图文本。
            context: 额外上下文（时间范围、设备 ID 等）。
        """
        ...
