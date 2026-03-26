<template>
  <div class="video-monitor">
    <h2 class="page-title">视频巡检</h2>
    <el-card shadow="hover" class="video-card">
      <el-empty description="视频流功能开发中，后续接入摄像头实时画面" :image-size="160">
        <template #image>
          <el-icon :size="120" color="#c0c4cc"><VideoCamera /></el-icon>
        </template>
        <el-text type="info">待接入 Video.js / HLS.js 实现实时视频播放</el-text>
      </el-empty>
    </el-card>
  </div>
</template>

<script setup>
import { VideoCamera } from "@element-plus/icons-vue";
</script>

<style scoped>
.page-title {
  margin: 0 0 20px 0;
  font-size: 20px;
  color: #303133;
}
.video-card {
  border-radius: 8px;
  min-height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
