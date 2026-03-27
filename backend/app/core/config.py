"""
全局配置（MVP 阶段通过环境变量读取）。

文档技术选型提到：Pydantic 用于数据验证与配置管理。
"""

from pydantic_settings import BaseSettings


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


settings = Settings()

