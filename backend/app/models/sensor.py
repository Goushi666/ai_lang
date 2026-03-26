from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class SensorData(Base):
    """
    传感器数据表模型（SQLAlchemy ORM）。

    注：MVP 阶段实际 Repository 使用内存实现，
    该模型用于后续把数据层切换到 SQLite/MySQL 时复用。
    """

    __tablename__ = "sensor_data"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), index=True)
    temperature = Column(Float)
    humidity = Column(Float)
    light = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

