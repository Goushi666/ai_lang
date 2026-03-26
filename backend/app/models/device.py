from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class Device(Base):
    """
    设备表模型（SQLAlchemy ORM）。

    MVP 阶段设备管理未在前端实现调用（仅保留占位路由 `/api/devices/ping`）。
    """

    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), unique=True, index=True)
    name = Column(String(100))
    type = Column(String(50))

