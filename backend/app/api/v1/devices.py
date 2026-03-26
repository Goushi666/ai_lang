from fastapi import APIRouter


router = APIRouter()

"""
设备管理 API（目前 MVP 仅保留占位路由）。

Web 端当前未直接使用 `/api/devices/*`（只在文档结构里出现），
因此这里先提供最小可用接口以验证路由挂载是否正常。
"""


@router.get("/ping")
async def ping():
    """健康/连通性检查（设备模块占位）"""
    return {"ok": True}

