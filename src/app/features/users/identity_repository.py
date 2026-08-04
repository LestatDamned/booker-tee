from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import case, delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.features.users.models import (
    AuthRateLimit,
    User,
    UserToken,
    UserTokenPurpose,
)


class UserTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace_active(
        self,
        *,
        user_id: UUID,
        purpose: UserTokenPurpose,
        token_hash: str,
        expires_at: datetime,
        target_email: str | None = None,
    ) -> UserToken:
        await self.session.execute(select(User.id).where(User.id == user_id).with_for_update())
        now = utc_now()
        await self.session.execute(
            update(UserToken)
            .where(
                UserToken.user_id == user_id,
                UserToken.purpose == purpose,
                UserToken.consumed_at.is_(None),
                UserToken.expires_at > now,
            )
            .values(consumed_at=now)
        )
        token = UserToken(
            user_id=user_id,
            purpose=purpose,
            token_hash=token_hash,
            target_email=target_email,
            expires_at=expires_at,
        )
        self.session.add(token)
        await self.session.flush()
        return token

    async def consume(
        self,
        *,
        purpose: UserTokenPurpose,
        token_hash: str,
    ) -> UserToken | None:
        now = utc_now()
        result = await self.session.execute(
            select(UserToken)
            .where(
                UserToken.purpose == purpose,
                UserToken.token_hash == token_hash,
                UserToken.consumed_at.is_(None),
                UserToken.expires_at > now,
            )
            .with_for_update()
        )
        token = result.scalar_one_or_none()
        if token is None:
            return None
        token.consumed_at = now
        await self.session.flush()
        return token

    async def consume_for_user(
        self,
        *,
        user_id: UUID,
        purpose: UserTokenPurpose,
        token_hash: str,
    ) -> UserToken | None:
        now = utc_now()
        result = await self.session.execute(
            select(UserToken)
            .where(
                UserToken.user_id == user_id,
                UserToken.purpose == purpose,
                UserToken.token_hash == token_hash,
                UserToken.consumed_at.is_(None),
                UserToken.expires_at > now,
            )
            .with_for_update()
        )
        token = result.scalar_one_or_none()
        if token is None:
            return None
        token.consumed_at = now
        await self.session.flush()
        return token

    async def consume_active_for_user(
        self,
        *,
        user_id: UUID,
        purpose: UserTokenPurpose,
    ) -> None:
        await self.session.execute(
            update(UserToken)
            .where(
                UserToken.user_id == user_id,
                UserToken.purpose == purpose,
                UserToken.consumed_at.is_(None),
            )
            .values(consumed_at=utc_now())
        )
        await self.session.flush()

    async def consume_all_active_for_user(self, *, user_id: UUID) -> None:
        await self.session.execute(
            update(UserToken)
            .where(
                UserToken.user_id == user_id,
                UserToken.consumed_at.is_(None),
            )
            .values(consumed_at=utc_now())
        )
        await self.session.flush()


class AuthRateLimitRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def increment(
        self,
        *,
        bucket_hash: str,
        window: timedelta,
        now: datetime | None = None,
    ) -> int:
        current_time = now or utc_now()
        next_expiry = current_time + window
        expired = AuthRateLimit.expires_at <= current_time
        statement = (
            insert(AuthRateLimit)
            .values(
                bucket_hash=bucket_hash,
                attempt_count=1,
                window_started_at=current_time,
                expires_at=next_expiry,
            )
            .on_conflict_do_update(
                index_elements=[AuthRateLimit.bucket_hash],
                set_={
                    "attempt_count": case(
                        (expired, 1),
                        else_=AuthRateLimit.attempt_count + 1,
                    ),
                    "window_started_at": case(
                        (expired, current_time),
                        else_=AuthRateLimit.window_started_at,
                    ),
                    "expires_at": case(
                        (expired, next_expiry),
                        else_=AuthRateLimit.expires_at,
                    ),
                },
            )
            .returning(AuthRateLimit.attempt_count)
        )
        return (await self.session.execute(statement)).scalar_one()

    async def delete_expired(self, *, limit: int = 1000) -> int:
        expired_buckets = (
            select(AuthRateLimit.bucket_hash)
            .where(AuthRateLimit.expires_at <= utc_now())
            .limit(limit)
        )
        result = await self.session.execute(
            delete(AuthRateLimit)
            .where(AuthRateLimit.bucket_hash.in_(expired_buckets))
            .returning(AuthRateLimit.bucket_hash)
        )
        return len(result.scalars().all())
