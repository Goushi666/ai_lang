import request from "@/utils/request";
import { nextTick } from "vue";

const jsonHeaders = {
  "Content-Type": "application/json",
  Accept: "application/json",
};

/**
 * 将 delta 按字（Unicode 码点）拆开，每步 onEvent + nextTick，配合页面侧 bump 触发列表重渲染。
 */
async function emitDeltaInChunks(onEvent, ev) {
  const reasoning = ev.reasoning || "";
  const content = ev.content || "";
  if (!reasoning && !content) {
    onEvent(ev);
    await nextTick();
    return;
  }
  const pushByChar = async (field, text) => {
    if (!text) return;
    for (const ch of text) {
      onEvent(field === "reasoning" ? { type: "delta", reasoning: ch } : { type: "delta", content: ch });
      await nextTick();
    }
  };
  await pushByChar("reasoning", reasoning);
  await pushByChar("content", content);
}

/**
 * SSE：`data:` 每行为 JSON，见后端 `/api/agent/chat/stream`
 * @param {object} body - ChatRequest：messages、session_id、mode
 * @param {(ev: object) => void} onEvent
 * @param {AbortSignal} [signal]
 */
export async function agentChatStream(body, onEvent, signal) {
  const url = `${import.meta.env.VITE_API_BASE_URL || ""}/api/agent/chat/stream`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      ...jsonHeaders,
      Accept: "text/event-stream",
    },
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
  const dec = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += dec.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const norm = block.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
      for (const line of norm.split("\n")) {
        if (!line.startsWith("data:")) continue;
        const raw = line.slice(5).trimStart();
        if (!raw) continue;
        try {
          const ev = JSON.parse(raw);
          if (ev.type === "delta") {
            await emitDeltaInChunks(onEvent, ev);
          } else {
            onEvent(ev);
            await nextTick();
          }
        } catch {
          /* skip malformed */
        }
      }
    }
  }
}

export const agentApi = {
  health: () => request.get("/api/agent/health"),
  chat: (body) => request.post("/api/agent/chat", body, { timeout: 120000 }),
  listSessions: (limit = 50) =>
    request.get("/api/agent/sessions", { params: { limit } }),
  getSession: (sessionId) => request.get(`/api/agent/sessions/${sessionId}`),
  deleteSession: (sessionId) => request.delete(`/api/agent/sessions/${sessionId}`),
};
