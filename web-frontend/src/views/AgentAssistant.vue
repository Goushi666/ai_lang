<template>
  <div class="agent-page app-main-route--agent">
    <div class="agent-header">
      <div class="agent-header-row">
        <h2 class="page-title">智能助手</h2>
        <el-radio-group v-model="chatMode" size="small" class="mode-switch" :disabled="sending">
          <el-radio-button value="general">通用对话</el-radio-button>
          <el-radio-button value="rag">知识问答</el-radio-button>
        </el-radio-group>
      </div>
      <p v-if="health?.message" class="page-sub">{{ health.message }}</p>
    </div>

    <div class="agent-body">
      <aside class="conv-sidebar">
        <el-button type="primary" class="new-chat-btn" :disabled="sending" @click="newConversation">
          + 新对话
        </el-button>
        <div class="conv-list">
          <div
            v-for="c in sortedConversations"
            :key="c.id"
            :class="['conv-item', { active: c.id === activeId }]"
            @click="selectConversation(c.id)"
          >
            <span class="conv-title" :title="c.title">{{ c.title }}</span>
            <el-icon v-if="conversations.length > 1" class="conv-del" @click.stop="deleteConversation(c.id)">
              <Close />
            </el-icon>
          </div>
        </div>
      </aside>

      <div class="chat-main">
        <div class="chat-panel">
          <div ref="listRef" class="messages">
            <div
              v-for="(m, i) in messages"
              :key="m._uid || `row-${i}`"
              :class="['msg-row', m.role === 'user' ? 'is-user' : 'is-assistant']"
            >
              <template v-if="m.role === 'assistant'">
                <div class="avatar assistant-av">
                  <el-icon><ChatDotRound /></el-icon>
                </div>
                <div class="msg-stack">
                  <details v-if="m.reasoning && !m.streaming" class="think-block" open>
                    <summary class="think-head">已深度思考</summary>
                    <div class="think-quote">{{ m.reasoning }}</div>
                  </details>
                  <div :class="['answer-block', { 'is-streaming': m.streaming }]">
                    <!-- 流式阶段同步渲染 Markdown（与结束后同一套 markdown-it + DOMPurify） -->
                    <div v-if="m.streaming" class="md-body streaming-stack streaming-md">
                      <template v-if="m.reasoning">
                        <div class="stream-phase-row">
                          <span class="stream-phase-label">思考</span>
                        </div>
                        <div class="stream-md stream-md--reason" v-html="renderMd(m.reasoning)" />
                      </template>
                      <template v-if="m.content">
                        <div v-if="m.reasoning" class="stream-phase-row stream-phase-row--gap">
                          <span class="stream-phase-label">回答</span>
                        </div>
                        <div class="stream-md stream-md--answer" v-html="renderMd(m.content)" />
                      </template>
                      <span class="stream-caret stream-caret--md" aria-hidden="true">▍</span>
                    </div>
                    <div v-else class="md-body" v-html="renderMd(m.content)" />
                  </div>
                  <div v-if="m.exports?.length" class="export-bar">
                    <span class="export-bar-label">导出文件</span>
                    <a
                      v-for="(exp, ei) in m.exports"
                      :key="`${exp.filename}-${ei}`"
                      class="export-link"
                      :href="exportFullHref(exp)"
                      :download="exp.filename"
                    >
                      保存到电脑（{{ exp.filename }}）
                    </a>
                  </div>
                </div>
              </template>
              <template v-else>
                <div class="msg-stack user-stack">
                  <div class="user-bubble md-body" v-html="renderMd(m.content)" />
                </div>
                <div class="avatar user-av">
                  <el-icon><User /></el-icon>
                </div>
              </template>
            </div>
          </div>

          <div class="composer">
            <div v-if="clarificationOptions.length" class="clarify-bar">
              <span class="clarify-label">快捷补充</span>
              <el-button
                v-for="(opt, idx) in clarificationOptions"
                :key="idx"
                type="primary"
                plain
                size="small"
                class="clarify-chip"
                @click="applyClarifyOption(opt)"
              >
                {{ opt.label }}
              </el-button>
            </div>
            <div class="input-row">
              <el-input
                v-model="input"
                type="textarea"
                :rows="3"
                placeholder="输入问题，例如：当前温度与告警情况如何？"
                @keydown.enter.exact.prevent="send"
              />
              <el-button type="primary" :loading="sending" :disabled="!health?.enabled" @click="send">
                发送
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, triggerRef, watch } from "vue";
import { ElMessage } from "element-plus";
import { ChatDotRound, Close, User } from "@element-plus/icons-vue";
import { agentApi, agentChatStream } from "../api/agent";
import { agentStreamDbg } from "../utils/agentStreamDebug";
import { renderMarkdown } from "../utils/markdown";

function renderMd(text) {
  try {
    return renderMarkdown(text == null ? "" : String(text));
  } catch {
    return "";
  }
}

/** Agent CSV：拼接 API 根路径，供 `<a download>` 触发系统「另存为」 */
function exportFullHref(exp) {
  const base = import.meta.env.VITE_API_BASE_URL || "";
  const p = exp?.download_path || "";
  if (!p) return "#";
  return `${base}${p}`;
}

/** 流式已累加的内容与 done 终值合并：部分接口终态 reasoning/content 比 delta 链更短，避免覆盖变短 */
function mergeStreamedField(accumulated, doneVal) {
  const a = accumulated == null ? "" : String(accumulated);
  const d = doneVal == null || doneVal === "" ? "" : String(doneVal);
  if (!d) return a;
  if (!a) return d;
  return d.length >= a.length ? d : a;
}

const STORAGE_KEY = "ai_lang_agent_conversations_v1";

const DEFAULT_GREETING =
  "你好，我是井场智能助手。你可以问我环境数据、告警记录、异常分析等问题。";

function defaultMessages() {
  return [{ role: "assistant", content: DEFAULT_GREETING, _uid: `m-${makeId()}` }];
}

function ensureMessageIds(msgs) {
  if (!Array.isArray(msgs)) return;
  msgs.forEach((m, i) => {
    if (m && m._uid == null) m._uid = `m-${i}-${makeId()}`;
  });
}

function makeId() {
  return typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : `c-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function loadPersisted() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data || !Array.isArray(data.conversations) || !data.activeId) return null;
    return data;
  } catch {
    return null;
  }
}

function persistState(conversations, activeId, mode) {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ conversations, activeId, chatMode: mode }),
    );
  } catch {
    /* quota */
  }
}

const health = ref(null);
const conversations = ref([]);
const activeId = ref("");
const chatMode = ref("general");
const input = ref("");
const sending = ref(false);
const listRef = ref(null);
const clarificationOptions = ref([]);

const messages = computed(() => {
  const c = conversations.value.find((x) => x.id === activeId.value);
  const list = c ? c.messages : defaultMessages();
  // 显式读嵌套字段，否则仅 return c.messages 时改 asst.content 不会失效本 computed
  for (const m of list) {
    if (m?.role === "assistant") {
      void m.reasoning;
      void m.content;
      void m.streaming;
      void m.exports;
    } else {
      void m.content;
    }
  }
  return list;
});

const sortedConversations = computed(() =>
  [...conversations.value].sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0)),
);

function touchActive() {
  const c = conversations.value.find((x) => x.id === activeId.value);
  if (c) c.updatedAt = Date.now();
}

/** 替换数组引用，确保侧栏标题等嵌套字段变更能触发列表重绘 */
function bumpConversationsRef() {
  conversations.value = conversations.value.slice();
}

/** 服务端首轮对答归纳的会话标题（SSE done / chat 响应） */
function applyConversationTitle(conv, title) {
  if (!conv || !title || typeof title !== "string") return;
  const t = title.trim();
  if (!t) return;
  conv.title = t.length > 28 ? `${t.slice(0, 28)}…` : t;
  bumpConversationsRef();
}

/** 服务端未返回标题时，用第一轮用户消息作侧栏名称 */
function deriveTitleFromFirstUserTurn(conv) {
  if (!conv?.messages?.length) return;
  const cur = String(conv.title || "").trim();
  if (cur && cur !== "新对话") return;
  const u = conv.messages.find((m) => m.role === "user" && String(m.content || "").trim());
  if (!u) return;
  let s = String(u.content).trim().replace(/\s+/g, " ");
  if (!s) return;
  conv.title = s.length > 28 ? `${s.slice(0, 28)}…` : s;
  bumpConversationsRef();
}

function scrollMessagesToEnd(smooth) {
  const el = listRef.value;
  if (!el) return;
  const top = el.scrollHeight;
  if (smooth) {
    el.scrollTo({ top, behavior: "smooth" });
  } else {
    el.scrollTop = top;
  }
}

function scrollToBottom() {
  nextTick(() => scrollMessagesToEnd(true));
}

let scrollRaf = 0;
function scrollToBottomThrottled() {
  if (scrollRaf) return;
  scrollRaf = requestAnimationFrame(() => {
    scrollRaf = 0;
    scrollMessagesToEnd(false);
  });
}

async function applyClarifyOption(opt) {
  if (sending.value) return;
  // 只发送选项语义（value），由对话历史承载上文；勿与上一轮已拼接内容再拼接，否则会越点越长
  const text = String(opt.value ?? opt.label ?? "").trim();
  if (!text) return;
  input.value = text;
  clarificationOptions.value = [];
  await send();
}

async function loadHealth() {
  try {
    health.value = await agentApi.health();
  } catch {
    health.value = { enabled: false, message: "无法连接后端", stream_enabled: false };
  }
}

function initConversations() {
  const saved = loadPersisted();
  if (saved?.conversations?.length) {
    conversations.value = saved.conversations;
    conversations.value.forEach((cc) => {
      if (cc.localOnly === undefined) {
        cc.localOnly = String(cc.id).startsWith("local-");
      }
      ensureMessageIds(cc.messages);
    });
    activeId.value = saved.activeId;
    if (!conversations.value.some((x) => x.id === activeId.value) && conversations.value.length) {
      activeId.value = conversations.value[0].id;
    }
    if (saved.chatMode === "rag" || saved.chatMode === "general") {
      chatMode.value = saved.chatMode;
    }
    return;
  }
  const id = `local-${makeId()}`;
  conversations.value = [
    {
      id,
      title: "新对话",
      updatedAt: Date.now(),
      backendSessionId: null,
      localOnly: true,
      messages: defaultMessages(),
    },
  ];
  activeId.value = id;
  persistState(conversations.value, activeId.value, chatMode.value);
}

watch(chatMode, () => {
  persistState(conversations.value, activeId.value, chatMode.value);
});

function newConversation() {
  if (sending.value) return;
  clarificationOptions.value = [];
  const id = `local-${makeId()}`;
  conversations.value.unshift({
    id,
    title: "新对话",
    updatedAt: Date.now(),
    backendSessionId: null,
    localOnly: true,
    messages: defaultMessages(),
  });
  activeId.value = id;
  persistState(conversations.value, activeId.value, chatMode.value);
}

async function selectConversation(id) {
  if (sending.value || id === activeId.value) return;
  clarificationOptions.value = [];
  activeId.value = id;
  persistState(conversations.value, activeId.value, chatMode.value);
  const c = conversations.value.find((x) => x.id === id);
  if (c?.backendSessionId && !c.localOnly) {
    await loadMessagesForConversation(c);
  }
  scrollToBottom();
}

async function deleteConversation(id) {
  if (conversations.value.length <= 1) {
    ElMessage.info("至少保留一个对话");
    return;
  }
  const c = conversations.value.find((x) => x.id === id);
  if (c?.backendSessionId && !String(id).startsWith("local-")) {
    try {
      await agentApi.deleteSession(c.backendSessionId);
    } catch {
      /* 仍从列表移除 */
    }
  }
  const idx = conversations.value.findIndex((x) => x.id === id);
  if (idx < 0) return;
  conversations.value.splice(idx, 1);
  if (activeId.value === id && conversations.value.length) {
    activeId.value = conversations.value[0].id;
  }
  clarificationOptions.value = [];
  persistState(conversations.value, activeId.value, chatMode.value);
}

function applyServerSessionId(c, sessionId) {
  if (!sessionId || !c) return;
  if (c.localOnly) {
    const oldId = c.id;
    c.id = sessionId;
    c.backendSessionId = sessionId;
    c.localOnly = false;
    if (activeId.value === oldId) activeId.value = sessionId;
  } else {
    c.backendSessionId = sessionId;
  }
}

async function loadMessagesForConversation(c) {
  if (!c?.backendSessionId) return;
  try {
    const data = await agentApi.getSession(c.backendSessionId);
    c.messages = (data.messages || []).map((m, idx) => ({
      role: m.role,
      content: m.content || "",
      reasoning: m.reasoning || "",
      _uid: `m-${idx}-${makeId()}`,
    }));
    if (data.mode === "rag" || data.mode === "general") {
      chatMode.value = data.mode;
    }
    persistState(conversations.value, activeId.value, chatMode.value);
  } catch {
    ElMessage.warning("无法加载该会话消息");
  }
}

async function initFromServer() {
  try {
    const res = await agentApi.listSessions(80);
    const items = res.items || [];
    if (!items.length) {
      initConversations();
      return;
    }
    conversations.value = items.map((it) => ({
      id: it.session_id,
      title: it.title || "新对话",
      updatedAt: tsToMs(it.updated_at),
      backendSessionId: it.session_id,
      localOnly: false,
      messages: [],
    }));
    if (conversations.value.length) {
      activeId.value = conversations.value[0].id;
      await loadMessagesForConversation(conversations.value[0]);
    }
  } catch {
    initConversations();
  }
}


function tsToMs(t) {
  if (t == null) return Date.now();
  const n = Number(t);
  return n > 1e12 ? n : n * 1000;
}

async function send() {
  const text = input.value.trim();
  if (!text) return;
  if (!health.value?.enabled) {
    ElMessage.warning("Agent 未启用或不可用");
    return;
  }

  const c = conversations.value.find((x) => x.id === activeId.value);
  if (!c) return;

  c.messages = [...c.messages, { role: "user", content: text, _uid: `m-${makeId()}` }];
  input.value = "";
  sending.value = true;
  clarificationOptions.value = [];

  const asst = {
    role: "assistant",
    content: "",
    reasoning: "",
    streaming: true,
    exports: [],
    _uid: `m-${makeId()}`,
  };
  c.messages = [...c.messages, asst];

  touchActive();
  persistState(conversations.value, activeId.value, chatMode.value);
  scrollToBottom();

  const toApiMessages = () =>
    c.messages.slice(0, -1).map((m) => {
      const item = { role: m.role, content: m.content || "" };
      if (m.role === "assistant" && m.reasoning) {
        item.reasoning = m.reasoning;
      }
      return item;
    });

  const useStream = health.value?.stream_enabled !== false;

  try {
    if (useStream) {
      await agentChatStream(
        {
          messages: toApiMessages(),
          mode: chatMode.value,
          session_id: c.backendSessionId || undefined,
        },
        (ev) => {
        if (ev.type === "export_ready") {
          if (!Array.isArray(asst.exports)) asst.exports = [];
          asst.exports.push({
            filename: ev.filename || "export.csv",
            download_path: ev.download_path || "",
          });
          triggerRef(conversations);
          scrollToBottomThrottled();
          return;
        }
        if (ev.type === "clarification") {
          asst.content = ev.question || "";
          asst.reasoning = "";
          asst.streaming = false;
          if (ev.session_id) applyServerSessionId(c, ev.session_id);
          clarificationOptions.value = (ev.options || []).map((o) => ({
            label: o.label,
            value: o.value,
          }));
          deriveTitleFromFirstUserTurn(c);
          touchActive();
          persistState(conversations.value, activeId.value, chatMode.value);
          return;
        }
        if (ev.type === "delta") {
          const dr = ev.reasoning;
          const dc = ev.content;
          if (dr != null && dr !== "") asst.reasoning = (asst.reasoning || "") + String(dr);
          if (dc != null && dc !== "") asst.content = (asst.content || "") + String(dc);
          agentStreamDbg("vue-delta", {
            dR: String(dr ?? "").length,
            dC: String(dc ?? "").length,
            totalR: (asst.reasoning || "").length,
            totalC: (asst.content || "").length,
          });
          triggerRef(conversations);
          scrollToBottomThrottled();
          return;
        }
        if (ev.type === "done") {
          asst.streaming = false;
          if (ev.session_id) applyServerSessionId(c, ev.session_id);
          asst.reasoning = mergeStreamedField(asst.reasoning, ev.reasoning);
          asst.content = mergeStreamedField(asst.content, ev.content);
          if (ev.conversation_title != null && String(ev.conversation_title).trim() !== "") {
            applyConversationTitle(c, ev.conversation_title);
          } else {
            deriveTitleFromFirstUserTurn(c);
          }
          touchActive();
          persistState(conversations.value, activeId.value, chatMode.value);
        }
        },
      );
    } else {
      const res = await agentApi.chat({
        messages: toApiMessages(),
        mode: chatMode.value,
        session_id: c.backendSessionId || undefined,
      });
      if (res.session_id) applyServerSessionId(c, res.session_id);
      asst.content = res.content || "";
      asst.reasoning = res.reasoning || "";
      asst.streaming = false;
      if (Array.isArray(res.exports) && res.exports.length) {
        asst.exports = res.exports.map((e) => ({
          filename: e.filename || "export.csv",
          download_path: e.download_path || "",
        }));
      }
      if (res.conversation_title != null && String(res.conversation_title).trim() !== "") {
        applyConversationTitle(c, res.conversation_title);
      } else {
        deriveTitleFromFirstUserTurn(c);
      }
      if (res.clarification?.options?.length) {
        clarificationOptions.value = res.clarification.options;
      } else {
        clarificationOptions.value = [];
      }
      touchActive();
      persistState(conversations.value, activeId.value, chatMode.value);
    }

    scrollToBottom();
  } catch (e) {
    ElMessage.error(e?.message || e?.response?.data?.detail || "请求失败");
    c.messages = c.messages.slice(0, -2);
    persistState(conversations.value, activeId.value, chatMode.value);
  } finally {
    asst.streaming = false;
    delete asst.streaming;
    sending.value = false;
  }
}

onMounted(async () => {
  await loadHealth();
  await initFromServer();
});
</script>

<style scoped>
.agent-header {
  flex-shrink: 0;
  margin-bottom: var(--ds-space-3);
}
.agent-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ds-space-3);
  flex-wrap: wrap;
}
.page-title {
  margin: 0;
  padding-left: 10px;
  border-left: 4px solid #3b82f6;
  font-size: 20px;
  font-weight: 800;
  color: var(--ds-text-primary);
  letter-spacing: 0.02em;
}
.mode-switch {
  flex-shrink: 0;
}
.page-sub {
  margin: var(--ds-space-2) 0 0 0;
  font-size: var(--ds-text-sm);
  color: var(--ds-text-secondary);
  line-height: 1.4;
}

.agent-body {
  flex: 1;
  min-height: 0;
  display: flex;
  gap: 0;
  border-radius: 16px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(6px);
  box-shadow: 0 16px 30px rgba(15, 23, 42, 0.08);
  border: 1px solid var(--ds-border-light);
}

.conv-sidebar {
  width: 240px;
  flex-shrink: 0;
  border-right: 1px solid var(--ds-border);
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.75), rgba(248, 250, 252, 0.92));
  padding: var(--ds-space-3);
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-3);
}
.new-chat-btn {
  width: 100%;
  border-radius: 10px !important;
  font-weight: 600;
}
.conv-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.conv-item {
  display: flex;
  align-items: center;
  gap: var(--ds-space-2);
  padding: var(--ds-space-2) var(--ds-space-3);
  border-radius: var(--ds-radius-sm);
  cursor: pointer;
  font-size: var(--ds-text-base);
  color: var(--ds-text-secondary);
  border: 1px solid transparent;
  transition: all var(--ds-transition);
}
.conv-item:hover {
  background: var(--ds-primary-bg);
  color: var(--ds-text-primary);
}
.conv-item.active {
  background: linear-gradient(135deg, rgba(219, 234, 254, 0.85), rgba(191, 219, 254, 0.7));
  border-color: rgba(59, 130, 246, 0.2);
  color: var(--ds-primary);
  font-weight: 500;
  box-shadow: 0 4px 10px rgba(59, 130, 246, 0.15);
}
.conv-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conv-del {
  flex-shrink: 0;
  font-size: var(--ds-text-base);
  color: var(--ds-text-muted);
  padding: 2px;
  border-radius: var(--ds-radius-sm);
  transition: all var(--ds-transition);
}
.conv-del:hover {
  color: var(--ds-danger);
  background: var(--ds-danger-light);
}

.chat-main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}
.chat-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--ds-bg-card);
}
.messages {
  flex: 1;
  min-height: 0;
  overflow-y: scroll;
  overflow-x: hidden;
  scrollbar-gutter: stable;
  padding: var(--ds-space-5) var(--ds-space-5) var(--ds-space-2);
}
.composer {
  flex-shrink: 0;
  border-top: 1px solid var(--ds-border);
  padding: var(--ds-space-3) var(--ds-space-4) var(--ds-space-4);
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.9), rgba(241, 245, 249, 0.9));
}

.msg-row {
  display: flex;
  gap: var(--ds-space-3);
  margin-bottom: var(--ds-space-4);
  align-items: flex-start;
}
.msg-row.is-user {
  justify-content: flex-end;
}
.avatar {
  width: 34px;
  height: 34px;
  border-radius: var(--ds-radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 16px;
}
.assistant-av {
  background: linear-gradient(135deg, #d1fae5, #a7f3d0);
  color: #059669;
  border: none;
}
.user-av {
  background: linear-gradient(135deg, #dbeafe, #bfdbfe);
  color: var(--ds-primary);
  border: none;
}
.msg-stack {
  max-width: min(720px, calc(100% - 48px));
  min-width: 0;
}
.user-stack {
  display: flex;
  justify-content: flex-end;
}
.user-bubble {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #ffffff;
  padding: var(--ds-space-3) var(--ds-space-4);
  border-radius: var(--ds-radius-lg) var(--ds-radius-lg) var(--ds-space-1) var(--ds-radius-lg);
  font-size: var(--ds-text-base);
  line-height: 1.55;
  max-width: 100%;
}
.think-block {
  margin-bottom: var(--ds-space-3);
}
.think-head {
  cursor: pointer;
  font-size: var(--ds-text-sm);
  color: var(--ds-text-muted);
  list-style: none;
  user-select: none;
  margin-bottom: var(--ds-space-2);
}
.think-head::-webkit-details-marker {
  display: none;
}
.think-head::after {
  content: " \25BE";
  font-size: var(--ds-text-xs);
}
.think-block:not([open]) .think-head::after {
  content: " \25B8";
}
.think-quote {
  margin: 0;
  padding: var(--ds-space-1) 0 var(--ds-space-1) var(--ds-space-3);
  border-left: 3px solid var(--ds-border);
  font-size: var(--ds-text-sm);
  line-height: 1.6;
  color: var(--ds-text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
}
.answer-block {
  padding: var(--ds-space-1) 0 var(--ds-space-2);
  color: var(--ds-text-primary);
}
.export-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--ds-space-2) var(--ds-space-3);
  margin-top: var(--ds-space-3);
  padding: var(--ds-space-3);
  background: var(--ds-primary-bg);
  border: 1px solid var(--ds-primary-lighter);
  border-radius: var(--ds-radius-sm);
  font-size: var(--ds-text-sm);
}
.export-bar-label {
  color: var(--ds-text-secondary);
  flex-shrink: 0;
}
.export-link {
  color: var(--ds-primary);
  text-decoration: none;
  font-weight: 500;
}
.export-link:hover {
  text-decoration: underline;
}
.streaming-stack {
  font-size: var(--ds-text-base);
  line-height: 1.65;
  word-break: break-word;
}
.streaming-md .stream-phase-row {
  margin-bottom: var(--ds-space-1);
}
.streaming-md .stream-phase-row--gap {
  margin-top: var(--ds-space-3);
}
.stream-md--reason :deep(p:last-child),
.stream-md--answer :deep(p:last-child) {
  margin-bottom: 0;
}
.stream-md--reason :deep(p) {
  color: var(--ds-text-secondary);
}
.stream-md--reason :deep(code) {
  color: var(--ds-text-secondary);
}
.stream-phase-label {
  display: inline;
  margin-right: var(--ds-space-2);
  font-size: var(--ds-text-sm);
  font-weight: 600;
  color: var(--ds-text-muted);
  user-select: none;
}
.stream-caret {
  display: inline;
  margin-left: 1px;
  color: var(--ds-primary);
  font-weight: 300;
  vertical-align: baseline;
  animation: streamCaretBlink 1s step-end infinite;
}
.stream-caret--md {
  display: inline-block;
  margin-top: 2px;
  vertical-align: text-bottom;
}
@keyframes streamCaretBlink {
  50% {
    opacity: 0;
  }
}
.md-body {
  font-size: var(--ds-text-base);
  line-height: 1.65;
  word-break: break-word;
}
.streaming-plain {
  white-space: pre-wrap;
  word-break: break-word;
}
.md-body :deep(p) {
  margin: 0 0 0.6em;
}
.md-body :deep(p:last-child) {
  margin-bottom: 0;
}
.md-body :deep(code) {
  background: var(--ds-bg-inset);
  padding: 1px 5px;
  border-radius: var(--ds-radius-sm);
  font-size: 0.9em;
  font-family: var(--ds-font-mono);
}
.md-body :deep(pre) {
  background: var(--ds-bg-inset);
  padding: var(--ds-space-3);
  border-radius: var(--ds-radius-sm);
  overflow-x: auto;
  margin: 0.5em 0;
  border: 1px solid var(--ds-border-light);
}
.md-body :deep(pre code) {
  background: none;
  padding: 0;
}
.md-body :deep(ul),
.md-body :deep(ol) {
  margin: 0.4em 0;
  padding-left: 1.4em;
}
.user-bubble.md-body :deep(p) {
  margin: 0;
}
.user-bubble.md-body :deep(code) {
  background: rgba(255, 255, 255, 0.2);
  color: #ffffff;
}

.clarify-bar {
  margin-bottom: var(--ds-space-3);
  padding: var(--ds-space-3);
  border-radius: var(--ds-radius-sm);
  background: var(--ds-primary-bg);
  border: 1px solid var(--ds-primary-lighter);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--ds-space-2);
}
.clarify-label {
  font-size: var(--ds-text-sm);
  font-weight: 600;
  color: var(--ds-text-primary);
  margin-right: var(--ds-space-1);
}
.clarify-chip {
  font-weight: 500;
  color: var(--ds-primary-dark) !important;
  border-color: rgba(59, 130, 246, 0.3) !important;
  background: var(--ds-bg-card) !important;
  border-radius: 999px !important;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.1);
}
.clarify-chip:hover {
  color: var(--ds-primary) !important;
  border-color: var(--ds-primary) !important;
  background: var(--ds-primary-bg) !important;
}
.input-row {
  display: flex;
  gap: var(--ds-space-3);
  align-items: flex-end;
  flex-shrink: 0;
}
.input-row .el-input {
  flex: 1;
}
</style>
