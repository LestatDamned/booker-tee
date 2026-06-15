from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.users.models import User
from app.features.users.repository import UserRepository
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
