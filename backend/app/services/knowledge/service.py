"""知识库检索：默认 SQLite FTS5（跨平台稳定）；旧版 Chroma 目录仅作历史数据保留。"""

from __future__ import annotations

import logging
import re
import sqlite3
import threading
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import Settings

from .chunker import chunk_text

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _safe_source_id(name: str) -> str:
    s = re.sub(r"[^\w.\-]+", "_", (name or "").strip())[:120]
    return s or "document"


def _sqlite_db_path(settings: Settings) -> Path:
    p = Path(getattr(settings, "KNOWLEDGE_SQLITE_PATH", "./data/knowledge_fts.db"))
    if not p.is_absolute():
        p = (_BACKEND_ROOT / p).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _fts_match_expression(query: str) -> Optional[str]:
    """将自然语言压成 FTS5 前缀检索串；过长时截断。"""
    terms = re.findall(r"[\w\u4e00-\u9fff]+", (query or "").strip())
    if not terms:
        return None
    parts: List[str] = []
    for t in terms[:14]:
        if len(t) < 2 and len(terms) > 1:
            continue
        safe = t.replace('"', "")
        if not safe:
            continue
        parts.append(f'"{safe}"*')
    if not parts:
        return None
    return " AND ".join(parts)


class KnowledgeService:
    """SQLite FTS5 全文索引；与脚本、HTTP API、Agent 工具共用。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._db_file = _sqlite_db_path(settings)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(self._db_file),
            check_same_thread=False,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks USING fts5(
                body,
                source UNINDEXED,
                chunk_id UNINDEXED,
                tokenize = 'unicode61'
            );
            """
        )

    @property
    def db_path(self) -> str:
        return str(self._db_file)

    @property
    def collection_name(self) -> str:
        return "knowledge_chunks(fts5)"

    def status(self) -> Dict[str, Any]:
        with self._lock:
            try:
                n = int(self._conn.execute("SELECT COUNT(*) FROM knowledge_chunks").fetchone()[0])
            except Exception as exc:  # pragma: no cover
                logger.warning("知识库 count 失败: %s", exc)
                n = 0
        return {
            "status": "ok",
            "total_chunks": n,
            "collection": self.collection_name,
            "db_path": self.db_path,
        }

    def reset_collection(self) -> None:
        with self._lock:
            self._conn.executescript("DROP TABLE IF EXISTS knowledge_chunks;")
            self._init_schema()

    def delete_by_source(self, source: str) -> int:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM knowledge_chunks WHERE source = ?",
                (source,),
            )
            self._conn.commit()
            return int(cur.rowcount or 0)

    def ingest_text(
        self,
        *,
        text: str,
        source: str,
        replace: bool = True,
    ) -> int:
        chunks = chunk_text(
            text,
            self._settings.RAG_CHUNK_SIZE,
            self._settings.RAG_CHUNK_OVERLAP,
        )
        if not chunks:
            return 0
        sid = _safe_source_id(source)
        with self._lock:
            if replace:
                self._conn.execute("DELETE FROM knowledge_chunks WHERE source = ?", (sid,))
            for i, ch in enumerate(chunks):
                cid = f"{sid}_{i}"
                self._conn.execute(
                    "INSERT INTO knowledge_chunks(body, source, chunk_id) VALUES (?,?,?)",
                    (ch, sid, cid),
                )
            self._conn.commit()
        return len(chunks)

    def ingest_file(self, path: Path, *, replace: bool = True) -> int:
        path = path.resolve()
        if not path.is_file():
            raise FileNotFoundError(str(path))
        text = path.read_text(encoding="utf-8")
        return self.ingest_text(text=text, source=path.name, replace=replace)

    def ingest_directory(self, directory: Path, *, pattern: str = "*.md") -> Dict[str, int]:
        directory = directory.resolve()
        out: Dict[str, int] = {}
        for f in sorted(directory.glob(pattern)):
            if f.is_file():
                out[f.name] = self.ingest_file(f, replace=True)
        return out

    def search(self, query: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return []
        k = top_k if top_k is not None else self._settings.AGENT_RAG_TOP_K
        k = max(1, min(20, int(k)))
        match_expr = _fts_match_expression(q)
        rows: List[Dict[str, Any]] = []
        with self._lock:
            if match_expr:
                try:
                    cur = self._conn.execute(
                        """
                        SELECT source, chunk_id, body, bm25(knowledge_chunks) AS r
                        FROM knowledge_chunks
                        WHERE knowledge_chunks MATCH ?
                        ORDER BY r
                        LIMIT ?
                        """,
                        (match_expr, k),
                    )
                    for r in cur.fetchall():
                        idx = 0
                        try:
                            idx = int(str(r["chunk_id"]).rsplit("_", 1)[-1])
                        except Exception:
                            pass
                        rows.append(
                            {
                                "text": r["body"],
                                "source": r["source"],
                                "chunk_index": idx,
                                "distance": float(r["r"]) if r["r"] is not None else None,
                            }
                        )
                except sqlite3.OperationalError as exc:
                    logger.debug("FTS MATCH 失败，回退 LIKE: %s", exc)
            if not rows:
                like = f"%{q[:80]}%"
                cur = self._conn.execute(
                    """
                    SELECT source, chunk_id, body FROM knowledge_chunks
                    WHERE body LIKE ? OR source LIKE ?
                    LIMIT ?
                    """,
                    (like, like, k),
                )
                for r in cur.fetchall():
                    idx = 0
                    try:
                        idx = int(str(r["chunk_id"]).rsplit("_", 1)[-1])
                    except Exception:
                        pass
                    rows.append(
                        {
                            "text": r["body"],
                            "source": r["source"],
                            "chunk_index": idx,
                            "distance": None,
                        }
                    )
        return rows
