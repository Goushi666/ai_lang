import request from "@/utils/request";

export const vehicleApi = {
  sendControl: (data) => request.post("/api/vehicle/control", data),
  /** 摄像头云台：后端向 MQTT arm/control 发 joint 6、7 */
  sendGimbal: (data) => request.post("/api/vehicle/gimbal", data),
  getStatus: () => request.get("/api/vehicle/status"),
};

