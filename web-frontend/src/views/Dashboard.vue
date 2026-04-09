<template>
  <div class="dashboard-fit">
    <h2 class="dash-title">环境监测</h2>

    <div class="dash-grid">
      <!-- 温度 -->
      <el-card class="g-m1 metric-card metric-temp" shadow="never" :body-style="{ padding: '14px 16px' }">
        <div class="metric-icon-wrap temp-bg">
          <el-icon :size="26" color="#fff"><Sunny /></el-icon>
        </div>
        <div class="metric-info">
          <span class="metric-label">温度</span>
          <div class="metric-value">
            {{ fmtTemp }}<span class="metric-unit">℃</span>
          </div>
        </div>
      </el-card>

      <!-- 湿度 -->
      <el-card class="g-m2 metric-card metric-hum" shadow="never" :body-style="{ padding: '14px 16px' }">
        <div class="metric-icon-wrap hum-bg">
          <el-icon :size="26" color="#fff"><Drizzling /></el-icon>
        </div>
        <div class="metric-info">
          <span class="metric-label">湿度</span>
          <div class="metric-value">
            {{ fmtHum }}<span class="metric-unit">%RH</span>
          </div>
        </div>
      </el-card>

      <!-- 光照 -->
      <el-card class="g-m3 metric-card metric-light" shadow="never" :body-style="{ padding: '14px 16px' }">
        <div class="metric-icon-wrap light-bg">
          <el-icon :size="26" color="#fff"><Sunrise /></el-icon>
        </div>
        <div class="metric-info">
          <span class="metric-label">光照</span>
          <div class="metric-value">
            {{ fmtLight }}<span class="metric-unit">lx</span>
          </div>
        </div>
      </el-card>

      <!-- 温度曲线 -->
      <el-card class="g-ct" shadow="never">
        <template #header>
          <div class="ch-hd ch-hd-row">
            <div class="ch-hd-text">
              温度（2 小时）
              <span class="ch-sub">实测 + 推算</span>
            </div>
            <div class="ch-zoom-bar" aria-label="温度图缩放">
              <el-tooltip content="时间轴放大（看更短时段）" placement="top">
                <el-button class="ch-zoom-btn" text size="small" @click="zoomTempTime('in')">
                  <el-icon><ZoomIn /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="时间轴缩小（看更长时段）" placement="top">
                <el-button class="ch-zoom-btn" text size="small" @click="zoomTempTime('out')">
                  <el-icon><ZoomOut /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="纵轴放大（突出小幅温度变化）" placement="top">
                <el-button class="ch-zoom-btn" text size="small" @click="zoomTempY('in')">
                  <el-icon><Top /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="纵轴缩小（恢复刻度范围）" placement="top">
                <el-button class="ch-zoom-btn" text size="small" @click="zoomTempY('out')">
                  <el-icon><Bottom /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="重置本图缩放" placement="top">
                <el-button class="ch-zoom-btn" text size="small" @click="resetTempZoom">
                  <el-icon><RefreshLeft /></el-icon>
                </el-button>
              </el-tooltip>
            </div>
          </div>
        </template>
        <div class="ch-body">
          <p v-if="timelineHint" class="ch-hint">{{ timelineHint }}</p>
          <p v-if="bandExplainHint" class="ch-hint ch-hint-sub">{{ bandExplainHint }}</p>
          <div ref="tempChartRef" class="chart-shell" />
        </div>
      </el-card>

      <!-- 湿度 / 光照曲线 -->
      <el-card class="g-ch" shadow="never">
        <template #header>
          <div class="ch-hd ch-hd-row">
            <div class="ch-hd-text">湿度与光照（2 小时）</div>
            <div class="ch-zoom-bar" aria-label="湿度光照图缩放">
              <el-tooltip content="时间轴放大" placement="top">
                <el-button class="ch-zoom-btn" text size="small" @click="zoomHumTime('in')">
                  <el-icon><ZoomIn /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="时间轴缩小" placement="top">
                <el-button class="ch-zoom-btn" text size="small" @click="zoomHumTime('out')">
                  <el-icon><ZoomOut /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="纵轴放大（湿度/光照刻度）" placement="top">
                <el-button class="ch-zoom-btn" text size="small" @click="zoomHumY('in')">
                  <el-icon><Top /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="纵轴缩小" placement="top">
                <el-button class="ch-zoom-btn" text size="small" @click="zoomHumY('out')">
                  <el-icon><Bottom /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="重置本图缩放" placement="top">
                <el-button class="ch-zoom-btn" text size="small" @click="resetHumZoom">
                  <el-icon><RefreshLeft /></el-icon>
                </el-button>
              </el-tooltip>
            </div>
          </div>
        </template>
        <div class="ch-body">
          <div ref="humChartRef" class="chart-shell" />
        </div>
      </el-card>

      <!-- 播报 + 异常 + 工具 -->
      <el-card class="g-bc" shadow="never" :body-style="{ padding: '10px 14px' }">
        <div class="bc-row">
          <div class="bc-content">
            <span class="bc-label">实时温度异常提示</span>
            <el-alert
              class="bc-alert"
              :type="tempAlertType"
              :title="tempAlertTitle"
              :closable="false"
              show-icon
            >
              <div class="bc-alert-body">
                <p v-for="(line, i) in tempAlertLines" :key="i" class="bc-line">{{ line }}</p>
              </div>
            </el-alert>
            <p v-if="anomalyBroadcast" class="bc-anomaly-hint">{{ anomalyBroadcast }}</p>
            <div v-if="anomalies.length" class="bc-anomaly-list">
              <div
                v-for="a in displayedAnomalies"
                :key="`${a.device_id}-${a.metric}-${a.start_time}`"
                class="bc-anomaly-pill"
                :title="a.detail_zh || a.metric"
              >
                {{ a.detail_zh || `${a.metric} 异常` }}
              </div>
            </div>
            <p v-else class="bc-anomaly-ok">近 24 小时无连续超阈异常记录</p>
            <div
              v-if="anomalies.length > ANOMALY_DISPLAY_MAX || latest?.timestamp"
              class="bc-anomaly-footer-row"
            >
              <span v-if="anomalies.length > ANOMALY_DISPLAY_MAX" class="bc-anomaly-truncate-hint">
                共 {{ anomalies.length }} 条异常片段，以下仅展示最近 {{ ANOMALY_DISPLAY_MAX }} 条
              </span>
              <span v-if="latest?.timestamp" class="bc-meta">最近上报：{{ formatTime(latest.timestamp) }}</span>
            </div>
          </div>
          <div class="bc-tools" aria-label="快捷操作">
            <div class="bc-tools-head">快捷操作</div>
            <div class="bc-tools-actions">
              <el-button
                class="bc-btn bc-btn-export"
                type="primary"
                :loading="exporting"
                @click="exportLast24h"
              >
                <el-icon class="bc-ico"><Download /></el-icon>
                <span>导出近24小时数据</span>
              </el-button>
              <el-button class="bc-btn bc-btn-refresh" @click="refreshAll">
                <el-icon class="bc-ico"><Refresh /></el-icon>
                <span>手动刷新</span>
              </el-button>
              <el-button
                class="bc-btn bc-btn-speak"
                type="success"
                :disabled="!canSpeakTempAlert"
                @click="speakTempAlert"
              >
                <el-icon class="bc-ico"><Microphone /></el-icon>
                <span>语音播报</span>
              </el-button>
            </div>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { computed, inject, nextTick, onMounted, onUnmounted, ref } from "vue";
import * as echarts from "echarts";
import { ElMessage } from "element-plus";
import {
  Sunny,
  Drizzling,
  Sunrise,
  Download,
  Refresh,
  Microphone,
  ZoomIn,
  ZoomOut,
  RefreshLeft,
  Top,
  Bottom,
} from "@element-plus/icons-vue";
import { sensorApi } from "../api/sensor";
import { monitoringApi } from "../api/monitoring";
import { alarmApi } from "../api/alarm";
import { formatDateTimeZh, parseBackendInstant, parseSensorPayloadTimestampMs } from "@/utils/datetime";

const ws = inject("ws");

const latest = ref(null);
const alarmConfig = ref(null);
const exporting = ref(false);
const timeline = ref(null);
/** 图表「过去推算」用：首次/手动刷新用接口值，轮询时用「旧未来」滚入合并，避免整条线随请求抖动 */
const displayPastPredicted = ref([]);
const anomalies = ref([]);
/** 实时异常条目标签最多展示条数（按片段结束时间取最近） */
const ANOMALY_DISPLAY_MAX = 8;
const tempChartRef = ref(null);
const humChartRef = ref(null);
let tempChart = null;
let humChart = null;
let pollTimer = null;

// 实时曲线数据缓冲（保留 2 小时）
const MAX_REALTIME_MS = 2 * 60 * 60 * 1000;
/** 单序列最多保留点数，避免历史接口极密采样撑爆内存与 ECharts */
const MAX_BUFFER_POINTS = 4500;
/** 绘图时下采样上限，显著降低 line/smooth 的 CPU */
const MAX_CHART_POINTS = 1600;
const tempRealtime = [];   // [{time_ms, value}]
const humRealtime = [];    // [{time_ms, value}]
const lightRealtime = [];  // [{time_ms, value}]

function pruneOld(arr) {
  const cutoff = Date.now() - MAX_REALTIME_MS;
  while (arr.length > 0 && arr[0].time_ms < cutoff) arr.shift();
}

/** 按索引均匀下采样，保持时间顺序，首尾保留 */
function thinSortedBuffer(arr, maxLen) {
  if (!arr || arr.length <= maxLen) return;
  const n = arr.length;
  const out = [];
  const denom = Math.max(1, maxLen - 1);
  for (let i = 0; i < maxLen; i++) {
    const idx = Math.min(n - 1, Math.round((i * (n - 1)) / denom));
    out.push(arr[idx]);
  }
  arr.splice(0, arr.length, ...out);
}

/** [[t,v],...] → 最多 maxN 点，供 ECharts 使用 */
function downsamplePairs(pairs, maxN) {
  if (!pairs || pairs.length <= maxN) return pairs || [];
  const n = pairs.length;
  const out = [];
  const denom = Math.max(1, maxN - 1);
  for (let i = 0; i < maxN; i++) {
    const idx = Math.min(n - 1, Math.round((i * (n - 1)) / denom));
    out.push(pairs[idx]);
  }
  return out;
}

function maybeThinBuffers() {
  thinSortedBuffer(tempRealtime, MAX_BUFFER_POINTS);
  thinSortedBuffer(humRealtime, MAX_BUFFER_POINTS);
  thinSortedBuffer(lightRealtime, MAX_BUFFER_POINTS);
}

/**
 * WebSocket 追加温湿光；若与缓冲区末尾 time_ms 相同则覆盖该点（不追加）。
 * 后端按 UTC 整秒合并时，同秒内 dht / light 分包会多次广播且时间戳毫秒相同；
 * 若每次都 push，会出现同 x 不同 y，ECharts 连成竖线，光照变化大时尤其明显；湿度不变则像「只有光照折一下」。
 */
function appendRealtimeTriplet(time_ms, temperature, humidity, light) {
  if (tempRealtime.length > 0 && tempRealtime[tempRealtime.length - 1].time_ms === time_ms) {
    const i = tempRealtime.length - 1;
    tempRealtime[i] = { time_ms, value: temperature };
    humRealtime[i] = { time_ms, value: humidity };
    lightRealtime[i] = { time_ms, value: light };
    return;
  }
  tempRealtime.push({ time_ms, value: temperature });
  humRealtime.push({ time_ms, value: humidity });
  lightRealtime.push({ time_ms, value: light });
}

/** WebSocket 高频推送时合并到下一帧只 setOption 一次 */
let chartUpdateRaf = 0;
function scheduleRealtimeCharts() {
  if (chartUpdateRaf) return;
  chartUpdateRaf = requestAnimationFrame(() => {
    chartUpdateRaf = 0;
    applyTempChart(timeline.value);
    applyHumChartRealtime();
  });
}

/* ---------- 格式化 ---------- */
const fmtTemp = computed(() => {
  const v = latest.value?.temperature;
  return v != null && Number.isFinite(Number(v)) ? Number(v).toFixed(1) : "--";
});
const fmtHum = computed(() => {
  const v = latest.value?.humidity;
  return v != null && Number.isFinite(Number(v)) ? Number(v).toFixed(1) : "--";
});
const fmtLight = computed(() => {
  const v = latest.value?.light;
  return v != null && Number.isFinite(Number(v)) ? Math.round(Number(v)) : "--";
});

/** 与系统设置中告警温度阈值对比，给出异常提示与处理建议 */
const tempAlertBlock = computed(() => {
  const cfg = alarmConfig.value;
  const d = latest.value;
  if (!cfg) {
    return {
      type: "info",
      title: "阈值未就绪",
      lines: ["正在加载告警阈值配置，请稍候；若长时间无数据请刷新页面。"],
    };
  }
  if (!d || !Number.isFinite(Number(d.temperature))) {
    return {
      type: "info",
      title: "暂无实时温度",
      lines: ["等待传感器上报温度数据后，将自动与设定阈值比对。"],
    };
  }
  const t = Number(d.temperature);
  const thr = Number(cfg.temperature_threshold);
  if (!Number.isFinite(thr)) {
    return {
      type: "warning",
      title: "阈值无效",
      lines: ["请在「系统设置」中检查温度阈值配置。"],
    };
  }
  if (t <= thr) {
    return {
      type: "success",
      title: "温度正常",
      lines: [
        `当前 ${t.toFixed(1)} ℃，未超过设定阈值 ${thr.toFixed(1)} ℃。`,
        "请继续观察曲线变化；若温升加快，可提前检查通风与设备散热。",
      ],
    };
  }
  return {
    type: "warning",
    title: "温度已超过阈值",
    lines: [
      `当前 ${t.toFixed(1)} ℃，已超过设定阈值 ${thr.toFixed(1)} ℃，请立即处置。`,
      "处理建议：检查井场通风与设备散热是否受阻；确认传感器未被阳光直射或靠近热源；持续偏高时请通知运维，必要时按规程停机排查。",
    ],
  };
});

const tempAlertType = computed(() => tempAlertBlock.value.type);
const tempAlertTitle = computed(() => tempAlertBlock.value.title);
const tempAlertLines = computed(() => tempAlertBlock.value.lines);

const canSpeakTempAlert = computed(() => tempAlertLines.value.length > 0);

const anomalyBroadcast = computed(() => {
  if (!anomalies.value.length) return "";
  const types = [...new Set(anomalies.value.map((a) => a.metric))];
  const names = types.map((t) => ({ temperature: "温度", humidity: "湿度", light: "光照" }[t] || t));
  return `注意：过去24小时存在${names.join("、")}超阈异常。`;
});

const displayedAnomalies = computed(() => {
  const list = (anomalies.value || []).slice();
  list.sort((a, b) => {
    const tb = Date.parse(b.end_time);
    const ta = Date.parse(a.end_time);
    return (Number.isNaN(tb) ? 0 : tb) - (Number.isNaN(ta) ? 0 : ta);
  });
  return list.slice(0, ANOMALY_DISPLAY_MAX);
});

const timelineHint = computed(() => timeline.value?.method_zh || "");

/** 说明「未来参考带」与 ECharts 叠层底序列（原 bandBase），避免图例/调试名误解 */
const bandExplainHint = computed(() => {
  const band = timeline.value?.future_band;
  if (!band?.length) return "";
  return "绿色浅带为「未来参考带」：表示未来推算的温度高低区间；另有一条以「__」开头的内部叠层序列，仅用于堆叠绘制该带，不是独立曲线。";
});

/** 过去推算滚动：用上一轮「未来」补当前窗口右段 */
const rollState = {
  initialized: false,
  anchorMs: 0,
  frozenPast: [],
  prevFuture: [],
};

function cloneTimelinePoints(arr) {
  return (arr || []).map((p) => ({ time_ms: p.time_ms, temperature_c: p.temperature_c }));
}

function interpSeries(points, tMs) {
  if (!points?.length) return null;
  const p = [...points].sort((a, b) => a.time_ms - b.time_ms);
  if (tMs <= p[0].time_ms) return p[0].temperature_c;
  const last = p[p.length - 1];
  if (tMs >= last.time_ms) return last.temperature_c;
  for (let i = 0; i < p.length - 1; i++) {
    const a = p[i];
    const b = p[i + 1];
    if (tMs >= a.time_ms && tMs <= b.time_ms) {
      const r = (tMs - a.time_ms) / (b.time_ms - a.time_ms || 1);
      return a.temperature_c + r * (b.temperature_c - a.temperature_c);
    }
  }
  return null;
}

function buildPastGridMs(nowMs) {
  const n = 13;
  const winStart = nowMs - 3600000;
  const step = 3600000 / (n - 1);
  const out = [];
  for (let i = 0; i < n; i++) {
    out.push(Math.min(winStart + i * step, nowMs));
  }
  return out;
}

function resetRollState(tl) {
  rollState.frozenPast = cloneTimelinePoints(tl.past_predicted);
  rollState.prevFuture = cloneTimelinePoints(tl.future_predicted);
  rollState.anchorMs = Date.parse(tl.now_iso);
  rollState.initialized = true;
}

function mergePastFromRoll(tl) {
  const newNow = Date.parse(tl.now_iso);
  const times = buildPastGridMs(newNow);
  const anchorMs = rollState.anchorMs;
  const frozenPast = rollState.frozenPast;
  const prevFuture = rollState.prevFuture;
  const out = [];
  for (const tMs of times) {
    let v = null;
    if (tMs <= anchorMs) {
      v = interpSeries(frozenPast, tMs);
    } else {
      v = interpSeries(prevFuture, tMs);
    }
    if (v == null) v = interpSeries(tl.past_predicted, tMs);
    if (v == null && prevFuture.length) v = prevFuture[prevFuture.length - 1].temperature_c;
    if (v == null && frozenPast.length) v = frozenPast[frozenPast.length - 1].temperature_c;
    out.push({ time_ms: tMs, temperature_c: Math.round(Number(v) * 100) / 100 });
  }
  rollState.frozenPast = cloneTimelinePoints(out);
  rollState.prevFuture = cloneTimelinePoints(tl.future_predicted);
  rollState.anchorMs = newNow;
  return out;
}

function formatTime(ts) {
  if (ts == null) return "";
  const t = formatDateTimeZh(ts);
  return t || String(ts);
}

function speakTempAlert() {
  const b = tempAlertBlock.value;
  const text = [b.title, ...b.lines].join("。");
  if (!text.trim()) return;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "zh-CN";
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
}

/* ---------- 图表 ---------- */
function seriesFromPoints(arr) {
  return (arr || []).map((p) => [p.time_ms, p.temperature_c]);
}

const chartLegendSmall = {
  bottom: 0,
  itemWidth: 12,
  itemHeight: 8,
  textStyle: { fontSize: 10 },
};

/** 图表缩放：时间/纵轴按钮与 dataZoom 共用 */
const CH_ZOOM_FACTOR = 0.72;
const CH_GRID_BOTTOM = 52;
const CH_LEGEND_BOTTOM = 26;
const CH_SLIDER_H = 16;

function getChartDataZoomList(chart) {
  const list = chart?.getOption()?.dataZoom;
  return Array.isArray(list) ? list : [];
}

function zoomTimeAxisOnChart(chart, dir) {
  if (!chart) return;
  const dz = getChartDataZoomList(chart);
  const idx = dz.findIndex((d) => d.xAxisIndex !== undefined && d.xAxisIndex !== false);
  if (idx < 0) return;
  const cur = dz[idx];
  const start = cur.start ?? 0;
  const end = cur.end ?? 100;
  const span = Math.max(end - start, 0.5);
  const mid = (start + end) / 2;
  let newSpan = dir === "in" ? span * CH_ZOOM_FACTOR : span / CH_ZOOM_FACTOR;
  newSpan = Math.min(100, Math.max(1.5, newSpan));
  let ns = mid - newSpan / 2;
  let ne = mid + newSpan / 2;
  if (ns < 0) {
    ne -= ns;
    ns = 0;
  }
  if (ne > 100) {
    ns -= ne - 100;
    ne = 100;
  }
  ns = Math.max(0, ns);
  ne = Math.min(100, ne);
  chart.dispatchAction({ type: "dataZoom", dataZoomIndex: idx, start: ns, end: ne });
}

function zoomYInsideOnChart(chart, dir) {
  if (!chart) return;
  const dz = getChartDataZoomList(chart);
  dz.forEach((d, idx) => {
    if (d.type !== "inside" || d.yAxisIndex === undefined) return;
    const start = d.start ?? 0;
    const end = d.end ?? 100;
    const span = Math.max(end - start, 0.5);
    const mid = (start + end) / 2;
    let newSpan = dir === "in" ? span * CH_ZOOM_FACTOR : span / CH_ZOOM_FACTOR;
    newSpan = Math.min(100, Math.max(4, newSpan));
    let ns = mid - newSpan / 2;
    let ne = mid + newSpan / 2;
    if (ns < 0) {
      ne -= ns;
      ns = 0;
    }
    if (ne > 100) {
      ns -= ne - 100;
      ne = 100;
    }
    ns = Math.max(0, ns);
    ne = Math.min(100, ne);
    chart.dispatchAction({ type: "dataZoom", dataZoomIndex: idx, start: ns, end: ne });
  });
}

function resetChartDataZoom(chart) {
  if (!chart) return;
  getChartDataZoomList(chart).forEach((_, idx) => {
    chart.dispatchAction({ type: "dataZoom", dataZoomIndex: idx, start: 0, end: 100 });
  });
}

function zoomTempTime(dir) {
  zoomTimeAxisOnChart(tempChart, dir);
}
function zoomHumTime(dir) {
  zoomTimeAxisOnChart(humChart, dir);
}
function zoomTempY(dir) {
  zoomYInsideOnChart(tempChart, dir);
}
function zoomHumY(dir) {
  zoomYInsideOnChart(humChart, dir);
}
function resetTempZoom() {
  resetChartDataZoom(tempChart);
}
function resetHumZoom() {
  resetChartDataZoom(humChart);
}

function tempAxisTooltipFormatter(params) {
  if (!Array.isArray(params) || !params.length) return "";
  const axisVal = params[0]?.axisValue;
  let timeStr = "";
  if (axisVal != null) {
    const tMs = typeof axisVal === "number" ? axisVal : Date.parse(axisVal);
    if (!Number.isNaN(tMs)) timeStr = formatDateTimeZh(tMs);
  }
  const rows = params
    .filter((p) => p.seriesName && !String(p.seriesName).startsWith("__"))
    .map((p) => {
      const v = Array.isArray(p.value) ? p.value[1] : p.data?.[1];
      if (v == null || Number.isNaN(Number(v))) return null;
      return `${p.marker}${p.seriesName}：<b>${Number(v).toFixed(1)}</b>℃`;
    })
    .filter(Boolean);
  if (!rows.length) return timeStr || "";
  return [timeStr, ...rows].filter(Boolean).join("<br/>");
}

function initTempChart() {
  if (!tempChartRef.value) return;
  tempChart = echarts.init(tempChartRef.value);
  tempChart.setOption({
    animation: false,
    tooltip: { trigger: "axis", formatter: tempAxisTooltipFormatter },
    toolbox: {
      right: 6,
      top: 2,
      itemSize: 14,
      feature: {
        dataZoom: {
          yAxisIndex: false,
          title: { zoom: "框选放大", back: "取消框选" },
        },
        restore: { title: "还原" },
      },
    },
    legend: {
      ...chartLegendSmall,
      bottom: CH_LEGEND_BOTTOM,
      data: ["实测", "过去推算", "未来推算", "未来参考带"],
    },
    grid: { left: 42, right: 10, top: 22, bottom: CH_GRID_BOTTOM, containLabel: true },
    dataZoom: [
      { type: "inside", xAxisIndex: 0, filterMode: "none" },
      { type: "inside", yAxisIndex: 0, filterMode: "none" },
      {
        type: "slider",
        xAxisIndex: 0,
        filterMode: "none",
        height: CH_SLIDER_H,
        bottom: 2,
        showDetail: false,
      },
    ],
    xAxis: { type: "time", axisLabel: { fontSize: 10 } },
    yAxis: { type: "value", name: "℃", scale: true, nameTextStyle: { fontSize: 10 }, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: "实测",
        type: "line",
        smooth: 0.35,
        sampling: "lttb",
        showSymbol: false,
        symbolSize: 0,
        data: [],
        lineStyle: { width: 1.5 },
        itemStyle: { color: "#409eff" },
        z: 3,
      },
      {
        name: "过去推算",
        type: "line",
        smooth: 0.35,
        sampling: "lttb",
        showSymbol: false,
        data: [],
        lineStyle: { type: "dashed", color: "#e6a23c", width: 1.5 },
        z: 2,
      },
      {
        name: "未来推算",
        type: "line",
        smooth: 0.35,
        sampling: "lttb",
        showSymbol: false,
        data: [],
        lineStyle: { type: "dashed", color: "#67c23a", width: 1.5 },
        z: 2,
      },
      {
        name: "__futBandBase",
        type: "line",
        stack: "futBand",
        data: [],
        lineStyle: { opacity: 0 },
        symbol: "none",
        silent: true,
        z: 0,
      },
      {
        name: "未来参考带",
        type: "line",
        stack: "futBand",
        data: [],
        lineStyle: { opacity: 0 },
        areaStyle: { color: "rgba(103, 194, 58, 0.22)" },
        symbol: "none",
        silent: true,
        z: 0,
      },
    ],
  });
}

function initHumChart() {
  if (!humChartRef.value) return;
  humChart = echarts.init(humChartRef.value);
  humChart.setOption({
    animation: false,
    tooltip: { trigger: "axis" },
    toolbox: {
      right: 6,
      top: 2,
      itemSize: 14,
      feature: {
        dataZoom: {
          yAxisIndex: false,
          title: { zoom: "框选放大", back: "取消框选" },
        },
        restore: { title: "还原" },
      },
    },
    legend: { ...chartLegendSmall, bottom: CH_LEGEND_BOTTOM, data: ["湿度", "光照"] },
    grid: { left: 42, right: 42, top: 22, bottom: CH_GRID_BOTTOM, containLabel: true },
    dataZoom: [
      { type: "inside", xAxisIndex: 0, filterMode: "none" },
      { type: "inside", yAxisIndex: 0, filterMode: "none" },
      { type: "inside", yAxisIndex: 1, filterMode: "none" },
      {
        type: "slider",
        xAxisIndex: 0,
        filterMode: "none",
        height: CH_SLIDER_H,
        bottom: 2,
        showDetail: false,
      },
    ],
    xAxis: { type: "time", axisLabel: { fontSize: 10 } },
    yAxis: [
      { type: "value", name: "%RH", position: "left", nameTextStyle: { fontSize: 10 }, axisLabel: { fontSize: 10 } },
      { type: "value", name: "lx", position: "right", nameTextStyle: { fontSize: 10 }, axisLabel: { fontSize: 10 } },
    ],
    series: [
      {
        name: "湿度",
        type: "line",
        smooth: 0.35,
        sampling: "lttb",
        showSymbol: false,
        data: [],
        itemStyle: { color: "#409eff" },
      },
      {
        name: "光照",
        type: "line",
        smooth: 0.35,
        sampling: "lttb",
        showSymbol: false,
        yAxisIndex: 1,
        data: [],
        itemStyle: { color: "#e6a23c" },
      },
    ],
  });
}

function applyTempChart(tl) {
  if (!tempChart) return;
  const rawActual = tempRealtime.map((p) => [p.time_ms, p.value]);
  const actualData = downsamplePairs(rawActual, MAX_CHART_POINTS);
  const ppSrc =
    displayPastPredicted.value?.length > 0
      ? displayPastPredicted.value
      : tl?.past_predicted || [];
  const ppData = downsamplePairs(seriesFromPoints(ppSrc), MAX_CHART_POINTS);
  const fpData = downsamplePairs(tl ? seriesFromPoints(tl.future_predicted) : [], MAX_CHART_POINTS);
  const band = tl?.future_band;
  let bandLow = [];
  let bandSpan = [];
  if (band?.length) {
    const low = band.map((b) => [b.time_ms, b.low_c]);
    const span = band.map((b) => [b.time_ms, Math.max(0.02, b.high_c - b.low_c)]);
    bandLow = downsamplePairs(low, MAX_CHART_POINTS);
    bandSpan = downsamplePairs(span, MAX_CHART_POINTS);
  }
  tempChart.setOption(
    {
      animation: false,
      series: [
        { data: actualData },
        { data: ppData },
        { data: fpData },
        { data: bandLow },
        { data: bandSpan },
      ],
    },
    { lazyUpdate: true },
  );
}

function applyHumChartRealtime() {
  if (!humChart) return;
  const hData = downsamplePairs(
    humRealtime.map((p) => [p.time_ms, p.value]),
    MAX_CHART_POINTS,
  );
  const lData = downsamplePairs(
    lightRealtime.map((p) => [p.time_ms, p.value]),
    MAX_CHART_POINTS,
  );
  humChart.setOption(
    { animation: false, series: [{ data: hData }, { data: lData }] },
    { lazyUpdate: true },
  );
}

/* ---------- 数据获取 ---------- */
async function fetchLatest() {
  try {
    latest.value = await sensorApi.getLatest();
  } catch {
    latest.value = null;
  }
}

async function fetchTimeline({ fullReset = false } = {}) {
  try {
    const tl = await monitoringApi.getTemperatureTimeline({});
    timeline.value = tl;
    if (fullReset || !rollState.initialized) {
      resetRollState(tl);
      displayPastPredicted.value = cloneTimelinePoints(tl.past_predicted);
    } else {
      displayPastPredicted.value = mergePastFromRoll(tl);
    }
    applyTempChart(tl);
  } catch {
    /* 静默 */
  }
}

function normalizeSensorTimestampMs(ts) {
  const ms = parseBackendInstant(ts);
  return Number.isNaN(ms) ? NaN : ms;
}

async function loadHistoryIntoBuffers() {
  const end = new Date();
  const start = new Date(end.getTime() - MAX_REALTIME_MS);
  try {
    const rows = await sensorApi.getHistory({
      start_time: start.toISOString(),
      end_time: end.toISOString(),
    });
    // 清空并填充缓冲（与 WebSocket 同一套毫秒规则，保证折线连续）
    tempRealtime.length = 0;
    humRealtime.length = 0;
    lightRealtime.length = 0;
    (rows || []).forEach((d) => {
      const ms = normalizeSensorTimestampMs(d.timestamp);
      if (Number.isNaN(ms)) return;
      tempRealtime.push({ time_ms: ms, value: d.temperature });
      humRealtime.push({ time_ms: ms, value: d.humidity });
      lightRealtime.push({ time_ms: ms, value: d.light });
    });
    maybeThinBuffers();
  } catch {
    /* 静默 */
  }
}

async function fetchAnomalies() {
  try {
    const res = await monitoringApi.getAnomalies({ hours: 24 });
    anomalies.value = res.anomalies || [];
  } catch {
    anomalies.value = [];
  }
}

async function fetchAlarmConfig() {
  try {
    alarmConfig.value = await alarmApi.getConfig();
  } catch {
    alarmConfig.value = null;
  }
}

async function refreshPrediction() {
  await fetchTimeline({ fullReset: false });
}

async function refreshAll() {
  await Promise.all([fetchLatest(), fetchAnomalies(), fetchAlarmConfig()]);
  // 必须先写入历史缓冲再画温度/湿度图，避免与 fetchTimeline 竞态导致「有库无线」
  await loadHistoryIntoBuffers();
  await fetchTimeline({ fullReset: true });
  applyHumChartRealtime();
}

async function exportLast24h() {
  const end = new Date();
  const start = new Date(end.getTime() - 24 * 60 * 60 * 1000);
  exporting.value = true;
  try {
    const blob = await sensorApi.exportData({
      start_time: start.toISOString(),
      end_time: end.toISOString(),
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "sensor_history_24h.csv";
    a.click();
    URL.revokeObjectURL(url);
    ElMessage.success("已开始下载");
  } catch {
    ElMessage.error("导出失败");
  } finally {
    exporting.value = false;
  }
}

function resizeCharts() {
  tempChart?.resize();
  humChart?.resize();
}

function onResize() {
  requestAnimationFrame(resizeCharts);
}

/** 与 ws.on 成对注销；重复挂载时若旧回调对已 dispose 的图表 setOption 抛错，会打断后续 listener，页面不再刷新 */
function onSensorWsPayload(payload) {
  let ms = parseSensorPayloadTimestampMs(payload.timestamp);
  if (Number.isNaN(ms)) ms = Date.now();

  latest.value = {
    device_id: payload.deviceId || payload.device_id || "—",
    temperature: payload.temperature,
    humidity: payload.humidity,
    light: payload.light,
    timestamp: ms,
  };

  appendRealtimeTriplet(ms, payload.temperature, payload.humidity, payload.light);

  pruneOld(tempRealtime);
  pruneOld(humRealtime);
  pruneOld(lightRealtime);
  maybeThinBuffers();

  scheduleRealtimeCharts();
}

onMounted(async () => {
  await fetchLatest();
  await nextTick();
  initTempChart();
  initHumChart();
  await refreshAll();
  await nextTick();
  requestAnimationFrame(resizeCharts);

  // 预测线 30s 刷新（从 DB）；异常/阈值 30s；最新采样 REST 兜底（避免仅依赖 WS 时断更）
  pollTimer = setInterval(() => {
    refreshPrediction();
    fetchAnomalies();
    fetchAlarmConfig();
    fetchLatest();
  }, 30000);

  ws.on("sensor_data", onSensorWsPayload);

  window.addEventListener("resize", onResize);
});

onUnmounted(() => {
  ws.off("sensor_data", onSensorWsPayload);
  if (chartUpdateRaf) {
    cancelAnimationFrame(chartUpdateRaf);
    chartUpdateRaf = 0;
  }
  if (pollTimer) clearInterval(pollTimer);
  window.removeEventListener("resize", onResize);
  tempChart?.dispose();
  humChart?.dispose();
  tempChart = null;
  humChart = null;
});
</script>

<style scoped>
.dashboard-fit {
  height: 100%;
  max-height: 100%;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}

.dash-title {
  margin: 0 0 8px 0;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  line-height: 1.2;
  flex-shrink: 0;
}

.dash-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  gap: 10px;
  grid-template-columns: 1fr 1fr 1fr;
  grid-template-rows: auto minmax(0, 1fr) auto;
  grid-template-areas:
    "m1 m2 m3"
    "ct ct ch"
    "bc bc bc";
}

/* ---------- 指标卡片 ---------- */
.g-m1 { grid-area: m1; }
.g-m2 { grid-area: m2; }
.g-m3 { grid-area: m3; }

.metric-card {
  border-radius: 10px;
  border: none;
}
.metric-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  gap: 14px;
}

.metric-temp { background: linear-gradient(135deg, #fff5f5 0%, #fff 100%); border-left: 3px solid #F56C6C; }
.metric-hum  { background: linear-gradient(135deg, #f0f7ff 0%, #fff 100%); border-left: 3px solid #409EFF; }
.metric-light { background: linear-gradient(135deg, #fef8f0 0%, #fff 100%); border-left: 3px solid #E6A23C; }

.metric-icon-wrap {
  width: 46px;
  height: 46px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.temp-bg  { background: linear-gradient(135deg, #F56C6C, #f78989); }
.hum-bg   { background: linear-gradient(135deg, #409EFF, #66b1ff); }
.light-bg { background: linear-gradient(135deg, #E6A23C, #ebb563); }

.metric-info {
  flex: 1;
  min-width: 0;
}
.metric-label {
  font-size: 12px;
  color: #909399;
  display: block;
  margin-bottom: 2px;
}
.metric-value {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
  line-height: 1.1;
}
.metric-unit {
  font-size: 13px;
  font-weight: 400;
  color: #909399;
  margin-left: 2px;
}

/* ---------- 图表 ---------- */
.g-ct {
  grid-area: ct;
  border-radius: 10px;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.g-ch {
  grid-area: ch;
  border-radius: 10px;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.g-ct :deep(.el-card__header),
.g-ch :deep(.el-card__header) {
  padding: 6px 12px;
  flex-shrink: 0;
}
.g-ct :deep(.el-card__body),
.g-ch :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 0 6px 4px;
}

.ch-hd {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.ch-hd-row {
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}
.ch-hd-text {
  display: flex;
  align-items: baseline;
  gap: 6px;
  flex-wrap: wrap;
  min-width: 0;
}
.ch-zoom-bar {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  gap: 0;
}
.ch-zoom-bar .ch-zoom-btn {
  padding: 4px;
  min-height: auto;
  color: #606266;
}
.ch-zoom-bar .ch-zoom-btn:hover {
  color: #409eff;
}
.ch-sub {
  font-size: 11px;
  font-weight: normal;
  color: #909399;
}
.ch-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.ch-hint {
  font-size: 10px;
  color: #909399;
  margin: 2px 4px 0;
  line-height: 1.35;
  max-height: 2.7em;
  overflow: hidden;
  flex-shrink: 0;
}
.ch-hint-sub {
  margin-top: 0;
  max-height: 4.2em;
}
.chart-shell {
  flex: 1;
  min-height: 0;
  width: 100%;
}

/* ---------- 播报卡片 ---------- */
.g-bc {
  grid-area: bc;
  border-radius: 10px;
  flex-shrink: 0;
}

.bc-row {
  display: flex;
  gap: 16px;
  align-items: stretch;
}
.bc-content {
  flex: 1;
  min-width: 0;
}
.bc-label {
  font-size: 12px;
  font-weight: 600;
  color: #303133;
  display: block;
  margin-bottom: 6px;
}
.bc-alert {
  padding: 8px 10px;
}
.bc-alert :deep(.el-alert__title) {
  font-size: 13px;
}
.bc-alert-body {
  margin: 4px 0 0 0;
}
.bc-line {
  margin: 0 0 4px 0;
  font-size: 12px;
  line-height: 1.5;
  color: #606266;
}
.bc-line:last-child {
  margin-bottom: 0;
}
.bc-anomaly-hint {
  margin: 6px 0 4px;
  font-size: 12px;
  color: #E6A23C;
  font-weight: 600;
}
.bc-anomaly-truncate-hint {
  margin: 0;
  font-size: 11px;
  color: #909399;
  line-height: 1.4;
}
.bc-anomaly-footer-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 16px;
  margin-top: 6px;
}
.bc-anomaly-footer-row .bc-meta {
  margin-left: auto;
  margin-top: 0;
}
.bc-anomaly-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}
.bc-anomaly-pill {
  max-width: 320px;
  font-size: 11px;
  line-height: 1.35;
  padding: 3px 8px;
  background: #fdf6ec;
  color: #b88230;
  border-radius: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.bc-anomaly-ok {
  margin: 4px 0 0;
  font-size: 12px;
  color: #67c23a;
}
.bc-meta {
  margin: 4px 0 0;
  font-size: 10px;
  color: #c0c4cc;
}
.bc-tools {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  align-self: stretch;
  gap: 10px;
  flex-shrink: 0;
  min-width: 200px;
  width: 200px;
  padding: 10px 12px;
  background: #ffffff;
  border: 1px solid #dcdfe6;
  border-radius: 10px;
  box-sizing: border-box;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
.bc-tools-actions {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-evenly;
  align-items: stretch;
}
.bc-tools-head {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 700;
  color: #606266;
  letter-spacing: 0.06em;
  text-align: center;
  padding-bottom: 2px;
  border-bottom: 1px solid #ebeef5;
  margin-bottom: 0;
}
.bc-btn {
  width: 100%;
  margin: 0 !important;
  height: 36px !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  border-radius: 6px !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 6px !important;
}
.bc-ico {
  font-size: 16px;
  flex-shrink: 0;
}
/* 手动刷新：深灰实心 + 白字，对比度最高 */
.bc-btn-refresh.el-button {
  background-color: #1f2937 !important;
  border-color: #111827 !important;
  color: #ffffff !important;
}
.bc-btn-refresh.el-button:hover,
.bc-btn-refresh.el-button:focus {
  background-color: #374151 !important;
  border-color: #1f2937 !important;
  color: #ffffff !important;
}
.bc-btn-refresh.el-button:active {
  background-color: #111827 !important;
  border-color: #030712 !important;
}
.bc-btn-export {
  box-shadow: 0 2px 6px rgba(64, 158, 255, 0.35);
}
.bc-btn-speak {
  box-shadow: 0 2px 6px rgba(103, 194, 58, 0.35);
}
.bc-btn-speak.is-disabled {
  opacity: 0.5;
  filter: grayscale(0.15);
  font-weight: 600 !important;
}

/* ---------- 响应式 ---------- */
@media (max-width: 1100px) {
  .bc-tools {
    width: 100%;
    flex-direction: row;
    flex-wrap: wrap;
    align-items: stretch;
    justify-content: center;
  }
  .bc-tools-head {
    flex: 1 0 100%;
    text-align: left;
    margin-bottom: 0;
    padding-bottom: 6px;
  }
  .bc-tools-actions {
    flex: 1 1 100%;
    flex-direction: row;
    flex-wrap: wrap;
    justify-content: space-evenly;
    align-items: center;
    min-height: auto;
  }
  .bc-btn {
    flex: 1 1 148px;
    width: auto;
    min-width: 128px;
  }

  .dash-grid {
    grid-template-columns: 1fr 1fr;
    grid-template-rows: auto auto minmax(0, 1fr) minmax(0, 1fr) auto;
    grid-template-areas:
      "m1 m2"
      "m3 m3"
      "ct ct"
      "ch ch"
      "bc bc";
  }
}
</style>
