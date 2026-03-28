import { createRouter, createWebHistory } from "vue-router";

import Dashboard from "../views/Dashboard.vue";
import VideoMonitor from "../views/VideoMonitor.vue";
import AlarmCenter from "../views/AlarmCenter.vue";
import VehicleControl from "../views/VehicleControl.vue";
import Settings from "../views/Settings.vue";
import AgentAssistant from "../views/AgentAssistant.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "Dashboard", component: Dashboard },
    { path: "/agent", name: "AgentAssistant", component: AgentAssistant },
    { path: "/video", name: "VideoMonitor", component: VideoMonitor },
    { path: "/alarms", name: "AlarmCenter", component: AlarmCenter },
    { path: "/vehicle", name: "VehicleControl", component: VehicleControl },
    { path: "/settings", name: "Settings", component: Settings },
  ],
});

export default router;

