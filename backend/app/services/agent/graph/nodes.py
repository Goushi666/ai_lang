"""LangGraph 节点：单职责，经边连接成与旧版等价的控制流。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Literal, Optional, Tuple, cast

from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer

from app.core.config import settings
from app.schemas.agent import ChatMessage, ClarificationOption, ClarificationPayload
from app.services.agent.context.session import Message

from .deps import AgentGraphDeps
from .safety import (
    AUDIT_SYSTEM,
    REFLECT_SYSTEM,
    build_audit_user_message,
    build_reflect_user_message,
    industrial_safety_enabled,
    normalize_audit,
    normalize_reflect,
    stub_audit_allow,
    stub_reflect_ok,
)
from .state import AgentGraphState
from .streamutil import sse_stream_enabled
from .tool_export import export_download_from_tool_result
from .tool_tier import should_run_reflection, tool_calls_need_llm_audit

logger = logging.getLogger(__name__)


async def node_ingest(
    deps: AgentGraphDeps,
    state: AgentGraphState,
    config: RunnableConfig,
) -> Dict[str, Any]:
    del config
    svc = deps.service
    session = state["session"]
    mode = state["mode"]
    messages: List[ChatMessage] = list(state["request_messages"])

    session.mode = mode
    session.messages.clear()
    for msg in messages:
        session.add_message(
            Message(
                role=msg.role,
                content=msg.content,
                reasoning=msg.reasoning if msg.role == "assistant" else None,
            )
        )
    svc._sync_conversation_title_done_flag(session, messages)

    last_user = ""
    for msg in reversed(messages):
        if msg.role == "user":
            last_user = msg.content or ""
            break
    svc.touch_working_memory(session.id, last_user)

    return {
        "last_user": last_user,
        "needs_clarification": False,
        "clarification_question": None,
        "llm_turn": 0,
        "collected_exports": [],
        "hit_tool_limit": False,
        "usage": {},
        "audit_blocked": False,
        "audit_requires_human_confirm": False,
    }


async def node_clarify(
    deps: AgentGraphDeps,
    state: AgentGraphState,
    config: RunnableConfig,
) -> Dict[str, Any]:
    del config
    if "last_user" not in state:
        return {"needs_clarification": False}
    cq = await deps.service._clarifier.check(state["last_user"], session_mode=state["mode"])
    if cq is None:
        return {"needs_clarification": False}
    return {
        "needs_clarification": True,
        "clarification_question": cq.question,
        "clarification_options": [{"label": o.label, "value": o.value} for o in cq.options],
        "clarification_allow_custom": cq.allow_custom,
    }


def route_after_clarify(state: AgentGraphState) -> Literal["finalize_clarify", "build_system"]:
    if state.get("needs_clarification"):
        return "finalize_clarify"
    return "build_system"


async def node_finalize_clarify(
    deps: AgentGraphDeps,
    state: AgentGraphState,
    config: RunnableConfig,
) -> Dict[str, Any]:
    session = state["session"]
    q = state.get("clarification_question") or ""
    session.add_message(Message(role="assistant", content=q))
    conv_title = await deps.service._finalize_title_and_persist(session)
    opts = state.get("clarification_options") or []
    allow_custom = bool(state.get("clarification_allow_custom", True))
    clarification = ClarificationPayload(
        question=q,
        options=[ClarificationOption(label=o["label"], value=o["value"]) for o in opts],
        allow_custom=allow_custom,
    )

    if sse_stream_enabled(config):
        writer = get_stream_writer()
        writer(
            {
                "type": "clarification",
                "session_id": session.id,
                "question": q,
                "options": [{"label": o["label"], "value": o["value"]} for o in opts],
                "allow_custom": allow_custom,
            }
        )
        writer(
            {
                "type": "done",
                "session_id": session.id,
                "usage": {},
                "reasoning": None,
                "content": q,
                "conversation_title": conv_title,
            }
        )

    return {
        "final_content": q,
        "final_reasoning": None,
        "usage": {},
        "conversation_title": conv_title,
        "framework": not deps.service._llm.is_configured,
        "clarification": clarification,
    }


async def node_build_system(
    deps: AgentGraphDeps,
    state: AgentGraphState,
    config: RunnableConfig,
) -> Dict[str, Any]:
    del config
    from app.services.agent.llm.prompts import get_system_prompt

    assert "last_user" in state, "agent graph: last_user missing before build_system"
    session = state["session"]
    system_prompt = get_system_prompt(
        mode=session.mode,
        tool_names=deps.service._tools.list_names() or None,
        user_level=state["user_level"],
    )
    system_prompt = await deps.service._append_rag_retrieval(
        mode=session.mode,
        last_user=state["last_user"],
        system_prompt=system_prompt,
    )
    system_prompt = await deps.service._append_memory_context(
        session_id=session.id,
        mode=session.mode,
        last_user=state["last_user"],
        system_prompt=system_prompt,
    )
    llm_messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    llm_messages.extend(session.to_llm_messages())
    tool_declarations = deps.service._tools.list_declarations() or None
    return {
        "system_prompt": system_prompt,
        "llm_messages": llm_messages,
        "tool_declarations": tool_declarations,
    }


async def node_llm(
    deps: AgentGraphDeps,
    state: AgentGraphState,
    config: RunnableConfig,
) -> Dict[str, Any]:
    from app.services.agent.llm.client import LLMResponse

    assert "llm_messages" in state, "agent graph: llm_messages missing before llm"
    llm_messages = state["llm_messages"]
    tools = state.get("tool_declarations")
    turn = int(state.get("llm_turn", 0)) + 1
    if sse_stream_enabled(config) and settings.AGENT_STREAM_ENABLED:
        writer = get_stream_writer()
        llm_resp: Optional[LLMResponse] = None
        async for ev in deps.service._llm.chat_completion_stream_round(llm_messages, tools):
            if ev.get("kind") == "delta":
                if ev.get("reasoning"):
                    writer({"type": "delta", "field": "reasoning", "text": ev["reasoning"]})
                if ev.get("content"):
                    writer({"type": "delta", "field": "content", "text": ev["content"]})
            elif ev.get("kind") == "final":
                llm_resp = ev["response"]
        if llm_resp is None:
            llm_resp = LLMResponse(content="抱歉，未能获取模型响应。")
        out: Dict[str, Any] = {"last_response": llm_resp, "llm_turn": turn}
        if llm_resp.usage:
            out["usage"] = cast(Dict[str, int], llm_resp.usage)
        return out

    resp = await deps.service._llm.chat_completion(messages=llm_messages, tools=tools)
    out2: Dict[str, Any] = {
        "last_response": resp,
        "llm_turn": turn,
    }
    if resp.usage:
        out2["usage"] = cast(Dict[str, int], resp.usage)
    return out2


def route_after_llm(
    state: AgentGraphState,
) -> Literal["tools", "audit", "reflect", "finalize"]:
    max_r = int(state.get("max_tool_rounds", 10))
    turn = int(state.get("llm_turn", 0))
    lr = state.get("last_response")
    ind = industrial_safety_enabled(state)

    if lr is None:
        return "reflect" if (ind and should_run_reflection(state)) else "finalize"

    tool_calls = getattr(lr, "tool_calls", None) or None
    if turn >= max_r:
        return "reflect" if (ind and should_run_reflection(state)) else "finalize"
    if not tool_calls:
        return "reflect" if (ind and should_run_reflection(state)) else "finalize"
    if ind and tool_calls_need_llm_audit(tool_calls):
        return "audit"
    return "tools"


def route_after_audit(state: AgentGraphState) -> Literal["tools", "finalize"]:
    ar = state.get("audit_result") or {}
    d = str(ar.get("decision") or "allow").lower()
    if d == "deny":
        return "finalize"
    if d == "require_human_confirm":
        return "finalize"
    return "tools"


async def node_audit(
    deps: AgentGraphDeps,
    state: AgentGraphState,
    config: RunnableConfig,
) -> Dict[str, Any]:
    llm = deps.service._llm
    raw = await llm.chat_completion_json(
        [
            {"role": "system", "content": AUDIT_SYSTEM},
            {"role": "user", "content": build_audit_user_message(state)},
        ],
        max_tokens=512,
        temperature=0.1,
    )
    if not raw:
        normalized = stub_audit_allow() if not llm.is_configured else normalize_audit(
            {
                "decision": "require_human_confirm",
                "risk_tier": "high",
                "policy_hits": ["audit_json_unavailable"],
                "rationale": "安全审计未能产生有效结果，按策略要求人工确认。",
                "remediation": "请稍后重试或联系管理员检查模型输出。",
            }
        )
    else:
        normalized = normalize_audit(raw)

    decision = normalized["decision"]
    out: Dict[str, Any] = {
        "audit_result": normalized,
        "audit_blocked": decision == "deny",
        "audit_requires_human_confirm": decision == "require_human_confirm",
    }

    if sse_stream_enabled(config):
        get_stream_writer()(
            {
                "type": "audit",
                "session_id": state["session"].id,
                "decision": decision,
                "risk_tier": normalized.get("risk_tier"),
                "rationale": normalized.get("rationale"),
                "remediation": normalized.get("remediation"),
                "policy_hits": normalized.get("policy_hits"),
            }
        )

    return out


async def node_reflect(
    deps: AgentGraphDeps,
    state: AgentGraphState,
    config: RunnableConfig,
) -> Dict[str, Any]:
    if not industrial_safety_enabled(state):
        return {}

    llm = deps.service._llm
    raw = await llm.chat_completion_json(
        [
            {"role": "system", "content": REFLECT_SYSTEM},
            {"role": "user", "content": build_reflect_user_message(state)},
        ],
        max_tokens=512,
        temperature=0.2,
    )
    if not raw:
        normalized = stub_reflect_ok() if not llm.is_configured else normalize_reflect(
            {
                "verdict": "escalate",
                "issues": ["反思模型未返回有效 JSON"],
                "revised_summary": None,
                "rationale": "无法完成自动反思，建议人工查看本轮答复。",
            }
        )
    else:
        normalized = normalize_reflect(raw)

    if sse_stream_enabled(config):
        get_stream_writer()(
            {
                "type": "reflection",
                "session_id": state["session"].id,
                "verdict": normalized.get("verdict"),
                "issues": normalized.get("issues"),
                "revised_summary": normalized.get("revised_summary"),
                "rationale": normalized.get("rationale"),
            }
        )

    return {"reflection_result": normalized}


async def node_tools(
    deps: AgentGraphDeps,
    state: AgentGraphState,
    config: RunnableConfig,
) -> Dict[str, Any]:
    assert "last_response" in state and "llm_messages" in state, (
        "agent graph: last_response/llm_messages missing before tools"
    )
    lr = state["last_response"]
    llm_messages = list(state["llm_messages"])
    exports = list(state.get("collected_exports") or [])
    session = state["session"]
    stream_sse = sse_stream_enabled(config)

    llm_messages.append(
        {
            "role": "assistant",
            "content": (getattr(lr, "content", None) or "") or "",
            "tool_calls": lr.tool_calls,
        }
    )

    tcs = list(lr.tool_calls or [])

    async def _run_tool(
        idx: int, tc: Dict[str, Any]
    ) -> Tuple[int, Dict[str, Any], str, Any]:
        func = tc.get("function", {})
        tool_name = func.get("name", "")
        try:
            tool_args = json.loads(func.get("arguments", "{}") or "{}")
        except Exception:
            tool_args = {}
        result = await deps.service._tools.execute(tool_name, **tool_args)
        return idx, tc, tool_name, result

    parallel = bool(getattr(settings, "AGENT_TOOLS_PARALLEL", True)) and len(tcs) > 1
    if parallel:
        executed = await asyncio.gather(*[_run_tool(i, tc) for i, tc in enumerate(tcs)])
        ordered_exec = sorted(executed, key=lambda x: x[0])
    else:
        ordered_exec = []
        for i, tc in enumerate(tcs):
            ordered_exec.append(await _run_tool(i, tc))

    for _idx, tc, tool_name, result in ordered_exec:
        link = export_download_from_tool_result(tool_name, result)
        if link:
            exports.append(link)
            if stream_sse:
                get_stream_writer()(
                    {
                        "type": "export_ready",
                        "session_id": session.id,
                        "filename": link["filename"],
                        "download_path": link["download_path"],
                    }
                )
        llm_messages.append(
            {
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "content": result.to_message_content(),
            }
        )

    ms = deps.service._memory_service
    if ms is not None and ordered_exec:
        names = [x[2] for x in ordered_exec]
        all_ok = all(x[3].ok for x in ordered_exec)
        try:
            await ms.record_tool_episode(session.id, tool_names=names, ok=all_ok)
        except Exception:
            pass

    return {"llm_messages": llm_messages, "collected_exports": exports}


async def node_finalize(
    deps: AgentGraphDeps,
    state: AgentGraphState,
    config: RunnableConfig,
) -> Dict[str, Any]:
    session = state["session"]
    max_r = int(state.get("max_tool_rounds", 10))
    turn = int(state.get("llm_turn", 0))
    lr = state.get("last_response")
    stream_sse = sse_stream_enabled(config)

    hit_limit = bool(lr and lr.tool_calls and turn >= max_r)

    if state.get("audit_blocked"):
        ar = state.get("audit_result") or {}
        final_content = (
            ar.get("remediation")
            or ar.get("rationale")
            or "安全审计未通过，已拦截工具执行。"
        ).strip()
        final_reasoning = None
        usage = state.get("usage") or {}
    elif state.get("audit_requires_human_confirm"):
        ar = state.get("audit_result") or {}
        rc = (ar.get("rationale") or "该操作需人工确认后方可执行。").strip()
        rm = (ar.get("remediation") or "请由具备权限的人员在控制台审核批准后重试。").strip()
        final_content = f"【待人工确认】{rc}\n{rm}"
        final_reasoning = None
        usage = state.get("usage") or {}
    elif hit_limit:
        final_content = "抱歉，分析过程超出了最大工具调用轮次限制。"
        final_reasoning = None
        usage = state.get("usage") or {}
    elif lr is None:
        final_content = "抱歉，未能获取模型响应。"
        final_reasoning = None
        usage = state.get("usage") or {}
    else:
        final_content = lr.content or ""
        final_reasoning = lr.reasoning
        usage = lr.usage or state.get("usage") or {}

    if (
        not state.get("audit_blocked")
        and not state.get("audit_requires_human_confirm")
        and industrial_safety_enabled(state)
    ):
        rr = state.get("reflection_result") or {}
        verdict = str(rr.get("verdict") or "ok").lower()
        if verdict == "escalate":
            issues = rr.get("issues") or []
            line = "【需人工复核】" + (
                "；".join(str(x) for x in issues if str(x).strip())
                if issues
                else (rr.get("rationale") or "模型建议人工复核本轮答复。")
            )
            final_content = f"{line}\n\n---\n{final_content}"
        elif verdict == "revise":
            rs = rr.get("revised_summary")
            if rs:
                final_content = f"{final_content}\n\n（反思说明：{rs}）"

    reasoning_for_client = final_reasoning
    if industrial_safety_enabled(state):
        meta_lines: List[str] = []
        ar = state.get("audit_result")
        if isinstance(ar, dict) and ar.get("decision"):
            meta_lines.append(
                "【安全审计】"
                f"{ar.get('decision')} "
                f"{ar.get('risk_tier') or ''} "
                f"{(ar.get('rationale') or '').strip()}"
            )
        rr = state.get("reflection_result")
        if isinstance(rr, dict) and rr.get("verdict"):
            iss = rr.get("issues") or []
            iss_s = "；".join(str(x) for x in iss if str(x).strip()) if isinstance(iss, list) else ""
            meta_lines.append(
                "【反思】"
                f"{rr.get('verdict')} "
                f"{iss_s} "
                f"{(rr.get('rationale') or '').strip()}"
            )
        if meta_lines:
            block = "\n".join(meta_lines)
            reasoning_for_client = (
                f"{final_reasoning}\n\n{block}".strip() if final_reasoning else block
            )

    session.add_message(
        Message(role="assistant", content=final_content, reasoning=reasoning_for_client)
    )
    conv_title = await deps.service._finalize_title_and_persist(session)

    if stream_sse:
        get_stream_writer()(
            {
                "type": "done",
                "session_id": session.id,
                "usage": usage,
                "reasoning": reasoning_for_client,
                "content": final_content,
                "conversation_title": conv_title,
            }
        )

    return {
        "final_content": final_content,
        "final_reasoning": reasoning_for_client,
        "usage": usage,
        "conversation_title": conv_title,
        "framework": not deps.service._llm.is_configured,
        "hit_tool_limit": hit_limit,
    }
