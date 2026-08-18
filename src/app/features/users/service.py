import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import NoReturn
from unicodedata import normalize
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    TokenPair,
    auth_rate_limit_bucket_hash,
    decode_access_token,
    decode_refresh_token,
    generate_token_pair,
    hash_password,
    hash_token,
    verify_and_update_password,
    verify_dummy_password,
)
from app.core.settings import Settings
from app.db.base import utc_now
from app.features.users.errors import (
    AuthRateLimitedError,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidEmailError,
    InvalidPasswordError,
    InvalidRefreshTokenError,
    RefreshRaceError,
    UserError,
)
from app.features.users.identity_repository import AuthRateLimitRepository
from app.features.users.models import User, UserSession
from app.features.users.repository import UserRepository
from app.features.users.sessions import summarize_user_agent
from app.features.workspaces.models import Workspace, WorkspaceAuditEventType, WorkspaceMember
from app.features.workspaces.repository import WorkspaceRepository


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized or "@" not in normalized:
        raise InvalidEmailError("Некорректный email пользователя.")
    return normalized


def clean_user_name(name: str | None) -> str | None:
    if name is None:
        return None
    cleaned = name.strip()
    return cleaned or None


_BLOCKED_PASSWORDS = frozenset(
    {
        "12345678",
        "123456789",
        "1234567890",
        "booker-tee",
        "bookertee",
        "bookertee123",
        "iloveyou",
        "letmein",
        "password",
        "password1",
        "password123",
        "qwerty123",
        "qwertyuiop",
        "welcome1",
    }
)
_LOGIN_FAILURE_WINDOW = timedelta(minutes=5)
_LOGIN_ACCOUNT_LIMIT = 5
_LOGIN_NETWORK_LIMIT = 50
_REFRESH_WINDOW = timedelta(minutes=5)
_REFRESH_NETWORK_LIMIT = 120
logger = logging.getLogger(__name__)


def validate_password(password: str, *, minimum_length: int = 8) -> str:
    if len(password) < minimum_length:
        raise InvalidPasswordError(f"Пароль должен быть не короче {minimum_length} символов.")
    if len(password) > 1024:
        raise InvalidPasswordError("Пароль должен быть не длиннее 1024 символов.")
    if normalize("NFKC", password).casefold() in _BLOCKED_PASSWORDS:
        raise InvalidPasswordError("Этот пароль слишком распространён. Выберите другой.")
    return password


def safe_next_path(next_path: str | None) -> str:
    if not next_path:
        return "/app/workspaces"
    if not next_path.startswith("/") or next_path.startswith("//"):
        return "/app/workspaces"
    return next_path


@dataclass(frozen=True)
class LoginSession:
    user: User
    workspace: Workspace
    membership: WorkspaceMember
    session: UserSession
    tokens: TokenPair | None


@dataclass(frozen=True)
class AuthenticatedSession:
    user: User
    session: UserSession


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def list_active(self) -> list[User]:
        return await self.users.list_active()

    async def get_active(self, user_id: UUID) -> User | None:
        return await self.users.get_active(user_id)

    async def create(self, *, email: str, password: str, name: str | None = None) -> User:
        normalized_email = normalize_email(email)
        existing_user = await self.users.get_by_email(normalized_email)
        if existing_user is not None:
            raise EmailAlreadyRegisteredError("Пользователь с таким email уже существует.")

        user = await self.users.create(
            email=normalized_email,
            password_hash=hash_password(validate_password(password)),
            name=clean_user_name(name),
        )
        await self.session.commit()
        return user

    async def update_name(self, *, user: User, name: str | None) -> User:
        user = await self.users.update_name(user=user, name=clean_user_name(name))
        await self.session.commit()
        return user


class AuthenticationService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)
        self.workspaces = WorkspaceRepository(session)
        self.rate_limits = AuthRateLimitRepository(session)

    async def login(
        self,
        *,
        email: str,
        password: str,
        network_key: str = "unknown",
        user_agent: str | None = None,
    ) -> LoginSession:
        normalized_email = normalize_email(email)
        user = await self.users.get_by_email(normalized_email)
        if user is None:
            verify_dummy_password(password)
            await self._reject_failed_login(normalized_email, network_key)

        password_valid, updated_hash = verify_and_update_password(password, user.password_hash)
        if (
            not password_valid
            or not user.is_active
            or user.deactivated_at is not None
            or user.email_verified_at is None
        ):
            await self._reject_failed_login(normalized_email, network_key)

        if updated_hash is not None:
            user.password_hash = updated_hash

        login_session = await self.create_login_session_for_user(user, user_agent=user_agent)
        await self.session.commit()
        logger.info(
            "Authentication login succeeded user_id=%s session_id=%s",
            user.id,
            login_session.session.id,
        )
        return login_session

    async def _reject_failed_login(
        self,
        normalized_email: str,
        network_key: str,
    ) -> NoReturn:
        account_count = await self.rate_limits.increment(
            bucket_hash=auth_rate_limit_bucket_hash(
                scope="login-account",
                key=normalized_email,
                settings=self.settings,
            ),
            window=_LOGIN_FAILURE_WINDOW,
        )
        network_count = await self.rate_limits.increment(
            bucket_hash=auth_rate_limit_bucket_hash(
                scope="login-network",
                key=network_key,
                settings=self.settings,
            ),
            window=_LOGIN_FAILURE_WINDOW,
        )
        await self.session.commit()
        if account_count > _LOGIN_ACCOUNT_LIMIT or network_count > _LOGIN_NETWORK_LIMIT:
            raise AuthRateLimitedError(int(_LOGIN_FAILURE_WINDOW.total_seconds()))
        raise InvalidCredentialsError("Неверный email или пароль.")

    async def create_login_session_for_user(
        self,
        user: User,
        *,
        user_agent: str | None = None,
    ) -> LoginSession:
        membership = await self.workspaces.get_first_active_membership_for_user(user.id)
        if membership is None:
            (
                workspace,
                membership,
            ) = await self.workspaces.create_personal_workspace_with_owner_membership(user.id)
            await self._record_personal_workspace_created(user_id=user.id, workspace=workspace)
        else:
            workspace = membership.workspace

        login_session = await self._create_login_session_record(
            user=user,
            workspace=workspace,
            membership=membership,
            user_agent=user_agent,
        )
        return login_session

    async def resolve_login_session(self, access_token: str) -> LoginSession | None:
        authenticated, changed = await self._resolve_access_session(access_token)
        if authenticated is None:
            if changed:
                await self.session.commit()
            return None
        login_session, workspace_changed = await self._resolve_login_session_record(
            authenticated.session
        )
        changed = changed or workspace_changed
        if changed:
            await self.session.commit()
        return login_session

    async def resolve_authenticated_session(
        self,
        access_token: str,
    ) -> AuthenticatedSession | None:
        authenticated, changed = await self._resolve_access_session(access_token)
        if changed:
            await self.session.commit()
        return authenticated

    async def switch_workspace(self, *, access_token: str, workspace_id: UUID) -> Workspace:
        authenticated, _changed = await self._resolve_access_session(access_token)
        if authenticated is None:
            raise UserError("Сессия не найдена.")
        login_session, _changed = await self._resolve_login_session_record(authenticated.session)
        if login_session is None:
            raise UserError("Сессия не найдена.")

        membership = await self.workspaces.get_active_membership(
            user_id=login_session.user.id,
            workspace_id=workspace_id,
        )
        if membership is None:
            raise UserError("Workspace не найден или недоступен.")

        login_session.session.current_workspace_id = membership.workspace_id
        login_session.session.last_seen_at = utc_now()
        await self.session.commit()
        return membership.workspace

    async def refresh(self, refresh_token: str, *, network_key: str = "unknown") -> TokenPair:
        count = await self.rate_limits.increment(
            bucket_hash=auth_rate_limit_bucket_hash(
                scope="refresh-network",
                key=network_key,
                settings=self.settings,
            ),
            window=_REFRESH_WINDOW,
        )
        await self.session.commit()
        if count > _REFRESH_NETWORK_LIMIT:
            raise AuthRateLimitedError(int(_REFRESH_WINDOW.total_seconds()))

        claims = decode_refresh_token(refresh_token, self.settings)
        if claims is None:
            raise InvalidRefreshTokenError("Refresh token недействителен.")
        user_session = await self.users.get_session_for_refresh(claims.session_id)
        now = utc_now()
        if (
            user_session is None
            or user_session.user_id != claims.user_id
            or not user_session.user.is_active
            or user_session.user.deactivated_at is not None
            or user_session.revoked_at is not None
            or user_session.expires_at <= now
            or user_session.last_seen_at
            <= now - timedelta(seconds=self.settings.session_idle_timeout_seconds)
        ):
            if user_session is not None and user_session.revoked_at is None:
                await self.users.revoke_session(user_session)
                await self.session.commit()
            raise InvalidRefreshTokenError("Refresh token недействителен.")

        token_hash = hash_token(refresh_token)
        if token_hash != user_session.refresh_token_hash:
            within_race_window = (
                token_hash == user_session.previous_refresh_token_hash
                and user_session.refresh_rotated_at is not None
                and user_session.refresh_rotated_at
                >= now - timedelta(seconds=self.settings.refresh_reuse_grace_seconds)
            )
            if within_race_window:
                raise RefreshRaceError("Refresh уже выполнен параллельным запросом.")
            await self.users.revoke_session(user_session)
            await self.session.commit()
            logger.warning(
                "Refresh token reuse revoked session user_id=%s session_id=%s",
                claims.user_id,
                claims.session_id,
            )
            raise InvalidRefreshTokenError("Обнаружено повторное использование refresh token.")

        tokens = self._rotate_session_tokens(user_session)
        await self.session.commit()
        return tokens

    async def logout(self, refresh_token: str | None) -> None:
        if refresh_token is None:
            return
        claims = decode_refresh_token(refresh_token, self.settings)
        if claims is None:
            return
        user_session = await self.users.get_session_for_refresh(claims.session_id)
        if user_session is not None and user_session.user_id == claims.user_id:
            await self.users.revoke_session(user_session)
            await self.session.commit()
            logger.info(
                "Authentication session revoked user_id=%s session_id=%s",
                claims.user_id,
                claims.session_id,
            )

    async def logout_all(self, user_id: UUID) -> None:
        await self.users.revoke_all_sessions(user_id)
        await self.session.commit()
        logger.info("All authentication sessions revoked user_id=%s", user_id)

    async def _resolve_login_session_record(
        self,
        user_session: UserSession,
    ) -> tuple[LoginSession | None, bool]:
        changed = False

        membership = None
        if user_session.current_workspace_id is not None:
            membership = await self.workspaces.get_active_membership(
                user_id=user_session.user_id,
                workspace_id=user_session.current_workspace_id,
            )

        if membership is None:
            membership = await self.workspaces.get_first_active_membership_for_user(
                user_session.user_id
            )
            if membership is None:
                (
                    workspace,
                    membership,
                ) = await self.workspaces.create_personal_workspace_with_owner_membership(
                    user_session.user_id
                )
                await self._record_personal_workspace_created(
                    user_id=user_session.user_id,
                    workspace=workspace,
                )
            else:
                workspace = membership.workspace
            user_session.current_workspace_id = workspace.id
            changed = True
        else:
            workspace = membership.workspace

        return (
            LoginSession(
                user=user_session.user,
                workspace=workspace,
                membership=membership,
                session=user_session,
                tokens=None,
            ),
            changed,
        )

    async def _resolve_access_session(
        self, access_token: str
    ) -> tuple[AuthenticatedSession | None, bool]:
        claims = decode_access_token(access_token, self.settings)
        if claims is None:
            return None, False
        user_session = await self.users.get_active_session(
            session_id=claims.session_id,
            user_id=claims.user_id,
        )
        if user_session is None:
            return None, False

        now = utc_now()
        idle_timeout = timedelta(seconds=self.settings.session_idle_timeout_seconds)
        if (
            not user_session.user.is_active
            or user_session.user.deactivated_at is not None
            or user_session.expires_at <= now
            or user_session.last_seen_at <= now - idle_timeout
        ):
            await self.users.revoke_session(user_session)
            return None, True

        touch_interval = timedelta(seconds=self.settings.session_touch_interval_seconds)
        if user_session.last_seen_at <= now - touch_interval:
            user_session.last_seen_at = now
            return AuthenticatedSession(user_session.user, user_session), True
        return AuthenticatedSession(user_session.user, user_session), False

    async def _create_login_session_record(
        self,
        *,
        user: User,
        workspace: Workspace,
        membership: WorkspaceMember,
        user_agent: str | None = None,
    ) -> LoginSession:
        expires_at = utc_now() + timedelta(seconds=self.settings.session_max_age_seconds)
        session_id = uuid4()
        tokens = generate_token_pair(
            user_id=user.id,
            session_id=session_id,
            refresh_expires_at=expires_at,
            settings=self.settings,
        )
        user_session = await self.users.create_session(
            UserSession(
                id=session_id,
                user_id=user.id,
                current_workspace_id=workspace.id,
                refresh_token_hash=hash_token(tokens.refresh_token),
                expires_at=expires_at,
                user_agent_summary=summarize_user_agent(user_agent),
            )
        )
        return LoginSession(
            user=user,
            workspace=workspace,
            membership=membership,
            session=user_session,
            tokens=tokens,
        )

    def _rotate_session_tokens(self, user_session: UserSession) -> TokenPair:
        tokens = self._token_pair_for_session(user_session)
        user_session.previous_refresh_token_hash = user_session.refresh_token_hash
        user_session.refresh_token_hash = hash_token(tokens.refresh_token)
        user_session.refresh_rotated_at = utc_now()
        user_session.last_seen_at = utc_now()
        return tokens

    def _token_pair_for_session(self, user_session: UserSession) -> TokenPair:
        return generate_token_pair(
            user_id=user_session.user_id,
            session_id=user_session.id,
            refresh_expires_at=user_session.expires_at,
            settings=self.settings,
        )

    async def _record_personal_workspace_created(
        self,
        *,
        user_id: UUID,
        workspace: Workspace,
    ) -> None:
        await self.workspaces.create_audit_event(
            workspace_id=workspace.id,
            event_type=WorkspaceAuditEventType.WORKSPACE_CREATED,
            actor_user_id=user_id,
            entity_type="workspace",
            entity_id=workspace.id,
            details={
                "name": workspace.name,
                "type": workspace.type.value,
                "default_currency": workspace.default_currency,
            },
        )
