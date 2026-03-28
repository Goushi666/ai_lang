# Web 端设计 · API 接口封装

## 1. 传感器 (`api/sensor.js`)

```javascript
import request from '@/utils/request'

export const sensorApi = {
  // 获取最新数据
  getLatest: () => request.get('/api/sensors/latest'),

  // 查询历史数据
  getHistory: (params) => request.get('/api/sensors/history', { params }),

  // 导出数据
  exportData: (params) => request.get('/api/sensors/export', {
    params,
    responseType: 'blob'
  })
}
```

## 2. 车辆控制 (`api/vehicle.js`)

```javascript
import request from '@/utils/request'

export const vehicleApi = {
  // 发送控制指令
  sendControl: (data) => request.post('/api/vehicle/control', data),

  // 获取车辆状态
  getStatus: () => request.get('/api/vehicle/status')
}
```

## 3. 告警 (`api/alarm.js`)

```javascript
import request from '@/utils/request'

export const alarmApi = {
  // 查询历史告警
  getHistory: (params) => request.get('/api/alarms/history', { params }),

  // 标记已读
  markRead: (id) => request.put(`/api/alarms/${id}/read`),

  // 获取告警配置
  getConfig: () => request.get('/api/alarms/config'),

  // 更新告警配置
  updateConfig: (data) => request.put('/api/alarms/config', data)
}
```

设备相关封装在实现 `GET/PUT /api/devices*` 后补充至 `api/device.js`。

## 4. 环境分析 (`api/analysis.js`)

```javascript
import request from '@/utils/request'

export const analysisApi = {
  getSummary: (params) =>
    request.get('/api/analysis/environment/summary', { params }),
  runAnalysis: (params) =>
    request.post('/api/analysis/environment/run', null, { params }),
}
```

## 5. 智能 Agent (`api/agent.js`)

```javascript
import request from '@/utils/request'

export const agentApi = {
  chat: (body) => request.post('/api/agent/chat', body),
  health: () => request.get('/api/agent/health'),
}
```

流式接口可用原生 `fetch` + SSE，见 [`10-Agent对话模块.md`](./10-Agent对话模块.md)。
