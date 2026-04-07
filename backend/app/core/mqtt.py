"""
MQTT 设备消息接入层 —— 百度智能云 IoT Core。

职责概览
--------
1. 使用 paho-mqtt 连接百度 IoT broker（用户名/密码签名与控制台一致）。
2. 订阅模板中的传感器主题（默认 ``sensor/data``），收到消息后交给上层处理。
3. 提供 ``normalize_sensor_dict``，把设备 JSON 转为统一字段，便于写入仓库并 WebSocket 推送给前端。

与 MQTTX「互踢」问题（重要）
---------------------------
MQTT 服务端对 **同一身份** 往往只保留 **一条在线连接**。常见两类原因：

- **ClientId 相同**：若后端与 MQTTX 都使用 ``client_id = 设备 DeviceKey``，后连上的会把先连上的挤掉。
- **同一设备凭证多会话**：部分平台按 **DeviceKey** 限流为单连接，此时即使用不同 ClientId，仍可能互踢。

推荐做法：

- **后端使用独立「网关/应用端」设备**（``MQTT_GATEWAY_KEY`` / ``MQTT_GATEWAY_SECRET``），MQTTX 使用现场设备 ``MQTT_DEVICE_KEY``；两端身份不同，可同时在线。
- 若暂时共用一个设备凭证：在 ``MQTT_STRICT_DEVICE_CLIENT_ID=false``（默认）下，本模块会为后端生成 **独立 ClientId**（``MQTT_CLIENT_ID`` + 随机后缀），
  可避免「仅因 ClientId 相同」导致的互踢；若平台强制 ClientId 必须等于 DeviceKey，请把 ``MQTT_STRICT_DEVICE_CLIENT_ID=true``，
  并接受「同一设备只能一端在线」，或改为网关设备方案。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import paho.mqtt.client as paho_mqtt

from app.core.config import settings

# paho-mqtt 2.0+ 提供 CallbackAPIVersion；1.x 没有。优先从 enums 导入（官方推荐），
# 也避免写成 paho_mqtt.CallbackAPIVersion 时部分类型检查器在 client 模块上解析不到。
try:
    from paho.mqtt.enums import CallbackAPIVersion
except ImportError:
    CallbackAPIVersion = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)


def _build_credentials() -> tuple[str, str, str, str]:
    """
    构造百度 IoT Core 的 username / password / broker 地址 / 用于认证的 device_key。

    优先使用网关身份（``MQTT_GATEWAY_*``），避免后端与现场设备共用同一 DeviceKey 导致单连接互踢。
    """
    ts = str(int(time.time()))
    algo = "MD5"

    device_key = settings.MQTT_GATEWAY_KEY or settings.MQTT_DEVICE_KEY
    device_secret = settings.MQTT_GATEWAY_SECRET or settings.MQTT_DEVICE_SECRET

    username = f"thingidp@{settings.MQTT_IOT_CORE_ID}|{device_key}|{ts}|{algo}"
    sign_str = f"{device_key}&{ts}&{algo}{device_secret}"
    password = hashlib.md5(sign_str.encode()).hexdigest()
    broker = f"{settings.MQTT_IOT_CORE_ID}.iot.{settings.MQTT_REGION}.baidubce.com"

    return username, password, broker, device_key


def _resolve_client_id(auth_device_key: str) -> str:
    """根据配置生成 MQTT ClientId（避免与 MQTTX 默认使用 DeviceKey 冲突）。"""
    if settings.MQTT_STRICT_DEVICE_CLIENT_ID:
        return auth_device_key

    base = (settings.MQTT_CLIENT_ID or "").strip() or f"{auth_device_key}-server"
    if settings.MQTT_UNIQUE_CLIENT_ID:
        return f"{base}-{uuid.uuid4().hex[:12]}"
    return base


def _parse_subscribe_topics() -> list[str]:
    raw = settings.MQTT_SUBSCRIBE_TOPICS or "sensor/data"
    return [t.strip() for t in raw.split(",") if t.strip()]


def _float_or_default(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _optional_float_from_keys(data: dict[str, Any], *keys: str) -> float | None:
    """
    若 data 中未出现任一 keys，则返回 None（表示「本包未携带该量，应沿用上次采样」）。
    若出现但无法解析为有限数值，同样视为未携带（None），避免把温湿度写成 0 覆盖真值。
    """
    for k in keys:
        if k not in data:
            continue
        v = _float_or_default(data.get(k), default=float("nan"))
        if v != v:  # NaN
            return None
        return v
    return None


def _parse_timestamp(value: Any) -> datetime:
    """支持毫秒/秒时间戳或缺省（使用当前 UTC）。"""
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, (int, float)):
        n = float(value)
        # 毫秒
        if n > 1e12:
            return datetime.fromtimestamp(n / 1000.0, tz=timezone.utc)
        if n > 1e9:
            return datetime.fromtimestamp(n, tz=timezone.utc)
        return datetime.now(timezone.utc)
    if isinstance(value, str):
        s = value.strip()
        if s.isdigit():
            return _parse_timestamp(int(s))
        try:
            # ISO8601
            return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            return datetime.now(timezone.utc)
    return datetime.now(timezone.utc)


def normalize_sensor_dict(data: dict[str, Any]) -> Optional[dict[str, Any]]:
    """
    将设备上报 JSON 转为内部统一结构。

    分 topic 上报时（如 sensor/dht 与 sensor/light）各包可能只含部分字段；
    未出现的字段用 None 表示，入库时与上一条同设备记录合并，避免缺省被写成 0 覆盖真值。

    Returns:
        dict 含 device_id, temperature/humidity/light（Optional[float]）, timestamp(datetime)；无法识别时返回 None。
    """
    if not isinstance(data, dict) or not data:
        return None

    device_id = (
        data.get("deviceId")
        or data.get("device_id")
        or data.get("deviceName")
        or data.get("device_name")
        or "mqtt_device"
    )
    if not isinstance(device_id, str):
        device_id = str(device_id)

    temperature = _optional_float_from_keys(data, "temperature", "temp", "t")
    humidity = _optional_float_from_keys(data, "humidity", "hum", "rh")
    light = _optional_float_from_keys(data, "light", "lux", "illumination", "light_level")

    # 至少应有一个「像传感器」的字段，避免把无关 JSON 当传感器
    has_any = any(
        k in data
        for k in (
            "temperature",
            "temp",
            "t",
            "humidity",
            "hum",
            "rh",
            "light",
            "lux",
            "illumination",
            "light_level",
        )
    )
    if not has_any:
        return None

    ts = _parse_timestamp(data.get("timestamp", data.get("ts", data.get("time"))))

    return {
        "device_id": device_id,
        "temperature": temperature,
        "humidity": humidity,
        "light": light,
        "timestamp": ts,
    }


class MqttClient:
    """封装 paho 连接、订阅与线程安全的回调调度到 asyncio 事件循环。"""

    def __init__(self) -> None:
        self._on_message: Optional[Callable[[str, str], None]] = None
        self._client: Optional[paho_mqtt.Client] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._topics: list[str] = []

    def set_message_handler(self, on_message: Callable[[str, str], None]) -> None:
        """同步回调，将在 asyncio 事件循环线程中执行（由 call_soon_threadsafe 投递）。"""
        self._on_message = on_message

    async def start(self, topics: list[str] | None = None) -> None:
        """连接百度 IoT Core 并订阅主题。"""
        if not settings.MQTT_ENABLED:
            logger.info("MQTT_ENABLED=false，跳过连接")
            return

        username, password, broker, auth_key = _build_credentials()
        if not settings.MQTT_IOT_CORE_ID or not auth_key or not (
            settings.MQTT_GATEWAY_SECRET or settings.MQTT_DEVICE_SECRET
        ):
            logger.warning("MQTT 配置不完整（IOT_CORE_ID / 设备或网关密钥），跳过连接")
            return

        self._loop = asyncio.get_running_loop()
        client_id = _resolve_client_id(auth_key)
        self._topics = topics if topics is not None else _parse_subscribe_topics()

        # paho-mqtt 2.x 默认 Callback API V2；为兼容现有 on_connect(rc) 签名，使用 VERSION1
        if CallbackAPIVersion is not None:
            self._client = paho_mqtt.Client(
                CallbackAPIVersion.VERSION1,
                client_id=client_id,
                protocol=paho_mqtt.MQTTv311,
            )
        else:
            self._client = paho_mqtt.Client(client_id=client_id, protocol=paho_mqtt.MQTTv311)

        self._client.username_pw_set(username, password)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_mqtt_message

        logger.info(
            "MQTT connecting broker=%s port=%s client_id=%s topics=%s",
            broker,
            settings.MQTT_PORT,
            client_id,
            self._topics,
        )

        self._client.connect_async(broker, settings.MQTT_PORT, keepalive=60)
        self._client.loop_start()

    def _on_connect(self, client, userdata, flags, rc):  # noqa: ANN001
        if rc == 0:
            logger.info("MQTT connected successfully")
            for topic in self._topics:
                client.subscribe(topic, qos=0)
                logger.info("MQTT subscribed to %s", topic)
        else:
            logger.error("MQTT connection failed, rc=%s", rc)

    def _on_mqtt_message(self, client, userdata, msg):  # noqa: ANN001
        topic = msg.topic
        try:
            payload = msg.payload.decode("utf-8")
        except UnicodeDecodeError:
            payload = msg.payload.decode("utf-8", errors="replace")

        logger.debug("MQTT message: %s -> %s", topic, payload)

        if self._on_message and self._loop:
            # paho 网络线程 -> 主线程：把业务回调投递到 asyncio 循环
            self._loop.call_soon_threadsafe(self._on_message, topic, payload)

    async def publish(self, topic: str, payload: str, qos: int = 0) -> None:
        """向 Broker 发布消息；小车控制等业务建议使用 qos=1（至少一次）。"""
        if self._client:
            self._client.publish(topic, payload, qos=qos)

    async def stop(self) -> None:
        if self._client:
            self._client.loop_stop()
            try:
                self._client.disconnect()
            except Exception:
                pass
            self._client = None
            logger.info("MQTT disconnected")

    async def simulate_message(self, topic: str, payload: str) -> None:
        """用于单测或联调：在不经过 broker 的情况下触发与 on_message 相同的处理链。"""
        if self._on_message:
            self._on_message(topic, payload)


def parse_json_payload(payload: str) -> Any:
    """尝试解析 JSON；失败则返回原始字符串包在 dict 中。"""
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return {"raw": payload}


mqtt_client = MqttClient()
