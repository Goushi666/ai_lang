"""Skill 注册表：管理所有可用 Skill。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

__all__ = ["SkillRegistry", "BaseSkill", "SkillResult"]


class SkillRegistry:
    """Skill 注册表。"""

    def __init__(self) -> None:
        self._skills: Dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[BaseSkill]:
        return self._skills.get(name)

    def list_names(self) -> List[str]:
        return list(self._skills.keys())
