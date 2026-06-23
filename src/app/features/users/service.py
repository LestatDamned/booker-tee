from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.core.settings import Settings
from app.db.base import utc_now
from app.features.users.errors import UserError
from app.features.users.models import User, UserSession
from app.features.users.repository import UserRepository
from app.features.workspaces.models import Workspace, WorkspaceType
from app.features.workspaces.repository import WorkspaceRepository


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized or "@" not in normalized:
        raise UserError("Некорректный email пользователя.")
    return normalized


def clean_user_name(name: str | None) -> str | None:
    if name is None:
        return None
    cleaned = name.strip()
    return cleaned or None


def validate_password(password: str) -> str:
    if len(password) < 8:
        raise UserError("Пароль должен быть не короче 8 символов.")
    return password


@dataclass(frozen=True)
class LoginSession:
    user: User
    workspace: Workspace
    session: UserSession
    session_token: str


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.workspaces = WorkspaceRepository(session)

    async def list_active(self) -> list[User]:
        return await self.users.list_active()

    async def get_active(self, user_id: UUID) -> User | None:
        return await self.users.get_active(user_id)

    async def create(self, *, email: str, password: str, name: str | None = None) -> User:
        normalized_email = normalize_email(email)
        existing_user = await self.users.get_by_email(normalized_email)
        if existing_user is not None:
            raise UserError("Пользователь с таким email уже существует.")

        user = await self.users.create(
            email=normalized_email,
            password_hash=hash_password(validate_password(password)),
            name=clean_user_name(name),
        )
        await self.session.commit()
        return user

    async def create_with_personal_workspace(
        self,
        *,
        email: str,
        password: str,
        name: str | None = None,
    ) -> tuple[User, Workspace]:
        normalized_email = normalize_email(email)
        existing_user = await self.users.get_by_email(normalized_email)
        if existing_user is not None:
            raise UserError("Пользователь с таким email уже существует.")

        user = await self.users.create(
            email=normalized_email,
            password_hash=hash_password(validate_password(password)),
            name=clean_user_name(name),
        )
        workspace = await self.workspaces.create_workspace(
            owner_id=user.id,
            name="Personal",
            workspace_type=WorkspaceType.PERSONAL,
            default_currency="RUB",
        )
        await self.session.commit()
        return user, workspace


class AuthenticationService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)
        self.workspaces = WorkspaceRepository(session)

    async def register(
        self,
        *,
        email: str,
        password: str,
        name: str | None = None,
    ) -> LoginSession:
        if not self.settings.allow_signups:
            raise UserError("Регистрация временно закрыта.")

        user, workspace = await UserService(self.session).create_with_personal_workspace(
            email=email,
            password=password,
            name=name,
        )
        return await self._create_login_session(user=user, workspace=workspace)

    async def login(self, *, email: str, password: str) -> LoginSession:
        normalized_email = normalize_email(email)
        user = await self.users.get_by_email(normalized_email)
        if user is None or not user.is_active:
            raise UserError("Неверный email или пароль.")
        if not verify_password(password, user.password_hash):
            raise UserError("Неверный email или пароль.")

        workspace = await self.workspaces.get_first_active_for_user(user.id)
        if workspace is None:
            workspace = await self.workspaces.create_personal_workspace(user.id)
            await self.session.commit()
        return await self._create_login_session(user=user, workspace=workspace)

    async def resolve_login_session(self, session_token: str) -> LoginSession | None:
        user_session = await self.users.get_active_session_by_token_hash(
            hash_session_token(session_token)
        )
        if user_session is None or not user_session.user.is_active:
            return None

        workspace = user_session.current_workspace
        if workspace is None or not workspace.is_active:
            workspace = await self.workspaces.get_first_active_for_user(user_session.user_id)
            if workspace is None:
                workspace = await self.workspaces.create_personal_workspace(user_session.user_id)
            user_session.current_workspace_id = workspace.id

        user_session.last_seen_at = utc_now()
        await self.session.commit()
        return LoginSession(
            user=user_session.user,
            workspace=workspace,
            session=user_session,
            session_token=session_token,
        )

    async def switch_workspace(self, *, session_token: str, workspace_id: UUID) -> Workspace:
        login_session = await self.resolve_login_session(session_token)
        if login_session is None:
            raise UserError("Сессия не найдена.")

        workspace = await self.workspaces.get_active_for_user(login_session.user.id, workspace_id)
        if workspace is None:
            raise UserError("Workspace не найден или недоступен.")

        login_session.session.current_workspace_id = workspace.id
        login_session.session.last_seen_at = utc_now()
        await self.session.commit()
        return workspace

    async def logout(self, session_token: str) -> None:
        user_session = await self.users.get_active_session_by_token_hash(
            hash_session_token(session_token)
        )
        if user_session is not None:
            await self.users.revoke_session(user_session)
            await self.session.commit()

    async def _create_login_session(self, *, user: User, workspace: Workspace) -> LoginSession:
        session_token = generate_session_token()
        expires_at = utc_now() + timedelta(seconds=self.settings.session_max_age_seconds)
        user_session = await self.users.create_session(
            UserSession(
                user_id=user.id,
                current_workspace_id=workspace.id,
                session_token_hash=hash_session_token(session_token),
                expires_at=expires_at,
            )
        )
        await self.session.commit()
        return LoginSession(
            user=user,
            workspace=workspace,
            session=user_session,
            session_token=session_token,
        )
