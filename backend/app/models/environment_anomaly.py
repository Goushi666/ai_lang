from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EnvironmentAnomaly(Base):
    """
    环境连续超阈异常落库：仅存业务字段与 **落库时间** ``recorded_at``（UTC naive），
    不存片段起止时刻；查询列表按 ``recorded_at`` 落在所选时段内筛选。
    """

    __tablename__ = "environment_anomalies"
    __table_args__ = (
        Index("ix_env_anomaly_recorded_at", "recorded_at"),
        Index("ix_env_anomaly_device_recorded", "device_id", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(50), index=True)
    metric: Mapped[str] = mapped_column(String(20))
    rule_id: Mapped[str] = mapped_column(String(64))
    peak: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    detail_zh: Mapped[str] = mapped_column(Text, default="")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, index=True)
