import request from "@/utils/request";

export const adminApi = {
  /** 清空 sensor_data / environment_anomalies（同一 SQLite 内两张表） */
  purgeData: (data) => request.post("/api/admin/purge-data", data),
};
