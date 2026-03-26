import request from "@/utils/request";

export const deviceApi = {
  ping: () => request.get("/api/devices/ping"),
};

