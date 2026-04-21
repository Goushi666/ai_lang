import request from "@/utils/request";
import { nextTick } from "vue";
import { agentStreamDbg } from "@/utils/agentStreamDebug";

/**
 * 同一 TCP 块里可能含大量 SSE 行；若同步连续 onEvent，Vue 会合并成一次渲染。
 * 每个事件后 await nextTick()，让界面按事件粒度刷新（流式可见）。
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
        if (ev.type !== "delta") {
          agentStreamDbg("event", { type: ev.type, session_id: ev.session_id });
        }
        await nextTick();
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
}

export const agentApi = {
  health: () => request.get("/api/agent/health"),
  chat: (body) => request.post("/api/agent/chat", body, { timeout: 120000 }),
  listSessions: (limit = 50) =>
    request.get("/api/agent/sessions", { params: { limit } }),
  getSession: (sessionId) => request.get(`/api/agent/sessions/${sessionId}`),
  deleteSession: (sessionId) => request.delete(`/api/agent/sessions/${sessionId}`),
};
