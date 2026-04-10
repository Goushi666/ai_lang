"""
全局配置：业务与环境相关项请在 backend/.env 中配置，见 backend/.env.example。

代码内仅保留与协议/算法相关的安全默认值；密钥、Broker、车机地址等必须由环境变量提供。
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# app/core/config.py -> backend 根目录（trained_models 等相对路径以此为基准）
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- 应用（可按环境覆盖）---
    APP_NAME: str = "ai_lang-backend"
    API_PREFIX: str = "/api"

    # --- CORS：字符串形式写在 .env，避免 pydantic-settings 对 list 强制 JSON 解析导致 * 报错 ---
    # 支持 *、逗号分隔多源、或 JSON 数组字符串（见 app/middleware/cors.py）
    CORS_ALLOW_ORIGINS: str = "*"

    # --- JWT：密钥仅来自 .env，勿在代码中写死生产密钥 ---
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"

    # --- 数据库 ---
    SQLITE_URL: str = "sqlite+aiosqlite:///./app.db"
    SENSOR_HISTORY_RETENTION_DAYS: int = Field(
        default=0,
        description=">0 时：定期删除早于该天数的 sensor_data，并删除 recorded_at 早于该时间的环境异常落库记录；0 表示不清理",
    )
    # naive 列含义：空/UTC=按 UTC；Asia/Shanghai=按东八区墙钟再换算（修历史误存）
    SQLITE_NAIVE_MEANS_TIMEZONE: str = ""
    # SQLite DateTime 无时区列按何「墙钟」存取：空/UTC=存 UTC 墙钟（推荐，与 ISO Z 一致）；
    # Asia/Shanghai=存北京时间墙钟，Navicat 直读与界面一致；切换后旧 UTC 数据会被误读，需自行迁移或清空。
    SQLITE_NAIVE_WALL_CLOCK_ZONE: str = ""
    # MQTT 无时区 ISO 按何墙钟理解再转 UTC 存库。默认 UTC：多数设备/云模板发的是「已是 UTC 的无时区串」，
    # 若默认上海会把整段时刻再减 8 小时，库内看起来比北京时间慢 8 小时。仅当设备明确发东八区墙钟无时区串时改为 Asia/Shanghai。
    MQTT_NAIVE_ISO_TIMEZONE: str = "UTC"

    # --- 百度智能云 IoT Core MQTT（账号/主题等均在 .env）---
    MQTT_IOT_CORE_ID: str = ""
    MQTT_REGION: str = "gz"
    MQTT_DEVICE_KEY: str = ""
    MQTT_DEVICE_SECRET: str = ""
    MQTT_GATEWAY_KEY: str = ""
    MQTT_GATEWAY_SECRET: str = ""
    MQTT_CLIENT_ID: str = "ai-lang-backend"
    MQTT_UNIQUE_CLIENT_ID: bool = True
    MQTT_STRICT_DEVICE_CLIENT_ID: bool = False
    MQTT_ENABLED: bool = True
    MQTT_SUBSCRIBE_TOPICS: str = "sensor/data"
    MQTT_DISABLE_SENSOR_SIM: bool = True
    MQTT_PORT: int = 1883
    # Web → 树莓派小车控制（SmartCar 手册：car/control，QoS 1）；置空则只更新内存/WebSocket 不发 MQTT
    MQTT_TOPIC_CAR_CONTROL: str = "car/control"
    # 循迹模式切换：car/control/track（JSON mode=normal|track）；置空则无法从 Web 下发模式切换
    MQTT_TOPIC_CAR_TRACK: str = "car/control/track"
    # Web → 树莓派机械臂/云台（手册 arm/control，QoS 1）；云台页仅下发 joint 6、7
    MQTT_TOPIC_ARM_CONTROL: str = "arm/control"

    # --- 环境分析（阈值与上限建议用 .env 按部署调整）---
    ANALYSIS_ENABLED: bool = True
    ANALYSIS_MAX_POINTS: int = 5000
    ANALYSIS_MIN_POINTS: int = 3
    ANALYSIS_STREAK_POINTS: int = 3
    ANALYSIS_MAX_ANOMALY_EXPORT_ROWS: int = 10000
    ANALYSIS_CHART_MAX_POINTS: int = 1500
    ANALYSIS_FORECAST_BASIS_POINTS: int = 200
    ANALYSIS_FORECAST_DAMPING_TAU_HOURS: float = 10.0
    ANALYSIS_FORECAST_MAX_SLOPE_C_PER_HOUR: float = 1.5

    # --- LSTM 温度预测 ---
    FORECAST_USE_LSTM: bool = True
    FORECAST_LSTM_MODEL_PATH: str = "trained_models/lstm_temp.pth"
    FORECAST_LSTM_WINDOW_HOURS: int = 6

    AGENT_ENABLED: bool = True

    # --- 车载视频（车机 URL、是否代理均在 .env）---
    VIDEO_MJPEG_URL: str = ""
    VIDEO_HLS_PLAYLIST_URL: str = ""
    VIDEO_PROXY_THROUGH_BACKEND: bool = False
    VIDEO_MJPEG_MEDIA_TYPE: str = "multipart/x-mixed-replace; boundary=frame"

    @model_validator(mode="after")
    def _resolve_lstm_model_path(self) -> Settings:
        p = Path(self.FORECAST_LSTM_MODEL_PATH)
        if not p.is_absolute():
            p = (_BACKEND_ROOT / p).resolve()
        self.FORECAST_LSTM_MODEL_PATH = str(p)
        return self


settings = Settings()
