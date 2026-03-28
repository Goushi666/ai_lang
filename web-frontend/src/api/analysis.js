import request from "@/utils/request";

export const analysisApi = {
  getSummary: (params) =>
    request.get("/api/analysis/environment/summary", { params }),
  runAnalysis: (params) =>
    request.post("/api/analysis/environment/run", null, { params }),
};
