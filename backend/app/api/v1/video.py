"""视频流：stream-config 与车端字段对齐；可选 MJPEG 字节流代理。"""

import logging

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.schemas.video import VideoStreamConfigResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _mjpeg_upstream() -> str | None:
    return (settings.VIDEO_MJPEG_URL or "").strip() or None


def _mjpeg_url_for_browser() -> str | None:
    upstream = _mjpeg_upstream()
    if not upstream:
        return None
    if settings.VIDEO_PROXY_THROUGH_BACKEND:
        return "/api/video/mjpeg-proxy"
    return upstream


def _pick_hint(hls_u: str, mjpeg_browser: str | None, proxy_on: bool) -> str:
    if hls_u and mjpeg_browser:
        return "已同时配置 HLS 与 MJPEG，前端优先使用 HLS。"
    if hls_u:
        return "已配置 HLS。请确保 .m3u8 与 .ts 片段与前端同源或已正确配置 CORS。"
    if mjpeg_browser:
        if proxy_on:
            return "已启用后端 MJPEG 代理，浏览器经同源地址拉流（等价于车端 /video_feed）。"
        return (
            "已配置 MJPEG（建议 URL 含 /video_feed）。若页面为 HTTPS 而车机为 HTTP，"
            "请设置 VIDEO_PROXY_THROUGH_BACKEND=true。"
        )
    return (
        "未配置视频：在 backend .env 设置 VIDEO_MJPEG_URL，例如 "
        "http://192.168.137.114:8080/video_feed；或设置 VIDEO_HLS_PLAYLIST_URL。"
    )


@router.get("/stream-config", response_model=VideoStreamConfigResponse)
async def video_stream_config() -> VideoStreamConfigResponse:
    hls_u = (settings.VIDEO_HLS_PLAYLIST_URL or "").strip() or None
    mjpeg_browser = _mjpeg_url_for_browser()
    proxy_on = bool(settings.VIDEO_PROXY_THROUGH_BACKEND and _mjpeg_upstream())
    return VideoStreamConfigResponse(
        hls_playlist_url=hls_u,
        mjpeg_url=mjpeg_browser,
        hint_zh=_pick_hint(hls_u or "", mjpeg_browser, proxy_on),
    )


@router.get("/mjpeg-proxy")
async def mjpeg_proxy() -> StreamingResponse:
    upstream = _mjpeg_upstream()
    if not upstream:
        raise HTTPException(status_code=503, detail="VIDEO_MJPEG_URL 未配置，无法代理 MJPEG")

    timeout = httpx.Timeout(connect=30.0, read=None, write=None, pool=None)
    client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)
    try:
        req = client.build_request("GET", upstream)
        resp = await client.send(req, stream=True)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        await client.aclose()
        logger.warning("MJPEG 上游连接失败: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"无法从车端拉取 MJPEG: {e!s}",
        ) from e

    ct = resp.headers.get("content-type") or settings.VIDEO_MJPEG_MEDIA_TYPE
    hop_headers = ("connection", "keep-alive", "transfer-encoding", "proxy-connection")
    passthrough_headers = {
        k: v
        for k, v in resp.headers.items()
        if k.lower() not in hop_headers and k.lower() != "content-length"
    }
    passthrough_headers["Content-Type"] = ct
    if "cache-control" not in {k.lower() for k in passthrough_headers}:
        passthrough_headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

    async def body():
        try:
            async for chunk in resp.aiter_bytes():
                yield chunk
        finally:
            await resp.aclose()
            await client.aclose()

    return StreamingResponse(body(), headers=passthrough_headers)
