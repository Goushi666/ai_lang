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

    <el-container>
      <!-- 左侧菜单栏 -->
      <el-aside width="200px" class="app-aside">
        <el-menu
          :default-active="currentRoute"
          router
          background-color="#304156"
          text-color="#bfcbd9"
          active-text-color="#409EFF"
        >
          <el-menu-item index="/">
            <el-icon><Monitor /></el-icon>
            <span>环境监测</span>
          </el-menu-item>
          <el-menu-item index="/video">
            <el-icon><VideoCamera /></el-icon>
            <span>视频巡检</span>
          </el-menu-item>
          <el-menu-item index="/alarms">
            <el-icon><Bell /></el-icon>
            <span>告警中心</span>
          </el-menu-item>
          <el-menu-item index="/vehicle">
            <el-icon><Van /></el-icon>
            <span>车辆控制</span>
          </el-menu-item>
          <el-menu-item index="/settings">
            <el-icon><Setting /></el-icon>
            <span>系统设置</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <!-- 主内容区 -->
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, provide } from "vue";
import { useRoute } from "vue-router";
import { Monitor, VideoCamera, Bell, Van, Setting } from "@element-plus/icons-vue";
import WebSocketClient from "./utils/websocket.js";

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

onMounted(() => { ws.connect(); });
onUnmounted(() => { ws.close(); });
</script>

<style>
/* 全局 reset */
html, body, #app {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: "Helvetica Neue", Helvetica, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", Arial, sans-serif;
}

.app-layout {
  height: 100vh;
}

.app-header {
  background-color: #1d2b3a;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 56px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, .15);
}

.logo-title {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 1px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.status-dot.online  { background: #67c23a; }
.status-dot.offline { background: #f56c6c; }

.app-aside {
  background-color: #304156;
  overflow-y: auto;
}

.app-aside .el-menu {
  border-right: none;
}

.app-main {
  background-color: #f0f2f5;
  padding: 20px;
  overflow-y: auto;
}
</style>
