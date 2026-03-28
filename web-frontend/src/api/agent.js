import request from "@/utils/request";

export const agentApi = {
  health: () => request.get("/api/agent/health"),
  chat: (body) => request.post("/api/agent/chat", body),
};
