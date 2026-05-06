<template>
  <div class="auth-page">
    <el-card class="auth-card" shadow="never">
      <h1 class="auth-title">注册</h1>
      <p class="auth-sub">首名注册用户将自动成为管理员</p>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名（字母、数字、下划线）">
          <el-input v-model="username" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码（至少 6 位）">
          <el-input v-model="password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="password2" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-button type="primary" class="auth-submit" native-type="submit" :loading="loading">
          注册并登录
        </el-button>
      </el-form>
      <p class="auth-footer">
        已有账号？
        <router-link to="/login">去登录</router-link>
      </p>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { authRegister } from "../api/auth.js";
import { setSession } from "../utils/authStore.js";

const router = useRouter();
const username = ref("");
const password = ref("");
const password2 = ref("");
const loading = ref(false);

async function submit() {
  const u = username.value.trim();
  if (!u || !password.value) {
    ElMessage.warning("请填写用户名和密码");
    return;
  }
  if (password.value !== password2.value) {
    ElMessage.warning("两次密码不一致");
    return;
  }
  loading.value = true;
  try {
    const res = await authRegister({ username: u, password: password.value });
    setSession(res.access_token, res.user);
    ElMessage.success("注册成功");
    router.replace("/");
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || "注册失败";
    ElMessage.error(typeof msg === "string" ? msg : "注册失败");
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
  line-height: 1.45;
}
.auth-submit {
  width: 100%;
  margin-top: var(--ds-space-2);
}
.auth-footer {
  margin: var(--ds-space-4) 0 0;
  font-size: var(--ds-text-sm);
  color: var(--ds-text-secondary);
  text-align: center;
}
.auth-footer a {
  color: var(--ds-primary);
  text-decoration: none;
  font-weight: 500;
}
.auth-footer a:hover {
  text-decoration: underline;
}
</style>
