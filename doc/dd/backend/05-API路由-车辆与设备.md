# 后端设计 · API 路由（车辆与设备）

## 1. 车辆控制

路由前缀：`/api/vehicle`（注意为单数 `vehicle`，与挂载一致）。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/control` | 接收 `action`、`speed` 等，转发至 `VehicleService` |
| GET | `/status` | 返回当前 `VehicleStatusResponse` |

设计要点：

- 请求体使用 Pydantic 模型校验（如 `VehicleControlRequest`）。
- 状态可被定时任务或硬件回传更新；WebSocket 推送与 REST 读取一致。

详见 `app/api/v1/vehicles.py`。

## 2. 设备管理

路由前缀：`/api/devices`。

目标形态见 [`../../prd/backend/04-设备管理.md`](../../prd/backend/04-设备管理.md)。当前 MVP 可仅保留占位路由（如连通性 `GET /ping`），待设备模型与注册流程确定后扩展列表与 CRUD。

详见 `app/api/v1/devices.py`。
