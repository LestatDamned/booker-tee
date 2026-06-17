from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.users.models import User
from app.features.users.repository import UserRepository
from app.features.workspaces.commands import CreateWorkspaceCommand, UpdateWorkspaceCommand
from app.features.workspaces.errors import WorkspaceError
from app.features.workspaces.models import Workspace
from app.features.workspaces.repository import WorkspaceRepository


@dataclass(frozen=True)
class WorkspaceContext:
    user: User
    workspace: Workspace


class WorkspaceService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)
        self.workspaces = WorkspaceRepository(session)

    async def ensure_development_context(self) -> WorkspaceContext:
        user = await self.users.get_by_email(self.settings.dev_user_email)
        if user is None:
            user = await self.users.create_development_user(self.settings.dev_user_email)

        workspace = await self.workspaces.get_first_active_for_user(user.id)
        if workspace is None:
            workspace = await self.workspaces.create_personal_workspace(user.id)

        await self.session.commit()
        return WorkspaceContext(user=user, workspace=workspace)

    async def resolve_context(
        self,
        *,
        user_id: UUID | None = None,
        workspace_id: UUID | None = None,
    ) -> WorkspaceContext:
        user = await self._resolve_user(user_id)
        workspace = await self._resolve_workspace(user.id, workspace_id)
        await self.session.commit()
        return WorkspaceContext(user=user, workspace=workspace)

    async def list_user_workspaces(self, user_id: UUID) -> list[Workspace]:
        return await self.workspaces.list_active_for_user(user_id)

    async def get_user_workspace(self, user_id: UUID, workspace_id: UUID) -> Workspace | None:
        return await self.workspaces.get_active_for_user(user_id, workspace_id)

    async def create_for_user(
        self,
        *,
        user_id: UUID,
        command: CreateWorkspaceCommand,
    ) -> Workspace:
        name = clean_workspace_name(command.name)
        currency = normalize_currency(command.default_currency)
        workspace = await self.workspaces.create_workspace(
            owner_id=user_id,
            name=name,
            workspace_type=command.workspace_type,
            default_currency=currency,
        )
        await self.session.commit()
        return workspace

    async def update_for_owner(
        self,
        *,
        owner_id: UUID,
        workspace_id: UUID,
        command: UpdateWorkspaceCommand,
    ) -> Workspace:
        workspace = await self.workspaces.get_active_for_user(owner_id, workspace_id)
        if workspace is None or workspace.owner_id != owner_id:
            raise WorkspaceError("Workspace не найден или недоступен.")

        workspace.name = clean_workspace_name(command.name)
        workspace.type = command.workspace_type
        workspace.default_currency = normalize_currency(command.default_currency)
        await self.session.commit()
        return workspace

    async def _resolve_user(self, user_id: UUID | None) -> User:
        if user_id is not None:
            user = await self.users.get_active(user_id)
            if user is not None:
                return user

        user = await self.users.get_by_email(self.settings.dev_user_email)
        if user is None:
            user = await self.users.create_development_user(self.settings.dev_user_email)
        return user

    async def _resolve_workspace(
        self,
        user_id: UUID,
        workspace_id: UUID | None,
    ) -> Workspace:
        if workspace_id is not None:
            workspace = await self.workspaces.get_active_for_user(user_id, workspace_id)
            if workspace is not None:
                return workspace

        workspace = await self.workspaces.get_first_active_for_user(user_id)
        if workspace is None:
            workspace = await self.workspaces.create_personal_workspace(user_id)
        return workspace


def clean_workspace_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise WorkspaceError("Название workspace не может быть пустым.")
    return cleaned


def normalize_currency(currency: str) -> str:
    normalized = currency.strip().upper()
    if len(normalized) != 3:
        raise WorkspaceError("Валюта должна быть трехбуквенным кодом.")
    return normalized
