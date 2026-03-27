import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";
import path from "path";

/**
 * 开发环境建议走同源代理：
 * - 浏览器只访问 http://localhost:5173，/api、/ws 由 Vite 转发到后端
 * - 避免「跨域 + WebSocket」在部分 CORS 配置下握手失败（如曾出现的 /ws 403）
 */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backend = env.VITE_DEV_PROXY_TARGET || "http://127.0.0.1:8000";

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: backend,
          changeOrigin: true,
        },
        "/ws": {
          target: backend,
          ws: true,
          changeOrigin: true,
        },
      },
    },
  };
});

