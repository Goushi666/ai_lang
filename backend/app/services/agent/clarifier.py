"""意图澄清：由大模型评估问题清晰度，低于阈值则再次调用模型生成追问与快捷选项。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .llm.client import LLMClient

logger = logging.getLogger(__name__)

_SMALL_TALK = re.compile(
    r"^(你好|您好|嗨|哈喽|在吗|谢谢|多谢|再见|拜拜|早上好|晚上好|help|帮助)\s*[!！。.…]*$",
    re.I,
)


@dataclass
class ClarificationOption:
    label: str
    value: str


@dataclass
class ClarificationQuestion:
    question: str
    options: List[ClarificationOption] = field(default_factory=list)
    allow_custom: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "options": [{"label": o.label, "value": o.value} for o in self.options],
            "allow_custom": self.allow_custom,
        }


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """从模型输出中取出第一个 JSON 对象（允许外层 markdown 围栏）。"""
    if not text or not text.strip():
        return None
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I)
        s = re.sub(r"\s*```\s*$", "", s)
    start = s.find("{")
    end = s.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(s[start : end + 1])
    except json.JSONDecodeError:
        return None


def _clamp01(x: Any) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, v))


class Clarifier:
    """
    使用主链路同一 LLMClient：
    1) 判别清晰度 clarity_score ∈ [0,1]；
    2) 若低于 min_clarity，再调用一次模型生成追问句与若干选项。
    未配置 LLM 或调用失败时放行（不澄清），避免阻断对话。
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        llm_client: Optional[LLMClient] = None,
        min_clarity: float = 0.55,
        judge_timeout_sec: float = 6.0,
        clarify_timeout_sec: float = 12.0,
        max_options: int = 5,
    ) -> None:
        self._enabled = enabled
        self._llm = llm_client
        self._min_clarity = max(0.0, min(1.0, float(min_clarity)))
        self._judge_timeout = max(1.0, float(judge_timeout_sec))
        self._clarify_timeout = max(1.0, float(clarify_timeout_sec))
        self._max_options = max(2, min(8, int(max_options)))

    async def check(
        self,
        user_message: str,
        session_mode: str = "general",
    ) -> Optional[ClarificationQuestion]:
        if not self._enabled:
            return None

        text = (user_message or "").strip()
        if len(text) < 2:
            return None

        if _SMALL_TALK.match(text):
            return None

        if self._llm is None or not self._llm.is_configured:
            return None

        clarity = await self._llm_clarity_score(text, session_mode)
        if clarity is None:
            return None

        if clarity >= self._min_clarity:
            return None

        return await self._llm_clarification_payload(text, session_mode)

    def _mode_label(self, session_mode: str) -> str:
        if session_mode == "rag":
            return "知识问答（可结合知识库）"
        return "通用对话"

    async def _llm_clarity_score(self, text: str, session_mode: str) -> Optional[float]:
        llm = self._llm
        if llm is None:
            return None
        mode_label = self._mode_label(session_mode)
        messages: List[Dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "你是「用户问题清晰度」判别器。只输出一个 JSON 对象，不要 markdown、不要解释。\n"
                    "JSON 格式严格为：{\"clarity_score\": <0到1之间的小数>}\n"
                    "含义：clarity_score=1 表示意图非常明确、信息足够助手直接作答；"
                    "clarity_score=0 表示严重模糊：缺关键条件、范围不明、指代不清、或无法判断用户要什么。\n"
                    "中间值按缺信息程度平滑打分。寒暄、致谢、明确操作指令等应给高分。"
                ),
            },
            {
                "role": "user",
                "content": f"会话模式：{mode_label}\n\n用户问题：\n{text[:2000]}",
            },
        ]
        try:
            resp = await asyncio.wait_for(
                llm.chat_completion(messages, None, max_tokens=80),
                timeout=self._judge_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("clarifier clarity judge timed out")
            return None
        except Exception as exc:
            logger.warning("clarifier clarity judge failed: %s", exc)
            return None

        raw = (resp.content or "").strip()
        data = _extract_json_object(raw)
        if not data:
            logger.warning("clarifier clarity judge unparsable: %s", raw[:200])
            return None
        return _clamp01(data.get("clarity_score"))

    async def _llm_clarification_payload(
        self,
        text: str,
        session_mode: str,
    ) -> Optional[ClarificationQuestion]:
        llm = self._llm
        if llm is None:
            return None
        mode_label = self._mode_label(session_mode)
        max_o = self._max_options
        messages: List[Dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "用户的上一句问题信息不足或意图模糊，你需要生成一条简短、友好的追问，并给出若干可点击的补全选项。\n"
                    "只输出一个 JSON 对象，不要 markdown、不要其它文字。\n"
                    "必须包含字段：question（字符串）、options（数组）；options 每项为对象，含 label、value 两个字符串。\n"
                    f"options 条目数须在 2～{max_o} 之间；label 为按钮短文案（尽量不超过 16 字）；"
                    "value 为用户点选后应补充给助手的完整语义（可与 label 相同或更具体）。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"会话模式：{mode_label}\n\n"
                    f"用户原问题：\n{text[:2000]}\n\n"
                    "请根据缺失的信息设计追问与选项。"
                ),
            },
        ]
        try:
            resp = await asyncio.wait_for(
                llm.chat_completion(messages, None, max_tokens=512),
                timeout=self._clarify_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("clarifier clarify generation timed out")
            return None
        except Exception as exc:
            logger.warning("clarifier clarify generation failed: %s", exc)
            return None

        data = _extract_json_object((resp.content or "").strip())
        if not data:
            return None

        question = (data.get("question") or "").strip()
        raw_opts = data.get("options")
        options: List[ClarificationOption] = []
        if isinstance(raw_opts, list):
            for item in raw_opts:
                if not isinstance(item, dict):
                    continue
                lab = str(item.get("label") or "").strip()
                val = str(item.get("value") or "").strip()
                if not lab:
                    continue
                if not val:
                    val = lab
                options.append(ClarificationOption(label=lab[:40], value=val[:500]))

        if not question or len(options) < 2:
            return None

        options = options[:max_o]
        return ClarificationQuestion(question=question, options=options, allow_custom=True)
