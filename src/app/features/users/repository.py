from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select, update
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

    async def get_by_email_for_update(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email.lower()).with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_for_update(self, user_id: UUID) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id).with_for_update()
        )
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

    async def update_name(self, *, user: User, name: str | None) -> User:
        user.name = name
        await self.session.flush()
        return user

    async def get_unrevoked_session_by_token_hash(
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
            )
        )
        return result.scalar_one_or_none()

    async def revoke_expired_sessions_for_user(
        self,
        *,
        user_id: UUID,
        now: datetime,
        idle_cutoff: datetime,
    ) -> int:
        result = await self.session.execute(
            update(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                or_(
                    UserSession.expires_at <= now,
                    UserSession.last_seen_at <= idle_cutoff,
                ),
            )
            .values(revoked_at=now)
            .returning(UserSession.id)
        )
        return len(result.scalars().all())

    async def list_active_sessions_for_user(
        self,
        *,
        user_id: UUID,
        now: datetime,
        idle_cutoff: datetime,
    ) -> list[UserSession]:
        result = await self.session.execute(
            select(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
                UserSession.last_seen_at > idle_cutoff,
            )
            .order_by(UserSession.last_seen_at.desc(), UserSession.id)
        )
        return list(result.scalars().all())

    async def revoke_owned_session(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        revoked_at: datetime,
    ) -> bool:
        result = await self.session.execute(
            update(UserSession)
            .where(
                UserSession.id == session_id,
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
            .returning(UserSession.id)
        )
        return result.scalar_one_or_none() is not None

    async def get_active_session_by_token_hash_for_update(
        self,
        session_token_hash: str,
        *,
        user_id: UUID,
    ) -> UserSession | None:
        result = await self.session.execute(
            select(UserSession)
            .where(
                UserSession.session_token_hash == session_token_hash,
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > utc_now(),
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def count_active_sessions_for_workspace(self, workspace_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(UserSession)
            .where(
                UserSession.current_workspace_id == workspace_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > utc_now(),
            )
        )
        return result.scalar_one()

    async def list_active_sessions_for_workspace_for_update(
        self,
        workspace_id: UUID,
    ) -> list[UserSession]:
        result = await self.session.execute(
            select(UserSession)
            .where(
                UserSession.current_workspace_id == workspace_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > utc_now(),
            )
            .order_by(UserSession.user_id, UserSession.id)
            .with_for_update()
        )
        return list(result.scalars().all())

    async def move_active_workspace_sessions(
        self,
        *,
        user_id: UUID,
        from_workspace_id: UUID,
        to_workspace_id: UUID | None,
    ) -> None:
        await self.session.execute(
            update(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.current_workspace_id == from_workspace_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > utc_now(),
            )
            .values(current_workspace_id=to_workspace_id)
        )
        await self.session.flush()

    async def revoke_session(self, user_session: UserSession) -> None:
        user_session.revoked_at = utc_now()
        await self.session.flush()

    async def revoke_all_sessions(self, user_id: UUID) -> None:
        await self.session.execute(
            update(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=utc_now())
        )
        await self.session.flush()

    async def revoke_other_sessions(self, *, user_id: UUID, current_session_id: UUID) -> int:
        result = await self.session.execute(
            update(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.id != current_session_id,
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=utc_now())
            .returning(UserSession.id)
        )
        await self.session.flush()
        return len(result.scalars().all())
