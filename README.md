# 井场环境监测与智能巡检系统

井场环境监测与智能巡检车远程控制的 Web 平台，支持实时环境数据监控、视频巡检、告警管理和巡检车远程操控。

## 功能模块

- **环境监测看板** — 温度、湿度、光照等传感器数据实时展示与历史趋势查询，支持 CSV 导出
- **视频巡检** — 巡检车摄像头实时视频流播放，支持全屏与状态监控
- **告警中心** — 多级告警（低/中/高/紧急）实时推送，支持桌面通知与声音提醒
- **车辆控制** — 巡检车远程操控（方向/速度），支持手动/自动模式切换与键盘控制
- **系统设置** — 设备管理与告警阈值配置

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + Element Plus + ECharts + Pinia |
| 后端 | FastAPI + SQLAlchemy 2.0 + Pydantic |
| 数据库 | MySQL 8.0 |
| 缓存 | Redis 7.0 |
| 消息 | MQTT (Mosquitto) |
| 实时通信 | WebSocket |

## 项目结构

```
ai_lang/
├── backend/            # 后端服务 (FastAPI)
│   ├── app/
│   │   ├── api/v1/     # API 路由
│   │   ├── core/       # 配置、安全、MQTT
│   │   ├── models/     # 数据库模型
│   │   ├── schemas/    # Pydantic 模型
│   │   ├── services/   # 业务逻辑
│   │   ├── repositories/ # 数据访问
│   │   ├── websocket/  # WebSocket 管理
│   │   └── main.py     # 入口
│   ├── tests/
│   └── requirements.txt
├── web-frontend/       # 前端应用 (Vue 3)
│   ├── src/
│   │   ├── api/        # 接口封装
│   │   ├── views/      # 页面组件
│   │   ├── store/      # 状态管理
│   │   ├── utils/      # 工具函数
│   │   └── router/     # 路由配置
│   ├── package.json
│   └── vite.config.js
└── doc/                # 设计文档与需求文档
```

## 快速开始

### 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端

```bash
cd web-frontend
npm install
npm run dev
```

前端默认访问 http://localhost:5173，后端 API 地址 http://localhost:8000。

## 环境依赖

- Python 3.12+
- Node.js 18+
- MySQL 8.0
- Redis 7.0
- MQTT Broker (Mosquitto)
