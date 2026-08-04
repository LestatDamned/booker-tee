from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.db.base import utc_now
from app.features.users.models import User
from app.features.users.repository import UserRepository
from app.features.workspaces.commands import (
    CreateWorkspaceCommand,
    CreateWorkspaceInvitationCommand,
    UpdateWorkspaceCommand,
    UpdateWorkspaceMemberRoleCommand,
)
from app.features.workspaces.errors import WorkspaceError
from app.features.workspaces.models import (
    Workspace,
    WorkspaceAuditEvent,
    WorkspaceAuditEventType,
    WorkspaceInvitation,
    WorkspaceInvitationStatus,
    WorkspaceMember,
    WorkspaceMemberStatus,
    WorkspaceRole,
)
from app.features.workspaces.permissions import (
    can_assign_member_role,
    can_disable_member,
    can_invite_members,
    can_reactivate_member,
    ensure_invitable_role,
)
from app.features.workspaces.repository import WorkspaceRepository
from app.features.workspaces.tokens import generate_invitation_token, hash_invitation_token

INVITATION_TTL = timedelta(hours=72)


@dataclass(frozen=True)
class WorkspaceContext:
    user: User
    workspace: Workspace
    membership: WorkspaceMember


@dataclass(frozen=True)
class CreatedWorkspaceInvitation:
    invitation: WorkspaceInvitation
    token: str


class WorkspaceService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)
        self.workspaces = WorkspaceRepository(session)

    async def resolve_context(
        self,
        *,
        user_id: UUID | None = None,
        workspace_id: UUID | None = None,
    ) -> WorkspaceContext:
        user = await self._resolve_user(user_id)
        membership = await self._resolve_membership(user.id, workspace_id)
        await self.session.commit()
        return WorkspaceContext(
            user=user,
            workspace=membership.workspace,
            membership=membership,
        )

    async def list_user_workspaces(self, user_id: UUID) -> list[Workspace]:
        return await self.workspaces.list_active_for_user(user_id)

    async def list_workspace_members(
        self,
        context: WorkspaceContext,
    ) -> list[WorkspaceMember]:
        return await self.workspaces.list_members_for_workspace(context.workspace.id)

    async def list_pending_invitations(
        self,
        context: WorkspaceContext,
    ) -> list[WorkspaceInvitation]:
        if not can_invite_members(context.membership):
            return []
        return await self.workspaces.list_pending_invitations(context.workspace.id)

    async def list_recent_audit_events(
        self,
        context: WorkspaceContext,
    ) -> list[WorkspaceAuditEvent]:
        return await self.workspaces.list_recent_audit_events(context.workspace.id)

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
        await self._record_audit_event(
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
        await self.session.commit()
        return workspace

    async def create_invitation(
        self,
        *,
        context: WorkspaceContext,
        command: CreateWorkspaceInvitationCommand,
    ) -> CreatedWorkspaceInvitation:
        if not can_invite_members(context.membership):
            raise WorkspaceError("Недостаточно прав для приглашения участников.")

        try:
            role = ensure_invitable_role(command.role)
        except ValueError as exc:
            raise WorkspaceError(str(exc)) from exc

        token = generate_invitation_token()
        invitation = await self.workspaces.create_invitation(
            workspace_id=context.workspace.id,
            role=role,
            token_hash=hash_invitation_token(token),
            invited_by_user_id=context.user.id,
            expires_at=utc_now() + INVITATION_TTL,
        )
        await self._record_audit_event(
            workspace_id=context.workspace.id,
            event_type=WorkspaceAuditEventType.INVITATION_CREATED,
            actor_user_id=context.user.id,
            entity_type="workspace_invitation",
            entity_id=invitation.id,
            details={"role": role.value},
        )
        await self.session.commit()
        return CreatedWorkspaceInvitation(invitation=invitation, token=token)

    async def preview_invitation(self, invitation_token: str) -> WorkspaceInvitation:
        return await self._resolve_usable_invitation(invitation_token)

    async def accept_invitation(
        self,
        *,
        context: WorkspaceContext,
        invitation_token: str,
    ) -> WorkspaceMember:
        invitation = await self._resolve_usable_invitation(invitation_token)
        membership = await self.workspaces.get_membership(
            user_id=context.user.id,
            workspace_id=invitation.workspace_id,
        )
        if membership is not None and membership.status != WorkspaceMemberStatus.ACTIVE:
            raise WorkspaceError("Доступ к этому пространству отключен.")

        if membership is None:
            membership = await self.workspaces.create_member(
                workspace_id=invitation.workspace_id,
                user_id=context.user.id,
                role=invitation.role,
                invited_by_user_id=invitation.invited_by_user_id,
            )

        invitation.status = WorkspaceInvitationStatus.ACCEPTED
        invitation.accepted_by_user_id = context.user.id
        invitation.accepted_at = utc_now()
        await self._record_audit_event(
            workspace_id=invitation.workspace_id,
            event_type=WorkspaceAuditEventType.INVITATION_ACCEPTED,
            actor_user_id=context.user.id,
            entity_type="workspace_invitation",
            entity_id=invitation.id,
            target_user_id=context.user.id,
            details={"role": invitation.role.value},
        )
        await self.session.commit()
        return membership

    async def revoke_invitation(
        self,
        *,
        context: WorkspaceContext,
        invitation_id: UUID,
    ) -> None:
        if not can_invite_members(context.membership):
            raise WorkspaceError("Недостаточно прав для отзыва приглашения.")

        invitation = await self.workspaces.get_pending_invitation(
            workspace_id=context.workspace.id,
            invitation_id=invitation_id,
        )
        if invitation is None:
            raise WorkspaceError("Приглашение не найдено или уже недействительно.")

        invitation.status = WorkspaceInvitationStatus.REVOKED
        invitation.revoked_at = utc_now()
        await self._record_audit_event(
            workspace_id=context.workspace.id,
            event_type=WorkspaceAuditEventType.INVITATION_REVOKED,
            actor_user_id=context.user.id,
            entity_type="workspace_invitation",
            entity_id=invitation.id,
            details={"role": invitation.role.value},
        )
        await self.session.commit()

    async def update_member_role(
        self,
        *,
        context: WorkspaceContext,
        command: UpdateWorkspaceMemberRoleCommand,
    ) -> WorkspaceMember:
        actor_membership, member = await self._locked_member_management_context(
            actor_user_id=context.user.id,
            workspace_id=context.workspace.id,
            member_id=command.member_id,
        )
        if member.user_id == context.user.id:
            raise WorkspaceError("Нельзя изменить собственную роль.")
        if not can_assign_member_role(actor_membership, member, command.role):
            raise WorkspaceError("Недостаточно прав для изменения роли участника.")

        old_role = member.role
        member.role = command.role
        await self._record_audit_event(
            workspace_id=context.workspace.id,
            event_type=WorkspaceAuditEventType.MEMBER_ROLE_CHANGED,
            actor_user_id=context.user.id,
            entity_type="workspace_member",
            entity_id=member.id,
            target_user_id=member.user_id,
            details={
                "old_role": old_role.value,
                "new_role": command.role.value,
            },
        )
        await self.session.commit()
        return member

    async def disable_member(
        self,
        *,
        context: WorkspaceContext,
        member_id: UUID,
    ) -> WorkspaceMember:
        actor_membership, member = await self._locked_member_management_context(
            actor_user_id=context.user.id,
            workspace_id=context.workspace.id,
            member_id=member_id,
        )
        if member.user_id == context.user.id:
            raise WorkspaceError("Нельзя отключить собственный доступ.")
        if not can_disable_member(actor_membership, member):
            raise WorkspaceError("Недостаточно прав для отключения участника.")
        if member.role == WorkspaceRole.OWNER:
            raise WorkspaceError("Сначала передайте владение пространством.")

        old_status = member.status
        member.status = WorkspaceMemberStatus.DISABLED
        await self._record_audit_event(
            workspace_id=context.workspace.id,
            event_type=WorkspaceAuditEventType.MEMBER_DISABLED,
            actor_user_id=context.user.id,
            entity_type="workspace_member",
            entity_id=member.id,
            target_user_id=member.user_id,
            details={
                "old_status": old_status.value,
                "new_status": WorkspaceMemberStatus.DISABLED.value,
                "role": member.role.value,
            },
        )
        await self.session.commit()
        return member

    async def reactivate_member(
        self,
        *,
        context: WorkspaceContext,
        member_id: UUID,
    ) -> WorkspaceMember:
        actor_membership, member = await self._locked_member_management_context(
            actor_user_id=context.user.id,
            workspace_id=context.workspace.id,
            member_id=member_id,
        )
        if not can_reactivate_member(actor_membership, member):
            raise WorkspaceError("Недостаточно прав для восстановления участника.")

        old_status = member.status
        member.status = WorkspaceMemberStatus.ACTIVE
        await self._record_audit_event(
            workspace_id=context.workspace.id,
            event_type=WorkspaceAuditEventType.MEMBER_REACTIVATED,
            actor_user_id=context.user.id,
            entity_type="workspace_member",
            entity_id=member.id,
            target_user_id=member.user_id,
            details={
                "old_status": old_status.value,
                "new_status": WorkspaceMemberStatus.ACTIVE.value,
                "role": member.role.value,
            },
        )
        await self.session.commit()
        return member

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
        await self._record_audit_event(
            workspace_id=workspace.id,
            event_type=WorkspaceAuditEventType.WORKSPACE_UPDATED,
            actor_user_id=owner_id,
            entity_type="workspace",
            entity_id=workspace.id,
            details={
                "name": workspace.name,
                "type": workspace.type.value,
                "default_currency": workspace.default_currency,
            },
        )
        await self.session.commit()
        return workspace

    async def _resolve_user(self, user_id: UUID | None) -> User:
        if user_id is None:
            raise WorkspaceError("Сначала создайте или выберите пользователя.")

        user = await self.users.get_active(user_id)
        if user is None:
            raise WorkspaceError("Пользователь не найден или недоступен.")
        return user

    async def _resolve_membership(
        self,
        user_id: UUID,
        workspace_id: UUID | None,
    ) -> WorkspaceMember:
        if workspace_id is not None:
            membership = await self.workspaces.get_active_membership(
                user_id=user_id,
                workspace_id=workspace_id,
            )
            if membership is not None:
                return membership

        membership = await self.workspaces.get_first_active_membership_for_user(user_id)
        if membership is None:
            (
                workspace,
                membership,
            ) = await self.workspaces.create_personal_workspace_with_owner_membership(user_id)
            await self._record_audit_event(
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
        return membership

    async def _locked_member_management_context(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        member_id: UUID,
    ) -> tuple[WorkspaceMember, WorkspaceMember]:
        workspace = await self.workspaces.lock_for_update(workspace_id)
        if workspace is None:
            raise WorkspaceError("Участник не найден.")
        actor_membership = await self.workspaces.get_membership_for_update(
            user_id=actor_user_id,
            workspace_id=workspace_id,
        )
        member = await self.workspaces.get_member_by_id_for_update(
            workspace_id=workspace_id,
            member_id=member_id,
        )
        if actor_membership is None or member is None:
            raise WorkspaceError("Участник не найден.")
        return actor_membership, member

    async def _record_audit_event(
        self,
        *,
        workspace_id: UUID,
        event_type: WorkspaceAuditEventType,
        actor_user_id: UUID | None,
        entity_type: str,
        entity_id: UUID | None,
        target_user_id: UUID | None = None,
        details: dict[str, str] | None = None,
    ) -> WorkspaceAuditEvent:
        return await self.workspaces.create_audit_event(
            workspace_id=workspace_id,
            event_type=event_type,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )

    async def _resolve_usable_invitation(self, invitation_token: str) -> WorkspaceInvitation:
        invitation = await self.workspaces.get_invitation_by_token_hash(
            hash_invitation_token(invitation_token)
        )
        if invitation is None or invitation.status != WorkspaceInvitationStatus.PENDING:
            raise WorkspaceError("Приглашение не найдено или уже недействительно.")

        if invitation.expires_at <= utc_now():
            invitation.status = WorkspaceInvitationStatus.EXPIRED
            await self.session.commit()
            raise WorkspaceError("Срок действия приглашения истек.")

        return invitation


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
