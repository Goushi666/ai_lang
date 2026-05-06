<template>
  <router-view v-if="isAuthPage" />
  <el-container v-else class="app-layout">
    <el-container class="app-body">
      <el-aside class="app-aside">
        <div class="aside-brand">
          <span class="brand-logo" aria-hidden="true">
            <svg class="brand-logo-svg" viewBox="0 0 1054 1024" xmlns="http://www.w3.org/2000/svg">
              <path
                d="M691.828488 808.294579H554.458227v117.461528h137.370261V808.294579z"
                fill="#333333"
              />
              <path
                d="M261.799845 925.756107l39.817467-586.312201h17.91786l-37.826593 586.312201h-19.908734z"
                fill="#333333"
              />
              <path
                d="M57.735327 364.329823H47.78096v443.964756h9.954367V364.329823zM965.573574 925.756107H261.799845v39.817467h703.773729v-39.817467zM301.617312 925.756107h37.826594V261.799845h-37.826594v663.956262z"
                fill="#999999"
              />
              <path
                d="M888.92495 731.645955l76.648624-19.908733-39.817467-175.196855-76.648624 17.91786 39.817467 177.187728z"
                fill="#666666"
              />
              <path
                d="M925.756107 654.001895H691.828488l-37.826593 271.754212h271.754212V654.001895z"
                fill="#999999"
              />
              <path
                d="M554.458227 925.756107H339.443906V654.001895h215.014321v271.754212z"
                fill="#666666"
              />
              <path
                d="M516.631634 654.001895l37.826593-137.370261-215.014321-77.644061v215.014322h177.187728z"
                fill="#4C4C4C"
              />
              <path
                d="M711.737222 351.389146l-14.93155-11.94524-289.672072 369.307006 14.93155 12.940676 289.672072-370.302442zM663.956261 294.649255l-14.93155-12.940676-289.672072 369.307006 14.93155 12.940676 289.672072-369.307006z"
                fill="#999999"
              />
              <path
                d="M320.530609 300.621875m-38.82203 0a38.82203 38.82203 0 1 0 77.64406 0 38.82203 38.82203 0 1 0-77.64406 0Z"
                fill="#4C4C4C"
              />
              <path
                d="M849.107483 731.645955l22.895043-11.94524 12.940677-23.89048 0.995437-13.936113-5.97262-25.881354-20.904171-19.908733-9.954366-1.990874-449.937377 19.908734v57.735327l449.937377 19.908733z"
                fill="#7F7F7F"
              />
              <path
                d="M634.093161 925.756107L417.087966 691.828488l-17.91786 19.908734 195.105588 214.018885h39.817467z"
                fill="#7F7F7F"
              />
              <path
                d="M398.17467 672.915191m-58.730764 0a58.730764 58.730764 0 1 0 117.461527 0 58.730764 58.730764 0 1 0-117.461527 0Z"
                fill="#4C4C4C"
              />
              <path
                d="M67.689694 808.294579H37.826594v19.908734h29.8631v-19.908734zM62.71251 828.203313H42.803777v117.461527h19.908733V828.203313z"
                fill="#B2B2B2"
              />
              <path
                d="M77.644061 878.970583H27.872227v19.908733h49.771834v-19.908733zM77.644061 903.8565H27.872227v6.968057h49.771834v-6.968057zM62.71251 965.573574l14.931551-19.908734H27.872227l14.93155 19.908734h19.908733z"
                fill="#B2B2B2"
              />
              <path
                d="M399.170106 672.915191m-34.840283 0a34.840284 34.840284 0 1 0 69.680567 0 34.840284 34.840284 0 1 0-69.680567 0Z"
                fill="#999999"
              />
              <path
                d="M672.915191 320.530609m-58.730763 0a58.730764 58.730764 0 1 0 117.461527 0 58.730764 58.730764 0 1 0-117.461527 0Z"
                fill="#4C4C4C"
              />
              <path
                d="M672.915191 320.530609m-33.844846 0a33.844847 33.844847 0 1 0 67.689693 0 33.844847 33.844847 0 1 0-67.689693 0Z"
                fill="#999999"
              />
              <path
                d="M165.242488 165.242488l505.68183 76.648624 60.721637 117.461527-607.216371-117.461527 40.812904-76.648624z"
                fill="#999999"
              />
              <path
                d="M47.78096 364.329823V221.982378l76.648624-194.110151 77.644061 79.634934L57.735327 364.329823H47.78096z"
                fill="#666666"
              />
              <path
                d="M57.735327 808.294579H44.79465v19.908734h12.940677v-19.908734zM54.749017 828.203313h-6.968057v117.461527h6.968057V828.203313z"
                fill="#E5E5E5"
              />
              <path
                d="M62.71251 878.970583H42.803777v19.908733h19.908733v-19.908733zM62.71251 903.8565H42.803777v6.968057h19.908733v-6.968057zM54.749017 965.573574l7.963493-19.908734H42.803777l4.977183 19.908734h6.968057z"
                fill="#E5E5E5"
              />
            </svg>
          </span>
          <span class="brand-name">智慧井场</span>
        </div>

        <el-menu :default-active="currentRoute" router class="side-menu">
          <el-menu-item index="/">
            <el-icon><Monitor /></el-icon>
            <span class="menu-text">环境监测</span>
          </el-menu-item>
          <el-menu-item index="/agent">
            <el-icon><ChatDotRound /></el-icon>
            <span class="menu-text">智能助手</span>
          </el-menu-item>
          <el-menu-item index="/inspection">
            <el-icon><VideoCamera /></el-icon>
            <span class="menu-text">巡检与遥控</span>
          </el-menu-item>
          <el-menu-item index="/alarms">
            <el-icon><Bell /></el-icon>
            <span class="menu-text">告警中心</span>
          </el-menu-item>
          <el-menu-item index="/settings">
            <el-icon><Setting /></el-icon>
            <span class="menu-text">系统设置</span>
          </el-menu-item>
        </el-menu>

        <div class="aside-status">
          <span :class="['status-dot', wsConnected ? 'online' : 'offline']"></span>
          <span class="status-text">{{ wsConnected ? '已连接' : '未连接' }}</span>
        </div>
      </el-aside>

      <el-main
        class="app-main"
        :class="{
          'app-main--dashboard': route.path === '/',
          'app-main--inspection': route.path === '/inspection',
          'app-main--agent': route.path === '/agent',
        }"
      >
        <router-view v-slot="{ Component }">
          <transition name="page-fade-slide" mode="out-in">
            <component :is="Component" :class="{ 'app-main-route--fill': route.path === '/inspection' }" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, provide, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElNotification } from "element-plus";
import { Monitor, VideoCamera, Bell, Setting, ChatDotRound } from "@element-plus/icons-vue";
import WebSocketClient from "./utils/websocket.js";
import { authMe } from "./api/auth.js";
import { clearSession, getToken, setSession } from "./utils/authStore.js";

function alarmLevelLabel(level) {
  const map = { low: "低", medium: "中", high: "高", urgent: "紧急" };
  return map[level] || level || "告警";
}

function alarmSeverity(level) {
  const o = { urgent: 4, high: 3, medium: 2, low: 1 };
  return o[level] ?? 2;
}

/** 后端同一次采样可合并多条告警（alarms 数组）；兼容旧版单条 payload */
function normalizeAlarmPayloadList(payload) {
  if (payload && Array.isArray(payload.alarms) && payload.alarms.length) return payload.alarms;
  if (payload && payload.id != null) return [payload];
  return [];
}

function showAlarmNotification(payload) {
  const list = normalizeAlarmPayloadList(payload);
  if (!list.length) return;
  const worst = list.reduce(
    (a, b) => (alarmSeverity(b.level) > alarmSeverity(a.level) ? b : a),
    list[0],
  );
  const n = list.length;
  const body = list.map((x) => x.message || "").filter(Boolean).join("\n");
  const isBad = list.some((x) => x.level === "urgent" || x.level === "high");
  ElNotification({
    title: n > 1 ? `${alarmLevelLabel(worst.level)}级告警（${n} 条）` : `${alarmLevelLabel(worst.level)}级告警`,
    message: body || worst.message || "",
    type: isBad ? "error" : "warning",
    duration: n > 1 ? 8000 : 6000,
  });
}

const route = useRoute();
const router = useRouter();
const currentRoute = computed(() => route.path);
const isAuthPage = computed(() => Boolean(route.meta?.public));
async function refreshAuthUser() {
  if (isAuthPage.value || !getToken()) {
    return;
  }
  try {
    const u = await authMe();
    setSession(getToken(), u);
  } catch {
    clearSession();
    router.push({ path: "/login", query: { redirect: route.fullPath } });
  }
}

watch(
  () => route.fullPath,
  () => {
    refreshAuthUser();
  },
);

/* ---------- 全局 WebSocket ---------- */
const wsConnected = ref(false);

function getWsUrl() {
  if (import.meta.env.VITE_WS_URL) return import.meta.env.VITE_WS_URL;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/ws`;
}

const ws = new WebSocketClient(getWsUrl());

// 扩展连接状态监听
const _origConnect = ws.connect.bind(ws);
ws.connect = function () {
  _origConnect();
  ws.ws.addEventListener("open", () => { wsConnected.value = true; });
  ws.ws.addEventListener("close", () => { wsConnected.value = false; });
};

// 通过 provide 共享给子页面，避免每个页面各自创建连接
provide("ws", ws);
provide("wsConnected", wsConnected);

onMounted(() => {
  refreshAuthUser();
  ws.on("alarm", showAlarmNotification);
  ws.connect();
});
onUnmounted(() => {
  ws.off("alarm", showAlarmNotification);
  ws.close();
});
</script>

<style>
/* 全局 reset */
html, body, #app {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: var(--ds-font-sans);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.app-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: var(--ds-bg-page);
  /* 明度几乎不变的对角过渡，不靠加色相/压暗提质感 */
  background-image: linear-gradient(
    165deg,
    var(--ds-bg-page) 0%,
    var(--ds-bg-soft) 50%,
    var(--ds-bg-page) 100%
  );
  position: relative;
}

/* 纸质颗粒：多层中性点阵，错位叠加，肉眼有「纸面」而不改整体颜色 */
.app-layout::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  background-image:
    radial-gradient(rgba(20, 20, 19, 0.028) 0.32px, transparent 0.32px),
    radial-gradient(rgba(20, 20, 19, 0.04) 0.5px, transparent 0.5px),
    radial-gradient(rgba(20, 20, 19, 0.018) 0.55px, transparent 0.55px);
  background-size: 2.5px 2.5px, 5px 5px, 11px 11px;
  background-position: 0 0, 1.2px 2.4px, 3px 0.8px;
}

/* 极淡定向纤维纹，增强触感；对比度极低，不当作着色层 */
.app-layout::after {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  background-image: repeating-linear-gradient(
    92deg,
    transparent 0,
    transparent 7px,
    rgba(20, 20, 19, 0.006) 7px,
    rgba(20, 20, 19, 0.006) 8px
  );
}

.brand-logo {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: transparent;
}

.brand-logo .brand-logo-svg {
  width: 40px;
  height: 40px;
  display: block;
  transition: transform var(--ds-transition);
}

.app-aside:hover .brand-logo .brand-logo-svg {
  transform: scale(1.05);
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: var(--ds-radius-full);
  display: inline-block;
}
.status-dot.online  {
  background: var(--ds-accent-teal);
  box-shadow: 0 0 0 2px rgba(93, 184, 166, 0.25);
}
.status-dot.offline {
  background: var(--ds-danger);
  box-shadow: 0 0 0 2px rgba(198, 69, 69, 0.2);
}

.app-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  padding: 10px;
  gap: 10px;
  position: relative;
  z-index: 1;
}

.app-aside {
  /* 展开/收起：略长时长 + 顺滑减速，质感主要靠时长与错开而非「弹」 */
  --aside-dur: 0.52s;
  --aside-ease: cubic-bezier(0.22, 1, 0.36, 1);
  --aside-stagger: 20ms;
  width: 76px;
  background: var(--ds-bg-soft);
  border: 1px solid var(--ds-border);
  border-radius: var(--ds-radius-xl);
  box-shadow: var(--ds-shadow-xs);
  transition:
    width var(--aside-dur) var(--aside-ease),
    background calc(var(--aside-dur) * 0.85) var(--aside-ease),
    box-shadow calc(var(--aside-dur) * 0.85) var(--aside-ease),
    border-color calc(var(--aside-dur) * 0.85) var(--aside-ease);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.app-aside:hover {
  width: 196px;
  background: var(--ds-bg-card);
  border-color: var(--ds-border-strong);
  box-shadow: var(--ds-shadow-md);
}

.aside-brand {
  height: 64px;
  margin: 12px 10px 8px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: transparent;
  transition:
    justify-content var(--aside-dur) var(--aside-ease),
    padding var(--aside-dur) var(--aside-ease),
    margin var(--aside-dur) var(--aside-ease);
}

.brand-name {
  opacity: 0;
  max-width: 0;
  white-space: nowrap;
  overflow: hidden;
  transform: translateX(-10px);
  transition:
    max-width var(--aside-dur) var(--aside-ease),
    opacity calc(var(--aside-dur) * 0.9) var(--aside-ease),
    transform var(--aside-dur) var(--aside-ease);
  transition-delay: 0ms;
  font-family: var(--ds-font-display);
  font-size: 20px;
  font-weight: 500;
  letter-spacing: -0.03em;
  color: var(--ds-text-primary);
}

.app-aside:hover .brand-name {
  opacity: 1;
  max-width: 120px;
  transform: translateX(0);
  transition-delay: 0.06s;
}

.app-aside:not(:hover) .brand-name {
  transition-delay: 0ms;
}

.app-aside:hover .aside-brand {
  justify-content: flex-start;
  padding: 0 12px;
}

.app-aside:not(:hover) .aside-brand {
  width: 52px;
  margin-left: auto;
  margin-right: auto;
  justify-content: center;
  padding: 0;
  position: relative;
}

.aside-brand .brand-logo {
  transition: transform var(--aside-dur) var(--aside-ease), left var(--aside-dur) var(--aside-ease);
}

.app-aside:not(:hover) .aside-brand .brand-logo {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.side-menu {
  flex: 1;
  border-right: none;
  background: transparent;
  padding: 8px 0 10px;
  min-height: 0;
}

.side-menu .el-menu-item {
  width: 52px;
  height: 44px;
  line-height: 44px;
  border-radius: var(--ds-radius-md);
  margin: 0 auto 10px;
  color: var(--ds-text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  transition:
    width var(--aside-dur) var(--aside-ease),
    padding var(--aside-dur) var(--aside-ease),
    gap var(--aside-dur) var(--aside-ease),
    border-radius var(--aside-dur) var(--aside-ease),
    margin var(--aside-dur) var(--aside-ease),
    justify-content var(--aside-dur) var(--aside-ease),
    background var(--ds-transition),
    color var(--ds-transition),
    box-shadow var(--ds-transition),
    transform var(--aside-dur) var(--aside-ease);
  transition-delay: 0ms;
  padding: 0 !important;
  border: none;
  background: transparent;
  text-indent: 0;
  letter-spacing: 0;
}

.side-menu .el-menu-item .el-icon {
  width: 20px;
  min-width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin: 0 !important;
  transition:
    transform var(--aside-dur) var(--aside-ease),
    left var(--aside-dur) var(--aside-ease);
}

.side-menu .el-menu-item .el-icon svg {
  width: 18px;
  height: 18px;
  min-width: 18px;
  min-height: 18px;
  display: block;
}

.side-menu .el-menu-item:hover {
  background: var(--ds-bg-card);
  color: var(--ds-text-primary);
}

.side-menu .el-menu-item.is-active {
  background: var(--ds-bg-card-strong);
  color: var(--ds-text-primary);
  font-weight: 500;
  box-shadow: inset 3px 0 0 var(--ds-primary);
}

.menu-text {
  opacity: 0;
  max-width: 0;
  white-space: nowrap;
  overflow: hidden;
  transform: translateX(-10px);
  transition:
    max-width var(--aside-dur) var(--aside-ease),
    opacity calc(var(--aside-dur) * 0.88) var(--aside-ease),
    transform var(--aside-dur) var(--aside-ease);
  transition-delay: 0ms;
  font-size: 13px;
  font-weight: 500;
  line-height: 1;
}

.app-aside:hover .menu-text {
  opacity: 1;
  max-width: 120px;
  transform: translateX(0);
  transition-delay: 0.08s;
}

.app-aside:not(:hover) .menu-text {
  transition-delay: 0ms;
}

.app-aside:hover .side-menu .el-menu-item {
  width: calc(100% - 16px);
  justify-content: flex-start;
  border-radius: var(--ds-radius-lg);
  padding: 0 12px !important;
  gap: 10px;
}

.app-aside:hover .side-menu .el-menu-item:nth-child(1) { transition-delay: 0ms; }
.app-aside:hover .side-menu .el-menu-item:nth-child(2) { transition-delay: calc(var(--aside-stagger) * 1); }
.app-aside:hover .side-menu .el-menu-item:nth-child(3) { transition-delay: calc(var(--aside-stagger) * 2); }
.app-aside:hover .side-menu .el-menu-item:nth-child(4) { transition-delay: calc(var(--aside-stagger) * 3); }
.app-aside:hover .side-menu .el-menu-item:nth-child(5) { transition-delay: calc(var(--aside-stagger) * 4); }

/* 收起：自下而上依次收回，与展开方向对称 */
.app-aside:not(:hover) .side-menu .el-menu-item:nth-child(1) { transition-delay: calc(var(--aside-stagger) * 4); }
.app-aside:not(:hover) .side-menu .el-menu-item:nth-child(2) { transition-delay: calc(var(--aside-stagger) * 3); }
.app-aside:not(:hover) .side-menu .el-menu-item:nth-child(3) { transition-delay: calc(var(--aside-stagger) * 2); }
.app-aside:not(:hover) .side-menu .el-menu-item:nth-child(4) { transition-delay: calc(var(--aside-stagger) * 1); }
.app-aside:not(:hover) .side-menu .el-menu-item:nth-child(5) { transition-delay: 0ms; }

.app-aside:not(:hover) .side-menu .el-menu-item {
  width: 52px;
  margin-left: auto;
  margin-right: auto;
  justify-content: center;
  padding: 0 !important;
  position: relative;
}

.app-aside:not(:hover) .side-menu .el-menu-item .el-icon {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.aside-status {
  margin: 6px 10px 12px;
  min-height: 30px;
  padding: 0 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--ds-space-2);
  color: var(--ds-text-secondary);
  font-size: var(--ds-text-sm);
  transition:
    justify-content var(--aside-dur) var(--aside-ease),
    padding var(--aside-dur) var(--aside-ease),
    margin var(--aside-dur) var(--aside-ease);
}

.aside-status .status-text {
  opacity: 0;
  max-width: 0;
  white-space: nowrap;
  overflow: hidden;
  transform: translateX(-8px);
  font-size: 11px;
  line-height: 1;
  transition:
    max-width var(--aside-dur) var(--aside-ease),
    opacity calc(var(--aside-dur) * 0.85) var(--aside-ease),
    transform var(--aside-dur) var(--aside-ease);
  transition-delay: 0ms;
}

.app-aside:hover .aside-status .status-text {
  opacity: 1;
  max-width: 84px;
  transform: translateX(0);
  transition-delay: calc(var(--aside-stagger) * 3 + 0.04s);
}

.app-aside:not(:hover) .aside-status .status-text {
  transition-delay: 0ms;
}

.app-aside:hover .aside-status {
  justify-content: flex-start;
  padding: 0 12px;
}

.app-aside:not(:hover) .aside-status {
  width: 52px;
  margin-left: auto;
  margin-right: auto;
  justify-content: center;
  padding: 0;
  position: relative;
}

.app-aside:not(:hover) .aside-status .status-dot {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  transition: transform var(--aside-dur) var(--aside-ease), left var(--aside-dur) var(--aside-ease);
}

@media (max-width: 1200px) {
  .app-aside {
    width: 68px;
    border-radius: 20px;
  }

  .app-aside:hover {
    width: 184px;
  }
}

.app-main {
  background-color: transparent;
  padding: var(--ds-space-4) var(--ds-space-5) var(--ds-space-5);
  overflow-y: auto;
  flex: 1;
  min-width: 0;
  min-height: 0;
  position: relative;
  border-radius: var(--ds-radius-xl);
  z-index: 1;
}

.app-main::before,
.app-main::after {
  display: none;
}

.app-main > * {
  position: relative;
  z-index: 1;
}

.app-main--dashboard {
  overflow: hidden;
  padding: var(--ds-space-3) var(--ds-space-4);
  display: flex;
  flex-direction: column;
}

.app-main--inspection {
  overflow: hidden;
  padding: var(--ds-space-4);
  display: flex;
  flex-direction: column;
}

.app-main--agent {
  overflow: hidden;
  padding: var(--ds-space-4) var(--ds-space-5) var(--ds-space-5);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.app-main--agent .agent-page {
  flex: 1;
  min-height: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.app-main--inspection .app-main-route--fill {
  flex: 1;
  min-height: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.page-fade-slide-enter-active {
  transition:
    opacity var(--ds-transition-page) var(--ds-ease-out-expo),
    transform var(--ds-transition-page) var(--ds-ease-out-expo),
    filter var(--ds-transition-page) var(--ds-ease-out-expo);
}

.page-fade-slide-leave-active {
  transition:
    opacity 0.22s var(--ds-ease-out-expo),
    transform 0.24s var(--ds-ease-out-expo);
}

.page-fade-slide-enter-from {
  opacity: 0;
  transform: translateY(14px);
  filter: blur(2px);
}

.page-fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
  filter: blur(1px);
}

@media (prefers-reduced-motion: reduce) {
  .page-fade-slide-enter-active,
  .page-fade-slide-leave-active {
    transition: opacity 0.15s ease;
  }
  .page-fade-slide-enter-from,
  .page-fade-slide-leave-to {
    transform: none;
    filter: none;
  }
}

/* 模块卡片：色块层次为主，hover 轻抬升（DESIGN.md） */
.app-main .el-card {
  border-radius: var(--ds-radius-lg);
  border: 1px solid var(--ds-border);
  background: var(--ds-bg-card);
  box-shadow: none;
  --el-card-bg-color: var(--ds-bg-card);
  --el-text-color-primary: var(--ds-text-primary);
  transition:
    transform var(--ds-transition) var(--ds-ease-out-expo),
    box-shadow var(--ds-transition),
    border-color var(--ds-transition),
    background var(--ds-transition);
}

.app-main .el-card:hover {
  background: var(--ds-bg-card-strong);
  border-color: var(--ds-border-strong);
  box-shadow: var(--ds-shadow-md);
  transform: translateY(-2px);
}

.app-main .el-card__header {
  border-bottom-color: var(--ds-border);
  color: var(--ds-text-primary);
}

.app-main .el-button {
  border-radius: var(--ds-radius-md);
  font-weight: 500;
  letter-spacing: 0;
  transition:
    transform var(--ds-transition) var(--ds-ease-spring),
    background-color var(--ds-transition),
    border-color var(--ds-transition),
    box-shadow var(--ds-transition);
}

.app-main .el-button:hover {
  transform: translateY(-1px);
}

.app-main .el-button:active {
  transform: scale(0.98);
}

.app-main .el-button--primary {
  border: none;
  background: var(--ds-primary);
  color: #fff;
  box-shadow: var(--ds-shadow-xs);
}

.app-main .el-button--primary:hover {
  background: var(--ds-primary-light);
  color: #fff;
  box-shadow: var(--ds-shadow-sm);
}

.app-main .el-button--primary:active {
  background: var(--ds-primary-active);
  box-shadow: none;
}

@media (prefers-reduced-motion: reduce) {
  .app-aside,
  .side-menu .el-menu-item,
  .app-main .el-card,
  .app-main .el-button {
    transition: none !important;
  }
  .app-main .el-card:hover {
    transform: none;
  }
}

.app-main .el-button--default {
  border: 1px solid var(--ds-border);
  background: var(--ds-bg-page);
  color: var(--ds-text-primary);
}

.app-main .el-button--default:hover {
  background: var(--ds-bg-soft);
  border-color: var(--ds-border-strong);
  color: var(--ds-text-primary);
}

.app-main .el-input__wrapper,
.app-main .el-textarea__inner,
.app-main .el-select__wrapper {
  border-radius: var(--ds-radius-md);
  background-color: var(--ds-bg-page) !important;
  box-shadow: 0 0 0 1px var(--ds-border) inset !important;
  transition: box-shadow var(--ds-transition), background-color var(--ds-transition);
}

.app-main .el-input__wrapper:hover,
.app-main .el-select__wrapper:hover {
  box-shadow: 0 0 0 1px var(--ds-border-strong) inset !important;
}

.app-main .el-input__wrapper.is-focus,
.app-main .el-select__wrapper.is-focused {
  box-shadow: 0 0 0 2px rgba(204, 120, 92, 0.35) inset !important;
}

.app-main .el-textarea__inner {
  background-color: var(--ds-bg-page);
  color: var(--ds-text-primary);
}

.app-main .el-table {
  --el-table-bg-color: var(--ds-bg-elevated);
  --el-table-tr-bg-color: var(--ds-bg-elevated);
  --el-table-header-bg-color: var(--ds-bg-soft);
  --el-table-row-hover-bg-color: var(--ds-bg-page);
  --el-table-border-color: var(--ds-border);
  --el-table-text-color: var(--ds-text-secondary);
  --el-table-header-text-color: var(--ds-text-primary);
}

.app-main .el-pagination {
  --el-pagination-text-color: var(--ds-text-muted);
  --el-pagination-button-color: var(--ds-text-secondary);
}
</style>
