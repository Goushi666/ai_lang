<template>
  <div class="alarm-center">
    <h2 class="page-title">告警中心</h2>
    <p class="page-hint">
      下列为数据库表 <code>environment_anomalies</code> 中的<strong>异常落库记录</strong>（按落库时间筛选）。
      超阈时已随实时告警自动落库；进入本页或点击「查询」拉取最新列表。删除将<strong>永久删除</strong>对应库记录。
      <span class="page-hint-sub"
        >落库时间：默认库内为 <strong>UTC</strong> 墙钟；若后端配置
        <code>SQLITE_NAIVE_WALL_CLOCK_ZONE=Asia/Shanghai</code> 则为北京时间墙钟。本表始终按北京时间显示。</span
      >
    </p>

    <el-card shadow="never" class="filter-card">
      <el-row :gutter="16" align="middle">
        <el-col :xs="24" :sm="12" :md="8">
          <el-date-picker
            v-model="timeRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="落库时间起"
            end-placeholder="落库时间止"
            size="default"
            style="width: 100%"
          />
        </el-col>
        <el-col :xs="12" :sm="6" :md="4">
          <el-select
            v-model="metricFilter"
            placeholder="异常指标"
            clearable
            size="default"
            style="width: 100%"
          >
            <el-option label="全部类型" value="" />
            <el-option label="温度" value="temperature" />
            <el-option label="湿度" value="humidity" />
            <el-option label="光照" value="light" />
          </el-select>
        </el-col>
        <el-col :xs="24" :sm="24" :md="12" class="filter-actions">
          <el-button type="primary" @click="onSearch">查询</el-button>
          <el-button type="primary" @click="exportCsv" :disabled="total === 0" :loading="exporting">
            导出 CSV
          </el-button>
          <el-button
            type="danger"
            class="btn-danger-solid"
            :disabled="!selectedRows.length"
            @click="confirmBatchDelete"
          >
            批量删除
          </el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-card shadow="hover" class="table-card">
      <el-table
        ref="tableRef"
        :data="rows"
        stripe
        style="width: 100%"
        empty-text="暂无记录"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="48" fixed="left" />
        <el-table-column prop="id" label="ID" width="72" />
        <el-table-column prop="device_id" label="设备" width="120" show-overflow-tooltip />
        <el-table-column label="指标" width="88">
          <template #default="{ row }">{{ typeLabel(row.metric) }}</template>
        </el-table-column>
        <el-table-column prop="rule_id" label="规则" width="140" show-overflow-tooltip />
        <el-table-column label="峰值" width="88">
          <template #default="{ row }">{{ row.peak ?? "--" }}</template>
        </el-table-column>
        <el-table-column label="阈值" width="88">
          <template #default="{ row }">{{ row.threshold ?? "--" }}</template>
        </el-table-column>
        <el-table-column prop="detail_zh" label="说明" min-width="200" show-overflow-tooltip />
        <el-table-column label="落库时间" width="168">
          <template #default="{ row }">{{ formatIso(row.recorded_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="danger" size="small" class="btn-danger-solid" @click="confirmDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="total > 0" class="pager-wrap">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 15, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @current-change="refreshList"
          @size-change="onPageSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { monitoringApi } from "../api/monitoring";
import { formatDateTimeZh } from "@/utils/datetime";

const rows = ref([]);
const metricFilter = ref("");
const timeRange = ref([
  new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
  new Date(),
]);
const currentPage = ref(1);
const pageSize = ref(15);
const total = ref(0);
const exporting = ref(false);
const tableRef = ref(null);
const selectedRows = ref([]);

function onSelectionChange(sel) {
  selectedRows.value = sel || [];
}

function buildQuery(overrides = {}) {
  const [start, end] = timeRange.value || [];
  const limit = overrides.limit ?? pageSize.value;
  const page = overrides.page ?? currentPage.value;
  const q = {
    start_time: start.toISOString(),
    end_time: end.toISOString(),
    limit,
    offset: Math.max(0, (page - 1) * limit),
  };
  const mf = metricFilter.value;
  if (mf) q.metric = mf;
  return q;
}

function typeLabel(type) {
  const map = { temperature: "温度", humidity: "湿度", light: "光照" };
  return map[type] || type || "--";
}

function formatIso(iso) {
  if (!iso) return "--";
  const t = formatDateTimeZh(iso);
  return t || String(iso);
}

function escapeCsvCell(s) {
  const t = String(s ?? "");
  if (/[",\r\n]/.test(t)) return `"${t.replace(/"/g, '""')}"`;
  return t;
}

async function exportCsv() {
  if (!timeRange.value || timeRange.value.length < 2) return;
  exporting.value = true;
  const pageSz = 200;
  try {
    const all = [];
    let page = 1;
    let t = 0;
    while (true) {
      const res = await monitoringApi.listAnomalyRecords(
        buildQuery({ limit: pageSz, page }),
      );
      t = res.total ?? 0;
      const chunk = res.items || [];
      all.push(...chunk);
      if (all.length >= t || chunk.length === 0) break;
      page += 1;
    }
    if (!all.length) {
      ElMessage.warning("暂无数据可导出");
      return;
    }
    const header = [
      "ID",
      "设备",
      "指标",
      "规则",
      "峰值",
      "阈值",
      "说明",
      "落库时间",
    ];
    const lines = [header.join(",")];
    for (const row of all) {
      lines.push(
        [
          escapeCsvCell(row.id),
          escapeCsvCell(row.device_id),
          escapeCsvCell(typeLabel(row.metric)),
          escapeCsvCell(row.rule_id),
          escapeCsvCell(row.peak),
          escapeCsvCell(row.threshold),
          escapeCsvCell(row.detail_zh),
          escapeCsvCell(formatIso(row.recorded_at)),
        ].join(","),
      );
    }
    const blob = new Blob(["\ufeff" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `environment_anomalies_${new Date().toISOString().slice(0, 19).replace(/:/g, "-")}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    ElMessage.success(`已导出 ${all.length} 条`);
  } catch (e) {
    // eslint-disable-next-line no-console
    console.error(e);
    ElMessage.error("导出失败，请确认后端可用");
  } finally {
    exporting.value = false;
  }
}

function onSearch() {
  currentPage.value = 1;
  refreshList();
}

function onPageSizeChange() {
  currentPage.value = 1;
  refreshList();
}

async function refreshList() {
  if (!timeRange.value || timeRange.value.length < 2) return;
  try {
    const res = await monitoringApi.listAnomalyRecords(buildQuery());
    rows.value = res.items || [];
    total.value = res.total ?? 0;
  } catch (e) {
    // eslint-disable-next-line no-console
    console.error(e);
    rows.value = [];
    total.value = 0;
    ElMessage.error("加载失败，请确认后端可用且时间范围有效");
  }
}

async function confirmBatchDelete() {
  const ids = selectedRows.value.map((r) => r.id).filter((id) => id != null);
  if (!ids.length) return;
  try {
    await ElMessageBox.confirm(
      `确定删除已选 ${ids.length} 条异常记录吗？此操作不可恢复。`,
      "批量删除",
      { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }
  try {
    const res = await monitoringApi.batchDeleteAnomalyRecords({ ids });
    const deleted = res?.deleted ?? 0;
    const requested = res?.requested ?? ids.length;
    if (deleted < requested) {
      ElMessage.warning(`已删除 ${deleted} 条（请求 ${requested} 条，部分 id 可能不存在）`);
    } else {
      ElMessage.success(`已删除 ${deleted} 条`);
    }
    tableRef.value?.clearSelection();
    await refreshList();
  } catch (e) {
    // eslint-disable-next-line no-console
    console.error(e);
    ElMessage.error("批量删除失败");
  }
}

async function confirmDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除 ID=${row.id} 的异常记录吗？此操作不可恢复。`,
      "删除确认",
      { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }
  try {
    await monitoringApi.deleteAnomalyRecord(row.id);
    ElMessage.success("已删除");
    tableRef.value?.clearSelection();
    await refreshList();
  } catch (e) {
    // eslint-disable-next-line no-console
    console.error(e);
    ElMessage.error("删除失败");
  }
}

onMounted(() => {
  refreshList();
});
</script>

<style scoped>
.page-title {
  margin: 0 0 var(--ds-space-3) 0;
  font-size: var(--ds-text-xl);
  font-weight: 700;
  color: var(--ds-text-primary);
}

.page-hint {
  margin: 0 0 var(--ds-space-4) 0;
  font-size: var(--ds-text-sm);
  color: var(--ds-text-muted);
  line-height: 1.5;
}

.page-hint code {
  font-size: var(--ds-text-xs);
  padding: 1px 4px;
  background: var(--ds-bg-inset);
  border-radius: 3px;
  font-family: var(--ds-font-mono);
}
.page-hint-sub {
  display: block;
  margin-top: var(--ds-space-2);
  color: var(--ds-text-muted);
}
.page-hint-sub code {
  font-size: var(--ds-text-xs);
}

.filter-card {
  margin-bottom: var(--ds-space-4);
  border-radius: var(--ds-radius-md);
  border: 1px solid var(--ds-border-light);
}

.table-card {
  border-radius: var(--ds-radius-md);
  border: 1px solid var(--ds-border-light);
}

.filter-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--ds-space-2);
}

.pager-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--ds-space-4);
  padding-top: var(--ds-space-2);
}

.table-card :deep(.btn-danger-solid.el-button--danger),
.filter-actions :deep(.btn-danger-solid.el-button--danger) {
  --el-button-bg-color: #dc2626;
  --el-button-border-color: #dc2626;
  --el-button-hover-bg-color: #ef4444;
  --el-button-hover-border-color: #ef4444;
  --el-button-active-bg-color: #b91c1c;
  --el-button-active-border-color: #b91c1c;
  background-color: #dc2626 !important;
  border-color: #dc2626 !important;
  color: #fff !important;
}
.table-card :deep(.btn-danger-solid.el-button--danger:hover),
.table-card :deep(.btn-danger-solid.el-button--danger:focus),
.filter-actions :deep(.btn-danger-solid.el-button--danger:hover),
.filter-actions :deep(.btn-danger-solid.el-button--danger:focus) {
  background-color: #ef4444 !important;
  border-color: #ef4444 !important;
  color: #fff !important;
}
.table-card :deep(.btn-danger-solid.el-button--danger.is-disabled),
.filter-actions :deep(.btn-danger-solid.el-button--danger.is-disabled) {
  opacity: 0.5;
}
</style>
