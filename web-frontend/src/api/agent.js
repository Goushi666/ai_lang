import request from "@/utils/request";
import { nextTick } from "vue";
import { agentStreamDbg } from "@/utils/agentStreamDebug";

/**
 * SSE 解析：非 delta 事件后 await nextTick 保证 clarification/done 等及时落屏；
 * delta 用 requestAnimationFrame 合并为每帧最多一次刷新，减轻逐 token 卡顿。
 */

const jsonHeaders = {
  "Content-Type": "application/json",
  Accept: "text/event-stream",
};

/**
 * SSE：`data:` 每行为 JSON，见后端 `/api/agent/chat/stream`
 * @param {object} body - ChatRequest：messages、session_id、mode
 * @param {(ev: object) => void} onEvent
 * @param {AbortSignal} [signal]
 */
export async function agentChatStream(body, onEvent, signal) {
  let deltaFlushRaf = 0;
  function scheduleDeltaUiFlush() {
    if (deltaFlushRaf) return;
    deltaFlushRaf = requestAnimationFrame(async () => {
      deltaFlushRaf = 0;
      await nextTick();
    });
  }

  const url = `${import.meta.env.VITE_API_BASE_URL || ""}/api/agent/chat/stream`;
  const token =
    typeof localStorage !== "undefined" ? localStorage.getItem("token") : null;
  const headers = {
    ...jsonHeaders,
    Accept: "text/event-stream",
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      detail = j.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  const reader = res.body?.getReader();
  if (!reader) throw new Error("无响应流");
  agentStreamDbg("fetch-open", { url, ok: res.ok, ct: res.headers.get("content-type") });
  const dec = new TextDecoder();
  let buffer = "";

  async function dispatchSseBlock(block) {
    const norm = block.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    for (const line of norm.split("\n")) {
      if (!line.startsWith("data:")) continue;
      const raw = line.slice(5).trimStart();
      if (!raw || raw === "[DONE]") continue;
      try {
        const ev = JSON.parse(raw);
        onEvent(ev);
        if (ev.type === "delta") {
          scheduleDeltaUiFlush();
        } else {
          agentStreamDbg("event", { type: ev.type, session_id: ev.session_id });
          await nextTick();
        }
      } catch (e) {
        agentStreamDbg("json-skip", { rawLen: raw.length, err: String(e) });
      }
    }
  }

  let readCount = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      agentStreamDbg("read-done", { readCount, bufferTailLen: buffer.length });
      break;
    }
    readCount += 1;
    const bytes = value?.byteLength ?? 0;
    buffer += dec.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      await dispatchSseBlock(block);
    }
    agentStreamDbg("read-chunk", { readCount, bytes, bufferLen: buffer.length });
  }
  buffer += dec.decode();
  const tail = buffer.trim();
  if (tail) {
    agentStreamDbg("buffer-flush-tail", { preview: tail.slice(0, 200) });
    await dispatchSseBlock(buffer);
  }
  if (deltaFlushRaf) {
    cancelAnimationFrame(deltaFlushRaf);
    deltaFlushRaf = 0;
  }
  await nextTick();
}

export const agentApi = {
  health: () => request.get("/api/agent/health"),
  chat: (body) => request.post("/api/agent/chat", body, { timeout: 120000 }),
  listSessions: (limit = 50) =>
    request.get("/api/agent/sessions", { params: { limit } }),
  getSession: (sessionId) => request.get(`/api/agent/sessions/${sessionId}`),
  deleteSession: (sessionId) => request.delete(`/api/agent/sessions/${sessionId}`),
};
