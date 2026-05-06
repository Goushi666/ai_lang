<template>
  <div class="settings-page">
    <h2 class="page-title">系统设置</h2>
    <p class="page-hint">
      管理当前登录账号、告警阈值、用户注册与数据库维护；版式与<strong>环境监测</strong>、<strong>告警中心</strong>保持一致。
    </p>

    <div class="settings-grid">
      <el-card class="settings-card" shadow="never">
        <template #header>
          <div class="settings-hd">
            <div class="settings-hd-icon" aria-hidden="true">
              <el-icon><User /></el-icon>
            </div>
            <span>登录账户</span>
          </div>
        </template>

        <div v-if="currentUser" class="settings-row">
          <div class="settings-row-main">
            <div class="account-head">
              <div class="account-avatar" aria-hidden="true">{{ sessionInitial }}</div>
              <div class="account-text">
                <span class="account-name" :title="currentUser.username">{{ currentUser.username }}</span>
                <el-tag :type="levelTagType(currentUser.level)" size="small" effect="light" round>
                  {{ levelLabel(currentUser.level) }}
                </el-tag>
              </div>
            </div>
            <p class="page-hint settings-tip">
              登录状态仅在此页管理；侧栏不展示账户信息。新账号请先退出，再打开注册页完成注册。
            </p>
          </div>
          <div class="settings-tools" aria-label="账户操作">
            <div class="settings-tools-head">账户操作</div>
            <div class="settings-tools-actions">
              <el-button type="danger" class="st-btn btn-danger-solid" @click="logout">退出登录</el-button>
              <el-button class="st-btn st-btn-secondary" @click="logoutAndRegister">退出并注册新账号</el-button>
            </div>
          </div>
        </div>
        <el-skeleton v-else :rows="3" animated />
      </el-card>

      <el-card class="settings-card" shadow="never">
        <template #header>
          <div class="settings-hd"><span>告警阈值配置</span></div>
        </template>
        <el-form v-if="config" :model="config" label-position="top" class="threshold-form">
          <el-row :gutter="16">
            <el-col :xs="24" :sm="8">
              <el-form-item label="温度阈值 (℃)">
                <el-input-number
                  v-model="config.temperature_threshold"
                  :min="0"
                  :max="100"
                  :precision="1"
                  controls-position="right"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :sm="8">
              <el-form-item label="湿度阈值 (%RH)">
                <el-input-number
                  v-model="config.humidity_threshold"
                  :min="0"
                  :max="100"
                  :precision="1"
                  controls-position="right"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :sm="8">
              <el-form-item label="光照阈值 (Lux)">
                <el-input-number
                  v-model="config.light_threshold"
                  :min="0"
                  :max="65535"
                  :precision="0"
                  controls-position="right"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
          </el-row>
          <div class="threshold-actions">
            <el-button type="primary" :loading="saving" @click="save">保存配置</el-button>
          </div>
        </el-form>
        <el-skeleton v-else :rows="4" animated />
      </el-card>

      <el-card v-if="isAdmin" class="settings-card" shadow="never">
        <template #header>
          <div class="settings-hd">
            <div class="settings-hd-icon">
              <el-icon><UserFilled /></el-icon>
            </div>
            <span>用户与注册</span>
          </div>
        </template>
        <div class="settings-row">
          <div class="settings-row-main">
            <p class="page-hint settings-lead">
              查看已注册账号与权限；可代建新用户（不切换当前会话）。删除用户前请确认对方未在使用中。
            </p>
          </div>
          <div class="settings-tools" aria-label="用户管理">
            <div class="settings-tools-head">用户管理</div>
            <div class="settings-tools-actions">
              <el-button type="primary" class="st-btn" @click="openUsersDialog">
                <el-icon class="st-ico"><View /></el-icon>
                <span>查看已注册用户</span>
              </el-button>
              <el-button class="st-btn st-btn-secondary" @click="openRegisterDialog">
                <el-icon class="st-ico"><CirclePlus /></el-icon>
                <span>注册新用户</span>
              </el-button>
            </div>
          </div>
        </div>
      </el-card>

      <el-card class="settings-card settings-card--risk" shadow="never" :class="{ 'settings-card--span': !isAdmin }">
        <template #header>
          <div class="settings-hd settings-hd--risk"><span>数据库维护</span></div>
        </template>
        <p class="page-hint risk-intro">
          当前 SQLite（<code>app.db</code>）内表 <code>sensor_data</code>、<code>environment_anomalies</code>。下方清空<strong>不可恢复</strong>。
        </p>
        <div class="risk-checks">
          <el-checkbox v-model="purgeSensor">清空传感器采样（sensor_data）</el-checkbox>
          <el-checkbox v-model="purgeAnomalies">清空环境异常记录（environment_anomalies）</el-checkbox>
        </div>
        <el-button
          type="danger"
          class="btn-danger-solid"
          :disabled="!purgeSensor && !purgeAnomalies"
          :loading="purging"
          @click="confirmPurge"
        >
          一键清空所选表
        </el-button>
      </el-card>
    </div>

    <el-dialog
      v-model="usersDialogVisible"
      title="已注册用户"
      width="min(960px, 94vw)"
      class="users-dlg"
      align-center
      destroy-on-close
      append-to-body
      @open="loadUsers"
    >
      <el-table v-loading="usersLoading" :data="userItems" stripe class="users-table" max-height="440">
        <el-table-column prop="id" label="ID" width="64" />
        <el-table-column prop="username" label="用户名" min-width="100" />
        <el-table-column prop="level" label="级别" width="172">
          <template #default="{ row }">
            <el-select
              :model-value="row.level"
              size="small"
              class="ua-level-select"
              @change="(v) => onLevelChange(row, v)"
            >
              <el-option label="观察员 viewer" value="viewer" />
              <el-option label="操作员 operator" value="operator" />
              <el-option label="管理员 admin" value="admin" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="启用" width="72">
          <template #default="{ row }">
            {{ row.is_active ? "是" : "否" }}
          </template>
        </el-table-column>
        <el-table-column label="注册时间" min-width="160">
          <template #default="{ row }">
            {{ formatDt(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="danger"
              class="del-user-btn"
              :disabled="row.id === currentUser?.id"
              @click="confirmDeleteUser(row)"
            >
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog
      v-model="registerDialogVisible"
      title="注册新用户"
      width="440px"
      align-center
      destroy-on-close
      append-to-body
      @closed="resetRegisterForm"
    >
      <p class="page-hint reg-hint">首名用户为管理员，其余默认为观察员（由后端决定）。创建后不会切换当前登录。</p>
      <el-form label-position="top" @submit.prevent="submitRegister">
        <el-form-item label="用户名（字母、数字、下划线）">
          <el-input v-model="regUsername" autocomplete="off" />
        </el-form-item>
        <el-form-item label="密码（至少 6 位）">
          <el-input v-model="regPassword" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="regPassword2" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-button type="primary" native-type="submit" class="register-submit" :loading="regLoading">创建用户</el-button>
      </el-form>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { User, UserFilled, View, CirclePlus, Delete } from "@element-plus/icons-vue";
import { alarmApi } from "../api/alarm";
import { adminApi } from "../api/admin";
import { authMe, authListUsers, authUpdateUserLevel, authRegister, authDeleteUser } from "../api/auth.js";
import { clearSession, getStoredUser, setSession, getToken } from "../utils/authStore.js";

const router = useRouter();

const config = ref(null);
const saving = ref(false);
const purging = ref(false);
const purgeSensor = ref(true);
const purgeAnomalies = ref(true);

const currentUser = ref(getStoredUser());
const isAdmin = computed(() => currentUser.value?.level === "admin");

const sessionInitial = computed(() => {
  const n = currentUser.value?.username?.trim();
  if (!n) return "?";
  return n[0].toUpperCase();
});

const usersDialogVisible = ref(false);
const usersLoading = ref(false);
const userItems = ref([]);

const registerDialogVisible = ref(false);
const regUsername = ref("");
const regPassword = ref("");
const regPassword2 = ref("");
const regLoading = ref(false);

function levelLabel(l) {
  const m = { viewer: "观察员", operator: "操作员", admin: "管理员" };
  return m[l] || l || "—";
}

function levelTagType(level) {
  const m = { admin: "danger", operator: "warning", viewer: "info" };
  return m[level] || "info";
}

function formatDt(v) {
  if (v == null || v === "") return "—";
  try {
    const d = typeof v === "string" ? new Date(v) : v;
    if (Number.isNaN(d.getTime())) return String(v);
    return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(d);
  } catch {
    return String(v);
  }
}

async function refreshMe() {
  if (!getToken()) return;
  try {
    const u = await authMe();
    currentUser.value = u;
    setSession(getToken(), u);
  } catch {
    currentUser.value = null;
  }
}

function logout() {
  clearSession();
  currentUser.value = null;
  router.push("/login");
}

function logoutAndRegister() {
  clearSession();
  currentUser.value = null;
  router.push("/register");
}

function openUsersDialog() {
  usersDialogVisible.value = true;
}

function openRegisterDialog() {
  registerDialogVisible.value = true;
}

async function loadUsers() {
  usersLoading.value = true;
  try {
    const res = await authListUsers();
    userItems.value = res.items || [];
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || "加载失败";
    ElMessage.error(typeof msg === "string" ? msg : "加载失败");
    userItems.value = [];
  } finally {
    usersLoading.value = false;
  }
}

async function onLevelChange(row, level) {
  if (row.level === level) return;
  try {
    await authUpdateUserLevel(row.id, level);
    ElMessage.success("已更新");
    row.level = level;
    if (row.id === currentUser.value?.id) {
      const u = { ...currentUser.value, level };
      currentUser.value = u;
      setSession(getToken(), u);
    }
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || "更新失败";
    ElMessage.error(typeof msg === "string" ? msg : "更新失败");
    await loadUsers();
  }
}

async function confirmDeleteUser(row) {
  if (row.id === currentUser.value?.id) return;
  try {
    await ElMessageBox.confirm(
      `将永久删除用户「${row.username}」，不可恢复。是否继续？`,
      "删除用户",
      {
        type: "warning",
        confirmButtonText: "删除",
        cancelButtonText: "取消",
        confirmButtonClass: "el-button--danger",
      },
    );
  } catch {
    return;
  }
  try {
    await authDeleteUser(row.id);
    ElMessage.success("已删除");
    await loadUsers();
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || "删除失败";
    ElMessage.error(typeof msg === "string" ? msg : "删除失败");
  }
}

function resetRegisterForm() {
  regUsername.value = "";
  regPassword.value = "";
  regPassword2.value = "";
}

async function submitRegister() {
  const u = regUsername.value.trim();
  if (!u || !regPassword.value) {
    ElMessage.warning("请填写用户名和密码");
    return;
  }
  if (regPassword.value !== regPassword2.value) {
    ElMessage.warning("两次密码不一致");
    return;
  }
  regLoading.value = true;
  try {
    await authRegister({ username: u, password: regPassword.value });
    ElMessage.success(`用户「${u}」已创建（未切换当前登录会话）`);
    registerDialogVisible.value = false;
    resetRegisterForm();
    if (usersDialogVisible.value) await loadUsers();
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || "注册失败";
    ElMessage.error(typeof msg === "string" ? msg : "注册失败");
  } finally {
    regLoading.value = false;
  }
}

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

onMounted(() => {
  load();
  refreshMe();
});
</script>

<style scoped>
/* 与 AlarmCenter / Dashboard 对齐的页面标题与说明 */
.page-title {
  margin: 0 0 var(--ds-space-3) 0;
  padding-left: 10px;
  border-left: 4px solid var(--ds-primary);
  font-size: 22px;
  font-weight: 500;
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

.settings-page {
  box-sizing: border-box;
  padding-bottom: var(--ds-space-5);
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--ds-space-4);
  align-items: start;
}

/* 卡片：同 AlarmCenter filter-card / Dashboard 曲线卡 */
.settings-card {
  border-radius: var(--ds-radius-lg);
  border: 1px solid var(--ds-border);
  background: var(--ds-bg-card);
  box-shadow: none;
}

.settings-card--risk {
  border-color: var(--ds-border);
}

.settings-card--span {
  grid-column: 1 / -1;
}

.settings-card :deep(.el-card__header) {
  padding: var(--ds-space-2) var(--ds-space-3);
  border-bottom: 1px solid var(--ds-border-light);
}

.settings-card :deep(.el-card__body) {
  padding: var(--ds-space-4);
}

.settings-hd {
  display: flex;
  align-items: center;
  gap: var(--ds-space-2);
  font-size: var(--ds-text-sm);
  font-weight: 600;
  color: var(--ds-text-primary);
}

.settings-hd--risk {
  color: var(--ds-danger);
}

.settings-hd-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--ds-radius-md);
  background: var(--ds-primary-lighter);
  color: var(--ds-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
  flex-shrink: 0;
}

/* 与 Dashboard 底部「内容区 + 快捷操作」相同的分栏 */
.settings-row {
  display: flex;
  gap: var(--ds-space-4);
  align-items: stretch;
}

.settings-row-main {
  flex: 1;
  min-width: 0;
}

.account-head {
  display: flex;
  align-items: center;
  gap: var(--ds-space-3);
  margin-bottom: var(--ds-space-2);
}

.account-avatar {
  width: 44px;
  height: 44px;
  border-radius: var(--ds-radius-md);
  background: linear-gradient(135deg, var(--ds-primary-active), var(--ds-primary-light));
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.account-text {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.account-name {
  font-size: 18px;
  font-weight: 700;
  color: var(--ds-text-primary);
  word-break: break-all;
  line-height: 1.25;
}

.settings-tip {
  margin: var(--ds-space-3) 0 0;
  padding-top: var(--ds-space-3);
  border-top: 1px dashed var(--ds-border-light);
}

.settings-lead {
  margin: 0;
}

/* 快捷操作侧栏：复刻 Dashboard .bc-tools */
.settings-tools {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  align-self: stretch;
  gap: var(--ds-space-3);
  flex-shrink: 0;
  min-width: 200px;
  width: 200px;
  padding: var(--ds-space-3);
  background: var(--ds-bg-elevated);
  border: 1px solid var(--ds-border-strong);
  border-radius: var(--ds-radius-md);
  box-sizing: border-box;
}

.settings-tools-head {
  flex-shrink: 0;
  font-size: var(--ds-text-xs);
  font-weight: 700;
  color: var(--ds-text-secondary);
  letter-spacing: 0.06em;
  text-align: center;
  text-transform: uppercase;
  padding-bottom: 2px;
  border-bottom: 1px solid var(--ds-border);
}

.settings-tools-actions {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-evenly;
  align-items: stretch;
  gap: var(--ds-space-2);
}

.st-btn {
  width: 100%;
  margin: 0 !important;
  height: 36px !important;
  font-size: var(--ds-text-sm) !important;
  font-weight: 600 !important;
  border-radius: 10px !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  gap: var(--ds-space-2) !important;
}

.st-ico {
  font-size: 16px;
  flex-shrink: 0;
}

.st-btn-secondary.el-button {
  background: var(--ds-bg-page) !important;
  border: 1px solid var(--ds-border) !important;
  color: var(--ds-text-primary) !important;
}

.st-btn-secondary.el-button:hover,
.st-btn-secondary.el-button:focus {
  background-color: var(--ds-bg-soft) !important;
  border-color: var(--ds-border-strong) !important;
  color: var(--ds-text-primary) !important;
}

.st-btn-secondary.el-button:active {
  background-color: var(--ds-bg-card) !important;
  border-color: var(--ds-border) !important;
}

/* 与 AlarmCenter 一致的危险按钮（白字 + 品牌红） */
.settings-page :deep(.btn-danger-solid.el-button--danger) {
  --el-button-bg-color: var(--ds-danger);
  --el-button-border-color: var(--ds-danger);
  --el-button-hover-bg-color: #d75a5a;
  --el-button-hover-border-color: #d75a5a;
  --el-button-active-bg-color: #a83838;
  --el-button-active-border-color: #a83838;
  background-color: var(--ds-danger) !important;
  border-color: var(--ds-danger) !important;
  color: #fff !important;
}

.settings-page :deep(.btn-danger-solid.el-button--danger:hover),
.settings-page :deep(.btn-danger-solid.el-button--danger:focus) {
  background-color: #d75a5a !important;
  border-color: #d75a5a !important;
  color: #fff !important;
}

.settings-page :deep(.btn-danger-solid.el-button--danger.is-disabled) {
  opacity: 0.5;
}

.threshold-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.threshold-form :deep(.el-form-item__label) {
  font-weight: 600;
  color: var(--ds-text-secondary);
}

.threshold-actions {
  margin-top: var(--ds-space-4);
  padding-top: var(--ds-space-3);
  border-top: 1px solid var(--ds-border-light);
}

.risk-intro {
  margin: 0 0 var(--ds-space-3);
}

.risk-intro code {
  background: var(--ds-danger-light);
}

.risk-checks {
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-2);
  margin-bottom: var(--ds-space-3);
}

.users-dlg :deep(.el-dialog__body) {
  padding-top: 8px;
}

.users-table {
  width: 100%;
  border-radius: 12px;
  overflow: hidden;
}

.ua-level-select {
  width: 156px;
}

.settings-page :deep(.del-user-btn) {
  font-weight: 600;
  color: var(--ds-danger) !important;
}

.settings-page :deep(.del-user-btn:hover) {
  color: #a83232 !important;
}

.reg-hint {
  margin: 0 0 var(--ds-space-3);
}

.register-submit {
  width: 100%;
  margin-top: var(--ds-space-2);
}

@media (max-width: 1100px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }

  .settings-tools {
    width: 100%;
    min-width: 0;
  }

  .settings-row {
    flex-direction: column;
  }

  .settings-tools-actions {
    flex-direction: row;
    flex-wrap: wrap;
    justify-content: flex-start;
  }

  .st-btn {
    flex: 1 1 160px;
    width: auto;
    min-width: 140px;
  }
}
</style>
