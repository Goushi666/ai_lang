# 前端样式优化 Prompt（复制即用）

将下方 **「Prompt 正文」** 整段复制给负责改样式的 AI 或协作者。目标是：**只优化视觉与交互样式，不改动后端、不破坏现有业务逻辑**。

---

## Prompt 正文

**角色与目标**  
你是资深前端（Vue 3 + Element Plus），任务是在 **不改动后端、不破坏现有业务逻辑** 的前提下，优化「井场环境监测与智能巡检系统」Web 前端的 **视觉与交互样式**（排版、色彩、字体、间距、组件观感、响应式与可访问性）。

**技术栈与代码位置（只读理解，勿改业务）**  
- 项目路径：`web-frontend/`；构建：Vite；框架：Vue 3 `<script setup>`；UI：Element Plus（全局 `import "element-plus/dist/index.css"`）。  
- 应用壳与全局样式：`src/App.vue`（`el-header` / `el-aside` / `el-main`、`el-menu` 路由、`provide('ws')` / `provide('wsConnected')`、告警 `ElNotification`）。  
- 页面：`src/views/Dashboard.vue`（环境监测 + ECharts）、`AgentAssistant.vue`（智能助手、流式 Markdown、会话列表）、`InspectionVehicle.vue`（巡检/视频/HLS、`inject('ws')`）、`AlarmCenter.vue`、`Settings.vue`。  
- 数据与网络：`src/api/*.js`、`src/utils/request.js`（axios baseURL/token）、`src/utils/websocket.js`。**禁止**修改请求 URL、路径、请求体字段名、WebSocket 消息类型与处理逻辑。

**硬性约束（必须遵守）**  
1. **不修改后端**：不改 Python/FastAPI 或其它服务端代码；不改环境变量含义（如 `VITE_API_BASE_URL`、`VITE_WS_URL`）。  
2. **不破坏功能**：不改路由 path、不改 `router-view` 结构、不改 `v-model` / 事件绑定 / `@click` 对应的方法名、不改 `inject('ws')` 与 `ws.on(...)` 的订阅逻辑、不改 ECharts 的 `setOption` 数据结构与缩放/重置逻辑、不改 Agent 流式解析与 `renderMd` / DOMPurify 用法。  
3. **布局敏感区**：`App.vue` 中为不同路由设置的 class（如 `app-main--dashboard`、`app-main--inspection`、`app-main--agent`、`app-main-route--fill`）用于 **flex + `min-height: 0` + `overflow`**，保证大屏图表、视频页、助手页 **不出现错误的全局滚动或裁切**。样式优化时须 **保留同等高度链与滚动职责**（可改颜色/圆角/阴影，但勿拆掉 flex/overflow 语义）。  
4. **Element Plus**：可通过 **CSS 变量 / 主题覆盖 / 组件 class** 统一视觉；避免全局选择器误伤图表容器或视频层（注意 `z-index`）。  
5. **改动范围**：优先 `<style>`、抽取的 `*.css`、必要时仅调整模板中的 **纯展示性** class 或包裹层，不删业务节点。

**期望产出**  
- 统一设计系统：主色/中性色/圆角/阴影/字阶/间距刻度；顶栏与侧栏与主内容区层次清晰。  
- 各页在 1920×1080 与常见笔记本宽度下 **无布局崩坏**；图表与视频区域仍占满可用高度。  
- 智能助手：消息气泡、侧栏会话列表、输入区在视觉上更现代，**滚动仍只在消息列表内**。  
- 可选项：暗色侧栏 + 浅色主区、或全站暗色（若做需完整覆盖 Element Plus 变量）。  
- 交付说明：列出修改的文件与 **为何不影响接口与 WebSocket**；若有布局类改动，说明如何验证了 Dashboard / 巡检 / 助手三页。

**禁止事项**  
- 不要「顺手」重构 script、重命名变量、改 API 模块、改 Pinia store（若有）、升级 major 依赖。  
- 不要用 `display: none` 隐藏仍应承担交互或无障碍角色的控件。

---

## 验证清单（改完后自测）

- [ ] `/` 环境监测：图表加载、缩放按钮、主区域无异常双滚动条  
- [ ] `/inspection` 巡检与遥控：视频区高度正常、控制按钮可点  
- [ ] `/agent` 智能助手：会话切换、发送、流式输出、消息区单独滚动  
- [ ] `/alarms`、`/settings`：列表与表单布局正常  
- [ ] 顶栏 WebSocket 状态显示与告警通知仍会出现（若后端有推送）

---

## 文件位置说明

本文件路径：`web-frontend/FRONTEND_STYLE_PROMPT.md`，与前端源码同目录，便于版本管理与检索。
