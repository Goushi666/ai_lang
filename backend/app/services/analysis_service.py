"""环境分析服务：当前为框架占位，返回与设计文档一致的结构，不做真实聚合。"""

from datetime import datetime
from typing import Optional

from app.schemas.analysis import AggregateMetric, EnvironmentSummaryResponse, TimeWindow


class AnalysisService:
    async def get_environment_summary(
        self,
        *,
        start_time: datetime,
        end_time: datetime,
        device_id: Optional[str] = None,
        bucket: Optional[str] = None,
    ) -> EnvironmentSummaryResponse:
        del bucket  # 框架阶段不使用，保留参数以稳定 API
        return EnvironmentSummaryResponse(
            device_id=device_id or "all",
            window=TimeWindow(start=start_time.isoformat(), end=end_time.isoformat()),
            aggregate={
                "temperature": AggregateMetric(count=0, min=None, max=None, avg=None),
                "humidity": AggregateMetric(count=0, min=None, max=None, avg=None),
                "light": AggregateMetric(count=0, min=None, max=None, avg=None),
            },
            buckets=[],
            summary_code="placeholder",
            summary_hints=[
                "环境分析模块已挂载，当前为框架占位：尚未读取传感器仓库做聚合与规则判定。",
            ],
            framework=True,
        )

    async def run_environment_analysis(
        self,
        *,
        start_time: datetime,
        end_time: datetime,
        device_id: Optional[str] = None,
        bucket: Optional[str] = None,
    ) -> EnvironmentSummaryResponse:
        """与 GET summary 等价（占位），供前端「重新分析」按钮调用。"""
        return await self.get_environment_summary(
            start_time=start_time,
            end_time=end_time,
            device_id=device_id,
            bucket=bucket,
        )
