import request from "../utils/request";

/** @returns {Promise<{ hls_playlist_url?: string, mjpeg_url?: string, hint_zh: string }>} */
export function getVideoStreamConfig() {
  return request.get("/api/video/stream-config");
}
