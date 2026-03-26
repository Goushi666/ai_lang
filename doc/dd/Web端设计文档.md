# Web端设计文档

## 1. 系统架构设计

### 1.1 整体架构
```
┌─────────────────────────────────────────────────────────┐
│                    前端应用层 (Vue.js)                    │
├─────────────────────────────────────────────────────────┤
│  环境监测  │  视频巡检  │  告警中心  │  车辆控制  │  系统设置  │
├─────────────────────────────────────────────────────────┤
│              通信层 (WebSocket + Axios)                  │
├─────────────────────────────────────────────────────────┤
│                  后端服务 (FastAPI)                       │
└─────────────────────────────────────────────────────────┘
```

### 1.2 技术选型
- **前端框架**：Vue 3 + Composition API
- **状态管理**：Pinia
- **路由管理**：Vue Router 4
- **UI组件库**：Element Plus
- **图表库**：ECharts
- **HTTP客户端**：Axios
- **WebSocket客户端**：原生WebSocket API
- **视频播放**：Video.js 或 HLS.js
- **构建工具**：Vite
- **代码规范**：ESLint + Prettier

---

## 2. 目录结构设计

```
web-frontend/
├── public/                  # 静态资源
│   ├── favicon.ico
│   └── index.html
├── src/
│   ├── api/                # API接口封装
│   │   ├── sensor.js       # 传感器数据接口
│   │   ├── alarm.js        # 告警接口
│   │   ├── vehicle.js      # 车辆控制接口
│   │   └── device.js       # 设备管理接口
│   ├── assets/             # 资源文件
│   │   ├── images/
│   │   └── styles/
│   ├── components/         # 公共组件
│   │   ├── common/         # 通用组件
│   │   ├── charts/         # 图表组件
│   │   └── video/          # 视频组件
│   ├── views/              # 页面视图
│   │   ├── Dashboard.vue   # 环境监测
│   │   ├── VideoMonitor.vue # 视频巡检
│   │   ├── AlarmCenter.vue  # 告警中心
│   │   ├── VehicleControl.vue # 车辆控制
│   │   └── Settings.vue     # 系统设置
│   ├── router/             # 路由配置
│   │   └── index.js
│   ├── store/              # 状态管理
│   │   ├── modules/
│   │   │   ├── sensor.js
│   │   │   ├── alarm.js
│   │   │   └── vehicle.js
│   │   └── index.js
│   ├── utils/              # 工具函数
│   │   ├── request.js      # HTTP请求封装
│   │   ├── websocket.js    # WebSocket封装
│   │   └── format.js       # 数据格式化
│   ├── config/             # 配置文件
│   │   └── index.js
│   ├── App.vue
│   └── main.js
├── .env.development        # 开发环境配置
├── .env.production         # 生产环境配置
├── package.json
└── vite.config.js
```

---

## 3. 核心模块设计

### 3.1 通信层设计

#### 3.1.1 HTTP请求封装 (utils/request.js)
```javascript
import axios from 'axios'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 10000
})

// 请求拦截器
request.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => Promise.reject(error)
)

// 响应拦截器
request.interceptors.response.use(
  response => response.data,
  error => {
    // 错误处理
    return Promise.reject(error)
  }
)

export default request
```

#### 3.1.2 WebSocket封装 (utils/websocket.js)
```javascript
class WebSocketClient {
  constructor(url) {
    this.url = url
    this.ws = null
    this.reconnectTimer = null
    this.heartbeatTimer = null
    this.listeners = new Map()
  }

  connect() {
    this.ws = new WebSocket(this.url)

    this.ws.onopen = () => {
      console.log('WebSocket连接成功')
      this.startHeartbeat()
    }

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      this.handleMessage(data)
    }

    this.ws.onclose = () => {
      console.log('WebSocket连接断开')
      this.reconnect()
    }

    this.ws.onerror = (error) => {
      console.error('WebSocket错误:', error)
    }
  }

  // 心跳保活
  startHeartbeat() {
    this.heartbeatTimer = setInterval(() => {
      if (this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30000)
  }

  // 断线重连
  reconnect() {
    if (this.reconnectTimer) return
    this.reconnectTimer = setTimeout(() => {
      this.connect()
      this.reconnectTimer = null
    }, 5000)
  }

  // 消息分发
  handleMessage(data) {
    const { type, payload } = data
    const listeners = this.listeners.get(type) || []
    listeners.forEach(callback => callback(payload))
  }

  // 订阅消息
  on(type, callback) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, [])
    }
    this.listeners.get(type).push(callback)
  }

  // 发送消息
  send(data) {
    if (this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  // 关闭连接
  close() {
    clearInterval(this.heartbeatTimer)
    clearTimeout(this.reconnectTimer)
    this.ws?.close()
  }
}

export default WebSocketClient
```

### 3.2 API接口设计

#### 3.2.1 传感器数据接口 (api/sensor.js)
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

#### 3.2.2 车辆控制接口 (api/vehicle.js)
```javascript
import request from '@/utils/request'

export const vehicleApi = {
  // 发送控制指令
  sendControl: (data) => request.post('/api/vehicle/control', data),

  // 获取车辆状态
  getStatus: () => request.get('/api/vehicle/status')
}
```

#### 3.2.3 告警接口 (api/alarm.js)
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

---

### 3.3 状态管理设计

#### 3.3.1 传感器数据状态 (store/modules/sensor.js)
```javascript
import { defineStore } from 'pinia'
import { sensorApi } from '@/api/sensor'

export const useSensorStore = defineStore('sensor', {
  state: () => ({
    latestData: null,
    historyData: [],
    loading: false
  }),

  actions: {
    async fetchLatest() {
      this.loading = true
      try {
        this.latestData = await sensorApi.getLatest()
      } finally {
        this.loading = false
      }
    },

    async fetchHistory(params) {
      this.loading = true
      try {
        this.historyData = await sensorApi.getHistory(params)
      } finally {
        this.loading = false
      }
    },

    updateRealtimeData(data) {
      this.latestData = data
    }
  }
})
```

#### 3.3.2 车辆控制状态 (store/modules/vehicle.js)
```javascript
import { defineStore } from 'pinia'
import { vehicleApi } from '@/api/vehicle'

export const useVehicleStore = defineStore('vehicle', {
  state: () => ({
    status: {
      mode: 'manual',
      speed: 0,
      connected: false
    },
    controlEnabled: false
  }),

  actions: {
    async sendCommand(command) {
      await vehicleApi.sendControl(command)
    },

    updateStatus(status) {
      this.status = { ...this.status, ...status }
      this.controlEnabled = status.connected
    }
  }
})
```

---

### 3.4 页面组件设计

#### 3.4.1 环境监测页面 (views/Dashboard.vue)
**功能模块**：
- 实时数据卡片展示（温度、湿度、光照）
- 历史数据趋势图表
- 时间范围选择器
- 数据导出按钮

**数据流**：
1. 页面加载时获取最新数据
2. 通过WebSocket订阅实时数据推送
3. 用户选择时间范围查询历史数据
4. ECharts渲染趋势图表

#### 3.4.2 车辆控制页面 (views/VehicleControl.vue)
**功能模块**：
- 方向控制按钮组（前进、后退、左转、右转、停止）
- 模式切换开关（手动/自动）
- 状态监控面板（速度、模式、连接状态）
- 紧急停止按钮

**交互逻辑**：
```javascript
// 控制指令发送
const sendCommand = async (action) => {
  if (!vehicleStore.controlEnabled) {
    ElMessage.warning('车辆未连接')
    return
  }

  await vehicleStore.sendCommand({
    action,
    speed: currentSpeed.value,
    timestamp: Date.now()
  })
}

// 键盘控制
const handleKeydown = (e) => {
  const keyMap = {
    'w': 'forward',
    's': 'backward',
    'a': 'left',
    'd': 'right'
  }

  const action = keyMap[e.key.toLowerCase()]
  if (action) sendCommand(action)
}
```

#### 3.4.3 告警中心页面 (views/AlarmCenter.vue)
**功能模块**：
- 告警列表（分级显示）
- 筛选器（级别、时间范围）
- 告警统计图表
- 桌面通知

**告警处理**：
```javascript
// WebSocket告警推送处理
ws.on('alarm', (alarm) => {
  // 添加到列表
  alarmStore.addAlarm(alarm)

  // 弹窗提示
  ElNotification({
    title: `${alarm.level}级告警`,
    message: alarm.message,
    type: getAlarmType(alarm.level),
    duration: 0
  })

  // 桌面通知
  if (Notification.permission === 'granted') {
    new Notification('系统告警', {
      body: alarm.message,
      icon: '/alarm-icon.png'
    })
  }

  // 声音提示
  if (settings.soundEnabled) {
    playAlarmSound()
  }
})
```

---

## 4. 数据模型设计

### 4.1 传感器数据模型
```typescript
interface SensorData {
  timestamp: number
  temperature: number    // 温度 (℃)
  humidity: number       // 湿度 (%RH)
  light: number          // 光照 (Lux)
  deviceId: string
}
```

### 4.2 车辆状态模型
```typescript
interface VehicleStatus {
  mode: 'manual' | 'auto'
  speed: number
  leftSpeed: number
  rightSpeed: number
  connected: boolean
  deviation?: number     // 循迹偏差
  correction?: number    // 修正量
}
```

### 4.3 告警数据模型
```typescript
interface Alarm {
  id: string
  type: string           // 告警类型
  level: 'low' | 'medium' | 'high' | 'urgent'
  message: string
  value: number
  threshold: number
  timestamp: number
  read: boolean
}
```

---

## 5. WebSocket消息协议设计

### 5.1 消息格式
```json
{
  "type": "message_type",
  "payload": {},
  "timestamp": 1234567890
}
```

### 5.2 消息类型

#### 5.2.1 传感器数据推送
```json
{
  "type": "sensor_data",
  "payload": {
    "temperature": 25.5,
    "humidity": 60.2,
    "light": 350
  },
  "timestamp": 1234567890
}
```

#### 5.2.2 车辆状态推送
```json
{
  "type": "vehicle_status",
  "payload": {
    "mode": "manual",
    "speed": 50,
    "connected": true
  },
  "timestamp": 1234567890
}
```

#### 5.2.3 告警推送
```json
{
  "type": "alarm",
  "payload": {
    "id": "alarm_001",
    "level": "high",
    "message": "温度超过阈值",
    "value": 35.5,
    "threshold": 30
  },
  "timestamp": 1234567890
}
```

---

## 6. 性能优化设计

### 6.1 前端优化
- **路由懒加载**：按需加载页面组件
- **组件缓存**：使用keep-alive缓存页面状态
- **图表优化**：大数据量时使用数据抽样
- **防抖节流**：控制指令发送频率
- **虚拟滚动**：告警列表使用虚拟滚动

### 6.2 网络优化
- **请求合并**：批量获取数据
- **数据缓存**：使用localStorage缓存配置
- **WebSocket复用**：单一连接多路复用
- **断线重连**：指数退避重连策略

---

## 7. 安全设计

### 7.1 认证授权
- JWT Token认证
- Token自动刷新机制
- 路由守卫权限控制

### 7.2 数据安全
- HTTPS/WSS加密传输
- 敏感数据加密存储
- XSS防护（内容转义）
- CSRF防护（Token验证）

---

## 8. 部署方案

### 8.1 构建配置
```javascript
// vite.config.js
export default {
  build: {
    outDir: 'dist',
    minify: 'terser',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
          'ui-vendor': ['element-plus'],
          'chart-vendor': ['echarts']
        }
      }
    }
  }
}
```

### 8.2 部署方式
- **开发环境**：npm run dev
- **生产构建**：npm run build
- **静态部署**：Nginx托管dist目录
- **容器部署**：Docker镜像部署

### 8.3 Nginx配置示例
```nginx
server {
  listen 80;
  server_name example.com;

  root /var/www/html/dist;
  index index.html;

  location / {
    try_files $uri $uri/ /index.html;
  }

  location /api {
    proxy_pass http://backend:8000;
    proxy_set_header Host $host;
  }

  location /ws {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
  }
}
```

---

## 9. 测试方案

### 9.1 单元测试
- 使用Vitest进行组件单元测试
- 测试覆盖率目标：>80%

### 9.2 集成测试
- API接口集成测试
- WebSocket通信测试
- 端到端功能测试

### 9.3 性能测试
- Lighthouse性能评分
- 首屏加载时间测试
- WebSocket消息延迟测试
