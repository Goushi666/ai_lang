"""
Redis 适配层（MVP stub）。

后续如果你接入 Redis 7.0 + aioredis，可在此文件替换实现，但尽量保持接口不变。

MVP 说明：
- 目前提供最小 get/set 能力，使用进程内 dict 模拟 Redis
- 不实现过期（ex）语义；等真正接入 Redis 后再补齐
"""

from __future__ import annotations

from typing import Any, Optional


class RedisClientStub:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    async def get(self, key: str) -> Optional[Any]:
        return self._store.get(key)

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> None:
        # ex 仅占位（stub 不做过期管理）
        self._store[key] = value

    async def close(self) -> None:
        return


redis_client = RedisClientStub()

