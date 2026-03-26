import request from "@/utils/request";

export const vehicleApi = {
  sendControl: (data) => request.post("/api/vehicle/control", data),
  getStatus: () => request.get("/api/vehicle/status"),
};

