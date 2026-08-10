from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import NoReturn
from uuid import UUID, uuid5

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_session_token
from app.core.settings import Settings
from app.db.base import utc_now
from app.features.users.repository import UserRepository
from app.features.users.service import normalize_email
from app.features.workspaces.domain.types import (
    WorkspaceAuditEventType,
    WorkspaceInvitationStatus,
    WorkspaceMemberStatus,
    WorkspaceRole,
)
from app.features.workspaces.errors import (
    WorkspaceIdempotencyConflictError,
    WorkspaceInvitationConflictError,
    WorkspaceInvitationNotFoundError,
    WorkspaceInvitationTransitionError,
    WorkspaceMemberDirectoryForbiddenError,
    WorkspaceNotFoundError,
)
from app.features.workspaces.models import Workspace, WorkspaceInvitation, WorkspaceMember
from app.features.workspaces.permissions import (
    ADMIN_MANAGEABLE_MEMBER_ROLES,
    INVITABLE_ROLES,
    can_invite_members,
    can_view_member_directory,
)
from app.features.workspaces.repository import WorkspaceRepository
from app.features.workspaces.schemas import (
    WorkspaceInvitationBlockingReason,
    WorkspaceInvitationCapabilitiesDto,
    WorkspaceInvitationItemDto,
    WorkspaceInvitationsCapabilitiesDto,
    WorkspaceInvitationsDto,
)
from app.features.workspaces.tokens import (
    hash_invitation_token,
    invitation_token_for_id,
)

INVITATION_DIRECTORY_LIMIT = 100
MAX_WORKSPACE_MEMBERS = 100
MAX_PENDING_INVITATIONS = 100
INVITATION_TTL = timedelta(hours=72)
PUBLIC_INVITATION_UNAVAILABLE = "Приглашение не найдено или уже недействительно."


@dataclass(frozen=True)
class CreatedWorkspaceInvitationResult:
    invitation: WorkspaceInvitationItemDto
    invitations: WorkspaceInvitationsDto
    token: str
    replayed: bool


@dataclass(frozen=True)
class PublicWorkspaceInvitation:
    workspace_name: str
    role: WorkspaceRole
    expires_at: datetime


@dataclass(frozen=True)
class AcceptedWorkspaceInvitation:
    workspace_id: UUID


class WorkspaceInvitationService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._users = UserRepository(session)
        self._workspaces = WorkspaceRepository(session)

    async def preview(self, *, invitation_token: str) -> PublicWorkspaceInvitation:
        invitation = self._require_public_invitation(
            await self._workspaces.get_invitation_by_token_hash(
                hash_invitation_token(invitation_token)
            )
        )
        if not invitation.workspace.is_active:
            self._unavailable()
        return PublicWorkspaceInvitation(
            workspace_name=invitation.workspace.name,
            role=invitation.role,
            expires_at=invitation.expires_at,
        )

    async def accept(
        self,
        *,
        actor_user_id: UUID,
        invitation_token: str,
        session_token: str,
    ) -> AcceptedWorkspaceInvitation:
        try:
            token_hash = hash_invitation_token(invitation_token)
            hint = self._require_public_invitation(
                await self._workspaces.get_invitation_by_token_hash(token_hash)
            )
            workspace = await self._workspaces.lock_for_update(hint.workspace_id)
            if workspace is None or not workspace.is_active:
                self._unavailable()
            invitation = self._require_public_invitation(
                await self._workspaces.get_invitation_by_token_hash_for_update(token_hash)
            )
            user_session = await self._users.get_active_session_by_token_hash_for_update(
                hash_session_token(session_token),
                user_id=actor_user_id,
            )
            if user_session is None:
                self._unavailable()
            actor = await self._users.get_for_update(actor_user_id)
            if (
                actor is None
                or not actor.is_active
                or actor.deactivated_at is not None
                or actor.email_verified_at is None
            ):
                self._unavailable()
            if normalize_email(actor.email) != invitation.invitee_email:
                self._blocked(
                    "Приглашение предназначено для другого аккаунта.",
                    WorkspaceInvitationBlockingReason.EMAIL_MISMATCH,
                )
            membership = await self._workspaces.get_any_membership_for_update(
                user_id=actor_user_id,
                workspace_id=invitation.workspace_id,
            )
            now = utc_now()
            if membership is None:
                if (
                    await self._workspaces.count_supported_members(invitation.workspace_id)
                    >= MAX_WORKSPACE_MEMBERS
                ):
                    self._blocked(
                        "В workspace достигнут лимит участников.",
                        WorkspaceInvitationBlockingReason.MEMBER_LIMIT_REACHED,
                    )
                await self._workspaces.create_member(
                    workspace_id=invitation.workspace_id,
                    user_id=actor_user_id,
                    role=invitation.role,
                    invited_by_user_id=invitation.invited_by_user_id,
                )
            elif membership.status == WorkspaceMemberStatus.REMOVED:
                if (
                    await self._workspaces.count_supported_members(invitation.workspace_id)
                    >= MAX_WORKSPACE_MEMBERS
                ):
                    self._blocked(
                        "В workspace достигнут лимит участников.",
                        WorkspaceInvitationBlockingReason.MEMBER_LIMIT_REACHED,
                    )
                membership.role = invitation.role
                membership.status = WorkspaceMemberStatus.ACTIVE
                membership.invited_by_user_id = invitation.invited_by_user_id
                membership.joined_at = now
            elif membership.status == WorkspaceMemberStatus.DISABLED:
                self._blocked(
                    "Доступ пользователя отключён. Восстановите его в списке участников.",
                    WorkspaceInvitationBlockingReason.MEMBER_DISABLED,
                )
            else:
                self._blocked(
                    "Пользователь уже состоит в workspace.",
                    WorkspaceInvitationBlockingReason.ALREADY_MEMBER,
                )
            invitation.status = WorkspaceInvitationStatus.ACCEPTED
            invitation.accepted_by_user_id = actor_user_id
            invitation.accepted_at = now
            user_session.current_workspace_id = invitation.workspace_id
            user_session.last_seen_at = now
            await self._workspaces.create_audit_event(
                workspace_id=invitation.workspace_id,
                event_type=WorkspaceAuditEventType.INVITATION_ACCEPTED,
                actor_user_id=actor_user_id,
                entity_type="workspace_invitation",
                entity_id=invitation.id,
                target_user_id=actor_user_id,
                details={
                    "role": invitation.role.value,
                    "invitee_email": invitation.invitee_email or actor.email,
                },
            )
            await self._session.commit()
            return AcceptedWorkspaceInvitation(workspace_id=invitation.workspace_id)
        except Exception:
            await self._session.rollback()
            raise

    async def read(self, *, actor_user_id: UUID, workspace_id: UUID) -> WorkspaceInvitationsDto:
        actor = await self._workspaces.get_visible_membership_for_user(
            user_id=actor_user_id,
            workspace_id=workspace_id,
        )
        if actor is None:
            raise WorkspaceNotFoundError("Workspace не найден.")
        if not can_view_member_directory(actor):
            raise WorkspaceMemberDirectoryForbiddenError(
                "Просмотр приглашений workspace недоступен."
            )
        return await self._directory(actor=actor, workspace=actor.workspace)

    async def create(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        email: str,
        role: WorkspaceRole,
        idempotency_key: UUID,
    ) -> CreatedWorkspaceInvitationResult:
        invitee_email = normalize_email(email)
        invitation_id = uuid5(
            workspace_id,
            f"workspace-invitation:{actor_user_id}:{idempotency_key}",
        )
        token = invitation_token_for_id(
            invitation_id=invitation_id,
            secret=self._settings.auth_secret_key,
        )
        try:
            workspace, actor = await self._locked_actor(
                actor_user_id=actor_user_id,
                workspace_id=workspace_id,
            )
            self._require_role(actor, role)
            existing = await self._workspaces.get_invitation(
                workspace_id=workspace_id,
                invitation_id=invitation_id,
            )
            if existing is not None:
                self._validate_replay(
                    existing,
                    actor_user_id=actor_user_id,
                    invitee_email=invitee_email,
                    role=role,
                )
                result = CreatedWorkspaceInvitationResult(
                    invitation=self._item(actor, existing),
                    invitations=await self._directory(actor=actor, workspace=workspace),
                    token=token,
                    replayed=True,
                )
                await self._session.commit()
                return result
            now = utc_now()
            await self._workspaces.expire_pending_invitations_for_email(
                workspace_id=workspace_id,
                invitee_email=invitee_email,
                expired_at=now,
            )
            if (
                await self._workspaces.get_pending_invitation_for_email(
                    workspace_id=workspace_id,
                    invitee_email=invitee_email,
                )
                is not None
            ):
                self._blocked(
                    "Для этого email уже есть действующее приглашение.",
                    WorkspaceInvitationBlockingReason.PENDING_EXISTS,
                )
            member = await self._workspaces.get_member_by_email(
                workspace_id=workspace_id,
                email=invitee_email,
            )
            if member is not None and member.status == WorkspaceMemberStatus.ACTIVE:
                self._blocked(
                    "Пользователь уже состоит в workspace.",
                    WorkspaceInvitationBlockingReason.ALREADY_MEMBER,
                )
            if member is not None and member.status == WorkspaceMemberStatus.DISABLED:
                self._blocked(
                    "Доступ пользователя отключён. Восстановите его в списке участников.",
                    WorkspaceInvitationBlockingReason.MEMBER_DISABLED,
                )
            if (
                await self._workspaces.count_supported_members(workspace_id)
                >= MAX_WORKSPACE_MEMBERS
            ):
                self._blocked(
                    "В workspace достигнут лимит участников.",
                    WorkspaceInvitationBlockingReason.MEMBER_LIMIT_REACHED,
                )
            if (
                await self._workspaces.count_pending_invitations(workspace_id)
                >= MAX_PENDING_INVITATIONS
            ):
                self._blocked(
                    "В workspace достигнут лимит ожидающих приглашений.",
                    WorkspaceInvitationBlockingReason.PENDING_LIMIT_REACHED,
                )
            invitation = await self._workspaces.create_invitation(
                workspace_id=workspace_id,
                invitee_email=invitee_email,
                role=role,
                token_hash=hash_invitation_token(token),
                invited_by_user_id=actor_user_id,
                expires_at=now + INVITATION_TTL,
                invitation_id=invitation_id,
            )
            await self._workspaces.create_audit_event(
                workspace_id=workspace_id,
                event_type=WorkspaceAuditEventType.INVITATION_CREATED,
                actor_user_id=actor_user_id,
                entity_type="workspace_invitation",
                entity_id=invitation.id,
                details={"role": role.value, "invitee_email": invitee_email},
            )
            await self._session.commit()
            return CreatedWorkspaceInvitationResult(
                invitation=self._item(actor, invitation),
                invitations=await self._directory(actor=actor, workspace=workspace),
                token=token,
                replayed=False,
            )
        except Exception:
            await self._session.rollback()
            raise

    async def revoke(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        invitation_id: UUID,
        expected_updated_at: datetime,
    ) -> WorkspaceInvitationsDto:
        try:
            workspace, actor = await self._locked_actor(
                actor_user_id=actor_user_id,
                workspace_id=workspace_id,
            )
            invitation = await self._workspaces.get_invitation_for_update(
                workspace_id=workspace_id,
                invitation_id=invitation_id,
            )
            if invitation is None:
                raise WorkspaceInvitationNotFoundError("Приглашение не найдено.")
            if invitation.updated_at != expected_updated_at:
                raise WorkspaceInvitationConflictError(
                    "Приглашение уже изменилось. Загрузите актуальные данные."
                )
            if invitation.status != WorkspaceInvitationStatus.PENDING:
                raise WorkspaceInvitationConflictError("Приглашение уже недействительно.")
            if invitation.expires_at <= utc_now():
                raise WorkspaceInvitationConflictError("Срок приглашения уже истёк.")
            if invitation.role not in self._assignable_roles(actor):
                self._blocked(
                    "Недостаточно прав для отзыва этого приглашения.",
                    WorkspaceInvitationBlockingReason.ROLE_FORBIDDEN,
                )
            invitation.status = WorkspaceInvitationStatus.REVOKED
            invitation.revoked_at = utc_now()
            await self._session.flush()
            await self._workspaces.create_audit_event(
                workspace_id=workspace_id,
                event_type=WorkspaceAuditEventType.INVITATION_REVOKED,
                actor_user_id=actor_user_id,
                entity_type="workspace_invitation",
                entity_id=invitation.id,
                details={
                    "role": invitation.role.value,
                    "invitee_email": invitation.invitee_email or "",
                },
            )
            await self._session.commit()
            return await self._directory(actor=actor, workspace=workspace)
        except Exception:
            await self._session.rollback()
            raise

    async def _locked_actor(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
    ) -> tuple[Workspace, WorkspaceMember]:
        workspace = await self._workspaces.lock_for_update(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("Workspace не найден.")
        actor = await self._workspaces.get_membership_for_update(
            user_id=actor_user_id,
            workspace_id=workspace_id,
        )
        if actor is None or actor.status != WorkspaceMemberStatus.ACTIVE:
            raise WorkspaceNotFoundError("Workspace не найден.")
        if not workspace.is_active:
            self._blocked(
                "Неактивное пространство нельзя изменять.",
                WorkspaceInvitationBlockingReason.WORKSPACE_INACTIVE,
            )
        if not can_invite_members(actor):
            self._blocked(
                "Недостаточно прав для управления приглашениями.",
                WorkspaceInvitationBlockingReason.FORBIDDEN,
            )
        return workspace, actor

    async def _directory(
        self,
        *,
        actor: WorkspaceMember,
        workspace: Workspace,
    ) -> WorkspaceInvitationsDto:
        roles = self._assignable_roles(actor) if workspace.is_active else []
        invitations = (
            await self._workspaces.list_pending_invitations(
                workspace.id,
                limit=INVITATION_DIRECTORY_LIMIT,
            )
            if roles
            else []
        )
        return WorkspaceInvitationsDto(
            workspace_id=workspace.id,
            items=[self._item(actor, invitation) for invitation in invitations],
            capabilities=WorkspaceInvitationsCapabilitiesDto(
                can_create=bool(roles),
                assignable_roles=roles,
            ),
        )

    @staticmethod
    def _assignable_roles(actor: WorkspaceMember) -> list[WorkspaceRole]:
        allowed = (
            set(INVITABLE_ROLES)
            if actor.role == WorkspaceRole.OWNER
            else ADMIN_MANAGEABLE_MEMBER_ROLES
            if actor.role == WorkspaceRole.ADMIN
            else set()
        )
        return [role for role in INVITABLE_ROLES if role in allowed]

    @classmethod
    def _item(
        cls,
        actor: WorkspaceMember,
        invitation: WorkspaceInvitation,
    ) -> WorkspaceInvitationItemDto:
        can_revoke = invitation.role in cls._assignable_roles(actor)
        return WorkspaceInvitationItemDto(
            id=invitation.id,
            invitee_email=cls._required_invitee_email(invitation),
            role=invitation.role,
            status=invitation.status,
            expires_at=invitation.expires_at,
            created_at=invitation.created_at,
            updated_at=invitation.updated_at,
            capabilities=WorkspaceInvitationCapabilitiesDto(can_revoke=can_revoke),
            blocking_reason_codes=(
                [] if can_revoke else [WorkspaceInvitationBlockingReason.ROLE_FORBIDDEN]
            ),
        )

    @classmethod
    def _require_role(cls, actor: WorkspaceMember, role: WorkspaceRole) -> None:
        if role not in cls._assignable_roles(actor):
            cls._blocked(
                "Эту роль нельзя выдать через приглашение.",
                WorkspaceInvitationBlockingReason.ROLE_FORBIDDEN,
            )

    @staticmethod
    def _validate_replay(
        invitation: WorkspaceInvitation,
        *,
        actor_user_id: UUID,
        invitee_email: str,
        role: WorkspaceRole,
    ) -> None:
        if (
            invitation.invited_by_user_id != actor_user_id
            or invitation.invitee_email != invitee_email
            or invitation.role != role
            or invitation.status != WorkspaceInvitationStatus.PENDING
            or invitation.expires_at <= utc_now()
        ):
            raise WorkspaceIdempotencyConflictError(
                "Idempotency-Key уже использован с другими данными приглашения."
            )

    @staticmethod
    def _required_invitee_email(invitation: WorkspaceInvitation) -> str:
        if invitation.invitee_email is None:
            raise WorkspaceInvitationConflictError("У приглашения отсутствует email.")
        return invitation.invitee_email

    @classmethod
    def _require_public_invitation(
        cls,
        invitation: WorkspaceInvitation | None,
    ) -> WorkspaceInvitation:
        if (
            invitation is None
            or invitation.invitee_email is None
            or invitation.status != WorkspaceInvitationStatus.PENDING
            or invitation.expires_at <= utc_now()
            or invitation.role not in INVITABLE_ROLES
        ):
            cls._unavailable()
        return invitation

    @staticmethod
    def _unavailable() -> NoReturn:
        raise WorkspaceInvitationNotFoundError(PUBLIC_INVITATION_UNAVAILABLE)

    @staticmethod
    def _blocked(
        message: str,
        reason: WorkspaceInvitationBlockingReason,
    ) -> None:
        raise WorkspaceInvitationTransitionError(message, reason_codes=[reason.value])
