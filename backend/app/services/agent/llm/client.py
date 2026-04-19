"""LLM 客户端：封装 OpenAI 兼容接口的调用。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """LLM 单次响应。"""

    content: Optional[str] = None
    reasoning: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None


def _message_reasoning(msg: Dict[str, Any]) -> Optional[str]:
    """OpenAI 兼容：部分推理模型返回 reasoning_content。"""
    if not msg:
        return None
    return msg.get("reasoning_content") or msg.get("reasoning")


def _merge_tool_call_deltas(
    slots: Dict[int, Dict[str, Any]],
    delta_tool_calls: Optional[List[Dict[str, Any]]],
) -> None:
    """合并流式 tool_calls 片段（按 index）。"""
    for tc in delta_tool_calls or []:
        idx = int(tc.get("index", 0))
        if idx not in slots:
            slots[idx] = {
                "id": "",
                "type": "function",
                "function": {"name": "", "arguments": ""},
            }
        s = slots[idx]
        if tc.get("id"):
            s["id"] = tc["id"]
        if tc.get("type"):
            s["type"] = tc["type"]
        fn = tc.get("function") or {}
        if fn.get("name"):
            s["function"]["name"] = (s["function"].get("name") or "") + fn["name"]
        if fn.get("arguments"):
            s["function"]["arguments"] = (
                (s["function"].get("arguments") or "") + fn["arguments"]
            )


def _tool_slots_to_list(slots: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not slots:
        return []
    return [slots[i] for i in sorted(slots.keys())]


class LLMClient:
    """
    OpenAI 兼容 LLM 客户端。

    当 api_key 为空时进入 stub 模式，返回框架占位回复，
    方便开发阶段无需真实 Key 即可调试整个链路。
    """

    def __init__(self, api_key: str = "", base_url: str = "", model: str = ""):
        self._api_key = api_key
        # httpx base_url 必须以 / 结尾，否则相对路径拼接会丢失路径段
        self._base_url = (base_url.rstrip("/") + "/") if base_url else ""
        self._model = model
        self._http_client: Any = None  # lazy init httpx.AsyncClient

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key and self._base_url and self._model)

    async def _ensure_client(self) -> Any:
        if self._http_client is None:
            import httpx
            self._http_client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=120.0,
            )
        return self._http_client

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        """
        非流式调用 /chat/completions。

        未配置时返回 stub 响应。
        """
        if not self.is_configured:
            return LLMResponse(
                content="【智能助手 · 框架占位】尚未配置 LLM（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL）。",
                finish_reason="stop",
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            )

        client = await self._ensure_client()
        body: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            body["tools"] = tools

        resp = await client.post("chat/completions", json=body)
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]
        message = choice["message"]
        return LLMResponse(
            content=message.get("content"),
            reasoning=_message_reasoning(message),
            tool_calls=message.get("tool_calls"),
            finish_reason=choice.get("finish_reason"),
            usage=data.get("usage"),
        )

    async def chat_completion_stream_round(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        单次流式 /chat/completions：边读边 yield delta，最后 yield final LLMResponse。

        事件：
        - ``{"kind": "delta", "reasoning": "..."}`` / ``{"kind": "delta", "content": "..."}``
        - ``{"kind": "final", "response": LLMResponse}``
        """
        if not self.is_configured:
            msg = "【智能助手 · 框架占位】尚未配置 LLM（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL）。"
            yield {"kind": "delta", "content": msg}
            yield {
                "kind": "final",
                "response": LLMResponse(
                    content=msg,
                    finish_reason="stop",
                    usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                ),
            }
            return

        client = await self._ensure_client()
        body: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
        }
        if tools:
            body["tools"] = tools

        full_reasoning = ""
        full_content = ""
        tool_slots: Dict[int, Dict[str, Any]] = {}
        last_usage: Optional[Dict[str, int]] = None
        last_finish: Optional[str] = None

        async with client.stream("POST", "chat/completions", json=body) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                try:
                    choice = chunk["choices"][0]
                except (KeyError, IndexError):
                    continue
                delta = choice.get("delta") or {}
                if chunk.get("usage"):
                    last_usage = chunk["usage"]
                fr = choice.get("finish_reason")
                if fr:
                    last_finish = fr

                reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                if reasoning:
                    full_reasoning += reasoning
                    yield {"kind": "delta", "reasoning": reasoning}
                text = delta.get("content")
                if text:
                    full_content += text
                    yield {"kind": "delta", "content": text}
                _merge_tool_call_deltas(tool_slots, delta.get("tool_calls"))

        merged_tools = _tool_slots_to_list(tool_slots)
        final_tools: Optional[List[Dict[str, Any]]] = merged_tools if merged_tools else None

        yield {
            "kind": "final",
            "response": LLMResponse(
                content=full_content or None,
                reasoning=full_reasoning or None,
                tool_calls=final_tools,
                usage=last_usage,
                finish_reason=last_finish,
            ),
        }

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        流式调用 /chat/completions（仅 delta 片段，兼容旧代码）。

        推理模型常见 ``delta.reasoning_content`` 与 ``delta.content`` 分开发送。
        """
        async for ev in self.chat_completion_stream_round(messages, tools):
            if ev.get("kind") != "delta":
                continue
            out: Dict[str, Any] = {}
            if ev.get("reasoning"):
                out["reasoning"] = ev["reasoning"]
            if ev.get("content"):
                out["content"] = ev["content"]
            if out:
                yield out

    async def close(self) -> None:
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
