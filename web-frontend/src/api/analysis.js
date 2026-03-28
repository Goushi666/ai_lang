import request from "@/utils/request";

export const analysisApi = {
  getSummary: (params) =>
    request.get("/api/analysis/environment/summary", { params }),
  runAnalysis: (params) =>
    request.post("/api/analysis/environment/run", null, { params }),

  /** @param {{ start_time: string, end_time: string, device_id?: string, format: 'json'|'csv', scope: 'anomalies'|'full' }} p */
  exportBlob: (p) =>
    request.get("/api/analysis/environment/export", {
      params: p,
      responseType: "blob",
    }),
};
