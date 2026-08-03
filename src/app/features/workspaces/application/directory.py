from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from app.features.workspaces.domain.types import WorkspaceRole, WorkspaceType
from app.features.workspaces.models import WorkspaceMember
from app.features.workspaces.permissions import can_invite_members, can_manage_members
from app.features.workspaces.schemas import (
    WorkspaceBlockingReason,
    WorkspaceDirectoryCapabilitiesDto,
    WorkspaceDirectoryDto,
    WorkspaceDirectoryItemCapabilitiesDto,
    WorkspaceDirectoryItemDto,
    WorkspaceMembershipDto,
    WorkspaceOptionDto,
)


class WorkspaceDirectorySource(Protocol):
    async def list_visible_memberships_for_user(
        self,
        user_id: UUID,
        *,
        current_workspace_id: UUID,
    ) -> Sequence[WorkspaceMember]: ...


class WorkspaceDirectoryReader:
    def __init__(self, source: WorkspaceDirectorySource) -> None:
        self._source = source

    async def read_for_user(
        self,
        *,
        user_id: UUID,
        current_workspace_id: UUID,
    ) -> WorkspaceDirectoryDto:
        memberships = await self._source.list_visible_memberships_for_user(
            user_id,
            current_workspace_id=current_workspace_id,
        )
        return WorkspaceDirectoryDto(
            current_workspace_id=current_workspace_id,
            items=[
                workspace_directory_item(
                    membership,
                    current_workspace_id=current_workspace_id,
                )
                for membership in memberships
            ],
            capabilities=WorkspaceDirectoryCapabilitiesDto(can_create=True),
            workspace_type_options=[
                WorkspaceOptionDto(value=WorkspaceType.PERSONAL.value, label="Личное"),
                WorkspaceOptionDto(value=WorkspaceType.FAMILY.value, label="Семейное"),
                WorkspaceOptionDto(value=WorkspaceType.BUSINESS.value, label="Бизнес"),
                WorkspaceOptionDto(
                    value=WorkspaceType.PROPERTY_MANAGEMENT.value,
                    label="Управление недвижимостью",
                ),
                WorkspaceOptionDto(value=WorkspaceType.PROJECT.value, label="Проект"),
                WorkspaceOptionDto(value=WorkspaceType.OTHER.value, label="Другое"),
            ],
            currency_options=[
                WorkspaceOptionDto(value="RUB", label="RUB — российский рубль"),
                WorkspaceOptionDto(value="USD", label="USD — доллар США"),
                WorkspaceOptionDto(value="EUR", label="EUR — евро"),
            ],
        )


def workspace_directory_item(
    membership: WorkspaceMember,
    *,
    current_workspace_id: UUID,
) -> WorkspaceDirectoryItemDto:
    workspace = membership.workspace
    is_current = workspace.id == current_workspace_id
    is_active = workspace.is_active
    is_owner = membership.role == WorkspaceRole.OWNER
    can_manage = is_active and can_manage_members(membership)
    reasons: list[WorkspaceBlockingReason] = []
    if is_current:
        reasons.append(WorkspaceBlockingReason.CURRENT)
    if not is_active:
        reasons.append(WorkspaceBlockingReason.INACTIVE)
    return WorkspaceDirectoryItemDto(
        id=workspace.id,
        name=workspace.name,
        type=workspace.type,
        default_currency=workspace.default_currency,
        is_active=is_active,
        archived_at=workspace.archived_at,
        updated_at=workspace.updated_at,
        membership=WorkspaceMembershipDto(
            role=membership.role,
            status=membership.status,
            updated_at=membership.updated_at,
        ),
        is_current=is_current,
        capabilities=WorkspaceDirectoryItemCapabilitiesDto(
            can_select=is_active and not is_current,
            can_update=is_active and is_owner,
            can_manage_members=can_manage,
            can_invite=is_active and can_invite_members(membership),
            can_leave=is_active and not is_owner,
            can_deactivate=is_active and is_owner,
            can_restore=not is_active and is_owner,
        ),
        blocking_reason_codes=reasons,
    )
