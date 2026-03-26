<template>
  <div class="dashboard">
    <h2 class="page-title">环境监测</h2>

    <!-- 实时数据卡片 -->
    <el-row :gutter="20" class="card-row">
      <el-col :span="8">
        <el-card shadow="hover" class="data-card temp-card">
          <div class="card-header">
            <el-icon :size="28" color="#F56C6C"><Sunny /></el-icon>
            <span class="card-label">温度</span>
          </div>
          <div class="card-value">{{ latest ? latest.temperature.toFixed(1) : '--' }}<span class="unit"> &#8451;</span></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="data-card hum-card">
          <div class="card-header">
            <el-icon :size="28" color="#409EFF"><Drizzling /></el-icon>
            <span class="card-label">湿度</span>
          </div>
          <div class="card-value">{{ latest ? latest.humidity.toFixed(1) : '--' }}<span class="unit"> %RH</span></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="data-card light-card">
          <div class="card-header">
            <el-icon :size="28" color="#E6A23C"><Sunrise /></el-icon>
            <span class="card-label">光照</span>
          </div>
          <div class="card-value">{{ latest ? latest.light.toFixed(0) : '--' }}<span class="unit"> Lux</span></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 趋势图表 -->
    <el-card shadow="hover" class="chart-card">
      <template #header>
        <div class="chart-header">
          <span>数据趋势</span>
          <el-date-picker
            v-model="timeRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            size="small"
            @change="fetchHistory"
          />
        </div>
      </template>
      <div ref="chartRef" class="chart-container"></div>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref, inject, onUnmounted, nextTick } from "vue";
import { Sunny, Drizzling, Sunrise } from "@element-plus/icons-vue";
import * as echarts from "echarts";
import { sensorApi } from "../api/sensor";

const ws = inject("ws");
const latest = ref(null);

/* ---------- 图表 ---------- */
const chartRef = ref(null);
let chart = null;

// 实时数据缓存（用于图表滚动追加）
const MAX_POINTS = 60;
const timestamps = ref([]);
const temps = ref([]);
const hums = ref([]);
const lights = ref([]);

function initChart() {
  chart = echarts.init(chartRef.value);
  chart.setOption({
    tooltip: { trigger: "axis" },
    legend: { data: ["温度(℃)", "湿度(%RH)", "光照(Lux)"] },
    grid: { left: 50, right: 30, top: 40, bottom: 30 },
    xAxis: { type: "category", data: timestamps.value, boundaryGap: false },
    yAxis: [
      { type: "value", name: "温度/湿度", position: "left" },
      { type: "value", name: "光照", position: "right" },
    ],
    series: [
      { name: "温度(℃)", type: "line", smooth: true, data: temps.value, itemStyle: { color: "#F56C6C" } },
      { name: "湿度(%RH)", type: "line", smooth: true, data: hums.value, itemStyle: { color: "#409EFF" } },
      { name: "光照(Lux)", type: "line", smooth: true, yAxisIndex: 1, data: lights.value, itemStyle: { color: "#E6A23C" } },
    ],
  });
}

function pushChartPoint(data) {
  const t = data.timestamp
    ? new Date(typeof data.timestamp === "number" ? data.timestamp : data.timestamp).toLocaleTimeString()
    : new Date().toLocaleTimeString();

  timestamps.value.push(t);
  temps.value.push(data.temperature);
  hums.value.push(data.humidity);
  lights.value.push(data.light);

  if (timestamps.value.length > MAX_POINTS) {
    timestamps.value.shift();
    temps.value.shift();
    hums.value.shift();
    lights.value.shift();
  }

  chart?.setOption({
    xAxis: { data: timestamps.value },
    series: [
      { data: temps.value },
      { data: hums.value },
      { data: lights.value },
    ],
  });
}

/* ---------- 历史查询 ---------- */
const timeRange = ref([
  new Date(Date.now() - 60 * 60 * 1000),
  new Date(),
]);

async function fetchHistory() {
  if (!timeRange.value || timeRange.value.length < 2) return;
  try {
    const res = await sensorApi.getHistory({
      start_time: timeRange.value[0].toISOString(),
      end_time: timeRange.value[1].toISOString(),
    });

    timestamps.value = [];
    temps.value = [];
    hums.value = [];
    lights.value = [];

    (res || []).forEach((d) => {
      timestamps.value.push(new Date(d.timestamp).toLocaleTimeString());
      temps.value.push(d.temperature);
      hums.value.push(d.humidity);
      lights.value.push(d.light);
    });

    chart?.setOption({
      xAxis: { data: timestamps.value },
      series: [
        { data: temps.value },
        { data: hums.value },
        { data: lights.value },
      ],
    });
  } catch {
    /* 静默 */
  }
}

/* ---------- 生命周期 ---------- */
onMounted(async () => {
  // 获取最新数据
  try {
    latest.value = await sensorApi.getLatest();
  } catch { /* 静默 */ }

  await nextTick();
  initChart();
  await fetchHistory();

  // WebSocket 实时更新
  ws.on("sensor_data", (payload) => {
    latest.value = {
      device_id: payload.deviceId || "dev_001",
      temperature: payload.temperature,
      humidity: payload.humidity,
      light: payload.light,
      timestamp: payload.timestamp,
    };
    pushChartPoint(latest.value);
  });
});

// 窗口缩放时重绘图表
function handleResize() { chart?.resize(); }
window.addEventListener("resize", handleResize);
onUnmounted(() => {
  window.removeEventListener("resize", handleResize);
  chart?.dispose();
});
</script>

<style scoped>
.dashboard { }

.page-title {
  margin: 0 0 20px 0;
  font-size: 20px;
  color: #303133;
}

.card-row { margin-bottom: 20px; }

.data-card {
  text-align: center;
  border-radius: 8px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-bottom: 12px;
}

.card-label {
  font-size: 14px;
  color: #909399;
}

.card-value {
  font-size: 36px;
  font-weight: 700;
  color: #303133;
}

.unit {
  font-size: 16px;
  font-weight: 400;
  color: #909399;
}

.chart-card { border-radius: 8px; }

.chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chart-container {
  width: 100%;
  height: 360px;
}
</style>
