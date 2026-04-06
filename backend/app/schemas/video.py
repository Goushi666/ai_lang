"""视频监控：前端拉流地址（与车端 stream-config 字段对齐，见 doc/Web前端-MJPEG视频显示说明.md）。"""

from typing import Any, Optional

from pydantic import BaseModel, Field, model_serializer


class VideoStreamConfigResponse(BaseModel):
    """浏览器可消费的流地址；video_feed 与 mjpeg 指向同一路 MJPEG，仅命名不同。"""

    hls_playlist_url: Optional[str] = Field(
        default=None, description="HLS 主播放列表 URL（.m3u8）"
    )
    mjpeg_url: Optional[str] = Field(
        default=None, description="MJPEG 流 URL（与 video_feed_url 同源同值）"
    )
    hint_zh: str = Field(description="对接说明摘要")

    @model_serializer(mode="plain")
    def _serialize(self) -> dict[str, Any]:
        hls = self.hls_playlist_url
        mj = self.mjpeg_url
        return {
            "hls_playlist_url": hls,
            "hlsPlaylistUrl": hls,
            "mjpeg_url": mj,
            "mjpegUrl": mj,
            "video_feed_url": mj,
            "videoFeedUrl": mj,
            "hint_zh": self.hint_zh,
        }
