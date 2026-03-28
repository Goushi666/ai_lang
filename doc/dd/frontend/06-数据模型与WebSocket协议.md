# Web 端设计 · 数据模型与 WebSocket 协议

## 1. 传感器数据

```typescript
interface SensorData {
  timestamp: number
  temperature: number    // 温度 (℃)
  humidity: number       // 湿度 (%RH)
  light: number          // 光照 (Lux)
  deviceId: string
}
```

## 2. 车辆状态

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

## 3. 告警数据

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

## 4. WebSocket 消息外层格式

```json
{
  "type": "message_type",
  "payload": {},
  "timestamp": 1234567890
}
```

## 5. 传感器数据推送

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

（`deviceId` 等字段若后端下发，前端应一并处理。）

## 6. 车辆状态推送

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

## 7. 告警推送

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

## 8. 环境分析摘要推送（可选）

```json
{
  "type": "analysis_summary",
  "payload": {
    "generated_at": 1710000000000,
    "summary_code": "temp_spike",
    "window": { "start": "2025-01-01T00:00:00Z", "end": "2025-01-01T23:59:59Z" }
  },
  "timestamp": 1710000000000
}
```
