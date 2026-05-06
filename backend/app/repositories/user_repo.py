from __future__ import annotations

from typing import List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.user import User as UserORM


class UserRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    async def count(self) -> int:
        async with self._sf() as session:
            r = await session.execute(select(func.count()).select_from(UserORM))
            return int(r.scalar() or 0)

    async def get_by_id(self, user_id: int) -> Optional[UserORM]:
        async with self._sf() as session:
            r = await session.execute(select(UserORM).where(UserORM.id == user_id))
            return r.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[UserORM]:
        async with self._sf() as session:
            r = await session.execute(
                select(UserORM).where(UserORM.username == username.strip())
            )
            return r.scalar_one_or_none()

    async def list_all(self) -> Sequence[UserORM]:
        async with self._sf() as session:
            r = await session.execute(
                select(UserORM).order_by(UserORM.id.asc())
            )
            return r.scalars().all()

    async def create(
        self,
        *,
        username: str,
        password_hash: str,
        level: str,
    ) -> UserORM:
        async with self._sf() as session:
            row = UserORM(
                username=username.strip(),
                password_hash=password_hash,
                level=level,
                is_active=True,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def set_level(self, user_id: int, level: str) -> bool:
        async with self._sf() as session:
            row = await session.get(UserORM, user_id)
            if row is None:
                return False
            row.level = level
            await session.commit()
            return True

    async def count_by_level(self, level: str) -> int:
        async with self._sf() as session:
            r = await session.execute(
                select(func.count())
                .select_from(UserORM)
                .where(UserORM.level == level, UserORM.is_active.is_(True))
            )
            return int(r.scalar() or 0)

    async def delete(self, user_id: int) -> bool:
        async with self._sf() as session:
            row = await session.get(UserORM, user_id)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True
