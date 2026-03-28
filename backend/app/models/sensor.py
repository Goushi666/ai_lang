from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SensorData(Base):
    """
    传感器采样表：MQTT / 模拟写入，REST history/latest/export 与后续环境分析只读查询。
    """

    __tablename__ = "sensor_data"
    __table_args__ = (Index("ix_sensor_data_device_timestamp", "device_id", "timestamp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(50), index=True)
    temperature: Mapped[float] = mapped_column(Float)
    humidity: Mapped[float] = mapped_column(Float)
    light: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
