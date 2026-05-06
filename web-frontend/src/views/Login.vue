<template>
  <div class="auth-page">
    <el-card class="auth-card" shadow="never">
      <h1 class="auth-title">登录</h1>
      <p class="auth-sub">智慧井场监测平台</p>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名">
          <el-input v-model="username" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="password" type="password" show-password autocomplete="current-password" />
        </el-form-item>
        <el-button type="primary" class="auth-submit" native-type="submit" :loading="loading">
          登录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { authLogin } from "../api/auth.js";
import { setSession } from "../utils/authStore.js";

const route = useRoute();
const router = useRouter();
const username = ref("");
const password = ref("");
const loading = ref(false);

async function submit() {
  if (!username.value.trim() || !password.value) {
    ElMessage.warning("请输入用户名和密码");
    return;
  }
  loading.value = true;
  try {
    const res = await authLogin({
      username: username.value.trim(),
      password: password.value,
    });
    setSession(res.access_token, res.user);
    ElMessage.success("登录成功");
    const redirect = route.query.redirect;
    router.replace(typeof redirect === "string" && redirect.startsWith("/") ? redirect : "/");
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || "登录失败";
    ElMessage.error(typeof msg === "string" ? msg : "登录失败");
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--ds-space-5);
  background: var(--ds-bg-page);
  box-sizing: border-box;
}
.auth-card {
  width: 100%;
  max-width: 400px;
  border-radius: var(--ds-radius-xl);
  border: 1px solid var(--ds-border);
}
.auth-title {
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 600;
  color: var(--ds-text-primary);
}
.auth-sub {
  margin: 0 0 var(--ds-space-4);
  font-size: var(--ds-text-sm);
  color: var(--ds-text-muted);
}
.auth-submit {
  width: 100%;
  margin-top: var(--ds-space-2);
}
</style>
