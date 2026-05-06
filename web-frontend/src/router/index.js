import { createRouter, createWebHistory } from "vue-router";

import Dashboard from "../views/Dashboard.vue";
import InspectionVehicle from "../views/InspectionVehicle.vue";
import AlarmCenter from "../views/AlarmCenter.vue";
import Settings from "../views/Settings.vue";
import AgentAssistant from "../views/AgentAssistant.vue";
import Login from "../views/Login.vue";
import Register from "../views/Register.vue";
import { getToken } from "../utils/authStore.js";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "Login", component: Login, meta: { public: true } },
    { path: "/register", name: "Register", component: Register, meta: { public: true } },
    { path: "/", name: "Dashboard", component: Dashboard },
    { path: "/agent", name: "AgentAssistant", component: AgentAssistant },
    {
      path: "/inspection",
      name: "InspectionVehicle",
      component: InspectionVehicle,
    },
    { path: "/video", redirect: "/inspection" },
    { path: "/vehicle", redirect: "/inspection" },
    { path: "/alarms", name: "AlarmCenter", component: AlarmCenter },
    { path: "/settings", name: "Settings", component: Settings },
    { path: "/users", redirect: "/settings" },
  ],
});

router.beforeEach((to, _from, next) => {
  if (to.meta.public) {
    if (getToken() && (to.path === "/login" || to.path === "/register")) {
      return next({ path: "/" });
    }
    return next();
  }
  if (!getToken()) {
    return next({ path: "/login", query: { redirect: to.fullPath } });
  }
  return next();
});

export default router;
