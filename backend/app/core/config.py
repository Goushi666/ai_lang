"""
全局配置（MVP 阶段通过环境变量读取）。

文档技术选型提到：Pydantic 用于数据验证与配置管理。
"""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings

# app/core/config.py -> backend 根目录（trained_models 等相对路径以此为基准）
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = {"env_file": ".env"}

    APP_NAME: str = "ai_lang-backend"
    API_PREFIX: str = "/api"

    # MVP：先放宽跨域与鉴权，后续再收紧
    CORS_ALLOW_ORIGINS: list[str] = ["*"]

    # JWT
    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"

    # SQLite (MVP) / MySQL (未来)
    SQLITE_URL: str = "sqlite+aiosqlite:///./app.db"
    # 传感器历史保留天数；0 表示不按时间自动删除（仅依赖磁盘与运维）
    SENSOR_HISTORY_RETENTION_DAYS: int = 0

    # 百度智能云 IoT Core MQTT
    MQTT_IOT_CORE_ID: str = ""
    MQTT_REGION: str = "gz"

    # 设备身份（真实设备用，可能受单连接限制）
    MQTT_DEVICE_KEY: str = ""
    MQTT_DEVICE_SECRET: str = ""

    # 后端网关身份（建议配置为独立账号，避免与设备冲突）
    MQTT_GATEWAY_KEY: str = ""
    MQTT_GATEWAY_SECRET: str = ""
    # MQTT 协议里的 ClientId（建议与设备 Key 不同，避免与 MQTTX 等工具互踢）
    MQTT_CLIENT_ID: str = "ai-lang-backend"
    # 为 True 时在 ClientId 后追加随机后缀，同一设备凭证可多开（若平台要求 ClientId=设备Key 请关）
    MQTT_UNIQUE_CLIENT_ID: bool = True
    # 为 True 时强制 ClientId=当前认证用的 DeviceKey/GatewayKey（易与 MQTTX 冲突，仅调试时用）
    MQTT_STRICT_DEVICE_CLIENT_ID: bool = False
    # 是否启用 MQTT 订阅（关则不调 broker，仅靠模拟数据）
    MQTT_ENABLED: bool = True
    # 订阅主题，逗号分隔；传感器默认 sensor/data（与物模型/模板配置一致）
    MQTT_SUBSCRIBE_TOPICS: str = "sensor/data"
    # 为 True 时不启动传感器模拟定时任务（默认关模拟，仅用 MQTT/硬件）
    MQTT_DISABLE_SENSOR_SIM: bool = True

    MQTT_PORT: int = 1883

    # 环境分析
    ANALYSIS_ENABLED: bool = True
    ANALYSIS_MAX_POINTS: int = 5000
    ANALYSIS_MIN_POINTS: int = 3
    ANALYSIS_STREAK_POINTS: int = 3
    ANALYSIS_MAX_ANOMALY_EXPORT_ROWS: int = 10000
    # 折线图点数上限（从时段内原始点均匀抽取）
    ANALYSIS_CHART_MAX_POINTS: int = 1500
    # 温度预测：参与直线拟合的最近采样条数上限
    ANALYSIS_FORECAST_BASIS_POINTS: int = 200
    # 预测阻尼：越大则越远时刻越接近「最后一条实测」，避免直线无限涨/跌（小时为单位）
    ANALYSIS_FORECAST_DAMPING_TAU_HOURS: float = 10.0
    # 允许的最大升温/降温速率（℃/小时），用于裁剪拟合斜率，抑制离谱趋势
    ANALYSIS_FORECAST_MAX_SLOPE_C_PER_HOUR: float = 1.5

    # LSTM 温度预测
    FORECAST_USE_LSTM: bool = True
    FORECAST_LSTM_MODEL_PATH: str = "trained_models/lstm_temp.pth"
    FORECAST_LSTM_WINDOW_HOURS: int = 6

    # 智能 Agent：关则 /api/agent/chat 返回 503
    AGENT_ENABLED: bool = True

    @model_validator(mode="after")
    def _resolve_lstm_model_path(self) -> "Settings":
        p = Path(self.FORECAST_LSTM_MODEL_PATH)
        if not p.is_absolute():
            p = (_BACKEND_ROOT / p).resolve()
        self.FORECAST_LSTM_MODEL_PATH = str(p)
        return self


settings = Settings()

