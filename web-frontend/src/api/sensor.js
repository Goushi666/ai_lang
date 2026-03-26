import request from "@/utils/request";

export const sensorApi = {
  getLatest: () => request.get("/api/sensors/latest"),
  getHistory: (params) => request.get("/api/sensors/history", { params }),
  exportData: (params) =>
    request.get("/api/sensors/export", {
      params,
      responseType: "blob",
    }),
};

