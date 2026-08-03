from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.features.workspaces.domain.types import (
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.shared.schemas import ApplicationModel


class WorkspaceBlockingReason(StrEnum):
    CURRENT = "workspace_current"
    INACTIVE = "workspace_inactive"


class WorkspaceMembershipDto(ApplicationModel):
    role: WorkspaceRole
    status: WorkspaceMemberStatus
    updated_at: datetime


class WorkspaceDirectoryItemCapabilitiesDto(ApplicationModel):
    can_select: bool
    can_update: bool
    can_manage_members: bool
    can_invite: bool
    can_leave: bool
    can_deactivate: bool
    can_restore: bool


class WorkspaceDirectoryItemDto(ApplicationModel):
    id: UUID
    name: str
    type: WorkspaceType
    default_currency: str
    is_active: bool
    archived_at: datetime | None
    updated_at: datetime
    membership: WorkspaceMembershipDto
    is_current: bool
    capabilities: WorkspaceDirectoryItemCapabilitiesDto
    blocking_reason_codes: list[WorkspaceBlockingReason]


class WorkspaceDirectoryCapabilitiesDto(ApplicationModel):
    can_create: bool


class WorkspaceOptionDto(ApplicationModel):
    value: str
    label: str


class WorkspaceDirectoryDto(ApplicationModel):
    current_workspace_id: UUID
    items: list[WorkspaceDirectoryItemDto]
    capabilities: WorkspaceDirectoryCapabilitiesDto
    workspace_type_options: list[WorkspaceOptionDto]
    currency_options: list[WorkspaceOptionDto]
