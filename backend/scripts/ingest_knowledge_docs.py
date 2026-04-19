#!/usr/bin/env python3
"""
将 knowledge_docs（或指定目录）下的 Markdown 裁切并写入知识库（SQLite FTS）。

在 backend 目录下执行：
  pip install -r requirements.txt
  python scripts/ingest_knowledge_docs.py
  python scripts/ingest_knowledge_docs.py --dir knowledge_docs --reset

与运行时共用 settings.KNOWLEDGE_SQLITE_PATH、RAG_CHUNK_* 裁切配置。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 保证可从 backend 根导入 app
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="裁切 Markdown 并写入 Chroma 知识库")
    parser.add_argument(
        "--dir",
        type=str,
        default="knowledge_docs",
        help="Markdown 所在目录（相对 backend 根，默认 knowledge_docs）",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="*.md",
        help="匹配 glob，默认 *.md",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="删除现有集合后重建（维度/嵌入变更或需清空时用）",
    )
    args = parser.parse_args()

    from app.core.config import settings
    from app.services.knowledge import KnowledgeService

    doc_dir = (Path(args.dir) if Path(args.dir).is_absolute() else _BACKEND_ROOT / args.dir).resolve()
    if not doc_dir.is_dir():
        print(f"目录不存在: {doc_dir}", file=sys.stderr)
        return 1

    ks = KnowledgeService(settings)
    if args.reset:
        print("重置集合:", ks.collection_name)
        ks.reset_collection()

    summary = ks.ingest_directory(doc_dir, pattern=args.pattern)
    total = sum(summary.values())
    print(f"已入库 {len(summary)} 个文件，共 {total} 条 chunk")
    for name, n in summary.items():
        print(f"  - {name}: {n} chunks")
    print("数据库路径:", ks.db_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
