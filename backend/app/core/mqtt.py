"""
MQTT 设备消息接入层（MVP 阶段：先做接口与 stub，等接入 Mosquitto 再完善）。

当前实现为“占位模块”：为了让后端的整体分层结构先跑通（WebSocket -> 推送链路），
等你后续接入 Mosquitto（MQTT broker）后，只需要把这里替换为真实订阅/回调即可。
"""

from typing import Callable, Optional


class MqttClient:
    def __init__(self):
        self._on_message: Optional[Callable[[str, str], None]] = None

    def set_message_handler(self, on_message: Callable[[str, str], None]) -> None:
        self._on_message = on_message

    async def start(self) -> None:
        # MVP stub：不连接真实 broker
        return

    async def publish(self, topic: str, payload: str) -> None:
        # MVP stub
        return

    async def simulate_message(self, topic: str, payload: str) -> None:
        # MVP：用于联调 WebSocket 推送链路
        if self._on_message:
            self._on_message(topic, payload)


mqtt_client = MqttClient()

