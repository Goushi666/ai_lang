from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class Alarm(Base):
    """
    告警数据表模型（SQLAlchemy ORM）。

    字段与 WebSocket/REST 返回模型对齐（AlarmResponse）。
    """

    __tablename__ = "alarms"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(50))
    level = Column(String(20))  # low, medium, high, urgent
    message = Column(String(255))
    value = Column(Float)
    threshold = Column(Float)
    read = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

