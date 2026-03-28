import request from "@/utils/request";

export const monitoringApi = {
  getTemperatureTimeline: (params) =>
    request.get("/api/monitoring/temperature-timeline", { params }),
  getAnomalies: (params) =>
    request.get("/api/monitoring/anomalies", { params }),
};
