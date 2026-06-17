from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.errors import UserError
from app.features.users.models import User
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


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.workspaces = WorkspaceRepository(session)

    async def list_active(self) -> list[User]:
        return await self.users.list_active()

    async def get_active(self, user_id: UUID) -> User | None:
        return await self.users.get_active(user_id)

    async def create(self, *, email: str, name: str | None = None) -> User:
        normalized_email = normalize_email(email)
        existing_user = await self.users.get_by_email(normalized_email)
        if existing_user is not None:
            raise UserError("Пользователь с таким email уже существует.")

        user = await self.users.create(
            email=normalized_email,
            name=clean_user_name(name),
        )
        await self.session.commit()
        return user

    async def create_with_personal_workspace(
        self,
        *,
        email: str,
        name: str | None = None,
    ) -> tuple[User, Workspace]:
        normalized_email = normalize_email(email)
        existing_user = await self.users.get_by_email(normalized_email)
        if existing_user is not None:
            raise UserError("Пользователь с таким email уже существует.")

        user = await self.users.create(
            email=normalized_email,
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
