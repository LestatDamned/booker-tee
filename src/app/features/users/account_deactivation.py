from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.db.base import utc_now
from app.features.chat_integrations.repository import ChatIntegrationRepository
from app.features.users.errors import (
    AccountDeactivationBlockedError,
    CurrentPasswordIncorrectError,
)
from app.features.users.identity_repository import UserTokenRepository
from app.features.users.models import User
from app.features.users.repository import UserRepository
from app.features.workspaces.domain.types import WorkspaceAuditEventType
from app.features.workspaces.models import Workspace
from app.features.workspaces.repository import WorkspaceRepository


@dataclass(frozen=True)
class DeactivationBlocker:
    workspace_id: UUID
    workspace_name: str
    active_other_member_count: int


@dataclass(frozen=True)
class AccountDeactivationImpact:
    blockers: list[DeactivationBlocker]
    auto_deactivated_workspace_count: int

    @property
    def can_deactivate(self) -> bool:
        return not self.blockers


class AccountDeactivationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.tokens = UserTokenRepository(session)
        self.workspaces = WorkspaceRepository(session)
        self.chat = ChatIntegrationRepository(session)

    async def impact(self, *, user_id: UUID) -> AccountDeactivationImpact:
        workspaces = [
            workspace
            for workspace in await self.workspaces.list_for_owner(user_id)
            if workspace.is_active
        ]
        return await self._impact(user_id=user_id, workspaces=workspaces)

    async def deactivate(self, *, user: User, current_password: str) -> None:
        locked_user = await self.users.get_for_update(user.id)
        if locked_user is None or not verify_password(current_password, locked_user.password_hash):
            raise CurrentPasswordIncorrectError("Текущий пароль указан неверно.")

        workspaces = await self.workspaces.list_active_for_owner_for_update(user.id)
        impact = await self._impact(user_id=user.id, workspaces=workspaces)
        if impact.blockers:
            raise AccountDeactivationBlockedError(list(impact.blockers))

        now = utc_now()
        for workspace in workspaces:
            await self._deactivate_owned_workspace(workspace=workspace, user_id=user.id)
        await self.workspaces.disable_active_memberships_for_user(user.id)
        await self.chat.revoke_all_access_for_user(user_id=user.id, revoked_at=now)
        await self.tokens.consume_all_active_for_user(user_id=user.id)
        await self.users.revoke_all_sessions(user.id)
        locked_user.is_active = False
        locked_user.deactivated_at = now
        await self.session.commit()

    async def _impact(
        self,
        *,
        user_id: UUID,
        workspaces: list[Workspace],
    ) -> AccountDeactivationImpact:
        blockers: list[DeactivationBlocker] = []
        for workspace in workspaces:
            other_members = await self.workspaces.count_active_members_excluding(
                workspace_id=workspace.id,
                user_id=user_id,
            )
            if other_members:
                blockers.append(
                    DeactivationBlocker(
                        workspace_id=workspace.id,
                        workspace_name=workspace.name,
                        active_other_member_count=other_members,
                    )
                )
        return AccountDeactivationImpact(
            blockers=blockers,
            auto_deactivated_workspace_count=len(workspaces) - len(blockers),
        )

    async def _deactivate_owned_workspace(
        self,
        *,
        workspace: Workspace,
        user_id: UUID,
    ) -> None:
        now = utc_now()
        workspace.is_active = False
        workspace.archived_at = now
        await self.workspaces.revoke_pending_invitations(workspace.id, revoked_at=now)
        await self.chat.deactivate_workspace_runtime(workspace.id, deactivated_at=now)
        await self.workspaces.create_audit_event(
            workspace_id=workspace.id,
            event_type=WorkspaceAuditEventType.WORKSPACE_UPDATED,
            actor_user_id=user_id,
            entity_type="workspace",
            entity_id=workspace.id,
            details={"action": "workspace_deactivated_with_account"},
        )
