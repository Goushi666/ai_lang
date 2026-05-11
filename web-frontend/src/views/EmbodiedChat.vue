<template>
  <div class="embodied-chat-root">
    <div
      v-show="!expanded"
      class="embodied-ball"
      :style="ballStyle"
      @pointerdown="onBallPointerDown"
    >
      <el-icon :size="24" color="#fff">
        <Monitor />
      </el-icon>
    </div>
    <transition name="embodied-fade">
      <div v-if="expanded" class="embodied-panel" :style="panelStyle">
        <div
          class="embodied-header embodied-header--drag"
          @pointerdown="onPanelHeaderPointerDown"
        >
          <span class="embodied-title">AI Control</span>
          <div class="embodied-header-actions" @pointerdown.stop>
            <button class="embodied-clear-btn" @click="clearMessages">
              <el-icon :size="14">
                <Delete />
              </el-icon>
            </button>
            <button class="embodied-close-btn" @click="expanded = false">
              <el-icon :size="16">
                <Close />
              </el-icon>
            </button>
          </div>
        </div>
        <div ref="msgListRef" class="embodied-messages">
          <div
            v-for="m in messages"
            :key="m._uid"
            :class="['embodied-msg', m.role === 'user' ? 'embodied-msg--user' : 'embodied-msg--assistant']"
          >
            <template v-if="m.role === 'assistant'">
              <div class="embodied-assistant-stack">
                <details
                  v-if="m.reasoning && !m.streaming"
                  class="embodied-think"
                  open
                >
                  <summary class="embodied-think-summary">已深度思考</summary>
                  <div class="embodied-think-body">{{ m.reasoning }}</div>
                </details>
                <div
                  :class="['embodied-msg-bubble', 'md-body', { 'is-streaming': m.streaming }]"
                >
                  <div
                    v-if="m.streaming"
                    class="streaming-stack streaming-md"
                  >
                    <template v-if="m.reasoning">
                      <div class="stream-phase-row">
                        <span class="stream-phase-label">思考</span>
                      </div>
                      <div
                        class="stream-md stream-md--reason"
                        v-html="renderMd(m.reasoning)"
                      />
                    </template>
                    <template v-if="m.content">
                      <div
                        v-if="m.reasoning"
                        class="stream-phase-row stream-phase-row--gap"
                      >
                        <span class="stream-phase-label">回答</span>
                      </div>
                      <div
                        class="stream-md stream-md--answer"
                        v-html="renderMd(m.content)"
                      />
                    </template>
                    <span class="stream-caret stream-caret--md" aria-hidden="true">▍</span>
                  </div>
                  <div v-else v-html="renderMd(m.content || '')" />
                </div>
                <div v-if="m.exports?.length" class="embodied-export-bar">
                  <span class="embodied-export-label">导出</span>
                  <a
                    v-for="(exp, ei) in m.exports"
                    :key="`${exp.filename}-${ei}`"
                    class="embodied-export-link"
                    :href="exportFullHref(exp)"
                    :download="exp.filename"
                  >
                    {{ exp.filename }}
                  </a>
                </div>
              </div>
            </template>
            <div v-else class="embodied-msg-bubble">{{ m.content }}</div>
          </div>
          <div v-if="sending" class="embodied-typing">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
        <div class="embodied-input-area">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="1"
            :autosize="{ minRows: 1, maxRows: 3 }"
            resize="none"
            @keydown.enter.exact.prevent="send"
          />
          <el-button
            type="primary"
            class="embodied-send-btn"
            :disabled="!inputText.trim() || sending"
            :icon="Promotion"
            @click="send"
          />
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onUnmounted, triggerRef } from "vue";
import { Monitor, Delete, Close, Promotion } from "@element-plus/icons-vue";
import { renderMarkdown } from "@/utils/markdown";
import { agentChatStream } from "@/api/agent";

const PANEL_W = 380;
const PANEL_H = 520;
const PANEL_MARGIN = 24;

const expanded = ref(false);
/** 展开面板位置（px）；null 表示尚未初始化，由 watch(expanded) 写入 */
const panelLeft = ref(null);
const panelTop = ref(null);

const panelStyle = computed(function () {
  if (!expanded.value || panelLeft.value === null || panelTop.value === null) {
    return {};
  }
  return {
    left: panelLeft.value + "px",
    top: panelTop.value + "px",
    right: "auto",
    bottom: "auto",
  };
});

function initPanelPosition() {
  if (ballX.value !== null && ballY.value !== null) {
    var left = ballX.value + 48 - PANEL_W;
    var top = ballY.value - PANEL_H - 8;
    panelLeft.value = Math.max(
      0,
      Math.min(window.innerWidth - PANEL_W, left)
    );
    panelTop.value = Math.max(
      0,
      Math.min(window.innerHeight - PANEL_H, top)
    );
  } else {
    panelLeft.value = window.innerWidth - PANEL_W - PANEL_MARGIN;
    panelTop.value = window.innerHeight - PANEL_H - PANEL_MARGIN;
  }
}

watch(expanded, function (v) {
  if (v && (panelLeft.value === null || panelTop.value === null)) {
    initPanelPosition();
  }
});

var panelDragging = false;
var panelDragStartX = 0;
var panelDragStartY = 0;
var panelStartLeft = 0;
var panelStartTop = 0;
/** setPointerCapture 所在元素，用于 pointerup 时 release */
var panelCaptureEl = null;
var panelCaptureId = null;

function onPanelPointerMove(e) {
  if (!panelDragging) return;
  var dx = e.clientX - panelDragStartX;
  var dy = e.clientY - panelDragStartY;
  var nl = panelStartLeft + dx;
  var nt = panelStartTop + dy;
  panelLeft.value = Math.max(
    0,
    Math.min(window.innerWidth - PANEL_W, nl)
  );
  panelTop.value = Math.max(
    0,
    Math.min(window.innerHeight - PANEL_H, nt)
  );
}

function onPanelPointerUp(e) {
  if (!panelDragging) return;
  panelDragging = false;
  window.removeEventListener("pointermove", onPanelPointerMove);
  window.removeEventListener("pointerup", onPanelPointerUp);
  if (panelCaptureEl && panelCaptureId != null) {
    try {
      panelCaptureEl.releasePointerCapture(panelCaptureId);
    } catch (_) {
      /* ignore */
    }
  }
  panelCaptureEl = null;
  panelCaptureId = null;
}

function onPanelHeaderPointerDown(e) {
  if (e.button !== undefined && e.button !== 0) return;
  if (!expanded.value) return;
  if (panelLeft.value === null || panelTop.value === null) {
    initPanelPosition();
  }
  panelDragging = true;
  panelDragStartX = e.clientX;
  panelDragStartY = e.clientY;
  panelStartLeft = panelLeft.value;
  panelStartTop = panelTop.value;
  panelCaptureEl = e.currentTarget;
  panelCaptureId = e.pointerId;
  panelCaptureEl.setPointerCapture(e.pointerId);
  window.addEventListener("pointermove", onPanelPointerMove);
  window.addEventListener("pointerup", onPanelPointerUp);
}
const inputText = ref("");
const sending = ref(false);
const msgListRef = ref(null);
const sessionId = ref(null);
let abortCtrl = null;
let uidSeq = 0;

const WELCOME_TEXT = "你好，我可以帮你控制机械臂和巡检车。";
const messages = ref([
  {
    role: "assistant",
    content: WELCOME_TEXT,
    reasoning: "",
    streaming: false,
    exports: [],
    _uid: ++uidSeq,
  },
]);

function renderMd(text) {
  return renderMarkdown(text || "");
}

function exportFullHref(exp) {
  const base = import.meta.env.VITE_API_BASE_URL || "";
  const p = exp?.download_path || "";
  if (!p) return "#";
  return `${base}${p}`;
}

/** 与智能助手页一致：done 终态可能比 delta 链短，避免误覆盖变短 */
function mergeStreamedField(accumulated, doneVal) {
  const a = accumulated == null ? "" : String(accumulated);
  const d = doneVal == null || doneVal === "" ? "" : String(doneVal);
  if (!d) return a;
  if (!a) return d;
  return d.length >= a.length ? d : a;
}

function scrollBottom() {
  nextTick(function () {
    var el = msgListRef.value;
    if (el) el.scrollTop = el.scrollHeight;
  });
}

function clearMessages() {
  if (sending.value) return;
  messages.value = [
    {
      role: "assistant",
      content: WELCOME_TEXT,
      reasoning: "",
      streaming: false,
      exports: [],
      _uid: ++uidSeq,
    },
  ];
  sessionId.value = null;
}

function toApiMessages() {
  return messages.value
    .filter(function (m) {
      return (
        m.role === "user" ||
        (m.role === "assistant" && m.content && m.content !== WELCOME_TEXT)
      );
    })
    .map(function (m) {
      return { role: m.role, content: m.content, reasoning: m.reasoning || null };
    });
}

async function send() {
  var text = inputText.value.trim();
  if (!text || sending.value) return;
  inputText.value = "";
  messages.value.push({ role: "user", content: text, _uid: ++uidSeq });
  scrollBottom();

  var assistantMsg = {
    role: "assistant",
    content: "",
    reasoning: "",
    streaming: true,
    exports: [],
    _uid: ++uidSeq,
  };
  messages.value.push(assistantMsg);
  sending.value = true;

  abortCtrl = new AbortController();
  try {
    await agentChatStream(
      {
        messages: toApiMessages(),
        mode: "vehicle",
        session_id: sessionId.value,
      },
      function (ev) {
        if (ev.type === "export_ready") {
          if (!Array.isArray(assistantMsg.exports)) assistantMsg.exports = [];
          assistantMsg.exports.push({
            filename: ev.filename || "export.csv",
            download_path: ev.download_path || "",
          });
          triggerRef(messages);
          scrollBottom();
          return;
        }
        if (ev.type === "delta") {
          if (ev.content) assistantMsg.content += String(ev.content);
          if (ev.reasoning) assistantMsg.reasoning += String(ev.reasoning);
          triggerRef(messages);
          scrollBottom();
          return;
        }
        if (ev.type === "done") {
          assistantMsg.streaming = false;
          if (ev.session_id) sessionId.value = ev.session_id;
          assistantMsg.reasoning = mergeStreamedField(
            assistantMsg.reasoning,
            ev.reasoning
          );
          assistantMsg.content = mergeStreamedField(
            assistantMsg.content,
            ev.content
          );
          triggerRef(messages);
          scrollBottom();
        }
      },
      abortCtrl.signal
    );
  } catch (e) {
    if (e.name !== "AbortError") {
      assistantMsg.content =
        assistantMsg.content || "请求失败: " + e.message;
      assistantMsg.streaming = false;
    }
  } finally {
    sending.value = false;
    assistantMsg.streaming = false;
    triggerRef(messages);
    abortCtrl = null;
    scrollBottom();
  }
}

var ballX = ref(null);
var ballY = ref(null);
var ballStyle = ref({});
var dragging = false;
var dragMoved = false;
var dragStartX = 0;
var dragStartY = 0;
var ballStartX = 0;
var ballStartY = 0;

function updateBallStyle() {
  if (ballX.value !== null && ballY.value !== null) {
    ballStyle.value = {
      left: ballX.value + "px",
      top: ballY.value + "px",
      right: "auto",
      bottom: "auto",
    };
  } else {
    ballStyle.value = {};
  }
}

function onBallPointerDown(e) {
  dragging = true;
  dragMoved = false;
  dragStartX = e.clientX;
  dragStartY = e.clientY;
  var rect = e.currentTarget.getBoundingClientRect();
  ballStartX = rect.left;
  ballStartY = rect.top;
  e.currentTarget.setPointerCapture(e.pointerId);
  e.currentTarget.addEventListener("pointermove", onBallPointerMove);
  e.currentTarget.addEventListener("pointerup", onBallPointerUp);
}

function onBallPointerMove(e) {
  if (!dragging) return;
  var dx = e.clientX - dragStartX;
  var dy = e.clientY - dragStartY;
  if (Math.abs(dx) > 3 || Math.abs(dy) > 3) dragMoved = true;
  ballX.value = Math.max(0, Math.min(window.innerWidth - 52, ballStartX + dx));
  ballY.value = Math.max(0, Math.min(window.innerHeight - 52, ballStartY + dy));
  updateBallStyle();
}

function onBallPointerUp(e) {
  dragging = false;
  e.currentTarget.removeEventListener("pointermove", onBallPointerMove);
  e.currentTarget.removeEventListener("pointerup", onBallPointerUp);
  if (!dragMoved) expanded.value = true;
}

onUnmounted(function () {
  if (abortCtrl) abortCtrl.abort();
  window.removeEventListener("pointermove", onPanelPointerMove);
  window.removeEventListener("pointerup", onPanelPointerUp);
});
</script>
<!-- STYLE_PLACEHOLDER -->
<style scoped>
.embodied-chat-root {
  position: fixed;
  z-index: 2000;
  pointer-events: none;
  inset: 0;
}
.embodied-ball {
  pointer-events: auto;
  position: fixed;
  right: 24px;
  bottom: 24px;
  width: 48px;
  height: 48px;
  border-radius: var(--ds-radius-full);
  background: linear-gradient(135deg, var(--ds-primary) 0%, var(--ds-primary-active) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: var(--ds-shadow-md);
  transition:
    box-shadow var(--ds-transition) var(--ds-ease-out-expo),
    transform var(--ds-transition) var(--ds-ease-spring);
  user-select: none;
  touch-action: none;
}
.embodied-ball:hover {
  box-shadow: var(--ds-shadow-lg);
  transform: scale(1.05);
}
.embodied-panel {
  pointer-events: auto;
  position: fixed;
  right: 24px;
  bottom: 24px;
  width: 380px;
  height: 520px;
  border-radius: var(--ds-radius-xl);
  background: var(--ds-bg-elevated);
  box-shadow: var(--ds-shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--ds-border);
}
.embodied-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--ds-space-3) var(--ds-space-3);
  background: linear-gradient(135deg, var(--ds-primary) 0%, var(--ds-primary-active) 100%);
  color: #fff;
}
.embodied-header--drag {
  cursor: grab;
  touch-action: none;
  user-select: none;
}
.embodied-header--drag:active {
  cursor: grabbing;
}
.embodied-title {
  font-family: var(--ds-font-display);
  font-size: 17px;
  font-weight: 500;
  letter-spacing: -0.02em;
}
.embodied-header-actions {
  display: flex;
  align-items: center;
  gap: var(--ds-space-2);
}
/* STYLE_CHUNK_2 */
.embodied-clear-btn,
.embodied-close-btn {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.75);
  cursor: pointer;
  padding: var(--ds-space-1);
  border-radius: var(--ds-radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--ds-transition), color var(--ds-transition);
}
.embodied-clear-btn:hover,
.embodied-close-btn:hover {
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
}
.embodied-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--ds-space-3) var(--ds-space-3);
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-3);
  background: var(--ds-bg-page);
}
.embodied-msg {
  display: flex;
}
.embodied-msg--user {
  justify-content: flex-end;
}
.embodied-msg--assistant {
  justify-content: flex-start;
}
.embodied-assistant-stack {
  max-width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-2);
}
.embodied-think {
  max-width: 85%;
  padding: var(--ds-space-2);
  border-radius: var(--ds-radius-sm);
  background: var(--ds-bg-soft);
  border: 1px solid var(--ds-border-light);
  font-size: var(--ds-text-xs);
  color: var(--ds-text-secondary);
}
.embodied-think-summary {
  cursor: pointer;
  font-weight: 600;
  color: var(--ds-text-primary);
}
.embodied-think-body {
  margin-top: var(--ds-space-1);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 120px;
  overflow-y: auto;
}
.embodied-export-bar {
  max-width: 85%;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--ds-space-2);
  padding: var(--ds-space-2);
  font-size: var(--ds-text-xs);
  background: var(--ds-primary-bg);
  border-radius: var(--ds-radius-sm);
  border: 1px solid var(--ds-primary-lighter);
}
.embodied-export-label {
  color: var(--ds-text-secondary);
  flex-shrink: 0;
}
.embodied-export-link {
  color: var(--ds-primary);
  text-decoration: none;
  font-weight: 500;
}
.embodied-export-link:hover {
  text-decoration: underline;
}
.embodied-msg-bubble {
  max-width: 85%;
  padding: var(--ds-space-2) var(--ds-space-3);
  border-radius: var(--ds-radius-md);
  font-size: var(--ds-text-sm);
  line-height: 1.55;
  word-break: break-word;
}
.embodied-msg--user .embodied-msg-bubble {
  background: linear-gradient(135deg, var(--ds-primary) 0%, var(--ds-primary-active) 100%);
  color: #fff;
  border-bottom-right-radius: 3px;
}
.embodied-msg--assistant .embodied-msg-bubble {
  background: var(--doc-surface-card);
  color: var(--doc-body);
  border: 1px solid var(--doc-hairline);
  border-left: 3px solid rgba(93, 184, 166, 0.45);
  border-bottom-left-radius: 3px;
  box-shadow: none;
}
.embodied-msg--assistant .embodied-msg-bubble.is-streaming {
  min-height: 2.5em;
}
.streaming-stack {
  font-size: var(--ds-text-sm);
  line-height: 1.55;
  word-break: break-word;
}
.streaming-md .stream-phase-row {
  margin-bottom: var(--ds-space-1);
}
.streaming-md .stream-phase-row--gap {
  margin-top: var(--ds-space-2);
}
.stream-md--reason :deep(p:last-child),
.stream-md--answer :deep(p:last-child) {
  margin-bottom: 0;
}
.stream-phase-label {
  display: inline;
  margin-right: var(--ds-space-2);
  font-size: var(--ds-text-xs);
  font-weight: 600;
  user-select: none;
  color: var(--ds-text-secondary);
}
.stream-caret {
  display: inline;
  margin-left: 1px;
  font-weight: 300;
  vertical-align: baseline;
  animation: embodied-caret-blink 1s step-end infinite;
}
.stream-caret--md {
  display: inline-block;
  margin-top: 2px;
  vertical-align: text-bottom;
}
@keyframes embodied-caret-blink {
  50% {
    opacity: 0;
  }
}
.embodied-typing {
  display: flex;
  gap: var(--ds-space-1);
  padding: var(--ds-space-1) 0;
}
.embodied-typing span {
  width: 6px;
  height: 6px;
  border-radius: var(--ds-radius-full);
  background: var(--ds-primary);
  animation: embodied-bounce 1.2s infinite;
}
.embodied-typing span:nth-child(2) { animation-delay: 0.15s; }
.embodied-typing span:nth-child(3) { animation-delay: 0.3s; }
@keyframes embodied-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-5px); opacity: 1; }
}
.embodied-input-area {
  flex-shrink: 0;
  display: flex;
  align-items: flex-end;
  gap: var(--ds-space-2);
  padding: var(--ds-space-3) var(--ds-space-3);
  border-top: 1px solid var(--ds-border-light);
  background: var(--ds-bg-inset);
}
.embodied-input-area :deep(.el-textarea__inner) {
  border-radius: var(--ds-radius-sm);
  font-size: var(--ds-text-sm);
  padding: var(--ds-space-2) var(--ds-space-3);
  box-shadow: none;
  border-color: var(--ds-border);
}
.embodied-input-area :deep(.el-textarea__inner:focus) {
  border-color: var(--ds-primary);
}
.embodied-send-btn {
  flex-shrink: 0;
  width: 36px !important;
  height: 36px !important;
  min-height: 36px !important;
  padding: 0 !important;
  border-radius: var(--ds-radius-sm) !important;
  background: linear-gradient(135deg, var(--ds-primary) 0%, var(--ds-primary-active) 100%) !important;
  border: none !important;
}
.embodied-fade-enter-active {
  transition:
    opacity var(--ds-transition-page) var(--ds-ease-out-expo),
    transform var(--ds-transition-page) var(--ds-ease-out-expo);
}
.embodied-fade-leave-active {
  transition:
    opacity 0.2s var(--ds-ease-out-expo),
    transform 0.22s var(--ds-ease-out-expo);
}
.embodied-fade-enter-from,
.embodied-fade-leave-to {
  opacity: 0;
  transform: translateY(16px) scale(0.97);
}
</style>
