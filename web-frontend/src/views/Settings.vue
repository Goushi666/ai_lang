<template>
  <div class="settings-page">
    <h2 class="page-title">系统设置</h2>

    <el-card shadow="hover" class="settings-card">
      <template #header><span>告警阈值配置</span></template>

      <el-form
        v-if="config"
        :model="config"
        label-width="120px"
        label-position="left"
        style="max-width: 480px"
      >
        <el-form-item label="温度阈值 (℃)">
          <el-input-number v-model="config.temperature_threshold" :min="0" :max="100" :precision="1" />
        </el-form-item>
        <el-form-item label="湿度阈值 (%RH)">
          <el-input-number v-model="config.humidity_threshold" :min="0" :max="100" :precision="1" />
        </el-form-item>
        <el-form-item label="光照阈值 (Lux)">
          <el-input-number v-model="config.light_threshold" :min="0" :max="65535" :precision="0" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="save" :loading="saving">保存配置</el-button>
        </el-form-item>
      </el-form>

      <el-skeleton :rows="4" v-else animated />
    </el-card>

    <el-card shadow="hover" class="settings-card danger-zone">
      <template #header><span>数据库维护</span></template>
      <p class="danger-hint">
        当前 SQLite（<code>app.db</code>）内两张业务表：传感器采样 <code>sensor_data</code>、环境异常落库
        <code>environment_anomalies</code>。下方可一键清空，<strong>不可恢复</strong>。
      </p>
      <div class="purge-checks">
        <el-checkbox v-model="purgeSensor">清空传感器采样（sensor_data）</el-checkbox>
        <el-checkbox v-model="purgeAnomalies">清空环境异常记录（environment_anomalies）</el-checkbox>
      </div>
      <el-button
        type="danger"
        class="btn-purge-solid"
        :disabled="!purgeSensor && !purgeAnomalies"
        :loading="purging"
        @click="confirmPurge"
      >
        一键清空所选表
      </el-button>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { alarmApi } from "../api/alarm";
import { adminApi } from "../api/admin";

const config = ref(null);
const saving = ref(false);
const purging = ref(false);
const purgeSensor = ref(true);
const purgeAnomalies = ref(true);

async function load() {
  try {
    config.value = await alarmApi.getConfig();
  } catch {
    ElMessage.error("加载配置失败");
  }
}

async function save() {
  if (!config.value) return;
  saving.value = true;
  try {
    await alarmApi.updateConfig({
      temperature_threshold: Number(config.value.temperature_threshold),
      humidity_threshold: Number(config.value.humidity_threshold),
      light_threshold: Number(config.value.light_threshold),
    });
    ElMessage.success("配置已保存");
    await load();
  } catch {
    ElMessage.error("保存失败");
  } finally {
    saving.value = false;
  }
}

async function confirmPurge() {
  if (!purgeSensor.value && !purgeAnomalies.value) return;
  const parts = [];
  if (purgeSensor.value) parts.push("sensor_data（全部采样）");
  if (purgeAnomalies.value) parts.push("environment_anomalies（异常落库）");
  try {
    await ElMessageBox.confirm(
      `将永久删除：${parts.join("、")}。此操作不可恢复，是否继续？`,
      "危险操作",
      { type: "error", confirmButtonText: "确认清空", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }
  purging.value = true;
  try {
    const res = await adminApi.purgeData({
      sensor_data: purgeSensor.value,
      environment_anomalies: purgeAnomalies.value,
    });
    ElMessage.success(
      `已清空：采样 ${res.sensor_data_deleted ?? 0} 条，异常记录 ${res.environment_anomalies_deleted ?? 0} 条`,
    );
  } catch {
    ElMessage.error("清空失败，请确认后端可用");
  } finally {
    purging.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.page-title {
  margin: 0 0 var(--ds-space-5) 0;
  font-size: var(--ds-text-xl);
  font-weight: 700;
  color: var(--ds-text-primary);
}
.settings-card {
  border-radius: var(--ds-radius-md);
  max-width: 640px;
  margin-bottom: var(--ds-space-4);
  border: 1px solid var(--ds-border-light);
}
.danger-zone :deep(.el-card__header) {
  color: #b91c1c;
  font-weight: 600;
}
.danger-hint {
  font-size: var(--ds-text-sm);
  color: var(--ds-text-secondary);
  line-height: 1.6;
  margin: 0 0 var(--ds-space-3) 0;
}
.danger-hint code {
  font-size: var(--ds-text-xs);
  padding: 1px 4px;
  background: var(--ds-danger-light);
  border-radius: 3px;
  font-family: var(--ds-font-mono);
}
.purge-checks {
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-2);
  margin-bottom: var(--ds-space-3);
}
.btn-purge-solid {
  background-color: #dc2626 !important;
  border-color: #dc2626 !important;
  color: #fff !important;
}
.btn-purge-solid:hover,
.btn-purge-solid:focus {
  background-color: #ef4444 !important;
  border-color: #ef4444 !important;
  color: #fff !important;
}
.btn-purge-solid:active {
  background-color: #b91c1c !important;
  border-color: #b91c1c !important;
  color: #fff !important;
}
.btn-purge-solid.is-disabled {
  opacity: 0.55;
}
</style>
