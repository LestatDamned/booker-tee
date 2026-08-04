from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    auth_rate_limit_bucket_hash,
    generate_user_token,
    hash_password,
    hash_user_token,
)
from app.core.settings import Settings
from app.db.base import utc_now
from app.features.users.email_delivery import (
    IdentityEmail,
    build_email_verification_message,
)
from app.features.users.errors import (
    AuthRateLimitedError,
    InvalidEmailVerificationTokenError,
    SignupsClosedError,
)
from app.features.users.identity_repository import (
    AuthRateLimitRepository,
    UserTokenRepository,
)
from app.features.users.models import User, UserTokenPurpose
from app.features.users.repository import UserRepository
from app.features.users.service import (
    AuthenticationService,
    LoginSession,
    clean_user_name,
    normalize_email,
    safe_next_path,
    validate_password,
)

VERIFICATION_TOKEN_LIFETIME = timedelta(hours=24)
RESEND_COOLDOWN = timedelta(seconds=60)
RESEND_NETWORK_LIMIT = 20


@dataclass(frozen=True)
class VerificationRequest:
    email: IdentityEmail | None = field(repr=False)
    retry_after_seconds: int = int(RESEND_COOLDOWN.total_seconds())


class EmailVerificationService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)
        self.tokens = UserTokenRepository(session)
        self.rate_limits = AuthRateLimitRepository(session)
        self.authentication = AuthenticationService(session, settings)

    async def request_signup(
        self,
        *,
        email: str,
        password: str,
        name: str | None,
        base_url: str,
        next_path: str | None = None,
    ) -> VerificationRequest:
        if not self.settings.allow_signups:
            raise SignupsClosedError("Регистрация временно закрыта.")

        normalized_email = normalize_email(email)
        password_hash = hash_password(
            validate_password(
                password,
                minimum_length=self.settings.password_min_length,
            )
        )
        if await self.users.get_by_email(normalized_email) is not None:
            return VerificationRequest(email=None)

        try:
            async with self.session.begin_nested():
                user = await self.users.create(
                    email=normalized_email,
                    password_hash=password_hash,
                    name=clean_user_name(name),
                )
        except IntegrityError:
            return VerificationRequest(email=None)

        message = await self._replace_token_email(
            user=user,
            base_url=base_url,
            next_path=safe_next_path(next_path) if next_path else None,
        )
        await self.session.commit()
        return VerificationRequest(email=message)

    async def request_resend(
        self,
        *,
        email: str,
        base_url: str,
        network_key: str,
    ) -> VerificationRequest:
        normalized_email = normalize_email(email)
        await self._enforce_resend_limit(
            normalized_email=normalized_email,
            network_key=network_key,
        )
        user = await self.users.get_by_email(normalized_email)
        message = None
        if (
            user is not None
            and user.is_active
            and user.deactivated_at is None
            and user.email_verified_at is None
        ):
            message = await self._replace_token_email(user=user, base_url=base_url)
        await self.session.commit()
        return VerificationRequest(email=message)

    async def verify(self, *, token: str) -> LoginSession:
        stored_token = await self.tokens.consume(
            purpose=UserTokenPurpose.VERIFY_EMAIL,
            token_hash=hash_user_token(token),
        )
        if stored_token is None:
            raise InvalidEmailVerificationTokenError(
                "Ссылка недействительна или срок её действия истёк."
            )

        user = await self.users.get_for_update(stored_token.user_id)
        if (
            user is None
            or not user.is_active
            or user.deactivated_at is not None
            or user.email_verified_at is not None
        ):
            raise InvalidEmailVerificationTokenError(
                "Ссылка недействительна или срок её действия истёк."
            )

        user.email_verified_at = utc_now()
        login_session = await self.authentication.create_login_session_for_user(user)
        await self.session.commit()
        return login_session

    async def _replace_token_email(
        self,
        *,
        user: User,
        base_url: str,
        next_path: str | None = None,
    ) -> IdentityEmail:
        token = generate_user_token()
        await self.tokens.replace_active(
            user_id=user.id,
            purpose=UserTokenPurpose.VERIFY_EMAIL,
            token_hash=hash_user_token(token),
            expires_at=utc_now() + VERIFICATION_TOKEN_LIFETIME,
        )
        return build_email_verification_message(
            recipient=user.email,
            token=token,
            base_url=base_url,
            next_path=next_path,
        )

    async def _enforce_resend_limit(
        self,
        *,
        normalized_email: str,
        network_key: str,
    ) -> None:
        account_count = await self.rate_limits.increment(
            bucket_hash=auth_rate_limit_bucket_hash(
                scope="verification-resend-account",
                key=normalized_email,
                settings=self.settings,
            ),
            window=RESEND_COOLDOWN,
        )
        network_count = await self.rate_limits.increment(
            bucket_hash=auth_rate_limit_bucket_hash(
                scope="verification-resend-network",
                key=network_key,
                settings=self.settings,
            ),
            window=RESEND_COOLDOWN,
        )
        if account_count > 1 or network_count > RESEND_NETWORK_LIMIT:
            await self.session.commit()
            raise AuthRateLimitedError(int(RESEND_COOLDOWN.total_seconds()))
