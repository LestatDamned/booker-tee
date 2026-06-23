from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.base import utc_now
from app.features.users.models import User, UserSession


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

    async def create(self, *, email: str, password_hash: str, name: str | None = None) -> User:
        user = User(email=email.lower(), password_hash=password_hash, name=name)
        self.session.add(user)
        await self.session.flush()
        return user

    async def create_session(self, user_session: UserSession) -> UserSession:
        self.session.add(user_session)
        await self.session.flush()
        return user_session

    async def get_active_session_by_token_hash(
        self,
        session_token_hash: str,
    ) -> UserSession | None:
        result = await self.session.execute(
            select(UserSession)
            .options(
                selectinload(UserSession.user),
                selectinload(UserSession.current_workspace),
            )
            .where(
                UserSession.session_token_hash == session_token_hash,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > utc_now(),
            )
        )
        return result.scalar_one_or_none()

    async def revoke_session(self, user_session: UserSession) -> None:
        user_session.revoked_at = utc_now()
        await self.session.flush()
