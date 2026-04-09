import request from "@/utils/request";

export const monitoringApi = {
  getTemperatureTimeline: (params) =>
    request.get("/api/monitoring/temperature-timeline", { params }),
  getAnomalies: (params) =>
    request.get("/api/monitoring/anomalies", { params }),
  /** 已落库环境异常（SQLite environment_anomalies） */
  listAnomalyRecords: (params) =>
    request.get("/api/monitoring/anomalies/records", { params }),
  deleteAnomalyRecord: (id) =>
    request.delete(`/api/monitoring/anomalies/records/${id}`),
  batchDeleteAnomalyRecords: (data) =>
    request.post("/api/monitoring/anomalies/records/batch-delete", data),
};
