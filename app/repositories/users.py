import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_anon_id(self, anon_id: str) -> User | None:
        res = await self.session.execute(select(User).where(User.anon_id == anon_id))
        return res.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        res = await self.session.execute(select(User).where(User.email == email))
        return res.scalar_one_or_none()

    async def create(self, **fields) -> User:
        user = User(**fields)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update(self, user: User, **fields) -> User:
        for k, v in fields.items():
            setattr(user, k, v)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user
