from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    generate_session_token,
    generate_user_token,
    hash_session_token,
    hash_user_token,
    verify_password,
)
from app.core.settings import Settings
from app.db.base import utc_now
from app.features.users.email_delivery import (
    IdentityEmail,
    build_email_change_messages,
    build_email_changed_message,
)
from app.features.users.errors import (
    CurrentPasswordIncorrectError,
    EmailAlreadyRegisteredError,
    InvalidEmailChangeTokenError,
)
from app.features.users.identity_repository import UserTokenRepository
from app.features.users.models import User, UserTokenPurpose
from app.features.users.repository import UserRepository
from app.features.users.service import normalize_email

EMAIL_CHANGE_TOKEN_LIFETIME = timedelta(minutes=30)


@dataclass(frozen=True)
class EmailChangeRequest:
    messages: tuple[IdentityEmail, IdentityEmail]


@dataclass(frozen=True)
class EmailChangeResult:
    email: str
    session_token: str
    notification: IdentityEmail


class EmailChangeService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)
        self.tokens = UserTokenRepository(session)

    async def request_change(
        self,
        *,
        user: User,
        current_password: str,
        target_email: str,
        base_url: str,
    ) -> EmailChangeRequest:
        normalized_email = normalize_email(target_email)
        locked_user = await self.users.get_for_update(user.id)
        if locked_user is None or not verify_password(current_password, locked_user.password_hash):
            raise CurrentPasswordIncorrectError("Текущий пароль указан неверно.")
        if normalized_email == locked_user.email or await self.users.get_by_email(normalized_email):
            raise EmailAlreadyRegisteredError("Этот email уже используется.")

        token = generate_user_token()
        await self.tokens.replace_active(
            user_id=locked_user.id,
            purpose=UserTokenPurpose.CHANGE_EMAIL,
            token_hash=hash_user_token(token),
            target_email=normalized_email,
            expires_at=utc_now() + EMAIL_CHANGE_TOKEN_LIFETIME,
        )
        messages = build_email_change_messages(
            current_email=locked_user.email,
            target_email=normalized_email,
            token=token,
            base_url=base_url,
        )
        await self.session.commit()
        return EmailChangeRequest(messages=messages)

    async def confirm_change(
        self,
        *,
        user: User,
        session_token: str,
        token: str,
    ) -> EmailChangeResult:
        stored_token = await self.tokens.consume_for_user(
            user_id=user.id,
            purpose=UserTokenPurpose.CHANGE_EMAIL,
            token_hash=hash_user_token(token),
        )
        if stored_token is None or stored_token.target_email is None:
            raise InvalidEmailChangeTokenError("Ссылка недействительна или срок её действия истёк.")

        locked_user = await self.users.get_for_update(user.id)
        current_session = await self.users.get_active_session_by_token_hash_for_update(
            hash_session_token(session_token),
            user_id=user.id,
        )
        if locked_user is None or current_session is None:
            await self.session.rollback()
            raise InvalidEmailChangeTokenError("Ссылка недействительна или срок её действия истёк.")
        target_email = stored_token.target_email
        if await self.users.get_by_email_for_update(target_email):
            await self.session.rollback()
            raise EmailAlreadyRegisteredError("Этот email уже используется.")

        previous_email = locked_user.email
        rotated_token = generate_session_token()
        locked_user.email = target_email
        locked_user.email_verified_at = utc_now()
        await self.users.revoke_other_sessions(
            user_id=user.id,
            current_session_id=current_session.id,
        )
        current_session.session_token_hash = hash_session_token(rotated_token)
        current_session.last_seen_at = utc_now()
        current_session.expires_at = utc_now() + timedelta(
            seconds=self.settings.session_max_age_seconds
        )
        await self.tokens.consume_active_for_user(
            user_id=user.id,
            purpose=UserTokenPurpose.CHANGE_EMAIL,
        )
        try:
            await self.session.flush()
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise EmailAlreadyRegisteredError("Этот email уже используется.") from error
        return EmailChangeResult(
            email=target_email,
            session_token=rotated_token,
            notification=build_email_changed_message(recipient=previous_email),
        )
