import request from "../utils/request";

/**
 * 与车端/业务后端 stream-config 对齐（见 doc/Web前端-MJPEG视频显示说明.md）。
 * @returns {Promise<{
 *   hls_playlist_url?: string|null,
 *   hlsPlaylistUrl?: string|null,
 *   mjpeg_url?: string|null,
 *   mjpegUrl?: string|null,
 *   video_feed_url?: string|null,
 *   videoFeedUrl?: string|null,
 *   hint_zh: string
 * }>}
 */
export function getVideoStreamConfig() {
  return request.get("/api/video/stream-config");
}
