/**
 * 与 doc/Web前端-MJPEG视频显示说明.md 一致：从业务后端或车端 stream-config 解析播放地址。
 * MJPEG 仅用 <img src>，优先 Flask 习惯的 video_feed 字段名。
 */

/** @param {Record<string, unknown>|null|undefined} cfg */
export function pickHlsPlaylistUrl(cfg) {
  if (!cfg) return "";
  const u = cfg.hls_playlist_url ?? cfg.hlsPlaylistUrl;
  return typeof u === "string" && u.trim() ? u.trim() : "";
}

/**
 * 文档约定：video_feed_url / videoFeedUrl 优先，否则 mjpeg_url / mjpegUrl。
 * @param {Record<string, unknown>|null|undefined} cfg
 */
export function pickMjpegFeedUrl(cfg) {
  if (!cfg) return "";
  const order = [
    cfg.video_feed_url,
    cfg.videoFeedUrl,
    cfg.mjpeg_url,
    cfg.mjpegUrl,
  ];
  for (const u of order) {
    if (typeof u === "string" && u.trim()) return u.trim();
  }
  return "";
}

/** 相对路径补全为当前站点绝对地址（便于 <img> 拉同源代理） */
export function toAbsoluteMediaUrl(u) {
  if (!u) return "";
  if (/^https?:\/\//i.test(u)) return u;
  if (typeof window === "undefined") return u;
  const origin = window.location.origin;
  return u.startsWith("/") ? `${origin}${u}` : `${origin}/${u}`;
}
