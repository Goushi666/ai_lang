<template>
  <div class="alarm-center">
    <h2 class="page-title">告警中心</h2>

    <!-- 筛选栏 -->
    <el-card shadow="never" class="filter-card">
      <el-row :gutter="16" align="middle">
        <el-col :span="10">
          <el-date-picker
            v-model="timeRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            size="default"
          />
        </el-col>
        <el-col :span="6">
          <el-select v-model="levelFilter" placeholder="告警级别" clearable size="default">
            <el-option label="低" value="low" />
            <el-option label="中" value="medium" />
            <el-option label="高" value="high" />
            <el-option label="紧急" value="urgent" />
          </el-select>
        </el-col>
        <el-col :span="8" class="filter-actions">
          <el-button type="primary" @click="refreshHistory">查询</el-button>
          <el-button type="primary" @click="exportCsv" :disabled="!filteredAlarms.length">
            导出 CSV
          </el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 告警表格 -->
    <el-card shadow="hover" class="table-card">
      <el-table :data="filteredAlarms" stripe style="width: 100%" empty-text="暂无告警">
        <el-table-column prop="id" label="ID" width="120" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            {{ typeLabel(row.type) }}
          </template>
        </el-table-column>
        <el-table-column label="级别" width="100">
          <template #default="{ row }">
            <el-tag :type="levelTagType(row.level)" effect="dark" size="small">
              {{ levelLabel(row.level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="告警信息" min-width="200" />
        <el-table-column label="触发值" width="100">
          <template #default="{ row }">{{ row.value ?? '--' }}</template>
        </el-table-column>
        <el-table-column label="阈值" width="100">
          <template #default="{ row }">{{ row.threshold ?? '--' }}</template>
        </el-table-column>
        <el-table-column label="时间" width="180">
          <template #default="{ row }">{{ formatTime(row.timestamp) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.read ? 'info' : 'danger'" size="small">
              {{ row.read ? '已读' : '未读' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="!row.read"
              type="primary"
              size="small"
              class="btn-mark-read"
              @click="markRead(row.id)"
            >
              标记已读
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, onUnmounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { alarmApi } from "../api/alarm";

const ws = inject("ws");
const alarms = ref([]);
const levelFilter = ref("");
const timeRange = ref([
  new Date(Date.now() - 24 * 60 * 60 * 1000),
  new Date(),
]);

/* ---------- 筛选 ---------- */
const filteredAlarms = computed(() => {
  if (!levelFilter.value) return alarms.value;
  return alarms.value.filter((a) => a.level === levelFilter.value);
});

/* ---------- 工具函数 ---------- */
function levelTagType(level) {
  const map = { low: "info", medium: "warning", high: "danger", urgent: "danger" };
  return map[level] || "info";
}

function levelLabel(level) {
  const map = { low: "低", medium: "中", high: "高", urgent: "紧急" };
  return map[level] || level;
}

function typeLabel(type) {
  const map = { temperature: "温度", humidity: "湿度", light: "光照" };
  return map[type] || type || "--";
}

function formatTime(ts) {
  if (!ts) return "--";
  const d = typeof ts === "number" ? new Date(ts) : new Date(ts);
  return d.toLocaleString();
}

function escapeCsvCell(s) {
  const t = String(s ?? "");
  if (/[",\r\n]/.test(t)) return `"${t.replace(/"/g, '""')}"`;
  return t;
}

function exportCsv() {
  const rows = filteredAlarms.value;
  if (!rows.length) {
    ElMessage.warning("暂无数据可导出，请先查询或等待告警产生");
    return;
  }
  const header = ["ID", "类型", "级别", "告警信息", "触发值", "阈值", "时间", "状态"];
  const lines = [header.join(",")];
  for (const row of rows) {
    lines.push(
      [
        escapeCsvCell(row.id),
        escapeCsvCell(typeLabel(row.type)),
        escapeCsvCell(levelLabel(row.level)),
        escapeCsvCell(row.message),
        escapeCsvCell(row.value),
        escapeCsvCell(row.threshold),
        escapeCsvCell(formatTime(row.timestamp)),
        escapeCsvCell(row.read ? "已读" : "未读"),
      ].join(",")
    );
  }
  const blob = new Blob(["\ufeff" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `alarms_${new Date().toISOString().slice(0, 19).replace(/:/g, "-")}.csv`;
  a.click();
  URL.revokeObjectURL(url);
  ElMessage.success("已导出当前列表（含级别筛选）");
}

/* ---------- 数据操作 ---------- */
async function refreshHistory() {
  if (!timeRange.value || timeRange.value.length < 2) return;
  try {
    const res = await alarmApi.getHistory({
      start_time: timeRange.value[0].toISOString(),
      end_time: timeRange.value[1].toISOString(),
    });
    alarms.value = res || [];
  } catch (e) {
    // eslint-disable-next-line no-console
    console.error(e);
    ElMessage.error("拉取告警历史失败，请确认后端可用且时间范围有效");
  }
}

function normalizeWsAlarm(p) {
  return {
    id: p.id || `alarm_${Date.now()}`,
    type: p.type || "temperature",
    level: p.level || "high",
    message: p.message || "",
    value: p.value,
    threshold: p.threshold,
    read: p.read ?? false,
    timestamp: p.timestamp,
  };
}

function prependAlarmsFromWsPayload(payload) {
  const list =
    payload && Array.isArray(payload.alarms) && payload.alarms.length
      ? payload.alarms
      : payload && payload.id != null
        ? [payload]
        : [];
  for (const p of [...list].reverse()) {
    alarms.value.unshift(normalizeWsAlarm(p));
  }
}

const onAlarmWs = (payload) => prependAlarmsFromWsPayload(payload);

async function markRead(id) {
  await alarmApi.markRead(id);
  const item = alarms.value.find((a) => a.id === id);
  if (item) item.read = true;
}

/* ---------- 生命周期 ---------- */
onMounted(async () => {
  await refreshHistory();
  ws.on("alarm", onAlarmWs);
});

onUnmounted(() => {
  ws.off("alarm", onAlarmWs);
});
</script>

<style scoped>
.page-title {
  margin: 0 0 20px 0;
  font-size: 20px;
  color: #303133;
}

.filter-card {
  margin-bottom: 16px;
  border-radius: 8px;
}

.table-card {
  border-radius: 8px;
}

.filter-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

/* 表格内蓝底白字，避免主题下对比度不足 */
.table-card :deep(.btn-mark-read.el-button--primary) {
  --el-button-bg-color: var(--el-color-primary);
  --el-button-border-color: var(--el-color-primary);
  --el-button-hover-bg-color: var(--el-color-primary-light-3);
  --el-button-hover-border-color: var(--el-color-primary-light-3);
  --el-button-active-bg-color: var(--el-color-primary-dark-2);
  --el-button-active-border-color: var(--el-color-primary-dark-2);
  color: #fff;
}
</style>
