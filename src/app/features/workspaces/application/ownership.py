from dataclasses import dataclass
from typing import NoReturn
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_session_token
from app.db.base import utc_now
from app.features.chat_integrations.repository import ChatIntegrationRepository
from app.features.users.models import User, UserSession
from app.features.users.repository import UserRepository
from app.features.workspaces.application.members import WorkspaceMemberService
from app.features.workspaces.commands import (
    LeaveWorkspaceCommand,
    TransferWorkspaceOwnershipCommand,
)
from app.features.workspaces.domain.types import (
    WorkspaceAuditEventType,
    WorkspaceMemberStatus,
    WorkspaceRole,
)
from app.features.workspaces.errors import (
    WorkspaceMemberConflictError,
    WorkspaceMemberTransitionError,
    WorkspaceNotFoundError,
    WorkspaceOwnershipTransferConflictError,
    WorkspaceSessionNotFoundError,
    WorkspaceSwitchConflictError,
)
from app.features.workspaces.models import Workspace, WorkspaceMember
from app.features.workspaces.repository import WorkspaceRepository
from app.features.workspaces.schemas import WorkspaceMembersDto


@dataclass(frozen=True)
class WorkspaceOwnershipTransferResult:
    user: User
    workspace: Workspace
    membership: WorkspaceMember
    members: WorkspaceMembersDto


@dataclass(frozen=True)
class WorkspaceLeaveResult:
    user: User
    workspace: Workspace
    membership: WorkspaceMember


class WorkspaceOwnershipService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._chat = ChatIntegrationRepository(session)
        self._members = WorkspaceMemberService(session)
        self._users = UserRepository(session)
        self._workspaces = WorkspaceRepository(session)

    async def transfer(
        self,
        *,
        actor: User,
        session_token: str,
        workspace_id: UUID,
        command: TransferWorkspaceOwnershipCommand,
    ) -> WorkspaceOwnershipTransferResult:
        try:
            workspace = await self._required_locked_workspace(workspace_id)
            user_session = await self._required_locked_session(
                actor=actor,
                session_token=session_token,
            )
            memberships = await self._workspaces.list_members_for_workspace_for_update(workspace_id)
            actor_membership = self._membership_for_user(memberships, actor.id)
            recipient = self._membership_by_id(
                memberships,
                command.recipient_member_id,
            )
            if actor_membership is None or recipient is None:
                raise WorkspaceNotFoundError("Workspace или участник не найден.")
            if (
                workspace.updated_at != command.expected_workspace_updated_at
                or recipient.updated_at != command.expected_recipient_updated_at
            ):
                raise WorkspaceOwnershipTransferConflictError(
                    "Владение или участник уже изменились. Загрузите актуальные данные."
                )
            self._require_authoritative_owner(
                workspace=workspace,
                actor_membership=actor_membership,
                memberships=memberships,
            )
            if recipient.user_id == actor.id:
                self._blocked("Вы уже владелец пространства.", "member_self")
            if recipient.status != WorkspaceMemberStatus.ACTIVE:
                self._blocked(
                    "Владение можно передать только активному участнику.", "member_disabled"
                )
            if recipient.role == WorkspaceRole.OWNER:
                raise WorkspaceOwnershipTransferConflictError(
                    "У пространства уже изменился владелец."
                )

            old_owner_id = workspace.owner_id
            workspace.owner_id = recipient.user_id
            actor_membership.role = WorkspaceRole.ADMIN
            recipient.role = WorkspaceRole.OWNER
            user_session.last_seen_at = utc_now()
            await self._session.flush()
            await self._workspaces.create_audit_event(
                workspace_id=workspace.id,
                event_type=WorkspaceAuditEventType.WORKSPACE_UPDATED,
                actor_user_id=actor.id,
                target_user_id=recipient.user_id,
                entity_type="workspace",
                entity_id=workspace.id,
                details={
                    "action": "ownership_transferred",
                    "old_owner_id": str(old_owner_id),
                    "new_owner_id": str(recipient.user_id),
                },
            )
            members = await self._members.read(
                actor_user_id=actor.id,
                workspace_id=workspace.id,
            )
            await self._session.commit()
            return WorkspaceOwnershipTransferResult(
                user=actor,
                workspace=workspace,
                membership=actor_membership,
                members=members,
            )
        except Exception:
            await self._session.rollback()
            raise

    async def leave(
        self,
        *,
        actor: User,
        session_token: str,
        workspace_id: UUID,
        command: LeaveWorkspaceCommand,
    ) -> WorkspaceLeaveResult:
        try:
            workspace = await self._required_locked_workspace(workspace_id)
            user_session = await self._required_locked_session(
                actor=actor,
                session_token=session_token,
            )
            current_workspace_id = user_session.current_workspace_id
            if (
                current_workspace_id is None
                or current_workspace_id != command.expected_current_workspace_id
            ):
                raise WorkspaceSwitchConflictError(current_workspace_id=current_workspace_id)
            membership = await self._workspaces.get_membership_for_update(
                user_id=actor.id,
                workspace_id=workspace_id,
            )
            if membership is None:
                raise WorkspaceNotFoundError("Workspace не найден.")
            if membership.updated_at != command.expected_member_updated_at:
                raise WorkspaceMemberConflictError(
                    "Ваш доступ уже изменился. Загрузите актуальные данные."
                )
            if not workspace.is_active:
                self._blocked("Неактивное пространство нельзя покинуть.", "workspace_inactive")
            if membership.role == WorkspaceRole.OWNER or workspace.owner_id == actor.id:
                self._blocked(
                    "Сначала передайте владение пространством.",
                    "last_owner_required",
                )
            leaving_current_workspace = current_workspace_id == workspace_id
            if leaving_current_workspace:
                get_fallback = (
                    self._workspaces.get_first_active_membership_for_user_excluding_for_update
                )
                fallback = await get_fallback(
                    user_id=actor.id,
                    excluded_workspace_id=workspace_id,
                )
            else:
                fallback = await self._workspaces.get_active_membership_for_update(
                    user_id=actor.id,
                    workspace_id=current_workspace_id,
                )
            if fallback is None:
                self._blocked(
                    "Сначала выберите или создайте другое пространство, затем повторите выход.",
                    "workspace_fallback_required",
                )

            membership.status = WorkspaceMemberStatus.REMOVED
            await self._session.flush()
            if leaving_current_workspace:
                await self._users.move_active_workspace_sessions(
                    user_id=actor.id,
                    from_workspace_id=workspace_id,
                    to_workspace_id=fallback.workspace_id,
                )
            await self._chat.revoke_workspace_access_for_user(
                workspace_id=workspace_id,
                user_id=actor.id,
                revoked_at=utc_now(),
            )
            await self._workspaces.create_audit_event(
                workspace_id=workspace.id,
                event_type=WorkspaceAuditEventType.MEMBER_DISABLED,
                actor_user_id=actor.id,
                target_user_id=actor.id,
                entity_type="workspace_member",
                entity_id=membership.id,
                details={
                    "action": "member_left",
                    "new_status": WorkspaceMemberStatus.REMOVED.value,
                    "role": membership.role.value,
                },
            )
            await self._session.commit()
            return WorkspaceLeaveResult(
                user=actor,
                workspace=fallback.workspace,
                membership=fallback,
            )
        except Exception:
            await self._session.rollback()
            raise

    async def _required_locked_workspace(self, workspace_id: UUID) -> Workspace:
        workspace = await self._workspaces.lock_for_update(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("Workspace не найден.")
        return workspace

    async def _required_locked_session(
        self,
        *,
        actor: User,
        session_token: str,
    ) -> UserSession:
        user_session = await self._users.get_active_session_by_token_hash_for_update(
            hash_session_token(session_token),
            user_id=actor.id,
        )
        if user_session is None:
            raise WorkspaceSessionNotFoundError("Сессия не найдена.")
        return user_session

    @staticmethod
    def _membership_for_user(
        memberships: list[WorkspaceMember],
        user_id: UUID,
    ) -> WorkspaceMember | None:
        return next((member for member in memberships if member.user_id == user_id), None)

    @staticmethod
    def _membership_by_id(
        memberships: list[WorkspaceMember],
        member_id: UUID,
    ) -> WorkspaceMember | None:
        return next((member for member in memberships if member.id == member_id), None)

    @staticmethod
    def _require_authoritative_owner(
        *,
        workspace: Workspace,
        actor_membership: WorkspaceMember,
        memberships: list[WorkspaceMember],
    ) -> None:
        active_owners = [
            member
            for member in memberships
            if member.role == WorkspaceRole.OWNER and member.status == WorkspaceMemberStatus.ACTIVE
        ]
        if (
            not workspace.is_active
            or workspace.owner_id != actor_membership.user_id
            or actor_membership.role != WorkspaceRole.OWNER
            or actor_membership.status != WorkspaceMemberStatus.ACTIVE
            or active_owners != [actor_membership]
        ):
            raise WorkspaceOwnershipTransferConflictError(
                "Authoritative owner изменился. Загрузите актуальные данные."
            )

    @staticmethod
    def _blocked(message: str, reason_code: str) -> NoReturn:
        raise WorkspaceMemberTransitionError(message, reason_codes=[reason_code])
