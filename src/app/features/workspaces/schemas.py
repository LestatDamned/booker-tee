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


class WorkspaceSettingsCapabilitiesDto(ApplicationModel):
    can_update: bool
    can_manage_members: bool
    can_invite: bool
    can_deactivate: bool
    can_restore: bool


class WorkspaceLifecycleImpactDto(ApplicationModel):
    financial_history_preserved: bool
    current_session_count: int
    pending_invitation_count: int
    active_integration_connection_count: int
    active_chat_identity_binding_count: int


class WorkspaceSettingsItemDto(ApplicationModel):
    id: UUID
    name: str
    type: WorkspaceType
    default_currency: str
    is_active: bool
    archived_at: datetime | None
    updated_at: datetime
    membership: WorkspaceMembershipDto
    capabilities: WorkspaceSettingsCapabilitiesDto
    blocking_reason_codes: list[WorkspaceBlockingReason]


class WorkspaceSettingsDto(ApplicationModel):
    workspace: WorkspaceSettingsItemDto
    workspace_type_options: list[WorkspaceOptionDto]
    currency_options: list[WorkspaceOptionDto]
    lifecycle_impact: WorkspaceLifecycleImpactDto | None


class WorkspaceMemberBlockingReason(StrEnum):
    WORKSPACE_INACTIVE = "workspace_inactive"
    SELF = "member_self"
    OWNER = "member_owner"
    ACTIVE = "member_active"
    DISABLED = "member_disabled"
    FORBIDDEN = "member_management_forbidden"
    FALLBACK_REQUIRED = "workspace_fallback_required"


class WorkspaceMemberCapabilitiesDto(ApplicationModel):
    can_update_role: bool
    can_disable: bool
    can_reactivate: bool
    can_transfer_ownership: bool
    can_leave: bool
    assignable_roles: list[WorkspaceRole]


class WorkspaceMemberItemDto(ApplicationModel):
    id: UUID
    user_id: UUID
    name: str | None
    email: str
    role: WorkspaceRole
    status: WorkspaceMemberStatus
    joined_at: datetime | None
    updated_at: datetime
    is_self: bool
    capabilities: WorkspaceMemberCapabilitiesDto
    blocking_reason_codes: list[WorkspaceMemberBlockingReason]


class WorkspaceMembersCapabilitiesDto(ApplicationModel):
    can_manage_members: bool


class WorkspaceMembersDto(ApplicationModel):
    workspace_id: UUID
    items: list[WorkspaceMemberItemDto]
    capabilities: WorkspaceMembersCapabilitiesDto
