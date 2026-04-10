<template>
  <div class="inspection-vehicle">
    <h2 class="page-title">巡检与遥控</h2>

    <!-- 左 70% 视频；右 30%：运行状态 + 云台 + 遥控面板（方向含行驶速度） -->
    <div class="inspection-layout">
      <div class="layout-col layout-col--video">
        <el-card shadow="never" class="video-card">
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
                decoding="async"
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
                  size="small"
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
                  size="small"
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
          <el-card shadow="never" class="status-card compact-panel">
            <template #header><span class="card-head">运行状态</span></template>
            <el-descriptions
              v-if="status"
              :column="1"
              border
              size="small"
              class="status-desc"
            >
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
              <el-descriptions-item label="行驶策略">
                <el-tag :type="status.drive_mode === 'track' ? 'warning' : 'success'" size="small">
                  {{ status.drive_mode === "track" ? "循迹（已锁遥控）" : "普通" }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="当前速度">{{ status.speed }}</el-descriptions-item>
              <el-descriptions-item label="左轮速度">{{ status.left_speed ?? 0 }}</el-descriptions-item>
              <el-descriptions-item label="右轮速度">{{ status.right_speed ?? 0 }}</el-descriptions-item>
            </el-descriptions>
            <div v-if="status" class="drive-mode-actions">
              <el-text type="info" size="small" class="drive-mode-hint">MQTT「car/control/track」</el-text>
              <el-button-group size="small">
                <el-button
                  :type="(status.drive_mode || 'normal') !== 'track' ? 'primary' : 'default'"
                  @click="setDriveMode('normal')"
                >
                  普通模式
                </el-button>
                <el-button
                  :type="status.drive_mode === 'track' ? 'primary' : 'default'"
                  @click="setDriveMode('track')"
                >
                  循迹模式
                </el-button>
              </el-button-group>
            </div>
            <el-skeleton :rows="4" v-else animated />
          </el-card>
        </div>

        <div class="side-lower">
          <div class="side-lower-inner">
            <el-card shadow="never" class="speed-gimbal-card compact-panel">
              <template #header>
                <div class="card-head-stack">
                  <span class="card-head">云台</span>
                  <el-text type="info" size="small">
                    {{
                      trackModeLocked
                        ? "循迹中：云台由车端固定位姿，已锁定。"
                        : "松手后下发；拖哪条只发该条（转速条会带当前两关节角）"
                    }}
                  </el-text>
                </div>
              </template>
              <div class="param-row">
                <span class="param-row-label">关节 6</span>
                <div class="param-row-slider">
                  <el-slider
                    v-model="gimbalJ6"
                    :min="0"
                    :max="180"
                    :step="1"
                    size="small"
                    :disabled="trackModeLocked"
                    @change="onGimbalJ6Change"
                  />
                </div>
                <span class="param-row-val">{{ gimbalJ6 }}°</span>
              </div>
              <div class="param-row">
                <span class="param-row-label">关节 7</span>
                <div class="param-row-slider">
                  <el-slider
                    v-model="gimbalJ7"
                    :min="0"
                    :max="90"
                    :step="1"
                    size="small"
                    :disabled="trackModeLocked"
                    @change="onGimbalJ7Change"
                  />
                </div>
                <span class="param-row-val">{{ gimbalJ7 }}°</span>
              </div>
              <div class="param-row">
                <span class="param-row-label">云台转速</span>
                <div class="param-row-slider">
                  <el-slider
                    v-model="gimbalSpeed"
                    :min="0"
                    :max="100"
                    :step="5"
                    size="small"
                    :disabled="trackModeLocked"
                    @change="onGimbalSpeedChange"
                  />
                </div>
                <span class="param-row-val">{{ gimbalSpeed }}</span>
              </div>
            </el-card>

            <el-card shadow="never" class="control-card compact-panel">
              <template #header>
                <div class="control-card-head">
                  <div class="control-card-head-titles">
                    <span class="card-head">遥控面板</span>
                    <el-text type="info" size="small">
                      {{
                        controlPanelMode === "vehicle"
                          ? trackModeLocked
                            ? "循迹中：方向键与本面板已锁定，请先切回「普通模式」。"
                            : "方向：W/A/S/D、空格停"
                          : "机械臂：松手后下发；拖哪个关节只发该关节（转速条会带齐 6 角）"
                      }}
                    </el-text>
                  </div>
                  <el-radio-group v-model="controlPanelMode" size="small" class="control-mode-toggle">
                    <el-radio-button label="vehicle">方向</el-radio-button>
                    <el-radio-button label="arm">机械臂</el-radio-button>
                  </el-radio-group>
                </div>
              </template>

              <div v-show="controlPanelMode === 'vehicle'" class="control-body">
                <div class="param-row vehicle-speed-row">
                  <span class="param-row-label">行驶速度</span>
                  <div class="param-row-slider">
                    <el-slider v-model="speed" :min="0" :max="100" :step="5" size="small" :disabled="trackModeLocked" />
                  </div>
                  <span class="param-row-val">{{ speed }}</span>
                </div>
                <div class="dpad-center">
                  <div class="dpad">
                    <div class="dpad-row">
                      <div class="dpad-cell"></div>
                      <div class="dpad-cell">
                        <el-button type="primary" class="dpad-btn" :disabled="trackModeLocked" @click="send('forward')">
                          <el-icon :size="20"><Top /></el-icon>
                          <div class="dpad-label">前进</div>
                        </el-button>
                      </div>
                      <div class="dpad-cell"></div>
                    </div>
                    <div class="dpad-row">
                      <div class="dpad-cell">
                        <el-button type="primary" class="dpad-btn" :disabled="trackModeLocked" @click="send('left')">
                          <el-icon :size="20"><Back /></el-icon>
                          <div class="dpad-label">左转</div>
                        </el-button>
                      </div>
                      <div class="dpad-cell">
                        <el-button type="warning" class="dpad-btn stop-btn" :disabled="trackModeLocked" @click="send('stop')">
                          <el-icon :size="20"><VideoPause /></el-icon>
                          <div class="dpad-label">停止</div>
                        </el-button>
                      </div>
                      <div class="dpad-cell">
                        <el-button type="primary" class="dpad-btn" :disabled="trackModeLocked" @click="send('right')">
                          <el-icon :size="20"><Right /></el-icon>
                          <div class="dpad-label">右转</div>
                        </el-button>
                      </div>
                    </div>
                    <div class="dpad-row">
                      <div class="dpad-cell"></div>
                      <div class="dpad-cell">
                        <el-button type="primary" class="dpad-btn" :disabled="trackModeLocked" @click="send('backward')">
                          <el-icon :size="20"><Bottom /></el-icon>
                          <div class="dpad-label">后退</div>
                        </el-button>
                      </div>
                      <div class="dpad-cell"></div>
                    </div>
                  </div>
                </div>
              </div>

              <div v-show="controlPanelMode === 'arm'" class="control-body arm-control-body">
                <div class="arm-sliders-scroll">
                  <div
                    v-for="i in 6"
                    :key="'arm-j' + (i - 1)"
                    class="param-row arm-param-row"
                  >
                    <span class="param-row-label arm-label">关节 {{ i - 1 }}</span>
                    <div class="param-row-slider arm-slider-wrap">
                      <el-slider
                        :model-value="armAngles[i - 1]"
                        :min="0"
                        :max="180"
                        :step="1"
                        size="small"
                        @update:model-value="(v) => setArmAngle(i - 1, v)"
                        @change="() => onArmJointChange(i - 1)"
                      />
                    </div>
                    <span class="param-row-val arm-val">{{ armAngles[i - 1] }}°</span>
                  </div>
                  <div class="param-row arm-param-row">
                    <span class="param-row-label arm-label">机械臂转速</span>
                    <div class="param-row-slider arm-slider-wrap">
                      <el-slider v-model="armSpeed" :min="0" :max="100" :step="5" size="small" @change="onArmSpeedChange" />
                    </div>
                    <span class="param-row-val arm-val">{{ armSpeed }}</span>
                  </div>
                </div>
              </div>
            </el-card>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, inject, nextTick, onMounted, onUnmounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { VideoCamera, Top, Bottom, Back, Right, VideoPause } from "@element-plus/icons-vue";
import Hls from "hls.js";
import { vehicleApi } from "../api/vehicle";
import { getVideoStreamConfig } from "../api/video";
import { pickHlsPlaylistUrl, pickMjpegFeedUrl, toAbsoluteMediaUrl } from "../utils/videoStream";

const ws = inject("ws");
const status = ref(null);
const speed = ref(50);

/** 循迹模式：锁定车体遥控、云台关节 6/7（与手册 car/control、车端云台策略一致） */
const trackModeLocked = computed(() => (status.value?.drive_mode || "normal") === "track");

const gimbalJ6 = ref(90);
const gimbalJ7 = ref(60);
const gimbalSpeed = ref(50);

/** 方向控制 | 机械臂控制 */
const controlPanelMode = ref("vehicle");

const armAngles = ref([110, 160, 180, 180, 90, 90]);
const armSpeed = ref(50);

function setArmAngle(index, value) {
  const next = armAngles.value.slice();
  next[index] = value;
  armAngles.value = next;
}

async function sendGimbalPartial(body) {
  if (trackModeLocked.value) {
    ElMessage.warning("循迹模式中云台已锁定，请先切回「普通模式」");
    return;
  }
  try {
    await vehicleApi.sendGimbal(body);
  } catch (e) {
    const msg = e?.response?.data?.detail;
    ElMessage.error(typeof msg === "string" ? msg : "云台下发失败，请确认 MQTT 已连接");
  }
}

function onGimbalJ6Change() {
  sendGimbalPartial({ joint_6_angle: gimbalJ6.value, speed: gimbalSpeed.value });
}

function onGimbalJ7Change() {
  sendGimbalPartial({ joint_7_angle: gimbalJ7.value, speed: gimbalSpeed.value });
}

function onGimbalSpeedChange() {
  sendGimbalPartial({
    joint_6_angle: gimbalJ6.value,
    joint_7_angle: gimbalJ7.value,
    speed: gimbalSpeed.value,
  });
}

async function sendArmPartial(body) {
  try {
    await vehicleApi.sendArmJoints(body);
  } catch (e) {
    const msg = e?.response?.data?.detail;
    ElMessage.error(typeof msg === "string" ? msg : "机械臂下发失败，请确认 MQTT 已连接");
  }
}

function onArmJointChange(index) {
  if (controlPanelMode.value !== "arm") return;
  const body = { speed: armSpeed.value };
  body[`joint_${index}_angle`] = armAngles.value[index];
  sendArmPartial(body);
}

function onArmSpeedChange() {
  if (controlPanelMode.value !== "arm") return;
  const a = armAngles.value;
  sendArmPartial({
    joint_0_angle: a[0],
    joint_1_angle: a[1],
    joint_2_angle: a[2],
    joint_3_angle: a[3],
    joint_4_angle: a[4],
    joint_5_angle: a[5],
    speed: armSpeed.value,
  });
}

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

async function setDriveMode(mode) {
  const cur = status.value?.drive_mode || "normal";
  if (cur === mode) return;
  try {
    await vehicleApi.sendTrackMode({
      mode,
      timestamp: Math.floor(Date.now() / 1000),
    });
    ElMessage.success(
      mode === "track"
        ? "已下发循迹模式：车体遥控与云台已锁定"
        : "已切回普通模式，可使用键盘、面板与云台",
    );
    await refreshStatus();
  } catch (e) {
    const msg = e?.response?.data?.detail;
    ElMessage.error(typeof msg === "string" ? msg : "模式切换失败，请确认 MQTT 与 Topic 配置");
  }
}

async function send(action) {
  if (trackModeLocked.value) {
    ElMessage.warning("循迹模式中已锁定手动控制，请先切回「普通模式」");
    return;
  }
  await vehicleApi.sendControl({
    action,
    speed: speed.value,
    duration: 0,
    timestamp: Date.now(),
  });
}

function handleKeydown(e) {
  if (trackModeLocked.value) return;
  if (controlPanelMode.value !== "vehicle") return;
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
      drive_mode: payload.driveMode ?? payload.drive_mode ?? status.value?.drive_mode ?? "normal",
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
.card-head-stack {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  line-height: 1.3;
}
.card-head-stack .card-head {
  margin: 0;
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
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow: visible;
}

.side-lower {
  flex: 1 1 0%;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.side-lower-inner {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.layout-col--video .video-card {
  border-radius: 6px;
  border: 1px solid var(--el-border-color-lighter);
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
  flex: 0 0 auto;
  max-height: min(120px, 22vh);
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
  isolation: isolate;
  transform: translateZ(0);
  backface-visibility: hidden;
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
  transform: translateZ(0);
  backface-visibility: hidden;
}

.compact-panel {
  border-radius: 6px;
  border: 1px solid var(--el-border-color-lighter);
}
.compact-panel :deep(.el-card__header) {
  padding: 5px 10px;
  min-height: auto;
  flex-shrink: 0;
}
.compact-panel :deep(.el-card__body) {
  padding: 8px 10px;
}

.status-card {
  flex: 0 0 auto;
}
.status-card :deep(.el-card__body) {
  overflow: visible;
  padding-top: 6px;
  padding-bottom: 8px;
}
.status-desc :deep(.el-descriptions__body) {
  background: transparent;
}
.status-desc :deep(.el-descriptions__label),
.status-desc :deep(.el-descriptions__content) {
  padding: 6px 10px !important;
  font-size: 12px;
}

.drive-mode-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--el-border-color-lighter);
}
.drive-mode-hint {
  flex: 1 1 auto;
  min-width: 0;
}

.speed-gimbal-card {
  flex: 0 0 auto;
}
.speed-gimbal-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.param-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.param-row:last-of-type {
  margin-bottom: 6px;
}
.param-row-label {
  flex: 0 0 5.25rem;
  font-size: 12px;
  color: #606266;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.param-row-slider {
  flex: 1 1 0;
  min-width: 0;
}
.param-row-slider :deep(.el-slider) {
  width: 100%;
}
.param-row-val {
  flex: 0 0 2.25rem;
  text-align: right;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  color: #303133;
  font-weight: 500;
}
.panel-divider {
  margin: 4px 0 10px !important;
}

.control-card {
  border-radius: 6px;
  flex: 1 1 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.control-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}
.control-card-head-titles {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  min-width: 0;
  line-height: 1.3;
}
.control-card-head-titles .card-head {
  margin: 0;
}
.control-mode-toggle {
  flex-shrink: 0;
}
.control-card :deep(.el-card__header) {
  padding: 5px 10px;
  min-height: auto;
  flex-shrink: 0;
}
.control-card :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 8px 10px 10px;
  overflow: hidden;
}

.control-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.vehicle-speed-row {
  flex-shrink: 0;
  margin-bottom: 4px;
}
.dpad-center {
  flex: 1 1 0;
  min-height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px 4px;
}

.dpad {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  flex: 0 0 auto;
}
.dpad-row {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: center;
}
.layout-col--side .side-lower .dpad-cell {
  width: 58px;
  height: 58px;
  flex-shrink: 0;
}
.layout-col--side .side-lower .dpad-btn {
  width: 54px;
  height: 54px;
}
.layout-col--side .side-lower .stop-btn {
  width: 54px;
  height: 54px;
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
  width: 54px;
  height: 54px;
}

.arm-control-body {
  min-height: 160px;
}
.arm-sliders-scroll {
  max-height: min(320px, 42vh);
  overflow-y: auto;
  padding-right: 2px;
  display: flex;
  flex-direction: column;
  gap: 0;
}
.arm-param-row {
  margin-bottom: 6px;
}
.arm-param-row:last-of-type {
  margin-bottom: 4px;
}
.arm-label {
  color: #722ed1;
  font-weight: 500;
}
.arm-val {
  color: #531dab;
}
.arm-slider-wrap :deep(.el-slider__runway) {
  background-color: rgba(114, 46, 209, 0.12);
}
.arm-slider-wrap :deep(.el-slider__bar) {
  background-color: #722ed1;
}
.arm-slider-wrap :deep(.el-slider__button) {
  border-color: #722ed1;
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
    max-height: min(100px, 20vh);
  }

  .side-upper,
  .side-lower {
    flex: 0 0 auto;
    min-height: 0;
  }

  .side-upper {
    max-height: none;
  }

  .side-lower {
    min-height: 200px;
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
}
</style>
