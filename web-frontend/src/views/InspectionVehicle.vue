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
                </div>
              </template>
              <div class="param-row gimbal-preset-row">
                <span class="param-row-label">目标档位</span>
                <el-radio-group
                  v-model="gimbalTargetPreset"
                  size="small"
                  class="gimbal-preset-rg"
                  :disabled="trackModeLocked"
                  @change="(v) => onGimbalPresetChange(v)"
                >
                  <el-radio-button label="control">控制 110/95</el-radio-button>
                  <el-radio-button label="track">循迹 110/145</el-radio-button>
                </el-radio-group>
              </div>
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
                    :max="145"
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
                <div class="control-card-head control-card-head--inline">
                  <span class="card-head control-card-head-title">遥控面板</span>
                  <el-radio-group
                    v-model="controlPanelMode"
                    size="small"
                    class="control-mode-toggle control-mode-toggle--triple"
                  >
                    <el-radio-button label="vehicle">方向</el-radio-button>
                    <el-radio-button label="arm">机械臂</el-radio-button>
                    <el-radio-button label="presets">程序动作</el-radio-button>
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
                          <el-icon :size="16"><Top /></el-icon>
                          <div class="dpad-label">前进</div>
                        </el-button>
                      </div>
                      <div class="dpad-cell"></div>
                    </div>
                    <div class="dpad-row">
                      <div class="dpad-cell">
                        <el-button type="primary" class="dpad-btn" :disabled="trackModeLocked" @click="send('left')">
                          <el-icon :size="16"><Back /></el-icon>
                          <div class="dpad-label">左转</div>
                        </el-button>
                      </div>
                      <div class="dpad-cell">
                        <el-button type="warning" class="dpad-btn stop-btn" :disabled="trackModeLocked" @click="send('stop')">
                          <el-icon :size="16"><VideoPause /></el-icon>
                          <div class="dpad-label">停止</div>
                        </el-button>
                      </div>
                      <div class="dpad-cell">
                        <el-button type="primary" class="dpad-btn" :disabled="trackModeLocked" @click="send('right')">
                          <el-icon :size="16"><Right /></el-icon>
                          <div class="dpad-label">右转</div>
                        </el-button>
                      </div>
                    </div>
                    <div class="dpad-row">
                      <div class="dpad-cell"></div>
                      <div class="dpad-cell">
                        <el-button type="primary" class="dpad-btn" :disabled="trackModeLocked" @click="send('backward')">
                          <el-icon :size="16"><Bottom /></el-icon>
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
                        :disabled="armSequenceRunning"
                        @update:model-value="(v) => setArmAngle(i - 1, v)"
                        @change="() => onArmJointChange(i - 1)"
                      />
                    </div>
                    <span class="param-row-val arm-val">{{ armAngles[i - 1] }}°</span>
                  </div>
                  <div class="param-row arm-param-row">
                    <span class="param-row-label arm-label">机械臂转速</span>
                    <div class="param-row-slider arm-slider-wrap">
                      <el-slider
                        v-model="armSpeed"
                        :min="0"
                        :max="100"
                        :step="5"
                        size="small"
                        :disabled="armSequenceRunning"
                        @change="onArmSpeedChange"
                      />
                    </div>
                    <span class="param-row-val arm-val">{{ armSpeed }}</span>
                  </div>
                </div>
              </div>

              <div v-show="controlPanelMode === 'presets'" class="control-body arm-actions-panel">
                <div class="arm-actions-toolbar">
                  <el-button
                    type="primary"
                    class="arm-toolbar-reset"
                    :loading="armSequenceRunning"
                    title="Shift+点击 可编辑复位角度"
                    @click="onResetButtonClick"
                  >
                    <el-icon style="margin-right: 4px"><RefreshRight /></el-icon>
                    复位
                  </el-button>
                  <el-button
                    class="arm-toolbar-plus"
                    :disabled="armSequenceRunning"
                    title="新建动作"
                    @click="openAddActionDialog"
                  >
                    <el-icon :size="15"><Plus /></el-icon>
                    <span>添加</span>
                  </el-button>
                </div>
                <div class="arm-actions-scroll">
                  <div v-if="armPresets.length" class="arm-actions-saved">
                    <div v-for="p in armPresets" :key="p.id" class="arm-saved-card">
                      <div class="arm-saved-info">
                        <span class="arm-saved-icon">▶</span>
                        <span class="arm-saved-name">{{ p.name }}</span>
                      </div>
                      <div class="arm-saved-actions">
                        <el-button
                          type="primary"
                          size="small"
                          class="arm-saved-run"
                          :loading="armSequenceRunning"
                          @click="runPresetSequence(p)"
                        >
                          执行
                        </el-button>
                        <el-button
                          text
                          type="danger"
                          size="small"
                          class="arm-saved-del"
                          :disabled="armSequenceRunning"
                          @click.stop="removePreset(p.id)"
                        >
                          删除
                        </el-button>
                      </div>
                    </div>
                  </div>
                  <div v-else class="arm-actions-empty">
                    <div class="arm-actions-empty-icon">
                      <el-icon :size="28" color="rgba(114,46,209,0.25)"><Plus /></el-icon>
                    </div>
                    <span class="arm-actions-empty-text">暂无预设动作</span>
                    <span class="arm-actions-empty-hint">点击上方「添加」创建</span>
                  </div>
                </div>
              </div>
            </el-card>
          </div>
        </div>
      </div>
    </div>

    <el-dialog v-model="resetAnglesDialogVisible" title="编辑复位角度" width="420px" destroy-on-close>
      <div class="reset-angles-grid">
        <div v-for="idx in 6" :key="'ra-' + (idx - 1)" class="reset-angle-item">
          <span class="reset-angle-label">关节 {{ idx - 1 }}</span>
          <el-input-number v-model="resetAnglesDraft[idx - 1]" :min="0" :max="180" :step="1" size="small" controls-position="right" />
        </div>
      </div>
      <template #footer>
        <el-button @click="resetAnglesDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveResetAnglesFromDialog">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="addActionDialogVisible"
      title="新建动作"
      width="480px"
      class="add-action-dialog"
      align-center
      destroy-on-close
    >
      <el-form label-position="top" size="default" class="add-action-form">
        <el-form-item label="名称" class="add-action-name-item">
          <el-input v-model="addActionForm.name" maxlength="32" show-word-limit placeholder="如：采样位" />
        </el-form-item>

        <div class="add-action-section add-action-section--boxed">
          <div class="add-action-section-head">
            <span class="add-action-section-title">关节顺序</span>
            <el-button type="primary" link size="small" @click="resetAddActionJointOrder">恢复 0→5</el-button>
          </div>
          <div class="joint-order-grid">
            <div v-for="step in 6" :key="'ord-' + step" class="joint-order-cell">
              <span class="joint-order-badge">{{ step }}</span>
              <el-select
                v-model="addActionForm.jointOrder[step - 1]"
                placeholder="轴"
                size="small"
                class="joint-order-select"
              >
                <el-option v-for="j in jointIndexOptions" :key="'jo-' + step + '-' + j" :label="'J' + j" :value="j" />
              </el-select>
            </div>
          </div>
        </div>

        <div class="add-action-section add-action-section--boxed">
          <span class="add-action-section-title">旋转速度</span>
          <div class="add-action-speed-wrap">
            <el-slider v-model="addActionForm.speed" :min="0" :max="100" :step="5" />
            <span class="add-action-speed-val">{{ addActionForm.speed }}</span>
          </div>
        </div>

        <div class="add-action-section add-action-section--boxed">
          <span class="add-action-section-title">目标角度 °</span>
          <div class="add-action-angles-grid">
            <div v-for="idx in 6" :key="'aa-' + (idx - 1)" class="add-action-angle-cell">
              <span class="add-action-angle-label">J{{ idx - 1 }}</span>
              <el-input-number
                v-model="addActionForm.angles[idx - 1]"
                :min="0"
                :max="180"
                :step="1"
                size="small"
                controls-position="right"
                class="add-action-angle-input"
              />
            </div>
          </div>
        </div>
      </el-form>
      <template #footer>
        <div class="add-action-dialog-footer">
          <el-button @click="addActionDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveAddActionDialog">保存</el-button>
        </div>
      </template>
    </el-dialog>

    <EmbodiedChat />
  </div>
</template>

<script setup>
import { computed, inject, nextTick, onMounted, onUnmounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { Plus, VideoCamera, Top, Bottom, Back, Right, VideoPause, RefreshRight } from "@element-plus/icons-vue";
import Hls from "hls.js";
import { vehicleApi } from "../api/vehicle";
import EmbodiedChat from "./EmbodiedChat.vue";
import { getVideoStreamConfig } from "../api/video";
import { pickHlsPlaylistUrl, pickMjpegFeedUrl, toAbsoluteMediaUrl } from "../utils/videoStream";

const ws = inject("ws");
const status = ref(null);
const speed = ref(50);

/** 循迹模式：锁定车体遥控、云台关节 6/7（与手册 car/control、车端云台策略一致） */
const trackModeLocked = computed(() => (status.value?.drive_mode || "normal") === "track");

/** 云台关节 6/7：普通控制默认与循迹前默认位（切循迹前会先下发循迹位） */
const GIMBAL_PRESET_CONTROL = { j6: 110, j7: 95 };
const GIMBAL_PRESET_TRACK = { j6: 110, j7: 145 };

const gimbalTargetPreset = ref("control");
const gimbalJ6 = ref(GIMBAL_PRESET_CONTROL.j6);
const gimbalJ7 = ref(GIMBAL_PRESET_CONTROL.j7);
const gimbalSpeed = ref(50);

/** 切入循迹过程中屏蔽云台滑块/档位触发的二次下发，避免先 110/145 再回到旧角度 */
const suppressGimbalAutoSend = ref(false);

/** 方向控制 | 机械臂控制 | 程序动作 */
const controlPanelMode = ref("vehicle");

const armAngles = ref([110, 180, 170, 150, 90, 90]);
const armSpeed = ref(50);

function setArmAngle(index, value) {
  const next = armAngles.value.slice();
  next[index] = value;
  armAngles.value = next;
}

/** 机械臂顺序动作：从关节 0 起依次下发，间隔与转速见 UI 说明 */
const ARM_PRESET_STEP_MS = 1500;
const STORAGE_ARM_RESET = "inspection_vehicle_arm_reset_angles_v1";
/** 程序动作预设：写入 localStorage，同一浏览器与源站下下次打开仍会加载（勿清站点数据）。 */
const STORAGE_ARM_PRESETS = "inspection_vehicle_arm_presets_v1";

function defaultResetAngles() {
  return [110, 180, 170, 150, 90, 90];
}

function clampJoint(v) {
  const n = Math.round(Number(v));
  return Math.max(0, Math.min(180, Number.isFinite(n) ? n : 0));
}

const armResetAngles = ref(defaultResetAngles());
const armPresets = ref([]);
const armSequenceRunning = ref(false);
const resetAnglesDialogVisible = ref(false);
const resetAnglesDraft = ref(defaultResetAngles());

const jointIndexOptions = [0, 1, 2, 3, 4, 5];

const addActionDialogVisible = ref(false);
const addActionForm = reactive({
  name: "",
  angles: [...defaultResetAngles()],
  jointOrder: [0, 1, 2, 3, 4, 5],
  speed: 50,
});

function loadArmPresetStorage() {
  try {
    const rawR = localStorage.getItem(STORAGE_ARM_RESET);
    if (rawR) {
      const arr = JSON.parse(rawR);
      if (Array.isArray(arr) && arr.length === 6) {
        armResetAngles.value = arr.map(clampJoint);
      }
    }
  } catch {
    /* ignore */
  }
  try {
    const rawP = localStorage.getItem(STORAGE_ARM_PRESETS);
    if (rawP) {
      const list = JSON.parse(rawP);
      if (Array.isArray(list)) {
        armPresets.value = list
          .filter((x) => x && typeof x.name === "string" && Array.isArray(x.angles) && x.angles.length === 6)
          .map((x, i) => {
            const sp = Number(x.speed);
            const fj = Number(x.firstJoint);
            return {
              id: x.id || `preset-${i}-${Date.now()}`,
              name: String(x.name).trim(),
              angles: x.angles.map(clampJoint),
              jointOrder: normalizeStoredJointOrder(x.jointOrder, Number.isFinite(fj) ? fj : 0),
              speed: Number.isFinite(sp) ? Math.max(0, Math.min(100, Math.round(sp))) : 50,
            };
          });
        persistArmPresets();
      }
    }
  } catch {
    /* ignore */
  }
}

function persistArmReset() {
  try {
    localStorage.setItem(STORAGE_ARM_RESET, JSON.stringify(armResetAngles.value));
  } catch {
    /* quota */
  }
}

function persistArmPresets() {
  try {
    const payload = armPresets.value.map((p) => ({
      id: p.id,
      name: p.name,
      angles: p.angles.map(clampJoint),
      jointOrder: normalizeStoredJointOrder(p.jointOrder, p.firstJoint),
      speed: clampArmSpeed(p.speed),
    }));
    localStorage.setItem(STORAGE_ARM_PRESETS, JSON.stringify(payload));
  } catch {
    /* quota */
  }
}

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function clampArmSpeed(v) {
  const n = Math.round(Number(v));
  return Math.max(0, Math.min(100, Number.isFinite(n) ? n : 50));
}

/** 关节下发顺序：从 firstJoint 递增到 5，再回到 0..firstJoint-1（仅用于迁移旧预设） */
function buildJointOrder(firstJoint) {
  const f = Math.max(0, Math.min(5, Math.floor(Number(firstJoint)) || 0));
  const order = [];
  for (let k = f; k < 6; k += 1) order.push(k);
  for (let k = 0; k < f; k += 1) order.push(k);
  return order;
}

function isValidJointPermutation(order) {
  if (!Array.isArray(order) || order.length !== 6) return false;
  const nums = order.map((x) => Math.round(Number(x)));
  if (nums.some((n) => !Number.isFinite(n) || n < 0 || n > 5)) return false;
  return new Set(nums).size === 6;
}

/** 从存储读取：合法 jointOrder 直接用，否则用旧字段 firstJoint 推导 */
function normalizeStoredJointOrder(rawOrder, firstJointFallback) {
  if (isValidJointPermutation(rawOrder)) {
    return rawOrder.map((x) => Math.max(0, Math.min(5, Math.round(Number(x)))));
  }
  const fj = Math.max(0, Math.min(5, Math.round(Number(firstJointFallback)) || 0));
  return buildJointOrder(fj);
}

function resolveRunJointOrder(opts) {
  if (opts && isValidJointPermutation(opts.jointOrder)) {
    return opts.jointOrder.map((x) => Math.max(0, Math.min(5, Math.round(Number(x)))));
  }
  if (opts && opts.firstJoint !== undefined && opts.firstJoint !== null) {
    return buildJointOrder(opts.firstJoint);
  }
  return [0, 1, 2, 3, 4, 5];
}

async function runArmSequentialToPose(targets, opts = {}) {
  if (armSequenceRunning.value) return;
  const t = targets.map(clampJoint);
  if (t.length !== 6) {
    ElMessage.error("需要 6 个关节角度（0°–180°）");
    return;
  }
  const useSpeed =
    opts.speed !== undefined && opts.speed !== null ? clampArmSpeed(opts.speed) : clampArmSpeed(armSpeed.value);
  const order = resolveRunJointOrder(opts);
  armSequenceRunning.value = true;
  try {
    for (let step = 0; step < order.length; step += 1) {
      const k = order[step];
      const body = { speed: useSpeed };
      body[`joint_${k}_angle`] = t[k];
      const ok = await sendArmPartial(body);
      if (!ok) return;
      setArmAngle(k, t[k]);
      if (step < order.length - 1) await sleep(ARM_PRESET_STEP_MS);
    }
    ElMessage.success("动作已完成");
  } finally {
    armSequenceRunning.value = false;
  }
}

function runResetSequence() {
  runArmSequentialToPose(armResetAngles.value.slice(), {
    jointOrder: [0, 1, 2, 3, 4, 5],
    speed: armSpeed.value,
  });
}

function runPresetSequence(p) {
  if (!p?.angles) return;
  runArmSequentialToPose(p.angles.slice(), {
    jointOrder: p.jointOrder,
    firstJoint: p.firstJoint,
    speed: p.speed !== undefined && p.speed !== null ? p.speed : armSpeed.value,
  });
}

function onResetButtonClick(e) {
  if (e?.shiftKey) {
    openResetAnglesDialog();
    return;
  }
  runResetSequence();
}

function openResetAnglesDialog() {
  resetAnglesDraft.value = armResetAngles.value.map((x) => clampJoint(x));
  resetAnglesDialogVisible.value = true;
}

function saveResetAnglesFromDialog() {
  armResetAngles.value = resetAnglesDraft.value.map(clampJoint);
  persistArmReset();
  resetAnglesDialogVisible.value = false;
  ElMessage.success("已保存复位角度");
}

function openAddActionDialog() {
  addActionForm.name = `动作${armPresets.value.length + 1}`;
  const cur = armAngles.value.map(clampJoint);
  for (let i = 0; i < 6; i += 1) addActionForm.angles[i] = cur[i];
  resetAddActionJointOrder();
  addActionForm.speed = clampArmSpeed(armSpeed.value);
  addActionDialogVisible.value = true;
}

function resetAddActionJointOrder() {
  for (let i = 0; i < 6; i += 1) addActionForm.jointOrder[i] = i;
}

function saveAddActionDialog() {
  const name = String(addActionForm.name || "").trim();
  if (!name) {
    ElMessage.warning("请填写名称");
    return;
  }
  const angles = addActionForm.angles.map(clampJoint);
  const jointOrder = addActionForm.jointOrder.map((x) => Math.max(0, Math.min(5, Math.round(Number(x)))));
  if (!isValidJointPermutation(jointOrder)) {
    ElMessage.warning("关节顺序须为 0～5 各出现一次，请检查六步选择");
    return;
  }
  const speed = clampArmSpeed(addActionForm.speed);
  const id =
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `preset-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
  armPresets.value = [...armPresets.value, { id, name, angles, jointOrder, speed }];
  persistArmPresets();
  addActionDialogVisible.value = false;
  ElMessage.success("已保存");
}

function removePreset(id) {
  armPresets.value = armPresets.value.filter((x) => x.id !== id);
  persistArmPresets();
  ElMessage.success("已删除");
}

async function sendGimbalPartial(body) {
  if (trackModeLocked.value) {
    ElMessage.warning("循迹模式中云台已锁定，请先切回「普通模式」");
    return false;
  }
  try {
    await vehicleApi.sendGimbal(body);
    return true;
  } catch (e) {
    const msg = e?.response?.data?.detail;
    ElMessage.error(typeof msg === "string" ? msg : "云台下发失败，请确认 MQTT 已连接");
    return false;
  }
}

function onGimbalPresetChange(val) {
  const p = val === "track" ? GIMBAL_PRESET_TRACK : GIMBAL_PRESET_CONTROL;
  gimbalJ6.value = p.j6;
  gimbalJ7.value = p.j7;
  if (suppressGimbalAutoSend.value) return;
  if (!trackModeLocked.value) {
    sendGimbalPartial({
      joint_6_angle: gimbalJ6.value,
      joint_7_angle: gimbalJ7.value,
      speed: gimbalSpeed.value,
    });
  }
}

function onGimbalJ6Change() {
  if (suppressGimbalAutoSend.value || trackModeLocked.value) return;
  sendGimbalPartial({ joint_6_angle: gimbalJ6.value, speed: gimbalSpeed.value });
}

function onGimbalJ7Change() {
  if (suppressGimbalAutoSend.value || trackModeLocked.value) return;
  sendGimbalPartial({ joint_7_angle: gimbalJ7.value, speed: gimbalSpeed.value });
}

function onGimbalSpeedChange() {
  if (suppressGimbalAutoSend.value || trackModeLocked.value) return;
  sendGimbalPartial({
    joint_6_angle: gimbalJ6.value,
    joint_7_angle: gimbalJ7.value,
    speed: gimbalSpeed.value,
  });
}

async function sendArmPartial(body) {
  try {
    await vehicleApi.sendArmJoints(body);
    return true;
  } catch (e) {
    const msg = e?.response?.data?.detail;
    ElMessage.error(typeof msg === "string" ? msg : "机械臂下发失败，请确认 MQTT 已连接");
    return false;
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
  let trackGimbalFlow = false;
  try {
    if (mode === "track" && cur !== "track") {
      trackGimbalFlow = true;
      suppressGimbalAutoSend.value = true;
      gimbalJ6.value = GIMBAL_PRESET_TRACK.j6;
      gimbalJ7.value = GIMBAL_PRESET_TRACK.j7;
      gimbalTargetPreset.value = "track";
      await nextTick();
      const ok = await sendGimbalPartial({
        joint_6_angle: GIMBAL_PRESET_TRACK.j6,
        joint_7_angle: GIMBAL_PRESET_TRACK.j7,
        speed: gimbalSpeed.value,
      });
      if (!ok) {
        suppressGimbalAutoSend.value = false;
        return;
      }
    }
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
    await nextTick();
    if (trackGimbalFlow) {
      setTimeout(() => {
        suppressGimbalAutoSend.value = false;
      }, 200);
    }
    if (mode === "normal" && cur === "track") {
      gimbalTargetPreset.value = "control";
      gimbalJ6.value = GIMBAL_PRESET_CONTROL.j6;
      gimbalJ7.value = GIMBAL_PRESET_CONTROL.j7;
      await sendGimbalPartial({
        joint_6_angle: gimbalJ6.value,
        joint_7_angle: gimbalJ7.value,
        speed: gimbalSpeed.value,
      });
    }
  } catch (e) {
    if (trackGimbalFlow) suppressGimbalAutoSend.value = false;
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
  loadArmPresetStorage();
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
  margin: 0 0 var(--ds-space-2) 0;
  font-size: var(--ds-text-lg);
  font-weight: 700;
  color: var(--ds-text-primary);
  flex-shrink: 0;
}

.card-head {
  font-weight: 600;
  font-size: var(--ds-text-sm);
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

.inspection-layout {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: row;
  gap: var(--ds-space-3);
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
  gap: var(--ds-space-2);
}

.side-upper {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-2);
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
  gap: var(--ds-space-2);
}

.layout-col--video .video-card {
  border-radius: var(--ds-radius-sm);
  border: 1px solid var(--ds-border);
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
}
.layout-col--video .video-card :deep(.el-card__header) {
  padding: var(--ds-space-2) var(--ds-space-3);
  min-height: auto;
  flex-shrink: 0;
}
.layout-col--video .video-card :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: var(--ds-space-2) var(--ds-space-3);
}

.video-hints {
  flex: 0 0 auto;
  max-height: min(120px, 22vh);
  min-height: 0;
  margin-top: var(--ds-space-2);
  padding-top: var(--ds-space-1);
  border-top: 1px solid var(--ds-border-light);
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
  background: #0a0a0a;
  border-radius: var(--ds-radius-sm);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  isolation: isolate;
  transform: translateZ(0);
  backface-visibility: hidden;
}
.stream-stage :deep(.el-empty) {
  padding: var(--ds-space-3) var(--ds-space-2);
}
.stream-stage :deep(.el-empty__description) {
  margin-top: var(--ds-space-2);
}

.stream-hint {
  width: 100%;
  max-width: 100%;
  flex-shrink: 0;
}
.stream-hint :deep(.el-alert__content) {
  font-size: var(--ds-text-sm);
}

.hints-body {
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-2);
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
  border-radius: var(--ds-radius-sm);
  border: 1px solid var(--ds-border);
}
.compact-panel :deep(.el-card__header) {
  padding: 5px var(--ds-space-3);
  min-height: auto;
  flex-shrink: 0;
}
.compact-panel :deep(.el-card__body) {
  padding: var(--ds-space-2) var(--ds-space-3);
}

.status-card {
  flex: 0 0 auto;
}
.status-card :deep(.el-card__body) {
  overflow: visible;
  padding-top: var(--ds-space-2);
  padding-bottom: var(--ds-space-2);
}
.status-desc :deep(.el-descriptions__body) {
  background: transparent;
}
.status-desc :deep(.el-descriptions__label),
.status-desc :deep(.el-descriptions__content) {
  padding: var(--ds-space-2) var(--ds-space-3) !important;
  font-size: var(--ds-text-sm);
}

.drive-mode-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--ds-space-2);
  margin-top: var(--ds-space-2);
  padding-top: var(--ds-space-2);
  border-top: 1px solid var(--ds-border-light);
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
.gimbal-preset-row {
  flex-wrap: wrap;
  align-items: center;
}
.gimbal-preset-rg {
  flex: 1;
  min-width: 0;
}
.param-row {
  display: flex;
  align-items: center;
  gap: var(--ds-space-2);
  margin-bottom: var(--ds-space-2);
}
.param-row:last-of-type {
  margin-bottom: var(--ds-space-2);
}
.param-row-label {
  flex: 0 0 5.25rem;
  font-size: var(--ds-text-sm);
  color: var(--ds-text-secondary);
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
  font-size: var(--ds-text-sm);
  font-variant-numeric: tabular-nums;
  color: var(--ds-text-primary);
  font-weight: 500;
}
.panel-divider {
  margin: 4px 0 10px !important;
}

.control-card {
  border-radius: var(--ds-radius-sm);
  flex: 1 1 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.control-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ds-space-2);
  flex-wrap: wrap;
}
.control-card-head--inline {
  flex-wrap: nowrap;
  gap: var(--ds-space-2);
}
.control-card-head-title {
  flex: 0 1 auto;
  min-width: 0;
  margin: 0;
  font-size: var(--ds-text-sm);
  font-weight: 600;
  line-height: 1.2;
  white-space: nowrap;
}
.control-mode-toggle {
  flex-shrink: 0;
}
.control-mode-toggle--triple {
  flex-wrap: nowrap;
  justify-content: flex-end;
  max-width: 100%;
}
.control-mode-toggle--triple :deep(.el-radio-button__inner) {
  padding: 4px 6px;
  font-size: var(--ds-text-xs);
  font-weight: 600;
}
.control-card :deep(.el-card__header) {
  padding: 5px var(--ds-space-3);
  min-height: auto;
  flex-shrink: 0;
}
.control-card :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: var(--ds-space-2) var(--ds-space-3) var(--ds-space-3);
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
  margin-bottom: var(--ds-space-1);
}
.dpad-center {
  flex: 1 1 0;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--ds-space-1) 2px var(--ds-space-2);
}

.dpad {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--ds-space-2);
  flex: 0 0 auto;
}
.dpad-row {
  display: flex;
  gap: var(--ds-space-2);
  align-items: center;
  justify-content: center;
}
.layout-col--side .side-lower .dpad-cell {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
}
.layout-col--side .side-lower .dpad-btn {
  width: 40px;
  height: 40px;
}
.layout-col--side .side-lower .stop-btn {
  width: 42px;
  height: 42px;
}

.dpad-cell {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.dpad-btn {
  width: 40px;
  height: 40px;
  min-height: 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: var(--ds-radius-sm);
  padding: 2px 3px;
}
.dpad-btn :deep(.el-button__content) {
  flex-direction: column;
  gap: 0;
  line-height: 1.05;
}
.dpad-btn :deep(.el-icon) {
  margin: 0;
}
.dpad-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.02em;
  margin-top: 1px;
  line-height: 1.05;
  color: #fff;
  text-shadow: 0 1px 1px rgba(0, 0, 0, 0.35);
}
.stop-btn .dpad-label {
  color: #1d2129;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.35);
}
.stop-btn {
  border-radius: var(--ds-radius-full);
  width: 42px;
  height: 42px;
  min-height: 42px;
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
  margin-bottom: var(--ds-space-2);
}
.arm-param-row:last-of-type {
  margin-bottom: var(--ds-space-1);
}
.arm-label {
  color: #7c3aed;
  font-weight: 500;
}
.arm-val {
  color: #6d28d9;
}
.arm-slider-wrap :deep(.el-slider__runway) {
  background-color: rgba(124, 58, 237, 0.1);
}
.arm-slider-wrap :deep(.el-slider__bar) {
  background-color: #7c3aed;
}
.arm-slider-wrap :deep(.el-slider__button) {
  border-color: #7c3aed;
}

.arm-actions-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-3);
  padding: var(--ds-space-2) 2px var(--ds-space-2);
  overflow: hidden;
}
.arm-actions-toolbar {
  display: flex;
  gap: var(--ds-space-2);
  align-items: center;
  flex-shrink: 0;
  padding: 0 2px;
}
.arm-toolbar-reset {
  flex: 1;
  height: 38px;
  border-radius: var(--ds-radius-sm);
  font-weight: 600;
  font-size: var(--ds-text-sm);
  letter-spacing: 0.02em;
  border: none;
  background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);
  box-shadow: 0 2px 6px rgba(124, 58, 237, 0.28);
}
.arm-toolbar-reset:hover {
  filter: brightness(1.08);
  box-shadow: 0 3px 10px rgba(124, 58, 237, 0.36);
}
.arm-toolbar-plus {
  height: 38px !important;
  padding: 0 var(--ds-space-3) !important;
  margin: 0 !important;
  border-radius: var(--ds-radius-sm);
  font-weight: 600;
  font-size: var(--ds-text-sm);
  color: #7c3aed;
  background: rgba(124, 58, 237, 0.06);
  border: 1.5px solid rgba(124, 58, 237, 0.2);
  transition: all var(--ds-transition);
}
.arm-toolbar-plus:hover {
  background: rgba(124, 58, 237, 0.12);
  border-color: rgba(124, 58, 237, 0.35);
  color: #6d28d9;
}
.arm-toolbar-plus span {
  margin-left: 3px;
}
.arm-actions-scroll {
  flex: 1 1 auto;
  min-height: 80px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.arm-actions-saved {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-2);
  padding: 2px 2px var(--ds-space-1);
}
.arm-saved-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ds-space-2);
  padding: var(--ds-space-2) var(--ds-space-3);
  background: linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%);
  border-radius: var(--ds-radius-sm);
  border: 1px solid rgba(124, 58, 237, 0.1);
  transition: all var(--ds-transition);
}
.arm-saved-card:hover {
  border-color: rgba(124, 58, 237, 0.25);
  box-shadow: 0 2px 8px rgba(124, 58, 237, 0.1);
  background: linear-gradient(135deg, #f3e8ff 0%, #ede9fe 100%);
}
.arm-saved-info {
  display: flex;
  align-items: center;
  gap: var(--ds-space-2);
  flex: 1;
  min-width: 0;
}
.arm-saved-icon {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  color: #7c3aed;
  background: rgba(124, 58, 237, 0.08);
  border-radius: var(--ds-radius-sm);
}
.arm-saved-name {
  font-size: var(--ds-text-sm);
  font-weight: 600;
  color: var(--ds-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.arm-saved-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}
.arm-saved-run {
  border-radius: var(--ds-radius-sm) !important;
  font-weight: 600 !important;
  font-size: var(--ds-text-sm) !important;
  padding: 4px var(--ds-space-3) !important;
  height: 28px !important;
  background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%) !important;
  border: none !important;
  box-shadow: 0 1px 4px rgba(124, 58, 237, 0.25);
}
.arm-saved-run:hover {
  filter: brightness(1.08);
}
.arm-saved-del {
  flex-shrink: 0;
  font-weight: 500;
  font-size: var(--ds-text-sm) !important;
  padding: 4px var(--ds-space-2) !important;
}
.arm-actions-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--ds-space-2);
  min-height: 90px;
  padding: var(--ds-space-5) var(--ds-space-3);
  border-radius: var(--ds-radius-md);
  border: 1.5px dashed rgba(124, 58, 237, 0.15);
  background: rgba(250, 245, 255, 0.5);
}
.arm-actions-empty-icon {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--ds-radius-full);
  background: rgba(124, 58, 237, 0.06);
}
.arm-actions-empty-text {
  font-size: var(--ds-text-sm);
  color: var(--ds-text-secondary);
  font-weight: 500;
}
.arm-actions-empty-hint {
  font-size: var(--ds-text-xs);
  color: var(--ds-text-muted);
}

.add-action-dialog :deep(.el-dialog) {
  border-radius: var(--ds-radius-lg);
  overflow: hidden;
}
.add-action-dialog :deep(.el-dialog__header) {
  padding: var(--ds-space-4) var(--ds-space-5) var(--ds-space-3);
  margin-right: 0;
  border-bottom: 1px solid rgba(124, 58, 237, 0.1);
  background: linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%);
}
.add-action-dialog :deep(.el-dialog__title) {
  font-weight: 700;
  font-size: 15px;
  color: var(--ds-text-primary);
}
.add-action-dialog :deep(.el-dialog__body) {
  padding: var(--ds-space-4) var(--ds-space-5) var(--ds-space-2);
}
.add-action-form :deep(.el-form-item__label) {
  font-weight: 600;
  font-size: var(--ds-text-sm);
  color: var(--ds-text-primary);
}
.add-action-name-item {
  margin-bottom: var(--ds-space-3);
}
.add-action-section {
  margin-bottom: var(--ds-space-3);
}
.add-action-section--boxed {
  padding: var(--ds-space-3);
  border-radius: var(--ds-radius-md);
  background: #faf5ff;
  border: 1px solid rgba(124, 58, 237, 0.08);
}
.add-action-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ds-space-2);
  margin-bottom: var(--ds-space-3);
}
.add-action-section-title {
  font-size: var(--ds-text-sm);
  font-weight: 700;
  color: #7c3aed;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: var(--ds-space-2);
  display: block;
}
.add-action-section-head .add-action-section-title {
  margin-bottom: 0;
}
.joint-order-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--ds-space-2) var(--ds-space-3);
}
.joint-order-cell {
  display: flex;
  align-items: center;
  gap: var(--ds-space-2);
}
.joint-order-badge {
  flex-shrink: 0;
  min-width: 22px;
  height: 22px;
  padding: 0 5px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: var(--ds-text-xs);
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);
  border-radius: var(--ds-radius-sm);
}
.joint-order-select {
  width: 100% !important;
}
.add-action-speed-wrap {
  display: flex;
  align-items: center;
  gap: var(--ds-space-3);
}
.add-action-speed-wrap .el-slider {
  flex: 1;
}
.add-action-speed-wrap :deep(.el-slider__runway) {
  background-color: rgba(124, 58, 237, 0.1);
}
.add-action-speed-wrap :deep(.el-slider__bar) {
  background-color: #7c3aed;
}
.add-action-speed-wrap :deep(.el-slider__button) {
  border-color: #7c3aed;
}
.add-action-speed-val {
  flex-shrink: 0;
  min-width: 32px;
  text-align: right;
  font-size: var(--ds-text-sm);
  font-weight: 600;
  color: #6d28d9;
}
.add-action-angles-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--ds-space-2) var(--ds-space-3);
}
.add-action-angle-cell {
  display: flex;
  align-items: center;
  gap: var(--ds-space-2);
}
.add-action-angle-label {
  font-size: var(--ds-text-sm);
  font-weight: 700;
  color: #7c3aed;
  flex-shrink: 0;
  min-width: 20px;
}
.add-action-angle-input {
  width: 100% !important;
}
.add-action-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--ds-space-3);
  width: 100%;
}
.add-action-dialog-footer .el-button--primary {
  background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);
  border: none;
  box-shadow: 0 2px 6px rgba(124, 58, 237, 0.25);
}

.arm-presets-block {
  margin-top: var(--ds-space-2);
  padding-top: var(--ds-space-2);
  border-top: 1px solid rgba(124, 58, 237, 0.1);
}
.arm-presets-head {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: var(--ds-space-2);
}
.arm-presets-title {
  font-size: var(--ds-text-sm);
  font-weight: 600;
  color: #6d28d9;
}
.arm-presets-hint {
  line-height: 1.35;
}
.arm-presets-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ds-space-2);
  margin-bottom: var(--ds-space-2);
}
.arm-presets-chips {
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-1);
}
.arm-preset-item {
  display: flex;
  align-items: center;
  gap: var(--ds-space-1);
  flex-wrap: wrap;
}
.arm-presets-empty {
  padding: var(--ds-space-1) 0;
}
.reset-angles-grid {
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-3);
}
.reset-angle-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ds-space-3);
}
.reset-angle-label {
  font-size: var(--ds-text-sm);
  color: var(--ds-text-secondary);
  flex-shrink: 0;
}

/* ── Responsive ── */
@media (max-width: 767px) {
  .inspection-layout {
    flex-direction: column;
    overflow-y: auto;
    overflow-x: hidden;
    gap: var(--ds-space-3);
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
