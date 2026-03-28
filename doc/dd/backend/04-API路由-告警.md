# 后端设计 · API 路由（告警）

路由前缀：`/api/alarms`。

## 端点一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/history` | 按 `start_time`、`end_time` 查询历史告警 |
| PUT | `/{alarm_id}/read` | 标记指定告警已读 |
| GET | `/config` | 获取告警阈值配置 |
| PUT | `/config` | 更新告警阈值配置 |

## 设计要点

- `AlarmService` 负责与 `AlarmRepository` 交互及阈值应用；推送新告警时通过 `websocket_manager` 广播。
- `AlarmConfig` 等 Schema 与前端表单字段对齐，便于双向绑定。

具体函数签名与响应模型见 `app/api/v1/alarms.py`、`app/schemas/alarm.py`。
