<template>
  <el-container class="app-layout">
    <!-- 顶部导航栏 -->
    <el-header class="app-header">
      <div class="header-left">
        <span class="logo-title">井场环境监测与智能巡检系统</span>
      </div>
      <div class="header-right">
        <span :class="['status-dot', wsConnected ? 'online' : 'offline']"></span>
        <span class="status-text">{{ wsConnected ? '已连接' : '未连接' }}</span>
      </div>
    </el-header>

    <el-container class="app-body">
      <!-- 左侧菜单栏 -->
      <el-aside width="200px" class="app-aside">
        <el-menu
          :default-active="currentRoute"
          router
          background-color="#1e293b"
          text-color="#94a3b8"
          active-text-color="#60a5fa"
        >
          <el-menu-item index="/">
            <el-icon><Monitor /></el-icon>
            <span>环境监测</span>
          </el-menu-item>
          <el-menu-item index="/agent">
            <el-icon><ChatDotRound /></el-icon>
            <span>智能助手</span>
          </el-menu-item>
          <el-menu-item index="/inspection">
            <el-icon><VideoCamera /></el-icon>
            <span>巡检与遥控</span>
          </el-menu-item>
          <el-menu-item index="/alarms">
            <el-icon><Bell /></el-icon>
            <span>告警中心</span>
          </el-menu-item>
          <el-menu-item index="/settings">
            <el-icon><Setting /></el-icon>
            <span>系统设置</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <!-- 主内容区 -->
      <el-main
        class="app-main"
        :class="{
          'app-main--dashboard': route.path === '/',
          'app-main--inspection': route.path === '/inspection',
          'app-main--agent': route.path === '/agent',
        }"
      >
        <router-view :class="{ 'app-main-route--fill': route.path === '/inspection' }" />
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
}

.app-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.app-header {
  background: var(--ds-bg-header);
  color: var(--ds-text-inverse);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--ds-space-5);
  height: 52px;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.06);
  z-index: 10;
}

.logo-title {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.5px;
  background: linear-gradient(135deg, #e0f2fe, #bfdbfe);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--ds-space-2);
  font-size: var(--ds-text-sm);
  color: var(--ds-text-muted);
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: var(--ds-radius-full);
  display: inline-block;
}
.status-dot.online  {
  background: var(--ds-success);
  box-shadow: 0 0 6px rgba(16, 185, 129, 0.5);
}
.status-dot.offline {
  background: var(--ds-danger);
  box-shadow: 0 0 6px rgba(239, 68, 68, 0.4);
}

.app-aside {
  background: var(--ds-bg-sidebar);
  overflow-y: auto;
  width: 200px;
  border-right: 1px solid rgba(255, 255, 255, 0.06);
}

.app-aside .el-menu {
  border-right: none;
  padding-top: var(--ds-space-2);
}

.app-aside .el-menu-item {
  height: 44px;
  line-height: 44px;
  margin: 2px 8px;
  border-radius: var(--ds-radius-sm);
  font-size: var(--ds-text-base);
  transition: all var(--ds-transition);
}

.app-aside .el-menu-item:hover {
  background: rgba(255, 255, 255, 0.06) !important;
}

.app-aside .el-menu-item.is-active {
  background: rgba(59, 130, 246, 0.15) !important;
  color: var(--ds-primary-light) !important;
  font-weight: 500;
  position: relative;
}

.app-aside .el-menu-item.is-active::before {
  content: "";
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 0 2px 2px 0;
  background: var(--ds-primary);
}

.app-main {
  background-color: var(--ds-bg-page);
  padding: var(--ds-space-5);
  overflow-y: auto;
  flex: 1;
  min-width: 0;
  min-height: 0;
}

.app-main--dashboard {
  overflow: hidden;
  padding: var(--ds-space-2) var(--ds-space-3);
  display: flex;
  flex-direction: column;
}

.app-main--inspection {
  overflow: hidden;
  padding: var(--ds-space-3);
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
</style>
