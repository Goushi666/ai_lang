"""意图澄清：由大模型评估问题清晰度，不足时生成追问与快捷选项。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.config import settings

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
    由 ``settings.AGENT_CLARIFICATION_ENABLED`` 总开关控制；关闭时 ``check`` 立即返回且不耗时。

    开启后可选「极短问句先走本地模板」避免 LLM；否则使用主链路 LLMClient：
    - one-shot（默认）：单次 JSON 含 clarity_score；不足 min_clarity 时同条带 question/options。
    - 两阶段（可关 one-shot）：先判别分数，再单独生成追问。
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

        raw_modes = (getattr(settings, "AGENT_CLARIFICATION_SKIP_MODES", "") or "").strip()
        if raw_modes:
            skip_set = {m.strip().lower() for m in raw_modes.split(",") if m.strip()}
            if (session_mode or "").strip().lower() in skip_set:
                return None

        skip_min = int(getattr(settings, "AGENT_CLARIFICATION_SKIP_MIN_USER_CHARS", 0) or 0)
        if skip_min > 0 and len(text) >= skip_min:
            return None

        hf = int(getattr(settings, "AGENT_CLARIFICATION_HEURISTIC_FIRST_MAX_CHARS", 0) or 0)
        if hf > 0 and len(text) <= hf:
            early = self._heuristic_vague_clarification(text, session_mode, len_limit=hf)
            if early is not None:
                return early

        if self._llm is None or not self._llm.is_configured:
            return None

        if bool(getattr(settings, "AGENT_CLARIFICATION_ONE_SHOT", True)):
            kind, cq = await self._check_one_shot(text, session_mode)
            if kind == "pass":
                return None
            if kind == "clarify":
                return cq
            heur = self._heuristic_vague_clarification(text, session_mode)
            if heur is not None:
                return heur
            # one-shot 已超时：不再串联两阶段（易二次超时导致长时间无响应）
            if kind == "timeout":
                logger.warning(
                    "clarifier: one-shot timed out, no heuristic match, pass through to main agent"
                )
                return None
            return await self._check_two_phase(text, session_mode)

        return await self._check_two_phase(text, session_mode)

    def _mode_label(self, session_mode: str) -> str:
        m = (session_mode or "").strip().lower()
        if m == "rag":
            return "知识问答（可结合知识库）"
        if m == "industrial":
            return "工业巡检对话"
        return "通用对话"

    def _question_from_payload(
        self,
        data: Dict[str, Any],
    ) -> Optional[ClarificationQuestion]:
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
        max_o = self._max_options
        if not question or len(options) < 2:
            return None
        return ClarificationQuestion(question=question, options=options[:max_o], allow_custom=True)

    def _heuristic_vague_clarification(
        self,
        text: str,
        session_mode: str,
        len_limit: Optional[int] = None,
    ) -> Optional[ClarificationQuestion]:
        """
        极短、笼统问句的本地追问模板。
        - ``len_limit`` 有值时用其作为字数上限（启发式优先路径）；
        - 否则用 ``AGENT_CLARIFICATION_HEURISTIC_MAX_CHARS``（LLM 失败后的兜底）。
        """
        if len_limit is not None:
            max_c = int(len_limit)
        else:
            max_c = int(getattr(settings, "AGENT_CLARIFICATION_HEURISTIC_MAX_CHARS", 0) or 0)
        if max_c <= 0:
            return None
        if len(text) > max_c:
            return None
        m = (session_mode or "").strip().lower()
        if m in ("rag", "vehicle"):
            return None
        return ClarificationQuestion(
            question=(
                "您的问题还比较笼统。请先选一下想了解的方向，或在下方用一句话补充"
                "（例如时间范围、具体指标或设备）。"
            ),
            options=[
                ClarificationOption(
                    label="实时环境监测",
                    value="请帮我查询当前各传感器最新读数，并说明是否接近告警阈值。",
                ),
                ClarificationOption(
                    label="最近告警",
                    value="请汇总最近24小时内的环境相关告警记录。",
                ),
                ClarificationOption(
                    label="历史或分析",
                    value="我想查看一段时间内的环境数据趋势或环境分析结论。",
                ),
                ClarificationOption(
                    label="功能与用法",
                    value="请介绍平台和环境监测相关功能该怎么用，不需要拉实时数值。",
                ),
            ],
            allow_custom=True,
        )

    async def _check_one_shot(
        self,
        text: str,
        session_mode: str,
    ) -> tuple[str, Optional[ClarificationQuestion]]:
        """
        Returns:
            ("pass", None) — 足够清晰，无需澄清
            ("clarify", ClarificationQuestion) — 需追问
            ("timeout", None) — one-shot 超时（勿再串联慢路径）
            ("fallback", None) — 解析/其它失败，可尝试两阶段兜底
        """
        llm = self._llm
        if llm is None:
            return ("fallback", None)
        mode_label = self._mode_label(session_mode)
        mc = self._min_clarity
        max_o = self._max_options
        timeout = float(getattr(settings, "AGENT_CLARIFICATION_ONE_SHOT_TIMEOUT_SEC", 10.0) or 10.0)
        timeout = max(2.0, min(120.0, timeout))
        shot_max = int(getattr(settings, "AGENT_CLARIFICATION_ONE_SHOT_MAX_TOKENS", 280) or 280)
        shot_max = max(64, min(1024, shot_max))

        system = (
            "判别用户问题清晰度并输出 JSON（无 markdown）。\n"
            "字段：clarity_score(0～1)；question(字符串)；options(数组，项为{label,value})。\n"
            f"若 clarity_score≥{mc}：question、options 为 null。\n"
            f"若 clarity_score<{mc}：必填简短中文追问与 {2}～{max_o} 个选项；label≤16字。\n"
            "短主题词无范围（如仅「环境」「告警」）须低分并追问。"
        )
        user = f"会话模式：{mode_label}\n\n用户问题：\n{text[:2000]}"
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        try:
            data = await asyncio.wait_for(
                llm.chat_completion_json(messages, max_tokens=shot_max, temperature=0.1),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("clarifier one-shot timed out")
            return ("timeout", None)
        except Exception as exc:
            logger.warning("clarifier one-shot failed: %s", exc)
            return ("fallback", None)

        if not data:
            return ("fallback", None)

        clarity = _clamp01(data.get("clarity_score"))
        if clarity >= self._min_clarity:
            return ("pass", None)

        qn = self._question_from_payload(data)
        if qn is None:
            return ("fallback", None)
        return ("clarify", qn)

    async def _check_two_phase(
        self,
        text: str,
        session_mode: str,
    ) -> Optional[ClarificationQuestion]:
        clarity = await self._llm_clarity_score(text, session_mode)
        if clarity is None:
            return None
        if clarity >= self._min_clarity:
            return None
        return await self._llm_clarification_payload(text, session_mode)

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
        parsed = _extract_json_object(raw)
        if not parsed:
            logger.warning("clarifier clarity judge unparsable: %s", raw[:200])
            return None
        return _clamp01(parsed.get("clarity_score"))

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
        return self._question_from_payload(data)
