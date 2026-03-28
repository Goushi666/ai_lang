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
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { alarmApi } from "../api/alarm";

const config = ref(null);
const saving = ref(false);

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

onMounted(load);
</script>

<style scoped>
.page-title {
  margin: 0 0 20px 0;
  font-size: 20px;
  color: #303133;
}
.settings-card {
  border-radius: 8px;
  max-width: 640px;
}
</style>
