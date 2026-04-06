"""视频监控：前端拉流地址配置（由硬件侧推流 + 边缘转码/反代后填入环境变量）。"""

from typing import Optional

from pydantic import BaseModel, Field


class VideoStreamConfigResponse(BaseModel):
    """浏览器可消费的流地址；空表示未配置，页面显示占位。"""

    hls_playlist_url: Optional[str] = Field(
        default=None, description="HLS 主播放列表 URL（.m3u8），相对路径则对应当前站点源"
    )
    mjpeg_url: Optional[str] = Field(default=None, description="MJPEG 或连续 JPEG 的 HTTP URL")
    hint_zh: str = Field(description="对接说明摘要")
