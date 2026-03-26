<template>
  <div class="vehicle-control">
    <h2 class="page-title">车辆控制</h2>

    <el-row :gutter="20">
      <!-- 左侧：状态面板 -->
      <el-col :span="10">
        <el-card shadow="hover" class="status-card">
          <template #header><span>运行状态</span></template>
          <el-descriptions :column="1" border size="default" v-if="status">
            <el-descriptions-item label="连接状态">
              <el-tag :type="status.connected ? 'success' : 'danger'" size="small">
                {{ status.connected ? '已连接' : '未连接' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="运行模式">
              <el-tag :type="status.mode === 'auto' ? 'primary' : 'info'" size="small">
                {{ status.mode === 'auto' ? '自动循迹' : '手动控制' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="当前速度">{{ status.speed }}</el-descriptions-item>
            <el-descriptions-item label="左轮速度">{{ status.left_speed ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="右轮速度">{{ status.right_speed ?? 0 }}</el-descriptions-item>
          </el-descriptions>
          <el-skeleton :rows="4" v-else animated />
        </el-card>

        <!-- 速度控制 -->
        <el-card shadow="hover" class="speed-card">
          <template #header><span>速度设置</span></template>
          <div class="speed-row">
            <span class="speed-label">速度：{{ speed }}</span>
            <el-slider v-model="speed" :min="0" :max="100" :step="5" show-stops />
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：方向控制 -->
      <el-col :span="14">
        <el-card shadow="hover" class="control-card">
          <template #header><span>方向控制 <el-text type="info" size="small">(键盘 W/A/S/D 可用)</el-text></span></template>

          <!-- 十字形控制面板 -->
          <div class="dpad">
            <div class="dpad-row">
              <div class="dpad-cell"></div>
              <div class="dpad-cell">
                <el-button type="primary" size="large" class="dpad-btn" @click="send('forward')">
                  <el-icon :size="24"><Top /></el-icon>
                  <div class="dpad-label">前进</div>
                </el-button>
              </div>
              <div class="dpad-cell"></div>
            </div>
            <div class="dpad-row">
              <div class="dpad-cell">
                <el-button type="primary" size="large" class="dpad-btn" @click="send('left')">
                  <el-icon :size="24"><Back /></el-icon>
                  <div class="dpad-label">左转</div>
                </el-button>
              </div>
              <div class="dpad-cell">
                <el-button type="warning" size="large" class="dpad-btn stop-btn" @click="send('stop')">
                  <el-icon :size="24"><VideoPause /></el-icon>
                  <div class="dpad-label">停止</div>
                </el-button>
              </div>
              <div class="dpad-cell">
                <el-button type="primary" size="large" class="dpad-btn" @click="send('right')">
                  <el-icon :size="24"><Right /></el-icon>
                  <div class="dpad-label">右转</div>
                </el-button>
              </div>
            </div>
            <div class="dpad-row">
              <div class="dpad-cell"></div>
              <div class="dpad-cell">
                <el-button type="primary" size="large" class="dpad-btn" @click="send('backward')">
                  <el-icon :size="24"><Bottom /></el-icon>
                  <div class="dpad-label">后退</div>
                </el-button>
              </div>
              <div class="dpad-cell"></div>
            </div>
          </div>

          <!-- 紧急停止 -->
          <div class="emergency-row">
            <el-button type="danger" size="large" class="emergency-btn" @click="send('stop')">
              紧急停止
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { inject, onMounted, onUnmounted, ref } from "vue";
import { Top, Bottom, Back, Right, VideoPause } from "@element-plus/icons-vue";
import { vehicleApi } from "../api/vehicle";

const ws = inject("ws");
const status = ref(null);
const speed = ref(50);

async function refreshStatus() {
  try {
    status.value = await vehicleApi.getStatus();
  } catch { /* 静默 */ }
}

async function send(action) {
  await vehicleApi.sendControl({
    action,
    speed: speed.value,
    timestamp: Date.now(),
  });
}

/* ---------- 键盘控制 ---------- */
function handleKeydown(e) {
  const map = { w: "forward", s: "backward", a: "left", d: "right", " ": "stop" };
  const action = map[e.key.toLowerCase()];
  if (action) {
    e.preventDefault();
    send(action);
  }
}

/* ---------- 生命周期 ---------- */
onMounted(async () => {
  await refreshStatus();
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
});
</script>

<style scoped>
.vehicle-control { }

.page-title {
  margin: 0 0 20px 0;
  font-size: 20px;
  color: #303133;
}

.status-card { margin-bottom: 16px; border-radius: 8px; }
.speed-card  { border-radius: 8px; }
.control-card { border-radius: 8px; }

.speed-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.speed-label {
  font-size: 14px;
  color: #606266;
}

/* 十字形方向控制 */
.dpad {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px 0;
}
.dpad-row {
  display: flex;
  gap: 8px;
}
.dpad-cell {
  width: 90px;
  height: 90px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.dpad-btn {
  width: 80px;
  height: 80px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
}
.dpad-label {
  font-size: 12px;
  margin-top: 4px;
}
.stop-btn {
  border-radius: 50%;
  width: 80px;
  height: 80px;
}

/* 紧急停止 */
.emergency-row {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}
.emergency-btn {
  width: 200px;
  height: 50px;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 2px;
  border-radius: 25px;
}
</style>
