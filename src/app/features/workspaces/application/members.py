from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.features.chat_integrations.repository import ChatIntegrationRepository
from app.features.users.repository import UserRepository
from app.features.workspaces.commands import (
    TransitionWorkspaceMemberCommand,
    UpdateWorkspaceMemberRoleApiCommand,
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
)
from app.features.workspaces.models import Workspace, WorkspaceMember
from app.features.workspaces.permissions import (
    ADMIN_MANAGEABLE_MEMBER_ROLES,
    MANAGEABLE_MEMBER_ROLES,
    can_assign_member_role,
    can_disable_member,
    can_manage_members,
    can_reactivate_member,
)
from app.features.workspaces.repository import WorkspaceRepository
from app.features.workspaces.schemas import (
    WorkspaceMemberBlockingReason,
    WorkspaceMemberCapabilitiesDto,
    WorkspaceMemberItemDto,
    WorkspaceMembersCapabilitiesDto,
    WorkspaceMembersDto,
)

MEMBER_DIRECTORY_LIMIT = 100


class WorkspaceMemberService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._chat = ChatIntegrationRepository(session)
        self._users = UserRepository(session)
        self._workspaces = WorkspaceRepository(session)

    async def read(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
    ) -> WorkspaceMembersDto:
        actor = await self._workspaces.get_visible_membership_for_user(
            user_id=actor_user_id,
            workspace_id=workspace_id,
        )
        if actor is None:
            raise WorkspaceNotFoundError("Workspace не найден.")
        return await self._directory(actor=actor, workspace=actor.workspace)

    async def update_role(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        command: UpdateWorkspaceMemberRoleApiCommand,
    ) -> WorkspaceMembersDto:
        async def mutate(
            actor: WorkspaceMember,
            workspace: Workspace,
            target: WorkspaceMember,
        ) -> None:
            self._require_current(target.updated_at, command.expected_updated_at)
            if target.user_id == actor_user_id:
                self._blocked("Нельзя изменить собственную роль.", "member_self")
            if not workspace.is_active:
                self._blocked("Неактивное пространство нельзя изменять.", "workspace_inactive")
            if not can_assign_member_role(actor, target, command.role):
                self._blocked(
                    "Недостаточно прав для изменения роли участника.",
                    "member_management_forbidden",
                )
            old_role = target.role
            if old_role == command.role:
                return
            target.role = command.role
            await self._session.flush()
            await self._audit(
                workspace_id=workspace_id,
                event_type=WorkspaceAuditEventType.MEMBER_ROLE_CHANGED,
                actor_user_id=actor_user_id,
                target=target,
                details={"old_role": old_role.value, "new_role": command.role.value},
            )

        return await self._mutate(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            member_id=command.member_id,
            mutation=mutate,
        )

    async def disable(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        command: TransitionWorkspaceMemberCommand,
    ) -> WorkspaceMembersDto:
        async def mutate(
            actor: WorkspaceMember,
            workspace: Workspace,
            target: WorkspaceMember,
        ) -> None:
            self._require_current(target.updated_at, command.expected_updated_at)
            if target.user_id == actor_user_id:
                self._blocked("Нельзя отключить собственный доступ.", "member_self")
            if target.role == WorkspaceRole.OWNER:
                self._blocked("Сначала передайте владение пространством.", "member_owner")
            if not workspace.is_active:
                self._blocked("Неактивное пространство нельзя изменять.", "workspace_inactive")
            if target.status != WorkspaceMemberStatus.ACTIVE:
                self._blocked("Участник уже неактивен.", "member_disabled")
            if not can_disable_member(actor, target):
                self._blocked(
                    "Недостаточно прав для отключения участника.",
                    "member_management_forbidden",
                )
            target.status = WorkspaceMemberStatus.DISABLED
            await self._session.flush()
            fallback = await self._workspaces.get_first_active_membership_for_user_excluding(
                user_id=target.user_id,
                excluded_workspace_id=workspace_id,
            )
            await self._users.move_active_workspace_sessions(
                user_id=target.user_id,
                from_workspace_id=workspace_id,
                to_workspace_id=fallback.workspace_id if fallback else None,
            )
            await self._chat.revoke_workspace_access_for_user(
                workspace_id=workspace_id,
                user_id=target.user_id,
                revoked_at=utc_now(),
            )
            await self._audit(
                workspace_id=workspace_id,
                event_type=WorkspaceAuditEventType.MEMBER_DISABLED,
                actor_user_id=actor_user_id,
                target=target,
                details={"new_status": target.status.value, "role": target.role.value},
            )

        return await self._mutate(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            member_id=command.member_id,
            mutation=mutate,
        )

    async def reactivate(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        command: TransitionWorkspaceMemberCommand,
    ) -> WorkspaceMembersDto:
        async def mutate(
            actor: WorkspaceMember,
            workspace: Workspace,
            target: WorkspaceMember,
        ) -> None:
            self._require_current(target.updated_at, command.expected_updated_at)
            if target.role == WorkspaceRole.OWNER:
                self._blocked("Статус владельца нельзя изменить.", "member_owner")
            if not workspace.is_active:
                self._blocked("Неактивное пространство нельзя изменять.", "workspace_inactive")
            if target.status != WorkspaceMemberStatus.DISABLED:
                self._blocked("Участник уже активен.", "member_active")
            if not can_reactivate_member(actor, target):
                self._blocked(
                    "Недостаточно прав для восстановления участника.",
                    "member_management_forbidden",
                )
            target.status = WorkspaceMemberStatus.ACTIVE
            await self._session.flush()
            await self._audit(
                workspace_id=workspace_id,
                event_type=WorkspaceAuditEventType.MEMBER_REACTIVATED,
                actor_user_id=actor_user_id,
                target=target,
                details={"new_status": target.status.value, "role": target.role.value},
            )

        return await self._mutate(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            member_id=command.member_id,
            mutation=mutate,
        )

    async def _mutate(self, *, actor_user_id, workspace_id, member_id, mutation):
        try:
            workspace = await self._workspaces.lock_for_update(workspace_id)
            if workspace is None:
                raise WorkspaceNotFoundError("Workspace не найден.")
            actor = await self._workspaces.get_membership_for_update(
                user_id=actor_user_id,
                workspace_id=workspace_id,
            )
            if actor is None:
                raise WorkspaceNotFoundError("Workspace не найден.")
            target = await self._workspaces.get_member_by_id_for_update(
                workspace_id=workspace_id,
                member_id=member_id,
            )
            if target is None:
                raise WorkspaceNotFoundError("Участник не найден.")
            await mutation(actor, workspace, target)
            await self._session.commit()
            return await self._directory(actor=actor, workspace=workspace)
        except Exception:
            await self._session.rollback()
            raise

    async def _directory(
        self,
        *,
        actor: WorkspaceMember,
        workspace: Workspace,
    ) -> WorkspaceMembersDto:
        members = await self._workspaces.list_members_for_workspace(
            workspace.id,
            limit=MEMBER_DIRECTORY_LIMIT,
        )
        fallback = await self._workspaces.get_first_active_membership_for_user_excluding(
            user_id=actor.user_id,
            excluded_workspace_id=workspace.id,
        )
        manageable = workspace.is_active and can_manage_members(actor)
        return WorkspaceMembersDto(
            workspace_id=workspace.id,
            items=[
                self._item(
                    actor=actor,
                    workspace=workspace,
                    member=member,
                    actor_has_fallback=fallback is not None,
                )
                for member in members
            ],
            capabilities=WorkspaceMembersCapabilitiesDto(can_manage_members=manageable),
        )

    @staticmethod
    def _item(
        *,
        actor: WorkspaceMember,
        workspace: Workspace,
        member: WorkspaceMember,
        actor_has_fallback: bool,
    ) -> WorkspaceMemberItemDto:
        is_self = actor.user_id == member.user_id
        active_workspace = workspace.is_active
        assignable = WorkspaceMemberService._assignable_roles(actor, member)
        can_update = active_workspace and not is_self and bool(assignable)
        can_disable = (
            active_workspace
            and not is_self
            and member.role != WorkspaceRole.OWNER
            and member.status == WorkspaceMemberStatus.ACTIVE
            and can_disable_member(actor, member)
        )
        can_reactivate = (
            active_workspace
            and member.role != WorkspaceRole.OWNER
            and member.status == WorkspaceMemberStatus.DISABLED
            and can_reactivate_member(actor, member)
        )
        authoritative_owner = (
            actor.role == WorkspaceRole.OWNER and workspace.owner_id == actor.user_id
        )
        can_transfer_ownership = (
            active_workspace
            and authoritative_owner
            and not is_self
            and member.role != WorkspaceRole.OWNER
            and member.status == WorkspaceMemberStatus.ACTIVE
        )
        can_leave = (
            active_workspace
            and is_self
            and member.role != WorkspaceRole.OWNER
            and actor_has_fallback
        )
        reasons: list[WorkspaceMemberBlockingReason] = []
        if not active_workspace:
            reasons.append(WorkspaceMemberBlockingReason.WORKSPACE_INACTIVE)
        if is_self:
            reasons.append(WorkspaceMemberBlockingReason.SELF)
        if member.role == WorkspaceRole.OWNER:
            reasons.append(WorkspaceMemberBlockingReason.OWNER)
        if not can_manage_members(actor):
            reasons.append(WorkspaceMemberBlockingReason.FORBIDDEN)
        if is_self and member.role != WorkspaceRole.OWNER and not actor_has_fallback:
            reasons.append(WorkspaceMemberBlockingReason.FALLBACK_REQUIRED)
        return WorkspaceMemberItemDto(
            id=member.id,
            user_id=member.user_id,
            name=member.user.name,
            email=member.user.email,
            role=member.role,
            status=member.status,
            joined_at=member.joined_at,
            updated_at=member.updated_at,
            is_self=is_self,
            capabilities=WorkspaceMemberCapabilitiesDto(
                can_update_role=can_update,
                can_disable=can_disable,
                can_reactivate=can_reactivate,
                can_transfer_ownership=can_transfer_ownership,
                can_leave=can_leave,
                assignable_roles=assignable if can_update else [],
            ),
            blocking_reason_codes=reasons,
        )

    @staticmethod
    def _assignable_roles(
        actor: WorkspaceMember,
        target: WorkspaceMember,
    ) -> list[WorkspaceRole]:
        if target.role == WorkspaceRole.OWNER or target.user_id == actor.user_id:
            return []
        source = (
            ADMIN_MANAGEABLE_MEMBER_ROLES
            if actor.role == WorkspaceRole.ADMIN
            else set(MANAGEABLE_MEMBER_ROLES)
            if actor.role == WorkspaceRole.OWNER
            else set()
        )
        return [role for role in MANAGEABLE_MEMBER_ROLES if role in source]

    @staticmethod
    def _require_current(actual: datetime, expected: datetime) -> None:
        if actual != expected:
            raise WorkspaceMemberConflictError("Участник уже изменён. Загрузите актуальные данные.")

    @staticmethod
    def _blocked(message: str, reason_code: str) -> None:
        raise WorkspaceMemberTransitionError(message, reason_codes=[reason_code])

    async def _audit(
        self,
        *,
        workspace_id: UUID,
        event_type: WorkspaceAuditEventType,
        actor_user_id: UUID,
        target: WorkspaceMember,
        details: dict[str, str],
    ) -> None:
        await self._workspaces.create_audit_event(
            workspace_id=workspace_id,
            event_type=event_type,
            actor_user_id=actor_user_id,
            target_user_id=target.user_id,
            entity_type="workspace_member",
            entity_id=target.id,
            details=details,
        )
