"""维护接口：数据清空、知识文档与 RAG（部分需管理员）。"""

from __future__ import annotations

import asyncio
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.core.config import settings
from app.deps import knowledge_service_dep, require_admin_user
from app.schemas.admin import KnowledgeImportOneRequest, PurgeDataRequest
from app.schemas.auth import UserPublic
from app.services.knowledge.service import KnowledgeService, knowledge_docs_path

router = APIRouter()


def _normalize_md_filename(raw: str) -> str:
    base = Path(raw).name
    if not base.lower().endswith(".md"):
        raise HTTPException(status_code=422, detail="仅支持 .md 文件")
    if not base or base in (".", ".."):
        raise HTTPException(status_code=422, detail="无效文件名")
    for c in base:
        if c in '\\/:*?"<>|':
            raise HTTPException(status_code=422, detail="文件名含非法字符")
    return base


@router.post(
    "/purge-data",
    summary="一键清空库内业务表（sensor_data / environment_anomalies）",
)
async def purge_data(body: PurgeDataRequest, request: Request):
    n_sensor = 0
    n_anomaly = 0
    if body.sensor_data:
        n_sensor = await request.app.state.sensor_repo.delete_all()
    if body.environment_anomalies:
        n_anomaly = await request.app.state.environment_anomaly_repo.delete_all()
    return {
        "ok": True,
        "sensor_data_deleted": n_sensor,
        "environment_anomalies_deleted": n_anomaly,
    }


# ---------------------------------------------------------------------------
# 知识文档目录 + RAG（仅管理员）
# ---------------------------------------------------------------------------


@router.get(
    "/knowledge/docs",
    summary="列出 knowledge_docs 目录下的 Markdown 文件",
)
async def list_knowledge_docs(
    _admin: UserPublic = Depends(require_admin_user),
) -> Dict[str, Any]:
    root = knowledge_docs_path(settings)
    items: List[Dict[str, Any]] = []
    for p in sorted(root.glob("*.md"), key=lambda x: x.name.lower()):
        if not p.is_file():
            continue
        st = p.stat()
        items.append(
            {
                "filename": p.name,
                "rag_source_id": KnowledgeService.rag_source_id_for_filename(p.name),
                "size_bytes": st.st_size,
                "modified_at": datetime.utcfromtimestamp(st.st_mtime).isoformat() + "Z",
            }
        )
    return {"directory": str(root), "items": items}


@router.post(
    "/knowledge/docs/upload",
    summary="上传 Markdown 到 knowledge_docs",
)
async def upload_knowledge_doc(
    _admin: UserPublic = Depends(require_admin_user),
    file: UploadFile = File(...),
):
    name = _normalize_md_filename(file.filename or "")
    root = knowledge_docs_path(settings)
    dest = (root / name).resolve()
    try:
        dest.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=400, detail="路径非法") from None

    raw = await file.read()
    max_b = int(getattr(settings, "AGENT_MEMORY_INJECT_MAX_CHARS", 6000)) * 500  # 上限约 3MB 量级
    max_b = max(500_000, min(max_b, 8_000_000))
    if len(raw) > max_b:
        raise HTTPException(status_code=413, detail=f"文件过大（上限 {max_b // 1_000_000}MB 内）")
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="文件须为 UTF-8 编码") from exc

    await asyncio.to_thread(dest.write_bytes, raw)
    return {"ok": True, "filename": name, "path": str(dest)}


@router.post(
    "/knowledge/rag/import-all",
    summary="将 knowledge_docs 下全部 .md 导入 RAG（FTS）",
)
async def rag_import_all_from_docs(
    _admin: UserPublic = Depends(require_admin_user),
    ks: KnowledgeService = Depends(knowledge_service_dep),
):
    root = knowledge_docs_path(settings)
    out = await asyncio.to_thread(partial(ks.ingest_directory, root, pattern="*.md"))
    total = sum(out.values()) if out else 0
    return {"ok": True, "files": out, "total_chunks": total}


@router.post(
    "/knowledge/rag/import-one",
    summary="将 knowledge_docs 中单个 .md 导入 RAG",
)
async def rag_import_one_from_docs(
    body: KnowledgeImportOneRequest,
    _admin: UserPublic = Depends(require_admin_user),
    ks: KnowledgeService = Depends(knowledge_service_dep),
):
    name = _normalize_md_filename(body.filename)
    root = knowledge_docs_path(settings)
    path = (root / name).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=400, detail="路径非法") from None
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在，请先上传或放入 knowledge_docs")
    n = await asyncio.to_thread(partial(ks.ingest_file, path, replace=True))
    return {"ok": True, "filename": name, "chunks": n}


@router.delete(
    "/knowledge/rag/clear",
    summary="清空 RAG 全文索引（不可恢复）",
)
async def rag_clear_all(
    _admin: UserPublic = Depends(require_admin_user),
    ks: KnowledgeService = Depends(knowledge_service_dep),
):
    await asyncio.to_thread(ks.reset_collection)
    return {"ok": True}


@router.delete(
    "/knowledge/rag/source/{source_id:path}",
    summary="按 RAG source 标识删除某文档的全部块",
)
async def rag_delete_source(
    source_id: str,
    _admin: UserPublic = Depends(require_admin_user),
    ks: KnowledgeService = Depends(knowledge_service_dep),
):
    sid = (source_id or "").strip()
    if not sid:
        raise HTTPException(status_code=422, detail="source 为空")
    removed = await asyncio.to_thread(ks.delete_by_source, sid)
    return {"ok": True, "removed_chunks": removed, "source": sid}


@router.delete(
    "/knowledge/docs/{filename:path}",
    summary="删除 knowledge_docs 目录中的文件（仅磁盘，不自动删 RAG）",
)
async def delete_knowledge_doc_file(
    filename: str,
    _admin: UserPublic = Depends(require_admin_user),
):
    name = _normalize_md_filename(filename)
    root = knowledge_docs_path(settings)
    path = (root / name).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=400, detail="路径非法") from None
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    await asyncio.to_thread(path.unlink)
    return {"ok": True, "filename": name}
