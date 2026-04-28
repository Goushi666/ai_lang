<template>
  <el-container class="app-layout">
    <el-container class="app-body">
      <el-aside class="app-aside">
        <div class="aside-brand">
          <span class="brand-logo" aria-hidden="true">
            <svg viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg">
              <path
                d="M464 879.2c-38-4.8-105.6-26.8-136.4-45.2-60.4-35.2-117.2-95.2-145.2-152-28.8-59.2-45.2-138.8-40.4-195.6 3.2-37.2 23.6-110.8 38.4-138l11.2-21.2-10-20c-14.8-29.2-32.8-90.8-37.6-128-2-18-3.2-33.2-2.4-34 0.4-0.8 5.6 2 10.8 6.4 22 16.8 71.6 38.8 119.2 52.4l26 7.2 12-9.2c46-34.4 129.2-58.4 202.4-58.4s156.4 24 202.4 58.4l12 9.2 26-7.2c46-13.2 96-35.2 122.8-54.4l9.2-6.8-2.4 23.6c-5.2 49.2-19.2 99.6-38.8 138.8-10.4 20.8-11.2 24.4-6 30 14.8 17.2 40 100.4 44.8 149.2 5.6 54-11.6 138.4-40.4 197.6-28 56.8-84.8 116.8-145.2 152-32.8 19.2-99.2 40.4-142.4 45.6-40.4 4.8-47.6 4.8-90-0.4z m-29.2-327.2c18.4-8 53.2-40.4 53.2-49.2 0-6.4-182.8-100-190.4-97.2-8 3.2-14.8 34-12.4 56.8 4 37.6 30 72.8 66.8 89.2 23.6 10.8 60 10.8 82.8 0.4z m238.8-4.4c31.6-14.8 58-49.2 64.4-84 2.8-14.4-3.6-50-10.4-58-2.8-3.6-11.6-0.4-34.8 12-16.8 8.8-59.2 30.8-94 48-34.4 17.6-62.8 33.2-62.8 35.2 0 6.8 22 31.6 35.2 40 32.4 20.4 68.8 22.8 102.4 6.8z"
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
import { computed, onMounted, onUnmounted, ref, provide } from "vue";
import { useRoute } from "vue-router";
import { ElNotification } from "element-plus";
import { Monitor, VideoCamera, Bell, Setting, ChatDotRound } from "@element-plus/icons-vue";
import WebSocketClient from "./utils/websocket.js";

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
const currentRoute = computed(() => route.path);

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
  background:
    radial-gradient(circle at 10% 16%, rgba(56, 189, 248, 0.17), transparent 46%),
    radial-gradient(circle at 88% 82%, rgba(45, 212, 191, 0.15), transparent 48%),
    linear-gradient(135deg, rgba(56, 189, 248, 0.12) 0%, rgba(45, 212, 191, 0.1) 100%),
    linear-gradient(180deg, #d9e5ee 0%, #ccdce8 100%);
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

.brand-logo svg {
  width: 26px;
  height: 26px;
  display: block;
  fill: #60a5fa;
  filter: drop-shadow(0 2px 4px rgba(59, 130, 246, 0.25));
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: var(--ds-radius-full);
  display: inline-block;
}
.status-dot.online  {
  background: var(--ds-success);
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.14);
}
.status-dot.offline {
  background: var(--ds-danger);
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.12);
}

.app-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  padding: 10px;
  gap: 10px;
}

.app-aside {
  width: 76px;
  background: linear-gradient(180deg, rgba(223, 233, 248, 0.96), rgba(208, 223, 243, 0.94));
  border: 1px solid rgba(99, 122, 164, 0.28);
  border-radius: 22px;
  backdrop-filter: blur(10px);
  box-shadow: 0 10px 28px rgba(30, 58, 138, 0.12);
  transition:
    width 0.34s cubic-bezier(0.22, 1, 0.36, 1),
    background 0.28s ease,
    box-shadow 0.28s ease;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.app-aside:hover {
  width: 196px;
  background: linear-gradient(180deg, rgba(217, 229, 247, 0.98), rgba(201, 218, 242, 0.96));
  box-shadow: 0 16px 34px rgba(37, 99, 235, 0.16);
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
}

.brand-name {
  opacity: 0;
  max-width: 0;
  white-space: nowrap;
  overflow: hidden;
  transform: translateX(-6px);
  transition:
    max-width 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.2s ease 0.08s,
    transform 0.24s ease 0.08s;
  font-size: 18px;
  font-weight: 800;
  letter-spacing: 0.02em;
  color: #1e293b;
}

.app-aside:hover .brand-name {
  opacity: 1;
  max-width: 120px;
  transform: translateX(0);
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
  border-radius: 14px;
  margin: 0 auto 10px;
  color: #64748b;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  transition: all 0.24s cubic-bezier(0.22, 1, 0.36, 1);
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
}

.side-menu .el-menu-item .el-icon svg {
  width: 18px;
  height: 18px;
  min-width: 18px;
  min-height: 18px;
  display: block;
}

.side-menu .el-menu-item:hover {
  background: rgba(255, 255, 255, 0.45);
  color: #1d4ed8;
  transform: translateY(-1px);
}

.side-menu .el-menu-item.is-active {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.34), rgba(37, 99, 235, 0.24));
  color: #1e40af;
  font-weight: 700;
  box-shadow: 0 10px 20px rgba(59, 130, 246, 0.2);
}

.menu-text {
  opacity: 0;
  max-width: 0;
  white-space: nowrap;
  overflow: hidden;
  transform: translateX(-6px);
  transition:
    max-width 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.2s ease 0.06s,
    transform 0.24s ease 0.06s;
  font-size: 14px;
  font-weight: 600;
  line-height: 1;
}

.app-aside:hover .menu-text {
  opacity: 1;
  max-width: 120px;
  transform: translateX(0);
}

.app-aside:hover .side-menu .el-menu-item {
  width: calc(100% - 16px);
  justify-content: flex-start;
  border-radius: 12px;
  padding: 0 12px !important;
  gap: 10px;
}

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
}

.aside-status .status-text {
  opacity: 0;
  max-width: 0;
  white-space: nowrap;
  overflow: hidden;
  transform: translateX(-6px);
  font-size: 11px;
  line-height: 1;
  transition:
    max-width 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.2s ease 0.1s,
    transform 0.24s ease 0.1s;
}

.app-aside:hover .aside-status .status-text {
  opacity: 1;
  max-width: 84px;
  transform: translateX(0);
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
  border-radius: 18px;
}

.app-main::before {
  content: "";
  position: fixed;
  top: 84px;
  right: -120px;
  width: 360px;
  height: 360px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.16) 0%, rgba(99, 102, 241, 0) 72%);
  pointer-events: none;
  z-index: 0;
}

.app-main::after {
  content: "";
  position: fixed;
  left: -140px;
  bottom: -120px;
  width: 380px;
  height: 380px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(14, 165, 233, 0.14) 0%, rgba(14, 165, 233, 0) 72%);
  pointer-events: none;
  z-index: 0;
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

.page-fade-slide-enter-active,
.page-fade-slide-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.page-fade-slide-enter-from,
.page-fade-slide-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

/* Modern global module + button style */
.app-main .el-card {
  border-radius: 16px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.9), rgba(247, 250, 255, 0.82));
  backdrop-filter: blur(6px);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
}

.app-main .el-card:hover {
  box-shadow: 0 14px 30px rgba(15, 23, 42, 0.1);
}

.app-main .el-button {
  border-radius: 10px;
  font-weight: 600;
  letter-spacing: 0.01em;
  transition: transform 0.16s ease, box-shadow 0.18s ease;
}

.app-main .el-button:hover {
  transform: translateY(-1px);
}

.app-main .el-button:active {
  transform: translateY(0);
}

.app-main .el-button--primary {
  border: none;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  box-shadow: 0 6px 14px rgba(37, 99, 235, 0.3);
}

.app-main .el-button--primary:hover {
  background: linear-gradient(135deg, #4f8ef7 0%, #2b6aed 100%);
  box-shadow: 0 10px 18px rgba(37, 99, 235, 0.34);
}

.app-main .el-button--default {
  border-color: rgba(148, 163, 184, 0.4);
  background: rgba(255, 255, 255, 0.75);
}

.app-main .el-input__wrapper,
.app-main .el-textarea__inner,
.app-main .el-select__wrapper {
  border-radius: 10px;
}
</style>
