import request from "@/utils/request";

const jsonHeaders = {
  "Content-Type": "application/json",
  Accept: "application/json",
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
      for (const line of block.split("\n")) {
        if (!line.startsWith("data:")) continue;
        const raw = line.slice(5).trimStart();
        if (!raw) continue;
        try {
          onEvent(JSON.parse(raw));
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
