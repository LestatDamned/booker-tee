from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_session_token
from app.db.base import utc_now
from app.features.users.models import User
from app.features.users.repository import UserRepository
from app.features.workspaces.errors import (
    WorkspaceNotFoundError,
    WorkspaceSessionNotFoundError,
    WorkspaceSwitchConflictError,
)
from app.features.workspaces.models import Workspace, WorkspaceMember
from app.features.workspaces.repository import WorkspaceRepository


@dataclass(frozen=True)
class WorkspaceSessionSwitchResult:
    user: User
    workspace: Workspace
    membership: WorkspaceMember


class WorkspaceSessionSwitcher:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._workspaces = WorkspaceRepository(session)

    async def switch(
        self,
        *,
        actor: User,
        session_token: str,
        target_workspace_id: UUID,
        expected_current_workspace_id: UUID,
    ) -> WorkspaceSessionSwitchResult:
        try:
            user_session = await self._users.get_active_session_by_token_hash_for_update(
                hash_session_token(session_token),
                user_id=actor.id,
            )
            if user_session is None:
                raise WorkspaceSessionNotFoundError("Сессия не найдена.")
            if user_session.current_workspace_id != expected_current_workspace_id:
                raise WorkspaceSwitchConflictError(
                    current_workspace_id=user_session.current_workspace_id
                )
            membership = await self._workspaces.get_active_membership(
                user_id=actor.id,
                workspace_id=target_workspace_id,
            )
            if membership is None:
                raise WorkspaceNotFoundError("Workspace не найден.")
            user_session.current_workspace_id = membership.workspace_id
            user_session.last_seen_at = utc_now()
            await self._session.commit()
            return WorkspaceSessionSwitchResult(
                user=actor,
                workspace=membership.workspace,
                membership=membership,
            )
        except Exception:
            await self._session.rollback()
            raise
