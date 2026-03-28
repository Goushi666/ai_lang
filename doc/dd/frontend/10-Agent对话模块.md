# Web 端设计 · Agent 对话模块

## 1. 路由与组件

- 路由：`/agent` 或使用 **全局抽屉** 组件 `components/agent/AgentDrawer.vue`，由 `App.vue` 或 layout 挂载「打开状态」。
- 建议同时提供 **小屏全屏页** `/agent` 与 **大屏抽屉**，共用 `AgentChatCore.vue`。

## 2. 目录（增量）

```
src/
├── api/
│   └── agent.js              # chat(messages), streamChat 可选
├── components/
│   └── agent/
│       AgentDrawer.vue       # 抽屉壳 + 标题 + 关闭
│       AgentChatCore.vue     # 消息列表 + 输入框 + 发送
├── views/
│   └── AgentAssistant.vue    # 全页模式
```

## 3. UI 行为

- **消息列表**：`v-for` 渲染；`role === 'user'` 右对齐，`assistant` 左对齐；Markdown 可选 `markdown-it` 轻量渲染（注意 XSS，仅白名单标签）。
- **输入区**：`el-input` type textarea + 发送按钮；`Enter` 发送 / `Shift+Enter` 换行（可配置）。
- **Loading**：请求进行中禁用发送，最后一条 assistant 占位气泡显示打字动画或 `el-skeleton`。
- **流式**：`fetch` + `ReadableStream` 解析 SSE，追加到当前 assistant 气泡；`done` 事件结束 Loading。

## 4. 状态管理

- MVP：组件内 `ref` 保存 `messages` 与 `sessionId`（后端返回则更新）。
- 若多页共享：`pinia` store `agent.ts` 存 `sessionId` 与 `messages` 快照（注意隐私，登出清空）。

## 5. API 封装 (`api/agent.js`)

非流式：

```javascript
import request from '@/utils/request'

export const agentApi = {
  chat: (body) => request.post('/api/agent/chat', body),
}
```

流式（示例，与后端 SSE 对齐）：

```javascript
export async function agentChatStream(body, onDelta, onDone, onError) {
  const res = await fetch('/api/agent/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body),
  })
  // 解析 event stream ...
}
```

开发环境经 Vite 代理到后端，路径与 `vite.config` 一致。

## 6. 入口集成

- `App.vue` 或主导航：悬浮 `el-button` circle，`@click` 打开抽屉。
- `AGENT_ENABLED`：可由 `GET /api/agent/health` 或配置接口决定；失败则隐藏按钮。

## 7. 从分析页带入上下文

- `AgentAssistant.vue` `onMounted`：`const q = route.query.context` → `JSON.parse(decodeURIComponent(q))` → 构造 `messages: [{ role: 'user', content: '请结合以下分析摘要解读：...' }]` 自动发送或预填输入框。

## 8. 安全展示

- 面板底部 `el-alert` type info：**助手回答仅供参考，控制与配置请以系统功能为准。**
