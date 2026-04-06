import { createRouter, createWebHistory } from "vue-router";

import Dashboard from "../views/Dashboard.vue";
import InspectionVehicle from "../views/InspectionVehicle.vue";
import AlarmCenter from "../views/AlarmCenter.vue";
import Settings from "../views/Settings.vue";
import AgentAssistant from "../views/AgentAssistant.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
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
  ],
});

export default router;

