import request from "@/utils/request";

export const vehicleApi = {
  sendControl: (data) => request.post("/api/vehicle/control", data),
  /** 摄像头云台：后端向 MQTT arm/control 发 joint 6、7 */
  sendGimbal: (data) => request.post("/api/vehicle/gimbal", data),
  /** 机械臂：后端向 MQTT arm/control 发 joint 0~5 */
  sendArmJoints: (data) => request.post("/api/vehicle/arm", data),
  getStatus: () => request.get("/api/vehicle/status"),
};

