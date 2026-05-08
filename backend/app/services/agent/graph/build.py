"""编译 LangGraph：澄清分支 + LLM⟷工具 循环。"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from .deps import AgentGraphDeps
from .nodes import (
    node_audit,
    node_build_system,
    node_clarify,
    node_finalize,
    node_finalize_clarify,
    node_ingest,
    node_llm,
    node_reflect,
    node_tools,
    route_after_audit,
    route_after_clarify,
    route_after_llm,
)
from .state import AgentGraphState


def build_agent_graph(deps: AgentGraphDeps):
    """
    流程：
    ingest → clarify → [ finalize_clarify → END | build_system → llm → … → finalize → END ]

    工业 / 遥控（mode 为 industrial 或 vehicle）：拟执行工具前经 audit 节点；收尾前经 reflect 节点。
    """
    g = StateGraph(AgentGraphState)

    async def _ingest(state: AgentGraphState, config: RunnableConfig):
        return await node_ingest(deps, state, config)

    async def _clarify(state: AgentGraphState, config: RunnableConfig):
        return await node_clarify(deps, state, config)

    async def _finalize_clarify(state: AgentGraphState, config: RunnableConfig):
        return await node_finalize_clarify(deps, state, config)

    async def _build_system(state: AgentGraphState, config: RunnableConfig):
        return await node_build_system(deps, state, config)

    async def _llm(state: AgentGraphState, config: RunnableConfig):
        return await node_llm(deps, state, config)

    async def _tools(state: AgentGraphState, config: RunnableConfig):
        return await node_tools(deps, state, config)

    async def _audit(state: AgentGraphState, config: RunnableConfig):
        return await node_audit(deps, state, config)

    async def _reflect(state: AgentGraphState, config: RunnableConfig):
        return await node_reflect(deps, state, config)

    async def _finalize(state: AgentGraphState, config: RunnableConfig):
        return await node_finalize(deps, state, config)

    g.add_node("ingest", _ingest)
    g.add_node("clarify", _clarify)
    g.add_node("finalize_clarify", _finalize_clarify)
    g.add_node("build_system", _build_system)
    g.add_node("llm", _llm)
    g.add_node("tools", _tools)
    g.add_node("audit", _audit)
    g.add_node("reflect", _reflect)
    g.add_node("finalize", _finalize)

    g.set_entry_point("ingest")
    g.add_edge("ingest", "clarify")
    g.add_conditional_edges(
        "clarify",
        route_after_clarify,
        {
            "finalize_clarify": "finalize_clarify",
            "build_system": "build_system",
        },
    )
    g.add_edge("finalize_clarify", END)
    g.add_edge("build_system", "llm")
    g.add_conditional_edges(
        "llm",
        route_after_llm,
        {
            "tools": "tools",
            "audit": "audit",
            "reflect": "reflect",
            "finalize": "finalize",
        },
    )
    g.add_conditional_edges(
        "audit",
        route_after_audit,
        {
            "tools": "tools",
            "finalize": "finalize",
        },
    )
    g.add_edge("tools", "llm")
    g.add_edge("reflect", "finalize")
    g.add_edge("finalize", END)

    return g.compile()
