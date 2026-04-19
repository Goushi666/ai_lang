# 后端设计 · Agent 模块

## 1. 定位

- **AgentService**（`app/services/agent/service.py`）：编排 LLM、多轮 **工具调用**、会话持久化与流式 SSE。
- **路由**：`app/api/v1/agent.py`，挂载前缀 **`/api/agent`**。
- **产品需求与验收**：[`../../prd/backend/09-智能Agent.md`](../../prd/backend/09-智能Agent.md)。本节补充**与实现对齐的架构表述**及**演进优先级**（不替代 PRD 正文）。

## 2. 目录结构（与仓库一致）

```
app/services/agent/
├── service.py           # AgentService
├── clarifier.py
├── conversation_title.py
├── context/
│   └── session.py       # SessionManager、Session、Message
├── llm/
│   ├── client.py        # OpenAI 兼容 httpx
│   ├── prompts.py       # 系统提示词
│   └── reasoning_split.py
├── tools/
│   ├── base.py
│   ├── sensor_tools.py
│   ├── alarm_tools.py
│   ├── analysis_tools.py
│   └── knowledge_tools.py   # search_knowledge_base（RAG）
└── skills/
    ├── base.py
    └── env_diagnosis.py
```

RAG 向量与嵌入实现见 **`app/services/knowledge/`**（与 `agent` 包并列）。

## 3. REST 端点一览（`/api/agent`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | Agent/LLM/流式/RAG 等开关状态（含 `knowledge_ready` 等） |
| POST | `/chat` | 非流式对话 |
| POST | `/chat/stream` | **SSE 流式**（已实现）：`delta` / `done` / `error` |
| GET | `/sessions/{session_id}` | 读会话（内存或 SQLite 回补） |
| DELETE | `/sessions/{session_id}` | 删会话 |
| GET | `/history` | 历史对话列表 |
| GET | `/history/{conversation_id}` | 读某历史对话 |
| DELETE | `/history/{conversation_id}` | 删历史对话 |
| GET | `/tools` | 当前已注册工具声明 |
| POST | `/knowledge/ingest` | 导入知识（Markdown 文件或正文） |
| GET | `/knowledge/status` | 向量库中文档数/分块数 |
| DELETE | `/knowledge/{doc_id}` | 按 doc_id 删除索引 |

## 4. 请求/响应要点

`POST /api/agent/chat` 请求体见 `ChatRequest`（`session_id`、`messages`、`mode`、`stream`）。

`ChatResponse` 主要字段：

| 字段 | 说明 |
|------|------|
| `content` | 助手正文 |
| `reasoning_content` | 链式思考（若有） |
| `session_id` | 会话 ID |
| `framework` | 未接入真实 LLM 时为 True（占位） |
| `clarification` | 追问载荷（可选） |
| `sources` | 引用来源等扩展（可选） |
| `usage` | Token 用量（可含嵌套 dict） |

## 5. 工具与 RAG

- 数据类工具：`get_sensor_latest`、`get_sensor_history`、`get_alarms_history`、`get_alarm_config`、`get_environment_analysis`（由配置决定是否注册）。
- **RAG**：`search_knowledge_base`（`knowledge_tools.py`），依赖 **Chroma** 持久化路径（`VECTOR_DB_PATH`）与 **SiliconFlow `/v1/embeddings`**（`EMBEDDING_MODEL` 等）；入库与状态见 §3 知识库路由。
- 系统提示词：`app/services/agent/llm/prompts.py`；`mode=rag` 时强调知识库检索。
- **已实现能力摘要**：LLM 编排（`LLMClient`）、Tool 注册表、会话内存 + SQLite、流式 SSE、RAG 全链路；输出侧可用 JSON `reasoning`/`answer` 约定 + `reasoning_split` 与前端解析（依模型配合程度）。

## 6. 流式说明

**流式已实现**：`POST /chat/stream` 返回 `text/event-stream`；工具轮在服务端完成，前端主要接收文本增量与结束事件（可额外收到 `type: "tool"` 仅含工具名，不暴露完整 tool JSON）。

## 7. 安全与配置

- 环境变量：`AGENT_ENABLED`、`LLM_*`、`AGENT_RAG_ENABLED`、`VECTOR_DB_PATH`、`EMBEDDING_*` 等。
- 工具仅调用已封装 Service，不执行任意 SQL/代码。

## 8. 会话存储

- 内存 **SessionManager**（TTL/条数上限；超长时按条数截断最早非 system 消息）+ **SQLite** `agent_conversations` / `agent_messages` 持久化（`AgentChatRepository`）。
- **未实现**（相对 PRD §7.2）：按 token 的摘要压缩、超长 tool 返回的结构化摘要策略。

---

## 9. 与 PRD 的差异及命名建议

PRD 中的 **「MCP + Tool + Skill」** 易被理解为 **Model Context Protocol 标准协议**。**当前仓库**为：**会话上下文 + OpenAI 兼容 function calling**（**未**接 MCP stdio/SSE 与外部 MCP Server）。设计表述建议用 **「Context + Tool + Skill」** 或 **「会话层 + 工具层 + 技能层」**；若未来接真实 MCP，再单设「MCP 适配层」与 `ToolRegistry` 的桥接说明。

| 项 | PRD 期望 | 当前代码 |
|----|----------|----------|
| **Clarifier** | 模糊意图返回 `clarification`，前端点选后继续。 | `Clarifier.check()` 固定返回 `None`；**`AgentService` 未调用**，澄清链路未闭合。 |
| **Skill** | `env_diagnosis` 编排多 Tool。 | `EnvDiagnosisSkill.run()` **占位**；主路径为 **LLM 自主 tool_calls**，无强制 Skill DAG。 |
| **RAG 相对 PRD §3.2** | Hybrid、`get_document_content`、PDF 等。 | 以向量检索 + Markdown 入库为主；**Hybrid / `get_document_content` / PDF** 未做；引用主要靠模型消费 tool 结果，**`sources` 字段未结构化填充**。 |
| **PRD 图示 vehicle/report Tool** | 可选扩展。 | Agent **未**注册车控类 Tool（车控仍在 REST `/api/vehicle`）。 |

---

## 10. 推荐目标架构（演进方向）

在**不推翻现有栈**的前提下：**Clarifier 前置短路 + 现有 LLM + Tool 主链**。

```
用户消息
    │
    ▼
┌─────────────────┐     否      ┌──────────────────┐
│ Clarifier 前置   │ ────────► │ LLM + Tool 循环   │──► 回答 / SSE
│（规则或小模型） │             │（AgentService）   │
└────────┬────────┘             └──────────────────┘
         │ 需澄清
         ▼
   返回 clarification → 前端选项 → 再进入主链
```

**原则**：（1）澄清是**控制流**，与多轮 tool **解耦**；（2）Skill **渐进落地**，先显式触发再考虑替代 LLM 全局规划；（3）RAG 继续走 **tool 消息**，避免大块检索结果进 system。

---

## 11. 分阶段演进（推荐优先级）

### 阶段 A（优先，对齐 PRD P0 验收「模糊追问 / 明确直答」）

| 工作项 | 说明 | 主要改动点 |
|--------|------|------------|
| **A1** | 在 `chat` / `chat_events` 对用户末条消息调用 `_clarifier.check()`；若需澄清则**短路**返回带 `clarification` 的响应或 SSE 事件，**不进入** tool 循环。 | `service.py`、`clarifier.py`、前端 SSE |
| **A2** | 澄清策略：先**规则**（缺时间窗/设备等），再视需要 **LLM 结构化输出**。 | `clarifier.py` |
| **A3** | 固定模糊/明确用例做回归。 | 测试或文档附录 |

### 阶段 B（Skill，对齐 PRD §4.3）

| 工作项 | 说明 |
|--------|------|
| **B1** | 实现 `EnvDiagnosisSkill.run()`：解析意图 → 不足则复用澄清模型 → 足则编排 `tool_registry.execute`。 |
| **B2** | 触发方式建议先 **显式**（入口或 intent 命中），再评估是否隐式全局化。 |

### 阶段 C（RAG 增强）

可选：`get_document_content`、Hybrid 检索、**`ChatResponse.sources`** 结构化填充、PDF 解析管道等（按数据规模与验收再引入）。

### 阶段 D（工程化，对齐 PRD §8、§10）

`GET /api/agent/config`（或扩展 `/health`）、`/api/agent/*` **限流**、LLM/工具 **超时 504**、控制类 **`AGENT_CONTROL_TOOLS_ENABLED`** 与审计（若引入车控类 Agent Tool）。

### 阶段 E（PRD P1/P2）

报告、告警分诊 Skill、推送、预测 Tool 等 **单独立项**，不在此表展开。

---

## 12. 演进时代码路径速查

| 主题 | 路径 |
|------|------|
| 对话主链 | `app/services/agent/service.py` |
| 澄清 | `app/services/agent/clarifier.py` |
| 提示词 / 模式 | `app/services/agent/llm/prompts.py` |
| Tool | `app/services/agent/tools/*.py`、注册于 `app/main.py` |
| Skill | `app/services/agent/skills/env_diagnosis.py` |
| RAG | `app/services/knowledge/*`、`tools/knowledge_tools.py` |
| API | `app/api/v1/agent.py` |

---

## 13. 刻意不做（避免过度设计）

- 不为「名义 MCP」引入 **完整 MCP 协议栈**，除非确定要接外部 MCP Server 生态。
- 澄清未稳定前，不把 Skill 做成复杂状态机以免与 LLM 规划双轨冲突。
- 小规模知识库阶段不强行上分布式向量库与重混合检索，除非实测不达标。

---

## 14. 文档维护

- PRD 范围/验收变更：**先改** [`09-智能Agent.md`](../../prd/backend/09-智能Agent.md)，再同步更新本节 §9～§11 与 §3 路由表（若有新端点）。
- 完成阶段 A/B/C 某项后，可在本节对应行或 PRD 验收表标注完成日期/PR。

---

## 15. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-04-18 | 合并原「08-Agent架构与演进方案」至本文；统一在 07 中维护 Agent 设计与演进。 |
