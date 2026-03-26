from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class VehicleStatus(Base):
    """
    车辆状态表模型（SQLAlchemy ORM）。

    MVP 暂未使用该表进行持久化；后续切换到 SQLite/MySQL repository 时会用到。
    """

    __tablename__ = "vehicle_status"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), index=True)
    mode = Column(String(20))  # manual, auto
    speed = Column(Integer)
    left_speed = Column(Integer)
    right_speed = Column(Integer)
    connected = Column(Boolean)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

