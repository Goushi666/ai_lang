"""图运行时依赖（闭包注入节点）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.agent.service import AgentService


@dataclass
class AgentGraphDeps:
    """持有 AgentService 以便复用 RAG、落库、标题等逻辑。"""

    service: "AgentService"
