import { createApp } from "vue";
import { createPinia } from "pinia";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import "./styles/design-tokens.css";
import router from "./router/index.js";
import App from "./App.vue";

createApp(App).use(createPinia()).use(router).use(ElementPlus).mount("#app");
