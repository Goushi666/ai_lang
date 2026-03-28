<template>
  <div class="agent-page">
    <h2 class="page-title">智能助手</h2>
    <el-alert
      type="warning"
      :closable="false"
      show-icon
      class="mb-4"
      title="助手回答仅供参考，控制与配置请以系统功能为准。"
    />
    <el-card shadow="hover" class="status-card">
      <span>服务状态：</span>
      <el-tag v-if="health === null" type="info">检测中…</el-tag>
      <template v-else>
        <el-tag :type="health.enabled ? 'success' : 'danger'">
          {{ health.enabled ? "已启用（占位）" : "已关闭" }}
        </el-tag>
        <span class="health-msg">{{ health.message }}</span>
      </template>
    </el-card>

    <el-card shadow="hover" class="chat-card">
      <div ref="listRef" class="messages">
        <div
          v-for="(m, i) in messages"
          :key="i"
          :class="['bubble', m.role === 'user' ? 'user' : 'assistant']"
        >
          <span class="role">{{ m.role === "user" ? "我" : "助手" }}</span>
          <div class="content">{{ m.content }}</div>
        </div>
      </div>
      <div class="input-row">
        <el-input
          v-model="input"
          type="textarea"
          :rows="3"
          placeholder="输入问题（当前仅返回占位回复）"
          @keydown.enter.exact.prevent="send"
        />
        <el-button type="primary" :loading="sending" :disabled="!health?.enabled" @click="send">
          发送
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { agentApi } from "../api/agent";

const health = ref(null);
const messages = ref([
  { role: "assistant", content: "你好，我是智能助手占位框架。发送任意内容将调用 /api/agent/chat。" },
]);
const input = ref("");
const sending = ref(false);
const listRef = ref(null);

async function loadHealth() {
  try {
    health.value = await agentApi.health();
  } catch {
    health.value = { enabled: false, message: "无法连接后端" };
  }
}

async function send() {
  const text = input.value.trim();
  if (!text) return;
  if (!health.value?.enabled) {
    ElMessage.warning("Agent 未启用或不可用");
    return;
  }
  messages.value.push({ role: "user", content: text });
  input.value = "";
  sending.value = true;
  try {
    const body = {
      messages: messages.value.map(({ role, content }) => ({ role, content })),
    };
    const res = await agentApi.chat(body);
    messages.value.push({ role: "assistant", content: res.content });
    await nextTick();
    listRef.value?.scrollTo?.({ top: listRef.value.scrollHeight, behavior: "smooth" });
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || "请求失败");
  } finally {
    sending.value = false;
  }
}

onMounted(loadHealth);
</script>

<style scoped>
.page-title {
  margin: 0 0 16px 0;
  font-size: 20px;
  color: #303133;
}
.mb-4 { margin-bottom: 16px; }
.status-card {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.health-msg { color: #909399; font-size: 13px; margin-left: 8px; }
.chat-card { min-height: 420px; display: flex; flex-direction: column; }
.messages {
  flex: 1;
  max-height: 360px;
  overflow-y: auto;
  margin-bottom: 16px;
  padding: 8px;
  background: #fafafa;
  border-radius: 8px;
}
.bubble {
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  max-width: 85%;
}
.bubble.user {
  margin-left: auto;
  background: #ecf5ff;
  border: 1px solid #d9ecff;
}
.bubble.assistant {
  background: #fff;
  border: 1px solid #ebeef5;
}
.role { font-size: 12px; color: #909399; display: block; margin-bottom: 4px; }
.content { white-space: pre-wrap; font-size: 14px; color: #303133; line-height: 1.5; }
.input-row {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}
.input-row .el-input { flex: 1; }
</style>
