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
      <div v-if="expanded" class="embodied-panel">
        <div class="embodied-header">
          <span class="embodied-title">AI Control</span>
          <div class="embodied-header-actions">
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
            <div
              v-if="m.role === 'assistant'"
              class="embodied-msg-bubble"
              v-html="renderMd(m.content)"
            ></div>
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
import { ref, nextTick, onUnmounted } from "vue";
import { Monitor, Delete, Close, Promotion } from "@element-plus/icons-vue";
import { renderMarkdown } from "@/utils/markdown";
import { agentChatStream } from "@/api/agent";

const expanded = ref(false);
const inputText = ref("");
const sending = ref(false);
const msgListRef = ref(null);
const sessionId = ref(null);
let abortCtrl = null;
let uidSeq = 0;

const WELCOME_TEXT = "你好，我可以帮你控制机械臂和巡检车。";
const messages = ref([
  { role: "assistant", content: WELCOME_TEXT, _uid: ++uidSeq },
]);

function renderMd(text) {
  return renderMarkdown(text || "");
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
    { role: "assistant", content: WELCOME_TEXT, _uid: ++uidSeq },
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
        if (ev.type === "delta") {
          if (ev.content) assistantMsg.content += ev.content;
          if (ev.reasoning) assistantMsg.reasoning += ev.reasoning;
          scrollBottom();
        } else if (ev.type === "done") {
          if (ev.session_id) sessionId.value = ev.session_id;
          if (ev.content && !assistantMsg.content)
            assistantMsg.content = ev.content;
        }
      },
      abortCtrl.signal
    );
  } catch (e) {
    if (e.name !== "AbortError") {
      assistantMsg.content =
        assistantMsg.content || "请求失败: " + e.message;
    }
  } finally {
    sending.value = false;
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
  border-radius: 50%;
  background: linear-gradient(135deg, #7c3aed 0%, #6366f1 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.4);
  transition: box-shadow 0.2s, transform 0.2s;
  user-select: none;
  touch-action: none;
}
.embodied-ball:hover {
  box-shadow: 0 6px 24px rgba(99, 102, 241, 0.55);
  transform: scale(1.06);
}
.embodied-panel {
  pointer-events: auto;
  position: fixed;
  right: 24px;
  bottom: 24px;
  width: 380px;
  height: 520px;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.16);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(99, 102, 241, 0.12);
}
.embodied-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  background: linear-gradient(135deg, #7c3aed 0%, #6366f1 100%);
  color: #fff;
}
.embodied-title {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.03em;
}
.embodied-header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}
/* STYLE_CHUNK_2 */
.embodied-clear-btn,
.embodied-close-btn {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.75);
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s, color 0.15s;
}
.embodied-clear-btn:hover,
.embodied-close-btn:hover {
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
}
.embodied-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
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
.embodied-msg-bubble {
  max-width: 85%;
  padding: 8px 12px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.55;
  word-break: break-word;
}
.embodied-msg--user .embodied-msg-bubble {
  background: linear-gradient(135deg, #7c3aed 0%, #6366f1 100%);
  color: #fff;
  border-bottom-right-radius: 3px;
}
.embodied-msg--assistant .embodied-msg-bubble {
  background: #f4f1fe;
  color: #1e1e2e;
  border-bottom-left-radius: 3px;
}
.embodied-msg--assistant .embodied-msg-bubble :deep(p) {
  margin: 0 0 6px;
}
.embodied-msg--assistant .embodied-msg-bubble :deep(p:last-child) {
  margin-bottom: 0;
}
.embodied-msg--assistant .embodied-msg-bubble :deep(code) {
  background: rgba(99, 102, 241, 0.08);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 12px;
}
.embodied-typing {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}
.embodied-typing span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #a78bfa;
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
  gap: 8px;
  padding: 10px 14px;
  border-top: 1px solid #f0ecf9;
  background: #faf9fe;
}
.embodied-input-area :deep(.el-textarea__inner) {
  border-radius: 8px;
  font-size: 13px;
  padding: 6px 10px;
  box-shadow: none;
  border-color: #e0d8f0;
}
.embodied-input-area :deep(.el-textarea__inner:focus) {
  border-color: #7c3aed;
}
.embodied-send-btn {
  flex-shrink: 0;
  width: 36px !important;
  height: 36px !important;
  min-height: 36px !important;
  padding: 0 !important;
  border-radius: 8px !important;
  background: linear-gradient(135deg, #7c3aed 0%, #6366f1 100%) !important;
  border: none !important;
}
.embodied-fade-enter-active,
.embodied-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.embodied-fade-enter-from,
.embodied-fade-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.95);
}
</style>
