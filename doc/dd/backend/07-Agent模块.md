# 后端设计 · Agent 模块

## 1. 定位

- **AgentService**（`app/services/agent/service.py`）：门面层；**对话控制流**由 **LangGraph** 编译图统一执行（非流式 `ainvoke`、SSE `astream` + `custom` 流）。
- **编排细节**（节点、边、SSE 与 JSON 如何共用一图）：见 [**08-Agent-LangGraph编排架构.md**](./08-Agent-LangGraph编排架构.md)。  
- **工业 Agent**（安全审计 Agent、反思机制与 LangGraph 衔接）：见 [**09-工业Agent-安全审计与反思.md**](./09-工业Agent-安全审计与反思.md)。  
- **多层记忆**（工作 / 情景 / 语义 / 感知）：见 [**10-Agent多层记忆架构.md**](./10-Agent多层记忆架构.md)。
- **路由**：`app/api/v1/agent.py`，挂载前缀 **`/api/agent`**。
- **产品需求与验收**：[`../../prd/backend/09-智能Agent.md`](../../prd/backend/09-智能Agent.md)。本节补充**与实现对齐的架构表述**及**演进优先级**（不替代 PRD 正文）。

## 2. 目录结构（与仓库一致）

```
app/services/agent/
├── service.py           # AgentService：ainvoke / astream、标题与落库
├── graph/               # LangGraph：build、state、nodes、工业审计/反思、safety、tool_tier
│   ├── build.py
│   ├── state.py
│   ├── nodes.py
│   ├── deps.py
│   ├── safety.py
│   ├── tool_tier.py
│   ├── streamutil.py
│   └── tool_export.py
├── clarifier.py
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
│   ├── knowledge_tools.py   # search_knowledge_base（FTS）
│   ├── csv_export_tools.py
│   ├── time_tools.py
│   └── vehicle_tools.py     # 巡检车 / 机械臂（与 industrial、vehicle 模式审计联动）
├── memory/                  # 多层记忆（工作/情景/语义桥/聚合）
│   ├── working.py
│   └── service.py
└── skills/
    ├── base.py
    └── env_diagnosis.py
```

知识检索实现见 **`app/services/knowledge/`**（`chunker` + **SQLite FTS5** 的 `KnowledgeService`，与 `agent` 包并列）。

## 3. REST 端点一览（`/api/agent`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | Agent/LLM/流式/RAG 等开关状态（含 `knowledge_ready` 等） |
| POST | `/chat` | 非流式对话 |
| POST | `/chat/stream` | **SSE 流式**（已实现）：`delta` / `done` / `error` |
| POST | `/memory/perceptual` | 写入感知记忆（多模态引用，需登录） |
| GET | `/sessions/{session_id}` | 读会话（内存或 SQLite 回补） |
| DELETE | `/sessions/{session_id}` | 删会话 |
| GET | `/history` | 历史对话列表 |
| GET | `/history/{conversation_id}` | 读某历史对话 |
| DELETE | `/history/{conversation_id}` | 删历史对话 |
| GET | `/tools` | 当前已注册工具声明 |
| POST | `/knowledge/ingest` | 导入知识（Markdown 文件或正文）→ FTS |
| GET | `/knowledge/status` | FTS 知识库状态（如 `total_chunks`、`db_path`） |
| DELETE | `/knowledge/{doc_id}` | 按 **source 标识**（与入库文件名经 `_safe_source_id` 规范化一致）删除该文档全部块 |

### 3.1 管理员知识维护（`/api/admin`，JWT 且 `level=admin`）

与 **`knowledge_docs/`** 目录及 FTS 索引相关的维护接口挂在 **`admin` 路由**（非 Agent 前缀），例如：列出/上传 `.md`、一键导入目录、按 source 删除索引、清空 FTS、删除磁盘文件等。实现见 `app/api/v1/admin.py`；前端在 **系统设置** 中仅对管理员展示。

## 4. 请求/响应要点

`POST /api/agent/chat` 请求体见 `ChatRequest`（`session_id`、`messages`、`mode`、`stream`）。

**对话模式 `mode`**（与前端一致）：`general` | `rag` | `vehicle` | `industrial`。其中 `industrial` 与 `vehicle` 在 LangGraph 中走 **安全审计（audit）** 与 **反思（reflect）** 分支（见 [08](./08-Agent-LangGraph编排架构.md)、[09](./09-工业Agent-安全审计与反思.md)）。

`ChatResponse` 主要字段：

| 字段 | 说明 |
|------|------|
| `content` | 助手正文 |
| `reasoning` | 链式思考（与 `content` 分离展示；推理模型常见） |
| `session_id` | 会话 ID |
| `framework` | 未接入真实 LLM 时为 True（占位） |
| `clarification` | 追问载荷（可选） |
| `industrial_audit` / `industrial_reflection` | 工业/车控链路下的审计与反思结构化结果（可选） |
| `sources` | 引用来源等扩展（可选，未结构化填充） |
| `usage` | Token 用量（可含嵌套 dict） |

## 5. 工具与知识库（RAG）

- **数据类**：`get_current_time`、`get_sensor_latest`、`get_sensor_history`、`get_alarms_history`、`get_alarm_config`、`get_environment_analysis`（由 `main.py` 注册决定）。
- **导出**：`export_csv_file`（小表）、`export_sensor_history_csv`、`export_alarms_history_csv`。
- **知识**：`search_knowledge_base` → `KnowledgeService.search`（**FTS5/BM25**，无独立向量服务）。
- **车控与机械臂**：`control_vehicle`、`control_arm_joints`、`get_vehicle_status`（MQTT 经 `VehicleService`；与 REST `/api/vehicle` 同源能力，供 Agent 自然语言调用）。
- **知识注入双路径**：
  1. **`mode=rag`**：在 `build_system` 中 **`_append_rag_retrieval`** 将检索片段直接写入 **system**（「已检索到的说明文档片段」），模型优先据此作答；仍可按提示调用 `search_knowledge_base` 补充。
  2. **通用等模式**：主要靠工具拉数；**多层记忆**中的语义层可在非 `rag` 下做轻量 FTS 摘要注入（见 [10-Agent多层记忆架构.md](./10-Agent多层记忆架构.md)）。
- 系统提示词：`app/services/agent/llm/prompts.py`（含 `general` / `rag` / `vehicle` / `industrial` 后缀与用户级别行）。
- **已实现能力摘要**：LangGraph 单图、`LLMClient`、Tool 注册表、会话内存 + SQLite 落库、SSE、FTS 知识库、工业审计/反思、多层记忆注入。

## 6. 流式说明

**流式已实现**：`POST /chat/stream` 返回 `text/event-stream`。**与 `POST /chat` 共用同一张 LangGraph**；图中在 `configurable.sse_stream=True` 时通过 `get_stream_writer` 推送 `delta` / `clarification` / `export_ready` / `done`（详见 [08-Agent-LangGraph编排架构.md](./08-Agent-LangGraph编排架构.md) §4）。工具轮仍在服务端完成，前端不接收完整 tool JSON。

## 7. 安全与配置

- 环境变量（节选）：`AGENT_ENABLED`、`LLM_*`、`AGENT_RAG_ENABLED`、`AGENT_RAG_TOP_K`、`KNOWLEDGE_SQLITE_PATH`、`KNOWLEDGE_DOCS_DIR`、多层记忆 `AGENT_MEMORY_*`、工业链路 `AGENT_INDUSTRIAL_*`、`AGENT_TOOLS_PARALLEL` 等（见 `app/core/config.py`）。**`VECTOR_DB_PATH` / `EMBEDDING_*`** 为历史字段，默认知识链路使用 **FTS**。
- 工具仅调用已封装 Service，不执行任意 SQL/代码。
- **用户级别**：由 JWT 解析；`guest` 级会话提示登录；控制类工具与工业审计策略见 `prompts.py` / `graph/safety.py` / `graph/tool_tier.py`。

## 8. 会话存储

- 内存 **SessionManager**（TTL/条数上限；超长时按条数截断最早非 system 消息）+ **SQLite** `agent_conversations` / `agent_messages` 持久化（`AgentChatRepository`）。
- **未实现**（相对 PRD §7.2）：按 token 的摘要压缩、超长 tool 返回的结构化摘要策略。

---

## 9. 与 PRD 的差异及命名建议

PRD 中的 **「MCP + Tool + Skill」** 易被理解为 **Model Context Protocol 标准协议**。**当前仓库**为：**会话上下文 + OpenAI 兼容 function calling**（**未**接 MCP stdio/SSE 与外部 MCP Server）。设计表述建议用 **「Context + Tool + Skill」** 或 **「会话层 + 工具层 + 技能层」**；若未来接真实 MCP，再单设「MCP 适配层」与 `ToolRegistry` 的桥接说明。

| 项 | PRD 期望 | 当前代码 |
|----|----------|----------|
| **Clarifier** | 模糊意图返回 `clarification`，前端点选后继续。 | **`graph.nodes.node_clarify`** 调用 `Clarifier.check()`；需追问时走 `finalize_clarify` 分支并返回 `ClarificationPayload`（与 SSE `clarification` 事件对齐）。 |
| **Skill** | `env_diagnosis` 编排多 Tool。 | `EnvDiagnosisSkill.run()` **占位**；主路径为 **LLM 自主 tool_calls**，无强制 Skill DAG。 |
| **RAG 相对 PRD §3.2** | Hybrid、`get_document_content`、PDF 等。 | 以 **FTS 全文检索** + Markdown 分块入库为主；**Hybrid / `get_document_content` / PDF** 未做；`rag` 模式另有 **system 级片段注入**，**`sources` 字段仍未结构化填充**。 |
| **车控类 Tool** | 可选扩展。 | **已注册** `control_vehicle`、`control_arm_joints`、`get_vehicle_status`（与 REST 车控并存）；`industrial`/`vehicle` 模式下拟执行控制/导出等会触发审计（见 [09](./09-工业Agent-安全审计与反思.md)）。 |

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

**原则**：（1）澄清是**控制流**，与多轮 tool **解耦**；（2）Skill **渐进落地**，先显式触发再考虑替代 LLM 全局规划；（3）知识问答模式（`rag`）以 **system 注入检索片段** 为主，与 **`search_knowledge_base` 工具** 形成互补；通用模式的大块实时数据仍优先走 **tool 消息**。

---

## 11. 分阶段演进（推荐优先级）

### 阶段 A（优先，对齐 PRD P0 验收「模糊追问 / 明确直答」）

| 工作项 | 说明 | 主要改动点 |
|--------|------|------------|
| **A1** | 对用户末条消息做澄清检查；若需澄清则**短路**返回 `clarification`，**不进入** LLM/tool 主链。 | **已在 LangGraph** `ingest → clarify → finalize_clarify` 路径实现（`graph/nodes.py`）；前端消费 SSE `clarification` / JSON 同构字段。 |
| **A2** | 澄清策略：先**规则**（缺时间窗/设备等），再视需要 **LLM 结构化输出**。 | `clarifier.py` 持续迭代 |
| **A3** | 固定模糊/明确用例做回归。 | 测试或文档附录 |

### 阶段 B（Skill，对齐 PRD §4.3）

| 工作项 | 说明 |
|--------|------|
| **B1** | 实现 `EnvDiagnosisSkill.run()`：解析意图 → 不足则复用澄清模型 → 足则编排 `tool_registry.execute`。 |
| **B2** | 触发方式建议先 **显式**（入口或 intent 命中），再评估是否隐式全局化。 |

### 阶段 C（知识检索增强）

可选：`get_document_content`、**向量混合检索**（在保留 FTS 的前提下）、**`ChatResponse.sources`** 结构化填充、PDF 解析管道等（按数据规模与验收再引入）。

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
| RAG / FTS | `app/services/knowledge/*`、`tools/knowledge_tools.py` |
| 工业审计与反思 | `app/services/agent/graph/safety.py`、`tool_tier.py`、`nodes.py` |
| 多层记忆 | `app/services/agent/memory/*`、`models/agent_memory_layers.py`、`repositories/agent_memory_repo.py` |
| API | `app/api/v1/agent.py`、`app/api/v1/admin.py`（知识维护） |

---

## 13. 刻意不做（避免过度设计）

- 不为「名义 MCP」引入 **完整 MCP 协议栈**，除非确定要接外部 MCP Server 生态。
- 澄清未稳定前，不把 Skill 做成复杂状态机以免与 LLM 规划双轨冲突。
- 当前 FTS 已满足中小规模说明文档检索；若后续要上 **向量混合检索**，再在 `KnowledgeService` 侧演进，避免 Agent 工具面频繁 Breaking Change。

---

## 14. 文档维护

- PRD 范围/验收变更：**先改** [`09-智能Agent.md`](../../prd/backend/09-智能Agent.md)，再同步更新本节 §9～§11 与 §3 路由表（若有新端点）。
- 完成阶段 A/B/C 某项后，可在本节对应行或 PRD 验收表标注完成日期/PR。

---

## 15. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-04-18 | 合并原「08-Agent架构与演进方案」至本文；统一在 07 中维护 Agent 设计与演进。 |
| 2026-05-07 | 对齐当前实现：SQLite FTS 知识库、四模式（含 industrial/vehicle）、车控工具、admin 知识接口、LangGraph 澄清与工业链路。 |
