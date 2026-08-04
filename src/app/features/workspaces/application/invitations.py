from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid5

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.db.base import utc_now
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
    WorkspaceNotFoundError,
)
from app.features.workspaces.models import Workspace, WorkspaceInvitation, WorkspaceMember
from app.features.workspaces.permissions import (
    ADMIN_MANAGEABLE_MEMBER_ROLES,
    INVITABLE_ROLES,
    can_invite_members,
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
INVITATION_TTL = timedelta(hours=72)


@dataclass(frozen=True)
class CreatedWorkspaceInvitationResult:
    invitation: WorkspaceInvitationItemDto
    invitations: WorkspaceInvitationsDto
    token: str
    replayed: bool


class WorkspaceInvitationService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._workspaces = WorkspaceRepository(session)

    async def read(self, *, actor_user_id: UUID, workspace_id: UUID) -> WorkspaceInvitationsDto:
        actor = await self._workspaces.get_visible_membership_for_user(
            user_id=actor_user_id,
            workspace_id=workspace_id,
        )
        if actor is None:
            raise WorkspaceNotFoundError("Workspace не найден.")
        return await self._directory(actor=actor, workspace=actor.workspace)

    async def create(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        role: WorkspaceRole,
        idempotency_key: UUID,
    ) -> CreatedWorkspaceInvitationResult:
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
                self._validate_replay(existing, actor_user_id=actor_user_id, role=role)
                result = CreatedWorkspaceInvitationResult(
                    invitation=self._item(actor, existing),
                    invitations=await self._directory(actor=actor, workspace=workspace),
                    token=token,
                    replayed=True,
                )
                await self._session.commit()
                return result
            invitation = await self._workspaces.create_invitation(
                workspace_id=workspace_id,
                role=role,
                token_hash=hash_invitation_token(token),
                invited_by_user_id=actor_user_id,
                expires_at=utc_now() + INVITATION_TTL,
                invitation_id=invitation_id,
            )
            await self._workspaces.create_audit_event(
                workspace_id=workspace_id,
                event_type=WorkspaceAuditEventType.INVITATION_CREATED,
                actor_user_id=actor_user_id,
                entity_type="workspace_invitation",
                entity_id=invitation.id,
                details={"role": role.value},
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
                details={"role": invitation.role.value},
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
        role: WorkspaceRole,
    ) -> None:
        if (
            invitation.invited_by_user_id != actor_user_id
            or invitation.role != role
            or invitation.status != WorkspaceInvitationStatus.PENDING
            or invitation.expires_at <= utc_now()
        ):
            raise WorkspaceIdempotencyConflictError(
                "Idempotency-Key уже использован с другими данными приглашения."
            )

    @staticmethod
    def _blocked(
        message: str,
        reason: WorkspaceInvitationBlockingReason,
    ) -> None:
        raise WorkspaceInvitationTransitionError(message, reason_codes=[reason.value])
