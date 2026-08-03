from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.chat_integrations.repository import ChatIntegrationRepository
from app.features.users.repository import UserRepository
from app.features.workspaces.application.directory import (
    workspace_currency_options,
    workspace_type_options,
)
from app.features.workspaces.commands import UpdateWorkspaceSettingsCommand
from app.features.workspaces.domain.types import WorkspaceRole
from app.features.workspaces.errors import (
    WorkspaceNotFoundError,
    WorkspaceSettingsForbiddenError,
    WorkspaceUpdateConflictError,
)
from app.features.workspaces.models import (
    WorkspaceAuditEventType,
    WorkspaceMember,
)
from app.features.workspaces.permissions import can_invite_members, can_manage_members
from app.features.workspaces.repository import WorkspaceRepository
from app.features.workspaces.schemas import (
    WorkspaceBlockingReason,
    WorkspaceLifecycleImpactDto,
    WorkspaceMembershipDto,
    WorkspaceSettingsCapabilitiesDto,
    WorkspaceSettingsDto,
    WorkspaceSettingsItemDto,
)
from app.features.workspaces.service import clean_workspace_name, normalize_currency


class WorkspaceSettingsService:
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
    ) -> WorkspaceSettingsDto:
        membership = await self._workspaces.get_visible_membership_for_user(
            user_id=actor_user_id,
            workspace_id=workspace_id,
        )
        if membership is None:
            raise WorkspaceNotFoundError("Workspace не найден.")
        return await self._settings(membership)

    async def update(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        command: UpdateWorkspaceSettingsCommand,
    ) -> WorkspaceSettingsDto:
        try:
            membership = await self._workspaces.get_visible_membership_for_user_for_update(
                user_id=actor_user_id,
                workspace_id=workspace_id,
            )
            if membership is None:
                raise WorkspaceNotFoundError("Workspace не найден.")
            workspace = membership.workspace
            if (
                membership.role != WorkspaceRole.OWNER
                or workspace.owner_id != actor_user_id
                or not workspace.is_active
            ):
                raise WorkspaceSettingsForbiddenError("Изменение настроек workspace недоступно.")
            if workspace.updated_at != command.expected_updated_at:
                raise WorkspaceUpdateConflictError(
                    "Workspace уже изменён. Загрузите актуальные данные."
                )

            old_name = workspace.name
            old_type = workspace.type
            old_currency = workspace.default_currency
            workspace.name = clean_workspace_name(command.name)
            workspace.type = command.workspace_type
            workspace.default_currency = normalize_currency(command.default_currency)
            await self._session.flush()
            await self._workspaces.create_audit_event(
                workspace_id=workspace.id,
                event_type=WorkspaceAuditEventType.WORKSPACE_UPDATED,
                actor_user_id=actor_user_id,
                entity_type="workspace",
                entity_id=workspace.id,
                details={
                    "old_name": old_name,
                    "new_name": workspace.name,
                    "old_type": old_type.value,
                    "new_type": workspace.type.value,
                    "old_default_currency": old_currency,
                    "new_default_currency": workspace.default_currency,
                },
            )
            await self._session.commit()
            return await self._settings(membership)
        except Exception:
            await self._session.rollback()
            raise

    async def _settings(self, membership: WorkspaceMember) -> WorkspaceSettingsDto:
        workspace = membership.workspace
        is_owner = membership.role == WorkspaceRole.OWNER
        can_update = workspace.is_active and is_owner
        lifecycle_impact = None
        if is_owner:
            lifecycle_impact = WorkspaceLifecycleImpactDto(
                financial_history_preserved=True,
                current_session_count=await self._users.count_active_sessions_for_workspace(
                    workspace.id
                ),
                pending_invitation_count=await self._workspaces.count_pending_invitations(
                    workspace.id
                ),
                active_integration_connection_count=(
                    await self._chat.count_active_connections_for_workspace(workspace.id)
                ),
                active_chat_identity_binding_count=(
                    await self._chat.count_active_identity_bindings_for_workspace(workspace.id)
                ),
            )
        reasons = [WorkspaceBlockingReason.INACTIVE] if not workspace.is_active else []
        return WorkspaceSettingsDto(
            workspace=WorkspaceSettingsItemDto(
                id=workspace.id,
                name=workspace.name,
                type=workspace.type,
                default_currency=workspace.default_currency,
                is_active=workspace.is_active,
                archived_at=workspace.archived_at,
                updated_at=workspace.updated_at,
                membership=WorkspaceMembershipDto(
                    role=membership.role,
                    status=membership.status,
                    updated_at=membership.updated_at,
                ),
                capabilities=WorkspaceSettingsCapabilitiesDto(
                    can_update=can_update,
                    can_manage_members=workspace.is_active and can_manage_members(membership),
                    can_invite=workspace.is_active and can_invite_members(membership),
                    can_deactivate=False,
                    can_restore=False,
                ),
                blocking_reason_codes=reasons,
            ),
            workspace_type_options=workspace_type_options(),
            currency_options=workspace_currency_options(),
            lifecycle_impact=lifecycle_impact,
        )
