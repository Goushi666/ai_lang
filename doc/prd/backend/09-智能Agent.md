# 后端需求 · 智能 Agent

## 1. 目标

在井场监测平台上加一个 **基于大模型的对话助手**，用自然语言完成日常运维中的 **查询、归纳、报告生成、文档问答** 等重复性工作，减轻值班负担。

Agent **只做语义层封装**：数据与计算仍由现有 `sensor_service` / `alarm_service` / `vehicle_service` / `analysis_service` 等模块提供，Agent 通过 **工具调用（Function Calling）** 访问它们。

---

## 2. 功能清单

### 2.1 对话查询（P0，必做）

用户用自然语言问，Agent 调后端工具拿数据后回答。

- 查传感器最新值 / 历史趋势
- 查告警列表 / 告警详情
- 查环境分析结果（聚合、异常片段）

### 2.2 报告生成（P1）

一句话生成结构化报告，输出 Markdown：

- 日报（昨日告警统计\数据统计）
- 触发 CSV 导出（复用现有导出接口）

### 2.3 告警智能分诊（P1）

告警中心每条告警旁加「问 AI」按钮。Agent 自动拉取告警前后的传感器数据与环境分析结果，给出 **可能原因 + 建议动作**。

### 2.4 文档问答（P2）

对 `doc/` 下的 PRD、SOP、故障手册做向量化检索，回答"XX 怎么排查 / 怎么操作"类问题，附引用来源。

### 2.5 预测联动（P2）

调用已有的 `temperature_forecast` 模型，回答"未来几小时会不会超限"并给出提示。

### 2.6 受控操作（P3，分期实现）

在 **严格二次确认** 下编排车辆巡检或修改告警阈值：

- Agent 只生成「动作计划」，不直接执行；
- 前端弹确认框展示计划，用户点确认后才真正下发指令；
- 所有控制类操作写审计日志。

默认 **关闭**（`AGENT_CONTROL_TOOLS_ENABLED=false`）。

---

## 3. 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/agent/health` | 是否启用、模型可达性 |
| POST | `/api/agent/chat` | 对话，支持 SSE 流式（`Accept: text/event-stream`）|
| POST | `/api/agent/confirm` | 确认 control 类工具的待执行动作 |
| DELETE | `/api/agent/sessions/{sid}` | 清空会话 |

---

## 4. 设计思路

### 4.1 整体结构

```
Vue 聊天面板
    │  SSE
FastAPI /api/agent/*
    │
AgentService（调度循环）
    ├── LLM 客户端（OpenAI 兼容，支持 DeepSeek/Qwen/Kimi）
    ├── 工具注册表（统一 schema）
    └── 会话存储（Redis）
         │
各工具包装现有 service 层（不直接读库）
```

### 4.2 调度循环

简单的 Function Calling 循环：

```
while True:
    resp = llm.chat(messages, tools=TOOLS, stream=True)
    if resp.tool_calls:
        for call in tool_calls:
            result = tool_registry[call.name].run(**args)
            messages.append(tool_result)
        continue
    else:
        yield resp.content   # SSE 流式返回
        break
```

循环有 **次数上限（默认 10）** 和 **总超时（默认 60s）**，防死循环。

### 4.3 工具分三类

| 类别 | 例子 | 执行策略 |
|------|------|----------|
| read | 查传感器 / 告警 / 车辆 / 分析结果 | 直接执行 |
| write | 生成报告、确认告警 | 直接执行 + 写审计 |
| control | 车辆控制、改阈值 | **先返回 pending_action，等前端确认后再执行** |

### 4.4 会话

Redis 存短期对话历史，key = `agent:session:{sid}`，默认 TTL 24h。历史按轮数或 token 滚动裁剪。

### 4.5 安全

- **系统提示词固定在服务端**，硬约束"只能用工具取数，不得编造数值"
- **API Key 只从环境变量读**，禁止入库
- **速率限制** 按 IP/用户限流（默认 10 次/分）
- **成本预算** 每会话 / 每日 token 上限，超限降级
- **审计日志** 记录工具名、参数摘要、耗时，**不记完整 prompt**

### 4.6 降级

- `AGENT_ENABLED=false` 时所有接口返回 503，前端隐藏入口
- 模型不可用时返回明确错误，平台其他功能不受影响

---

## 5. 关键配置项

| 配置项 | 说明 |
|--------|------|
| `AGENT_ENABLED` | 总开关 |
| `AGENT_LLM_BASE_URL` / `AGENT_LLM_API_KEY` / `AGENT_LLM_MODEL` | OpenAI 兼容接口配置 |
| `AGENT_LOOP_TIMEOUT_SEC` | 对话循环总超时（默认 60） |
| `AGENT_MAX_TOOL_CALLS` | 单次对话工具调用上限（默认 10） |
| `AGENT_SESSION_TTL_SEC` | 会话过期时间（默认 86400） |
| `AGENT_RATE_LIMIT_PER_MIN` | 限流阈值（默认 10） |
| `AGENT_CONTROL_TOOLS_ENABLED` | control 类工具开关（默认 false） |
| `AGENT_RAG_ENABLED` | 文档检索开关（默认 false） |

---

## 6. 分期

| 阶段 | 范围 |
|------|------|
| **P0** | LLM 接入 + SSE 流式 + 只读工具（传感器/告警/车辆/分析/设备）+ 会话 + 开关 |
| **P1** | 报告生成工具 + 告警分诊 + 速率限制 + 审计日志 |
| **P2** | 文档 RAG + 预测工具 |
| **P3** | Control 类工具 + 二次确认链路 |

---

## 7. 验收要点

1. `AGENT_ENABLED=false` 时接口返回 503，前端入口隐藏
2. 无数据时 Agent 明确说"无数据"而不是编造
3. 工具循环不超过次数上限，到上限优雅终止
4. control 类工具未确认前不会下发任何实际指令
5. 模型故障不影响平台其他功能
