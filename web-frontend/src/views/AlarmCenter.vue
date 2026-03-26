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
        <el-col :span="4">
          <el-button type="primary" @click="refreshHistory">查询</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 告警表格 -->
    <el-card shadow="hover" class="table-card">
      <el-table :data="filteredAlarms" stripe style="width: 100%" empty-text="暂无告警">
        <el-table-column prop="id" label="ID" width="120" />
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
              link
              size="small"
              @click="markRead(row.id)"
            >标记已读</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, ref } from "vue";
import { ElNotification } from "element-plus";
import { alarmApi } from "../api/alarm";

const ws = inject("ws");
const alarms = ref([]);
const levelFilter = ref("");
const timeRange = ref([
  new Date(Date.now() - 60 * 60 * 1000),
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

function formatTime(ts) {
  if (!ts) return "--";
  const d = typeof ts === "number" ? new Date(ts) : new Date(ts);
  return d.toLocaleString();
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
  } catch { /* 静默 */ }
}

async function markRead(id) {
  await alarmApi.markRead(id);
  const item = alarms.value.find((a) => a.id === id);
  if (item) item.read = true;
}

/* ---------- 生命周期 ---------- */
onMounted(async () => {
  await refreshHistory();

  ws.on("alarm", (payload) => {
    const alarm = {
      id: payload.id || `alarm_${Date.now()}`,
      type: payload.type || "temperature",
      level: payload.level || "high",
      message: payload.message || "",
      value: payload.value,
      threshold: payload.threshold,
      read: payload.read ?? false,
      timestamp: payload.timestamp,
    };

    alarms.value.unshift(alarm);

    // 弹窗通知
    ElNotification({
      title: `${levelLabel(alarm.level)}级告警`,
      message: alarm.message,
      type: alarm.level === "urgent" || alarm.level === "high" ? "error" : "warning",
      duration: 5000,
    });
  });
});
</script>

<style scoped>
.alarm-center { }

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
</style>
