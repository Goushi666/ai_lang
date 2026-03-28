<template>
  <div class="analysis-page">
    <h2 class="page-title">环境分析</h2>
    <p class="page-desc">
      选好时间段后点「计算」：会显示<strong>这段时间里温度的最低、最高、平均、中间值（中位数）</strong>，湿度和光照同样；
      若有连续多点超过设定阈值，会在<strong>下方橙色图里用浅色标出</strong>，并列出说明。
      温度预测由后端根据配置选用 <strong>LSTM</strong>（需有足够逐小时聚合数据）或<strong>阻尼直线外推</strong>，具体算法与免责说明见结果区「推算」小节。
    </p>

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
        <el-select v-model="bucket" placeholder="按小时拆开" style="width: 140px">
          <el-option label="整段汇总" value="none" />
          <el-option label="按小时分别算" value="1h" />
        </el-select>
        <el-input
          v-model="deviceId"
          clearable
          placeholder="只查某台设备时填写编号，不填则全部合并"
          style="width: 260px"
        />
        <el-button type="primary" :loading="loading" @click="fetchSummary">计算</el-button>
        <el-button :loading="loadingRun" @click="runAnalysis">再算一遍</el-button>

        <el-dropdown split-button type="default" @click="doExport('csv', 'full')" :loading="loadingExport">
          导出当前时段
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="doExport('csv', 'full')">表格：全部采样（CSV）</el-dropdown-item>
              <el-dropdown-item @click="doExport('csv', 'anomalies')">表格：仅异常（CSV）</el-dropdown-item>
              <el-dropdown-item divided @click="doExport('json', 'full')">给程序用：全文（JSON）</el-dropdown-item>
              <el-dropdown-item @click="doExport('json', 'anomalies')">给程序用：仅异常（JSON）</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-card>

    <el-card v-if="summary" shadow="hover" class="result-card">
      <template #header>
        <div class="card-head">
          <span class="head-title">本时段结果</span>
          <el-tag v-if="summary.downsampled" type="warning" size="small">数据太多，统计时做了抽样</el-tag>
        </div>
      </template>

      <el-alert
        v-if="summary.anomalies?.length"
        type="warning"
        show-icon
        :closable="false"
        class="mb-alert"
        :title="'本时段发现 ' + summary.anomalies.length + ' 段异常（连续多点超阈值）'"
        description="请看下方曲线上的浅色区间与表格说明。"
      />
      <el-alert
        v-else-if="summary.summary_code === 'insufficient_data'"
        type="info"
        show-icon
        :closable="false"
        class="mb-alert"
        title="本时段里用来计算的数据条数太少，只显示上面的汇总数字，不做「连续超阈」判断。"
      />
      <el-alert
        v-else
        type="success"
        show-icon
        :closable="false"
        class="mb-alert"
        title="本时段未发现「连续多点超阈值」的情况。"
      />

      <div class="label-block">
        <div class="label-main">{{ summary.summary_label }}</div>
        <div class="label-sub">
          参与统计 {{ summary.sample_count_used }} 条
          <template v-if="summary.sample_count_in_window !== summary.sample_count_used">
            （库里本时段共 {{ summary.sample_count_in_window }} 条）</template>
          · 连续 {{ summary.streak_points_required }} 个点超阈算一段异常
        </div>
        <el-collapse class="tech-collapse">
          <el-collapse-item title="技术用简短代号（一般不用看）" name="1">
            <code>{{ summary.summary_code }}</code>
          </el-collapse-item>
        </el-collapse>
      </div>

      <el-descriptions v-if="summary.thresholds" :column="3" border class="thr-desc" title="当前阈值（用于判断是否异常）">
        <el-descriptions-item label="温度">{{ summary.thresholds.temperature_c }} ℃</el-descriptions-item>
        <el-descriptions-item label="湿度">{{ summary.thresholds.humidity_percent }} %RH</el-descriptions-item>
        <el-descriptions-item label="光照">{{ summary.thresholds.light_lux }} lx</el-descriptions-item>
      </el-descriptions>

      <div class="section-title">数字一览（最低 / 最高 / 平均 / 中间值）</div>
      <p class="hint-inline">中间值：有一半的采样比它低、一半比它高，比单纯平均更不怕极端值干扰。</p>
      <el-table :data="aggregateRows" size="small" border style="width: 100%; max-width: 800px">
        <el-table-column prop="name" label="项目" width="130" />
        <el-table-column prop="count" label="用了多少个点" width="120" />
        <el-table-column prop="min" label="最低" width="90" />
        <el-table-column prop="max" label="最高" width="90" />
        <el-table-column prop="avg" label="平均" width="90" />
        <el-table-column prop="median" label="中间值" width="90" />
      </el-table>

      <div class="section-title">温度曲线与异常区间</div>
      <p class="hint-inline">实线：这段时间实际记录的温度；浅色竖条：判为异常的时间段；虚线：{{ forecastChartHint }}</p>
      <div v-if="summary.chart_points?.length" ref="chartRef" class="chart-box" />
      <el-empty v-else description="本时段没有可画曲线的数据" />

      <div v-if="summary.temperature_forecast?.hours?.length" class="section-title">{{ forecastSectionTitle }}</div>
      <p v-if="summary.temperature_forecast" class="hint-inline">{{ summary.temperature_forecast.method_zh }} {{ summary.temperature_forecast.disclaimer_zh }}</p>
      <p v-if="summary.temperature_forecast?.anchor_time_iso" class="hint-inline forecast-anchor">
        推算基准为<strong>查询时段内最后一条采样</strong>（不是「当前时刻」）：{{ formatIsoLocal(summary.temperature_forecast.anchor_time_iso) }}，
        当时实测约 <strong>{{ summary.temperature_forecast.last_observed_temperature_c }} ℃</strong>。
        表格<strong>第 1 行</strong>即「该时刻之后第 1 小时」的推算温度，共
        {{ summary.temperature_forecast.horizon_hours ?? summary.temperature_forecast.hours.length }} 步、约覆盖末条采样后连续
        {{ summary.temperature_forecast.horizon_hours ?? summary.temperature_forecast.hours.length }} 小时。
        曲线上实线末端与虚线起点之间会空出最多约 1 小时，属正常（虚线从末条 +1h 开始）。
      </p>
      <el-table
        v-if="summary.temperature_forecast?.hours?.length"
        :data="summary.temperature_forecast.hours"
        size="small"
        border
        max-height="240"
        style="width: 100%; max-width: 520px"
      >
        <el-table-column prop="hours_after_last_sample" label="末条之后第几小时" width="140" />
        <el-table-column prop="time_iso" label="对应时刻" min-width="200" />
        <el-table-column prop="temperature_c" label="推算温度℃" width="110" />
      </el-table>

      <div v-if="summary.lines_plain?.length" class="section-title">文字说明</div>
      <ol v-if="summary.lines_plain?.length" class="plain-list">
        <li v-for="(line, i) in summary.lines_plain" :key="i">{{ line }}</li>
      </ol>

      <div v-if="summary.buckets?.length" class="section-title">按小时拆开</div>
      <el-collapse v-if="summary.buckets?.length">
        <el-collapse-item
          v-for="(b, i) in summary.buckets"
          :key="i"
          :title="'从 ' + b.bucket_start + ' 起这一小时'"
        >
          <el-table :data="bucketAggRows(b)" size="small" border>
            <el-table-column prop="name" label="项目" width="130" />
            <el-table-column prop="count" label="点数" width="90" />
            <el-table-column prop="min" label="最低" />
            <el-table-column prop="max" label="最高" />
            <el-table-column prop="avg" label="平均" />
            <el-table-column prop="median" label="中间值" />
          </el-table>
        </el-collapse-item>
      </el-collapse>

      <div v-if="summary.anomalies?.length" class="section-title">异常片段明细</div>
      <el-table
        v-if="summary.anomalies?.length"
        :data="summary.anomalies"
        size="small"
        border
        style="width: 100%; margin-top: 8px"
      >
        <el-table-column prop="detail_zh" label="说明" min-width="300" />
        <el-table-column prop="device_id" label="设备" width="120" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">{{ metricLabel(row.metric) }}</template>
        </el-table-column>
        <el-table-column prop="peak" label="这段最高读数" width="110" />
        <el-table-column prop="threshold" label="阈值" width="80" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import * as echarts from "echarts";
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { analysisApi } from "../api/analysis";

const metricNames = {
  temperature: "温度",
  humidity: "湿度",
  light: "光照",
};

function metricLabel(m) {
  return metricNames[m] || m;
}

/** ISO 字符串转本地可读时间（浏览器时区） */
function formatIsoLocal(iso) {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso;
  return new Date(t).toLocaleString();
}

const timeRange = ref([
  new Date(Date.now() - 24 * 60 * 60 * 1000),
  new Date(),
]);
const loading = ref(false);
const loadingRun = ref(false);
const loadingExport = ref(false);
const summary = ref(null);
const bucket = ref("none");
const deviceId = ref("");
const chartRef = ref(null);
let chartInst = null;

const forecastChartHint = computed(() => {
  const m = summary.value?.temperature_forecast?.method;
  if (m === "lstm") {
    return "LSTM 推算的未来温度（多步为自回归滚动，越远误差可能越大）";
  }
  return "按简单公式推算的未来约 24 小时";
});

const forecastSectionTitle = computed(() => {
  const n = summary.value?.temperature_forecast?.hours?.length || 0;
  if (summary.value?.temperature_forecast?.method === "lstm") {
    return n ? `未来 ${n} 步温度（LSTM，含滚动）` : "温度推算";
  }
  return n ? `未来约 ${n} 小时温度（推算）` : "温度推算";
});

const aggregateRows = computed(() => {
  const a = summary.value?.aggregate;
  if (!a) return [];
  return [
    { key: "temperature", name: "温度（℃）" },
    { key: "humidity", name: "湿度（%RH）" },
    { key: "light", name: "光照（lx）" },
  ].map(({ key, name }) => {
    const m = a[key] || {};
    return {
      name,
      count: m.count ?? "—",
      min: m.min ?? "—",
      max: m.max ?? "—",
      avg: m.avg ?? "—",
      median: m.median ?? "—",
    };
  });
});

function bucketAggRows(b) {
  const a = b.aggregate || {};
  return [
    { key: "temperature", name: "温度（℃）" },
    { key: "humidity", name: "湿度（%RH）" },
    { key: "light", name: "光照（lx）" },
  ].map(({ key, name }) => {
    const m = a[key] || {};
    return {
      name,
      count: m.count ?? "—",
      min: m.min ?? "—",
      max: m.max ?? "—",
      avg: m.avg ?? "—",
      median: m.median ?? "—",
    };
  });
}

function paramsFromRange() {
  if (!timeRange.value || timeRange.value.length < 2) return null;
  const p = {
    start_time: timeRange.value[0].toISOString(),
    end_time: timeRange.value[1].toISOString(),
  };
  if (bucket.value && bucket.value !== "none") {
    p.bucket = bucket.value;
  }
  const d = deviceId.value?.trim();
  if (d) {
    p.device_id = d;
  }
  return p;
}

function disposeChart() {
  if (chartInst) {
    chartInst.dispose();
    chartInst = null;
  }
}

function renderChart() {
  const s = summary.value;
  if (!chartRef.value || !s?.chart_points?.length) {
    disposeChart();
    return;
  }
  if (!chartInst) {
    chartInst = echarts.init(chartRef.value);
  }
  const hist = s.chart_points.map((p) => [p.time_ms, p.temperature]);
  const bandData = (s.chart_anomaly_bands || []).map((b) => [
    { xAxis: b.start_ms },
    { xAxis: b.end_ms },
  ]);
  const fc = s.temperature_forecast?.hours || [];
  const fcData = fc.map((h) => [Date.parse(h.time_iso), h.temperature_c]);

  const series = [
    {
      name: "已观测温度",
      type: "line",
      smooth: true,
      showSymbol: false,
      data: hist,
      itemStyle: { color: "#409eff" },
      markArea:
        bandData.length > 0
          ? {
              itemStyle: { color: "rgba(230, 162, 60, 0.22)" },
              label: { show: false },
              data: bandData,
            }
          : undefined,
    },
  ];
  if (fcData.length) {
    series.push({
      name: "推算温度",
      type: "line",
      smooth: false,
      showSymbol: false,
      lineStyle: { type: "dashed", color: "#67c23a" },
      data: fcData,
    });
  }

  chartInst.setOption(
    {
      tooltip: {
        trigger: "axis",
        formatter(params) {
          if (!params?.length) return "";
          const x = params[0].value[0];
          const t = new Date(x).toLocaleString();
          return params
            .map((p) => {
              const v = p.value[1];
              return `${p.marker}${p.seriesName}：${v != null ? v : "—"} ℃`;
            })
            .join("<br/>") + `<br/>${t}`;
        },
      },
      legend: { data: series.map((x) => x.name), bottom: 0 },
      grid: { left: 48, right: 24, top: 16, bottom: 40 },
      xAxis: { type: "time" },
      yAxis: { type: "value", name: "℃", scale: true },
      series,
    },
    true,
  );
}

watch(
  () => summary.value,
  () => {
    nextTick(() => renderChart());
  },
  { deep: true },
);

function onResize() {
  chartInst?.resize();
}

onMounted(() => {
  fetchSummary();
  window.addEventListener("resize", onResize);
});

onUnmounted(() => {
  window.removeEventListener("resize", onResize);
  disposeChart();
});

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
    ElMessage.error("获取失败");
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
    ElMessage.success("已算完");
  } catch (e) {
    ElMessage.error("请求失败");
  } finally {
    loadingRun.value = false;
  }
}

const exportNames = {
  "csv-full": "env_all_samples.csv",
  "csv-anomalies": "env_anomalies.csv",
  "json-full": "env_analysis_full.json",
  "json-anomalies": "env_anomalies_only.json",
};

async function doExport(format, scope) {
  const p = paramsFromRange();
  if (!p) {
    ElMessage.warning("请选择时间范围");
    return;
  }
  loadingExport.value = true;
  try {
    const blob = await analysisApi.exportBlob({
      ...p,
      format,
      scope,
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = exportNames[`${format}-${scope}`] || "export.bin";
    a.click();
    URL.revokeObjectURL(url);
    ElMessage.success("已下载");
  } catch (e) {
    ElMessage.error("导出失败");
  } finally {
    loadingExport.value = false;
  }
}
</script>

<style scoped>
.page-title {
  margin: 0 0 8px 0;
  font-size: 20px;
  color: #303133;
}
.page-desc {
  margin: 0 0 16px 0;
  font-size: 14px;
  color: #606266;
  line-height: 1.55;
  max-width: 960px;
}
.toolbar-card { margin-bottom: 16px; }
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}
.result-card { margin-bottom: 24px; }
.card-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.head-title { font-weight: 600; }
.mb-alert { margin-bottom: 14px; }
.label-block {
  margin-bottom: 16px;
  padding: 12px 14px;
  background: #f5f7fa;
  border-radius: 6px;
}
.label-main {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 6px;
}
.label-sub {
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
  margin-bottom: 8px;
}
.tech-collapse {
  border: none;
  --el-collapse-header-bg-color: transparent;
}
.thr-desc { margin-bottom: 16px; }
.section-title {
  margin: 20px 0 8px;
  font-weight: 600;
  color: #303133;
  font-size: 15px;
}
.hint-inline {
  margin: 0 0 10px 0;
  font-size: 13px;
  color: #909399;
  max-width: 920px;
  line-height: 1.5;
}
.chart-box {
  width: 100%;
  height: 380px;
  margin-bottom: 8px;
}
.plain-list {
  margin: 0 0 8px 0;
  padding-left: 1.25rem;
  color: #303133;
  line-height: 1.65;
  max-width: 960px;
}
.plain-list li { margin-bottom: 6px; }
</style>
