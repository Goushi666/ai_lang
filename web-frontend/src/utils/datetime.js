/**
 * 时间约定（避免把 UTC 瞬间与北京墙钟混比而「慢 8 小时」）：
 *
 * - **Unix 纪元时间戳（秒或毫秒）**：与设备/服务器本地时区无关，表示自 1970-01-01 **UTC** 起的同一瞬间。
 *   MQTT 常见 10 位秒或 13 位毫秒；**不要**在设备上对 timestamp 再加 28800。
 * - **REST ISO 字符串**：带 `Z` 或 `±HH:MM` 的按标准解析为瞬间。
 *   含 `T` 但无时区后缀的，按 `VITE_NAIVE_ISO_OFFSET`（默认 `+08:00`）当作墙钟再换算——仅用于少数「无时区本地 ISO」设备，与 Unix 数字无关。
 *
 * **展示北京时间**：`formatDateTimeZh` 使用 `toLocaleString(..., timeZone: "Asia/Shanghai")`，
 * 等价于先得到正确 `Date` 再按东八区格式化。
 */
const NAIVE_OFFSET =
  import.meta.env.VITE_NAIVE_ISO_OFFSET != null && import.meta.env.VITE_NAIVE_ISO_OFFSET !== ""
    ? String(import.meta.env.VITE_NAIVE_ISO_OFFSET)
    : "+08:00";

const SHANGHAI = "Asia/Shanghai";

/**
 * 将 Unix 秒或毫秒转为 JavaScript 毫秒时间戳（UTC 瞬间）。
 * @param {number} n
 * @returns {number} 无效为 NaN
 */
export function unixEpochToMs(n) {
  if (typeof n !== "number" || !Number.isFinite(n)) return NaN;
  return n >= 1e12 ? Math.round(n) : Math.round(n * 1000);
}

function hasExplicitTz(s) {
  return /[zZ]$|[+\-]\d{2}:?\d{2}$/.test(String(s).trim());
}

/**
 * @param {string|number|Date} input
 * @returns {number} 毫秒时间戳，无效为 NaN
 */
export function parseBackendInstant(input) {
  if (input == null) return NaN;
  if (input instanceof Date) return input.getTime();
  if (typeof input === "number") return unixEpochToMs(input);
  let s = String(input).trim();
  if (!s) return NaN;
  if (/^\d+$/.test(s)) return unixEpochToMs(Number(s));
  if (s.includes("T") && !hasExplicitTz(s)) {
    const off = NAIVE_OFFSET.startsWith("+") || NAIVE_OFFSET.startsWith("-") ? NAIVE_OFFSET : `+${NAIVE_OFFSET}`;
    s = `${s}${off}`;
  }
  const t = Date.parse(s);
  return Number.isNaN(t) ? NaN : t;
}

/**
 * WebSocket `sensor_data` 等 payload 的 `timestamp`：
 * 可为秒/毫秒 number、纯数字字符串（Unix）、或 ISO 字符串。
 * Unix 数字一律按 UTC epoch 解读，绝不叠加东八偏移。
 * @param {unknown} raw
 * @returns {number} 毫秒，无法解析为 NaN
 */
export function parseSensorPayloadTimestampMs(raw) {
  if (raw == null || raw === "") return NaN;
  if (typeof raw === "number") return unixEpochToMs(raw);
  if (typeof raw === "string") {
    const t = raw.trim();
    if (/^\d+$/.test(t)) return unixEpochToMs(Number(t));
    return parseBackendInstant(raw);
  }
  return NaN;
}

/**
 * 统一用东八区展示（与手机北京时间对齐）。
 */
export function formatDateTimeZh(input) {
  const ms = parseBackendInstant(input);
  if (Number.isNaN(ms)) return input == null ? "" : String(input);
  return new Date(ms).toLocaleString("zh-CN", {
    timeZone: SHANGHAI,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}
