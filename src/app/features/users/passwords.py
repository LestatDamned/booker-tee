from dataclasses import dataclass, field
from datetime import timedelta
from typing import NoReturn, TypeGuard
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    TokenPair,
    auth_rate_limit_bucket_hash,
    generate_token_pair,
    generate_user_token,
    hash_password,
    hash_token,
    hash_user_token,
    verify_password,
)
from app.core.settings import Settings
from app.db.base import utc_now
from app.features.users.email_delivery import IdentityEmail, build_password_reset_message
from app.features.users.errors import (
    AuthRateLimitedError,
    CurrentPasswordIncorrectError,
    InvalidPasswordError,
    InvalidPasswordResetTokenError,
)
from app.features.users.identity_repository import (
    AuthRateLimitRepository,
    UserTokenRepository,
)
from app.features.users.models import User, UserTokenPurpose
from app.features.users.repository import UserRepository
from app.features.users.service import normalize_email, validate_password

RESET_TOKEN_LIFETIME = timedelta(minutes=30)
RESET_REQUEST_WINDOW = timedelta(seconds=60)
RESET_ATTEMPT_WINDOW = timedelta(minutes=5)
RESET_NETWORK_LIMIT = 20
RESET_TOKEN_ATTEMPT_LIMIT = 5


@dataclass(frozen=True)
class PasswordResetRequest:
    email: IdentityEmail | None = field(repr=False)
    retry_after_seconds: int = int(RESET_REQUEST_WINDOW.total_seconds())


class PasswordService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)
        self.tokens = UserTokenRepository(session)
        self.rate_limits = AuthRateLimitRepository(session)

    async def request_reset(
        self,
        *,
        email: str,
        base_url: str,
        network_key: str,
    ) -> PasswordResetRequest:
        normalized_email = normalize_email(email)
        await self._enforce_reset_request_limit(normalized_email, network_key)
        user = await self.users.get_by_email(normalized_email)
        message = None
        if self._can_reset(user):
            token = generate_user_token()
            await self.tokens.replace_active(
                user_id=user.id,
                purpose=UserTokenPurpose.RESET_PASSWORD,
                token_hash=hash_user_token(token),
                expires_at=utc_now() + RESET_TOKEN_LIFETIME,
            )
            message = build_password_reset_message(
                recipient=user.email,
                token=token,
                base_url=base_url,
            )
        await self.session.commit()
        return PasswordResetRequest(email=message)

    async def reset_password(
        self,
        *,
        token: str,
        new_password: str,
        network_key: str,
    ) -> None:
        validated_password = validate_password(
            new_password,
            minimum_length=self.settings.password_min_length,
        )
        token_hash = hash_user_token(token)
        stored_token = await self.tokens.consume(
            purpose=UserTokenPurpose.RESET_PASSWORD,
            token_hash=token_hash,
        )
        if stored_token is None:
            await self._reject_invalid_reset(token_hash, network_key)

        user = await self.users.get_for_update(stored_token.user_id)
        if not self._can_reset(user):
            await self.session.rollback()
            raise InvalidPasswordResetTokenError(
                "Ссылка недействительна или срок её действия истёк."
            )

        user.password_hash = hash_password(validated_password)
        await self.tokens.consume_active_for_user(
            user_id=user.id,
            purpose=UserTokenPurpose.RESET_PASSWORD,
        )
        await self.users.revoke_all_sessions(user.id)
        await self.session.commit()

    async def change_password(
        self,
        *,
        user: User,
        session_token: UUID,
        current_password: str,
        new_password: str,
    ) -> TokenPair:
        validated_password = validate_password(
            new_password,
            minimum_length=self.settings.password_min_length,
        )
        locked_user = await self.users.get_for_update(user.id)
        if locked_user is None or not verify_password(current_password, locked_user.password_hash):
            raise CurrentPasswordIncorrectError("Текущий пароль указан неверно.")
        if verify_password(validated_password, locked_user.password_hash):
            raise InvalidPasswordError("Новый пароль должен отличаться от текущего.")

        current_session = await self.users.get_active_session_for_update(
            session_id=session_token,
            user_id=user.id,
        )
        if current_session is None:
            raise CurrentPasswordIncorrectError("Текущая сессия больше не активна.")

        tokens = generate_token_pair(
            user_id=user.id,
            session_id=current_session.id,
            refresh_expires_at=current_session.expires_at,
            settings=self.settings,
        )
        locked_user.password_hash = hash_password(validated_password)
        await self.users.revoke_other_sessions(
            user_id=user.id,
            current_session_id=current_session.id,
        )
        current_session.previous_refresh_token_hash = current_session.refresh_token_hash
        current_session.refresh_token_hash = hash_token(tokens.refresh_token)
        current_session.refresh_rotated_at = utc_now()
        current_session.last_seen_at = utc_now()
        await self.tokens.consume_active_for_user(
            user_id=user.id,
            purpose=UserTokenPurpose.RESET_PASSWORD,
        )
        await self.session.commit()
        return tokens

    async def _enforce_reset_request_limit(
        self,
        normalized_email: str,
        network_key: str,
    ) -> None:
        account_count = await self.rate_limits.increment(
            bucket_hash=auth_rate_limit_bucket_hash(
                scope="password-reset-account",
                key=normalized_email,
                settings=self.settings,
            ),
            window=RESET_REQUEST_WINDOW,
        )
        network_count = await self.rate_limits.increment(
            bucket_hash=auth_rate_limit_bucket_hash(
                scope="password-reset-network",
                key=network_key,
                settings=self.settings,
            ),
            window=RESET_REQUEST_WINDOW,
        )
        if account_count > 1 or network_count > RESET_NETWORK_LIMIT:
            await self.session.commit()
            raise AuthRateLimitedError(int(RESET_REQUEST_WINDOW.total_seconds()))

    async def _reject_invalid_reset(self, token_hash: str, network_key: str) -> NoReturn:
        token_count = await self.rate_limits.increment(
            bucket_hash=auth_rate_limit_bucket_hash(
                scope="password-reset-token",
                key=token_hash,
                settings=self.settings,
            ),
            window=RESET_ATTEMPT_WINDOW,
        )
        network_count = await self.rate_limits.increment(
            bucket_hash=auth_rate_limit_bucket_hash(
                scope="password-reset-attempt-network",
                key=network_key,
                settings=self.settings,
            ),
            window=RESET_ATTEMPT_WINDOW,
        )
        await self.session.commit()
        if token_count > RESET_TOKEN_ATTEMPT_LIMIT or network_count > RESET_NETWORK_LIMIT:
            raise AuthRateLimitedError(int(RESET_ATTEMPT_WINDOW.total_seconds()))
        raise InvalidPasswordResetTokenError("Ссылка недействительна или срок её действия истёк.")

    @staticmethod
    def _can_reset(user: User | None) -> TypeGuard[User]:
        return bool(
            user is not None
            and user.is_active
            and user.deactivated_at is None
            and user.email_verified_at is not None
        )
