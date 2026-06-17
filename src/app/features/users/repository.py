from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def get_active(self, user_id: UUID) -> User | None:
        result = await self.session.execute(
            select(User).where(
                User.id == user_id,
                User.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> list[User]:
        result = await self.session.execute(
            select(User).where(User.is_active.is_(True)).order_by(User.created_at, User.email)
        )
        return list(result.scalars().all())

    async def create(self, *, email: str, name: str | None = None) -> User:
        user = User(email=email.lower(), name=name)
        self.session.add(user)
        await self.session.flush()
        return user

    async def create_development_user(self, email: str) -> User:
        user = User(email=email.lower(), name="Development User")
        self.session.add(user)
        await self.session.flush()
        return user
