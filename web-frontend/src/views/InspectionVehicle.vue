<template>
  <div class="inspection-vehicle">
    <h2 class="page-title">巡检与遥控</h2>

    <!-- 左 70% 仅视频；右 30% 纵向：上 50% = 运行状态+速度（各占一半），下 50% = 方向控制 -->
    <div class="inspection-layout">
      <div class="layout-col layout-col--video">
        <el-card shadow="hover" class="video-card">
          <template #header>
            <span class="card-head">实时画面</span>
          </template>
          <div class="video-body">
            <div class="stream-stage">
              <video
                v-show="playMode === 'hls'"
                ref="videoEl"
                class="stream-video"
                controls
                playsinline
                muted
              />
              <img
                v-if="playMode === 'mjpeg'"
                :src="mjpegAbsoluteUrl"
                class="stream-mjpeg"
                alt="车载摄像头 MJPEG"
                @error="onMjpegImgError"
              />
              <el-empty
                v-if="playMode === 'none'"
                description="未配置视频流地址"
                :image-size="72"
              >
                <template #image>
                  <el-icon :size="64" color="#c0c4cc"><VideoCamera /></el-icon>
                </template>
                <el-text type="info">{{
                  streamHint ||
                    "在 backend .env 设置 VIDEO_MJPEG_URL（如 http://192.168.137.114:8080/video_feed）或 VIDEO_HLS_PLAYLIST_URL 后刷新"
                }}</el-text>
              </el-empty>
            </div>
            <div class="video-hints">
              <div class="hints-body">
                <el-alert
                  v-if="streamHint && playMode !== 'none'"
                  type="info"
                  :closable="false"
                  show-icon
                  class="stream-hint"
                >
                  {{ streamHint }}
                </el-alert>
                <el-alert
                  v-if="videoError"
                  type="warning"
                  :title="videoError"
                  :closable="false"
                  show-icon
                  class="stream-hint"
                />
                <el-text v-if="playMode === 'none' && streamHint" type="warning" size="small" class="hints-fallback">
                  {{ streamHint }}
                </el-text>
                <el-text v-else-if="!streamHint && !videoError" type="info" size="small">暂无提示</el-text>
              </div>
            </div>
          </div>
        </el-card>
      </div>

      <div class="layout-col layout-col--side">
        <div class="side-upper">
          <el-card shadow="hover" class="status-card metric-card">
            <template #header><span class="card-head">运行状态</span></template>
            <el-descriptions :column="1" border size="small" v-if="status">
              <el-descriptions-item label="连接状态">
                <el-tag :type="status.connected ? 'success' : 'danger'" size="small">
                  {{ status.connected ? "已连接" : "未连接" }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="运行模式">
                <el-tag :type="status.mode === 'auto' ? 'primary' : 'info'" size="small">
                  {{ status.mode === "auto" ? "自动循迹" : "手动控制" }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="当前速度">{{ status.speed }}</el-descriptions-item>
              <el-descriptions-item label="左轮速度">{{ status.left_speed ?? 0 }}</el-descriptions-item>
              <el-descriptions-item label="右轮速度">{{ status.right_speed ?? 0 }}</el-descriptions-item>
            </el-descriptions>
            <el-skeleton :rows="4" v-else animated />
          </el-card>

          <el-card shadow="hover" class="speed-card metric-card">
            <template #header><span class="card-head">速度设置</span></template>
            <div class="speed-row">
              <span class="speed-label">速度：{{ speed }}</span>
              <el-slider v-model="speed" :min="0" :max="100" :step="5" show-stops />
            </div>
          </el-card>
        </div>

        <div class="side-lower">
          <el-card shadow="hover" class="control-card">
            <template #header>
              <span class="card-head"
                >方向控制 <el-text type="info" size="small">(键盘 W/A/S/D、空格停止)</el-text></span
              >
            </template>

            <div class="dpad">
              <div class="dpad-row">
                <div class="dpad-cell"></div>
                <div class="dpad-cell">
                  <el-button type="primary" class="dpad-btn" @click="send('forward')">
                    <el-icon :size="18"><Top /></el-icon>
                    <div class="dpad-label">前进</div>
                  </el-button>
                </div>
                <div class="dpad-cell"></div>
              </div>
              <div class="dpad-row">
                <div class="dpad-cell">
                  <el-button type="primary" class="dpad-btn" @click="send('left')">
                    <el-icon :size="18"><Back /></el-icon>
                    <div class="dpad-label">左转</div>
                  </el-button>
                </div>
                <div class="dpad-cell">
                  <el-button type="warning" class="dpad-btn stop-btn" @click="send('stop')">
                    <el-icon :size="18"><VideoPause /></el-icon>
                    <div class="dpad-label">停止</div>
                  </el-button>
                </div>
                <div class="dpad-cell">
                  <el-button type="primary" class="dpad-btn" @click="send('right')">
                    <el-icon :size="18"><Right /></el-icon>
                    <div class="dpad-label">右转</div>
                  </el-button>
                </div>
              </div>
              <div class="dpad-row">
                <div class="dpad-cell"></div>
                <div class="dpad-cell">
                  <el-button type="primary" class="dpad-btn" @click="send('backward')">
                    <el-icon :size="18"><Bottom /></el-icon>
                    <div class="dpad-label">后退</div>
                  </el-button>
                </div>
                <div class="dpad-cell"></div>
              </div>
            </div>

            <div class="emergency-row">
              <el-button type="danger" class="emergency-btn" @click="send('stop')">
                紧急停止
              </el-button>
            </div>
          </el-card>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { inject, nextTick, onMounted, onUnmounted, ref } from "vue";
import { VideoCamera, Top, Bottom, Back, Right, VideoPause } from "@element-plus/icons-vue";
import Hls from "hls.js";
import { vehicleApi } from "../api/vehicle";
import { getVideoStreamConfig } from "../api/video";
import { pickHlsPlaylistUrl, pickMjpegFeedUrl, toAbsoluteMediaUrl } from "../utils/videoStream";

const ws = inject("ws");
const status = ref(null);
const speed = ref(50);

const videoEl = ref(null);
const playMode = ref("none");
const streamHint = ref("");
const videoError = ref("");
const mjpegAbsoluteUrl = ref("");
let hlsInstance = null;

function destroyHls() {
  if (hlsInstance) {
    hlsInstance.destroy();
    hlsInstance = null;
  }
}

async function setupHls(playlistUrl) {
  videoError.value = "";
  destroyHls();
  await nextTick();
  const el = videoEl.value;
  if (!el) return;
  const src = toAbsoluteMediaUrl(playlistUrl);
  if (Hls.isSupported()) {
    hlsInstance = new Hls({ enableWorker: true });
    hlsInstance.loadSource(src);
    hlsInstance.attachMedia(el);
    hlsInstance.on(Hls.Events.ERROR, (_, data) => {
      if (!data.fatal) return;
      if (data.type === Hls.ErrorTypes.NETWORK_ERROR) {
        videoError.value =
          "HLS 网络错误：请确认转码服务已启动，且开发环境下 Vite 已将 /live 代理到 MediaMTX/FFmpeg 输出端口。";
      } else {
        videoError.value = "HLS 解码失败：请检查 m3u8 与切片路径是否可访问、是否同源或已放行 CORS。";
      }
    });
  } else if (el.canPlayType("application/vnd.apple.mpegurl")) {
    el.src = src;
  } else {
    videoError.value = "当前浏览器不支持 HLS（可换 Chrome / Edge 或改用 MJPEG）";
  }
}

function onMjpegImgError() {
  videoError.value =
    "MJPEG 画面加载失败：请确认车端 video_stream 已启用，且 URL 可访问（如 /video_feed）；使用代理时请确认后端能访问 VIDEO_MJPEG_URL。";
}

/**
 * 接收画面逻辑（文档）：GET stream-config → 有 HLS 则用 video+hls.js，否则用 <img> + MJPEG URL。
 * MJPEG URL 优先 video_feed_url，再 mjpeg_url（含业务后端同源代理路径）。
 */
async function loadStreamConfig() {
  streamHint.value = "";
  videoError.value = "";
  playMode.value = "none";
  mjpegAbsoluteUrl.value = "";
  destroyHls();
  try {
    const cfg = await getVideoStreamConfig();
    streamHint.value = cfg.hint_zh || "";
    const hlsUrl = pickHlsPlaylistUrl(cfg);
    const feedUrl = pickMjpegFeedUrl(cfg);
    if (hlsUrl) {
      playMode.value = "hls";
      await setupHls(hlsUrl);
    } else if (feedUrl) {
      playMode.value = "mjpeg";
      mjpegAbsoluteUrl.value = toAbsoluteMediaUrl(feedUrl);
    }
  } catch {
    streamHint.value = "无法拉取视频配置：请确认后端已启动且可访问 /api/video/stream-config";
  }
}

async function refreshStatus() {
  try {
    status.value = await vehicleApi.getStatus();
  } catch {
    /* 静默 */
  }
}

async function send(action) {
  await vehicleApi.sendControl({
    action,
    speed: speed.value,
    timestamp: Date.now(),
  });
}

function handleKeydown(e) {
  const map = { w: "forward", s: "backward", a: "left", d: "right", " ": "stop" };
  const action = map[e.key.toLowerCase()];
  if (action) {
    e.preventDefault();
    send(action);
  }
}

onMounted(async () => {
  await refreshStatus();
  await loadStreamConfig();
  window.addEventListener("keydown", handleKeydown);

  ws.on("vehicle_status", (payload) => {
    status.value = {
      ...(status.value || {}),
      mode: payload.mode || "manual",
      speed: payload.speed ?? 0,
      connected: payload.connected ?? true,
      left_speed: payload.leftSpeed ?? payload.left_speed ?? 0,
      right_speed: payload.rightSpeed ?? payload.right_speed ?? 0,
      timestamp: payload.timestamp,
    };
  });
});

onUnmounted(() => {
  window.removeEventListener("keydown", handleKeydown);
  destroyHls();
});
</script>

<style scoped>
.inspection-vehicle {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.page-title {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  flex-shrink: 0;
}

.card-head {
  font-weight: 600;
  font-size: 13px;
}

/* 横向：左 70% 视频、右 30% 侧栏；侧栏纵向 50% / 50% */
.inspection-layout {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: row;
  gap: 14px;
  align-items: stretch;
}

.layout-col--video {
  flex: 7 1 0%;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.layout-col--side {
  flex: 3 1 0%;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.side-upper {
  flex: 1 1 0%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow: hidden;
}

.side-lower {
  flex: 1 1 0%;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.layout-col--video .video-card {
  border-radius: 6px;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
}
.layout-col--video .video-card :deep(.el-card__header) {
  padding: 6px 10px;
  min-height: auto;
  flex-shrink: 0;
}
.layout-col--video .video-card :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 8px 10px;
}

.video-hints {
  flex: 0 1 auto;
  max-height: 32%;
  min-height: 0;
  margin-top: 6px;
  padding-top: 4px;
  border-top: 1px solid var(--el-border-color-lighter);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.video-hints .hints-body {
  overflow-y: auto;
  min-height: 0;
}

.video-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.stream-stage {
  flex: 1;
  min-height: 0;
  width: 100%;
  background: #0b0b0b;
  border-radius: 4px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}
.stream-stage :deep(.el-empty) {
  padding: 12px 8px;
}
.stream-stage :deep(.el-empty__description) {
  margin-top: 6px;
}

.stream-hint {
  width: 100%;
  max-width: 100%;
  flex-shrink: 0;
}
.stream-hint :deep(.el-alert__content) {
  font-size: 12px;
}

.hints-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.hints-fallback {
  line-height: 1.5;
}

.stream-video,
.stream-mjpeg {
  width: 100%;
  height: 100%;
  max-height: none;
  background: #000;
  border-radius: 0;
  object-fit: contain;
  flex-shrink: 0;
}
.stream-mjpeg {
  display: block;
}

.metric-card {
  border-radius: 6px;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.metric-card :deep(.el-card__header) {
  padding: 6px 10px;
  min-height: auto;
  flex-shrink: 0;
}
.metric-card :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 8px 10px;
}

.control-card {
  border-radius: 6px;
  flex: 1;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.control-card :deep(.el-card__header) {
  padding: 6px 10px;
  min-height: auto;
  flex-shrink: 0;
}
.control-card :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 8px 10px;
  overflow-y: auto;
}

.speed-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.speed-label {
  font-size: 12px;
  color: #606266;
}
.speed-card :deep(.el-slider) {
  margin-top: 0;
}

.dpad {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 4px 0 0;
  flex: 1;
  min-height: 0;
}
.dpad-row {
  display: flex;
  gap: 6px;
}
.layout-col--side .side-lower .dpad-cell {
  width: 50px;
  height: 50px;
}
.layout-col--side .side-lower .dpad-btn {
  width: 46px;
  height: 46px;
}
.layout-col--side .side-lower .stop-btn {
  width: 46px;
  height: 46px;
}

.dpad-cell {
  width: 58px;
  height: 58px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.dpad-btn {
  width: 52px;
  height: 52px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  padding: 4px;
}
.dpad-label {
  font-size: 10px;
  margin-top: 2px;
  line-height: 1;
}
.stop-btn {
  border-radius: 50%;
  width: 52px;
  height: 52px;
}

.emergency-row {
  display: flex;
  justify-content: center;
  margin-top: 8px;
  flex-shrink: 0;
}
.emergency-btn {
  width: 140px;
  height: 36px;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 1px;
  border-radius: 18px;
}

.layout-col--side .side-lower .emergency-btn {
  width: min(100%, 160px);
  height: 32px;
  font-size: 13px;
}

/* 窄屏：纵向堆叠 */
@media (max-width: 767px) {
  .inspection-layout {
    flex-direction: column;
    overflow-y: auto;
    overflow-x: hidden;
    gap: 10px;
  }

  .layout-col--video,
  .layout-col--side {
    flex: 0 0 auto;
    width: 100%;
  }

  .layout-col--video .stream-stage {
    aspect-ratio: 16 / 9;
    max-height: min(42vh, 360px);
    flex: none;
  }

  .video-hints {
    max-height: 24vh;
  }

  .side-upper,
  .side-lower {
    flex: 0 0 auto;
    min-height: 0;
  }

  .metric-card {
    flex: none;
  }

  .side-lower {
    min-height: 220px;
  }

  .layout-col--side .side-lower .dpad-cell {
    width: 58px;
    height: 58px;
  }
  .layout-col--side .side-lower .dpad-btn {
    width: 52px;
    height: 52px;
  }
  .layout-col--side .side-lower .stop-btn {
    width: 52px;
    height: 52px;
  }
  .layout-col--side .side-lower .emergency-btn {
    width: 140px;
    height: 36px;
    font-size: 14px;
  }
}
</style>
