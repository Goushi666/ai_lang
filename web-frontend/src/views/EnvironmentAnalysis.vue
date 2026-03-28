<template>
  <div class="analysis-page">
    <h2 class="page-title">环境分析</h2>
    <el-alert
      title="框架占位"
      type="info"
      :closable="false"
      show-icon
      class="mb-4"
      description="以下为接口联调与展示骨架；聚合、分桶与规则引擎尚未实现，后端返回固定占位结构。"
    />

    <el-card shadow="hover" class="toolbar-card">
      <div class="toolbar">
        <el-date-picker
          v-model="timeRange"
          type="datetimerange"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          size="default"
        />
        <el-button type="primary" :loading="loading" @click="fetchSummary">获取摘要</el-button>
        <el-button :loading="loadingRun" @click="runAnalysis">重新分析 (POST)</el-button>
      </div>
    </el-card>

    <el-card v-if="summary" shadow="hover" class="result-card">
      <template #header>
        <span>分析结果（JSON 结构预览）</span>
        <el-tag v-if="summary.framework" type="warning" size="small" class="ml-2">framework</el-tag>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="summary_code">{{ summary.summary_code }}</el-descriptions-item>
        <el-descriptions-item label="device_id">{{ summary.device_id }}</el-descriptions-item>
        <el-descriptions-item label="时间窗" :span="2">
          {{ summary.window?.start }} — {{ summary.window?.end }}
        </el-descriptions-item>
      </el-descriptions>
      <div class="hints" v-if="summary.summary_hints?.length">
        <div class="hints-title">提示</div>
        <ul>
          <li v-for="(h, i) in summary.summary_hints" :key="i">{{ h }}</li>
        </ul>
      </div>
      <div class="agg-title">聚合（占位）</div>
      <el-table :data="aggregateRows" size="small" border style="width: 100%; max-width: 640px">
        <el-table-column prop="metric" label="指标" width="120" />
        <el-table-column prop="count" label="count" width="80" />
        <el-table-column prop="min" label="min" />
        <el-table-column prop="max" label="max" />
        <el-table-column prop="avg" label="avg" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { analysisApi } from "../api/analysis";

const timeRange = ref([
  new Date(Date.now() - 24 * 60 * 60 * 1000),
  new Date(),
]);
const loading = ref(false);
const loadingRun = ref(false);
const summary = ref(null);

const aggregateRows = computed(() => {
  const a = summary.value?.aggregate;
  if (!a) return [];
  return ["temperature", "humidity", "light"].map((k) => {
    const m = a[k] || {};
    return {
      metric: k,
      count: m.count ?? "—",
      min: m.min ?? "—",
      max: m.max ?? "—",
      avg: m.avg ?? "—",
    };
  });
});

function paramsFromRange() {
  if (!timeRange.value || timeRange.value.length < 2) return null;
  return {
    start_time: timeRange.value[0].toISOString(),
    end_time: timeRange.value[1].toISOString(),
  };
}

async function fetchSummary() {
  const p = paramsFromRange();
  if (!p) {
    ElMessage.warning("请选择时间范围");
    return;
  }
  loading.value = true;
  try {
    summary.value = await analysisApi.getSummary(p);
  } catch (e) {
    ElMessage.error("获取摘要失败");
    summary.value = null;
  } finally {
    loading.value = false;
  }
}

async function runAnalysis() {
  const p = paramsFromRange();
  if (!p) {
    ElMessage.warning("请选择时间范围");
    return;
  }
  loadingRun.value = true;
  try {
    summary.value = await analysisApi.runAnalysis(p);
    ElMessage.success("已触发（占位）");
  } catch (e) {
    ElMessage.error("请求失败");
  } finally {
    loadingRun.value = false;
  }
}

onMounted(() => {
  fetchSummary();
});
</script>

<style scoped>
.page-title {
  margin: 0 0 16px 0;
  font-size: 20px;
  color: #303133;
}
.mb-4 { margin-bottom: 16px; }
.toolbar-card { margin-bottom: 16px; }
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}
.result-card { margin-bottom: 24px; }
.ml-2 { margin-left: 8px; }
.hints { margin: 16px 0; }
.hints-title { font-weight: 600; margin-bottom: 8px; color: #606266; }
.agg-title { margin: 16px 0 8px; font-weight: 600; color: #606266; }
</style>
