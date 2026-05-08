"""工作记忆：会话内键值 + TTL（进程内，重启清空）。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class _Entry:
    value: str
    expires_at: float


class WorkingMemoryStore:
    """临时上下文槽位；默认 TTL 由配置决定。"""

    def __init__(self, default_ttl_sec: float = 600.0) -> None:
        self._default_ttl = max(30.0, float(default_ttl_sec))
        self._lock = RLock()
        self._by_session: Dict[str, Dict[str, _Entry]] = {}

    def _prune_session(self, sid: str, now: float) -> None:
        d = self._by_session.get(sid)
        if not d:
            return
        dead = [k for k, e in d.items() if e.expires_at <= now]
        for k in dead:
            del d[k]
        if not d:
            del self._by_session[sid]

    def set(
        self,
        session_id: str,
        key: str,
        value: str,
        *,
        ttl_sec: Optional[float] = None,
    ) -> None:
        if not session_id or not key:
            return
        ttl = float(ttl_sec) if ttl_sec is not None else self._default_ttl
        ttl = max(5.0, ttl)
        now = time.time()
        with self._lock:
            self._prune_session(session_id, now)
            self._by_session.setdefault(session_id, {})[key] = _Entry(
                value=value[:8000],
                expires_at=now + ttl,
            )

    def get(self, session_id: str, key: str) -> Optional[str]:
        now = time.time()
        with self._lock:
            self._prune_session(session_id, now)
            d = self._by_session.get(session_id)
            if not d:
                return None
            e = d.get(key)
            if e is None or e.expires_at <= now:
                if e is not None:
                    del d[key]
                return None
            return e.value

    def snapshot_lines(self, session_id: str) -> List[Tuple[str, str]]:
        """返回 (key, value) 列表供注入 system。"""
        now = time.time()
        with self._lock:
            self._prune_session(session_id, now)
            d = self._by_session.get(session_id)
            if not d:
                return []
            out: List[Tuple[str, str]] = []
            for k, e in list(d.items()):
                if e.expires_at <= now:
                    continue
                out.append((k, e.value))
            return out

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._by_session.pop(session_id, None)
