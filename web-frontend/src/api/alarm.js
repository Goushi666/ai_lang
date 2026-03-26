import request from "@/utils/request";

export const alarmApi = {
  getHistory: (params) => request.get("/api/alarms/history", { params }),
  markRead: (id) => request.put(`/api/alarms/${id}/read`),
  getConfig: () => request.get("/api/alarms/config"),
  updateConfig: (data) => request.put("/api/alarms/config", data),
};

