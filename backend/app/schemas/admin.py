from pydantic import BaseModel, Field


class KnowledgeImportOneRequest(BaseModel):
    """将 knowledge_docs 下单个 Markdown 导入 FTS 知识索引。"""

    filename: str = Field(..., min_length=1, description="文件名，如 01-xxx.md")


class PurgeDataRequest(BaseModel):
    """清空 SQLite 中业务表（同一 app.db 内 sensor_data 与 environment_anomalies）。"""

    sensor_data: bool = Field(default=True, description="清空 sensor_data 采样表")
    environment_anomalies: bool = Field(
        default=True,
        description="清空 environment_anomalies 异常落库表",
    )
