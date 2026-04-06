"""视频流配置：不转发视频本体，仅下发由运维/硬件约定的播放地址。"""

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.video import VideoStreamConfigResponse

router = APIRouter()


def _pick_hint(hls_u: str, mjpeg_u: str) -> str:
    if hls_u and mjpeg_u:
        return "已同时配置 HLS 与 MJPEG，前端优先使用 HLS。"
    if hls_u:
        return "已配置 HLS。请确保 .m3u8 与 .ts 片段与前端同源或已正确配置 CORS。"
    if mjpeg_u:
        return "已配置 MJPEG。若站点为 HTTPS，流地址也须为 HTTPS，否则浏览器会拦截混合内容。"
    return (
        "未配置视频地址：在 backend .env 中设置 VIDEO_HLS_PLAYLIST_URL 或 VIDEO_MJPEG_URL；"
        "硬件侧常见做法为摄像头 RTSP → 车上或网关 FFmpeg/MediaMTX 转 HLS，再由 Nginx 反代到 /live/…。"
    )


@router.get("/stream-config", response_model=VideoStreamConfigResponse)
async def video_stream_config() -> VideoStreamConfigResponse:
    hls_u = (settings.VIDEO_HLS_PLAYLIST_URL or "").strip() or None
    mjpeg_u = (settings.VIDEO_MJPEG_URL or "").strip() or None
    return VideoStreamConfigResponse(
        hls_playlist_url=hls_u,
        mjpeg_url=mjpeg_u,
        hint_zh=_pick_hint(hls_u or "", mjpeg_u or ""),
    )
