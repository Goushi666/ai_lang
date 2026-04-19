# 后端设计 · API 路由（车辆与设备）

## 1. 车辆控制

路由前缀：`/api/vehicle`（注意为单数 `vehicle`，与挂载一致）。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/control` | 小车方向控制：`action`、`speed`、`timestamp`；可选 **duration**（持续时间，与车端协议一致） |
| GET | `/status` | 返回 `VehicleStatusResponse`（含 **drive_mode**：`normal` \| `track` 等） |
| POST | `/track` | **循迹模式切换**：`mode`=`normal` \| `track`，经 MQTT `car/control/track` |
| POST | `/gimbal` | **云台**：关节 **6**（如 0–180°）、关节 **7**（如 0–90°）、`speed`；循迹模式下 **409** |
| POST | `/arm` | **机械臂**：关节 **0–5**（0–180°）、`speed` |

**drive_mode**：`normal` 表示可手动控制；`track` 为循迹，服务端会拒绝手动方向/云台（与实现一致）。

**duration**：在 `/control` 请求体中用于短时运动控制，具体含义见 `VehicleControlRequest` 与车端约定。

设计要点：

- 请求体使用 Pydantic 模型校验。
- 循迹与 MQTT 主题 `MQTT_TOPIC_CAR_TRACK`、`MQTT_TOPIC_ARM_CONTROL` 等由 `settings` 配置。

详见 `app/api/v1/vehicles.py`。

## 2. 设备管理

路由前缀：`/api/devices`。

目标形态见 [`../../prd/backend/04-设备管理.md`](../../prd/backend/04-设备管理.md)。当前 MVP 可仅保留占位路由（如连通性 `GET /ping`），待设备模型与注册流程确定后扩展列表与 CRUD。

详见 `app/api/v1/devices.py`。
