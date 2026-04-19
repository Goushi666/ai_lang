"""将 Markdown/纯文本裁切为带重叠的块，供向量库存储。"""

from __future__ import annotations

from typing import List


def chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """固定窗口 + 重叠滑动裁切；简单可靠，适合说明类 Markdown。"""
    raw = (text or "").strip()
    if not raw:
        return []
    chunk_size = max(120, int(chunk_size))
    overlap = max(0, min(int(overlap), chunk_size // 2))
    step = max(1, chunk_size - overlap)
    chunks = [raw[i : i + chunk_size] for i in range(0, len(raw), step)]
    # 去掉末尾过短的重复尾片（与上一块几乎完全重叠时）
    if len(chunks) >= 2 and len(chunks[-1]) < max(40, overlap):
        tail = chunks[-1]
        if tail and tail in chunks[-2]:
            chunks.pop()
    return chunks
