"""渐进式意图澄清：在调用主 LLM 前，对模糊的环境数据类问题追问时间范围等。

默认采用 **规则 + 关键词**（不额外请求大模型），与主对话模型无关；若日后需要更强语义理解，
可在本模块内增加「同一 LLM 一次轻量 JSON 分类」的可选路径（仍共用 LLM_API_KEY / LLM_BASE_URL）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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


# 明显寒暄 / 过短，不追问
_SMALL_TALK = re.compile(
    r"^(你好|您好|嗨|哈喽|在吗|谢谢|多谢|再见|拜拜|早上好|晚上好|help|帮助)\s*[!！。.…]*$",
    re.I,
)

# 更像「说明书 / 界面操作」而非时序数据查询（不强制追问时间）
_KNOWLEDGE_OR_UI = re.compile(
    r"(设置|菜单|导航|在哪|怎么打开|怎么用|如何控制|机械臂|云台|循迹|视频|画面|"
    r"导出|阈值|清空|数据库|手册|文档|FAQ|帮助中心)",
)

# 与环境数据 / 分析相关，才可能需要「时间范围」
_ENV_DATA = re.compile(
    r"(温度|湿度|光照|传感器|采样|告警|报警|环境|数据|分析|趋势|历史|统计|"
    r"最高|最低|平均|异常|监测|井场|设备|时段|区间|曲线|超阈)",
)

# 已包含可解析的时间语义则不再追问「时间范围」
_TIME_HINT = re.compile(
    r"(最近|过去|近)\s*\d+\s*(小时|分钟|天|周|日)|"
    r"\d+\s*(小时|天|周|分钟)|"
    r"(24|二十四)\s*小时|"
    r"今日|今天|昨天|昨日|本周|本月|上周|上星期|"
    r"\d{4}[-年]\d{1,2}[-月]\d{1,2}|"
    r"(上|本|下)周|"
    r"(凌晨|上午|下午|晚间|夜里)",
)

# 「当前 / 实时」视为时间意图已明确（点查）
_NOW_HINT = re.compile(r"(现在|当前|实时|此刻|马上|目前|这一刻)")


class Clarifier:
    """
    意图澄清器。

    - **默认**：规则判断，**不调用任何大模型**（无额外费用、延迟低）。
    - **与主回复模型**：无需区分；澄清与最终回答共用同一 SiliconFlow 配置即可。
      若将来增加「LLM 辅助澄清」，建议使用 **同一 LLMClient**、短 prompt、低 max_tokens，可选 `settings` 独立 `CLARIFICATION_MODEL` 覆盖（一般不必）。
    """

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled

    async def check(
        self,
        user_message: str,
        session_mode: str = "general",
    ) -> Optional[ClarificationQuestion]:
        """
        检查本轮用户消息在调用主链路前是否需要先澄清。

        当前策略：仅对「像环境数据查询、且未给出时间/当前点查语义」的句子返回时间范围选项。
        """
        if not self._enabled:
            return None

        text = (user_message or "").strip()
        if len(text) < 4:
            return None

        if _SMALL_TALK.match(text):
            return None

        # 纯知识/界面类问题不拦（RAG 或操作说明）
        if _KNOWLEDGE_OR_UI.search(text) and not _ENV_DATA.search(text):
            return None

        if not _ENV_DATA.search(text):
            return None

        if _TIME_HINT.search(text) or _NOW_HINT.search(text):
            return None

        # 过长句子往往已自带上下文，减少误触发
        if len(text) > 280:
            return None

        return ClarificationQuestion(
            question="为准确查询环境数据，请选择时间范围（也可在输入框直接说明，例如「昨天下午」）：",
            options=[
                ClarificationOption(label="最近 1 小时", value="最近1小时"),
                ClarificationOption(label="最近 24 小时", value="最近24小时"),
                ClarificationOption(label="今天（从 0 点至今）", value="今天"),
                ClarificationOption(label="最近一周", value="最近一周"),
            ],
            allow_custom=True,
        )
