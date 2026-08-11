from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.features.debts.domain import DebtKind
from app.features.ledger.domain.types import OperationType
from app.features.workspaces.domain.types import (
    WorkspaceAuditEventType,
    WorkspaceInvitationStatus,
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.shared.schemas import ApplicationModel


class WorkspaceBlockingReason(StrEnum):
    CURRENT = "workspace_current"
    INACTIVE = "workspace_inactive"
    FALLBACK_REQUIRED = "workspace_fallback_required"


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
    can_view_member_directory: bool
    can_view_workspace_activity: bool
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


class WorkspaceLifecycleBlockingReason(StrEnum):
    FORBIDDEN = "workspace_lifecycle_forbidden"
    FALLBACK_REQUIRED = "workspace_fallback_required"
    ALREADY_ACTIVE = "workspace_already_active"
    ALREADY_INACTIVE = "workspace_already_inactive"


class WorkspaceLifecycleMutationImpactDto(ApplicationModel):
    moved_session_count: int
    revoked_invitation_count: int
    disabled_integration_connection_count: int
    disabled_chat_conversation_binding_count: int
    disabled_chat_identity_binding_count: int
    consumed_chat_conversation_state_count: int
    failed_integration_delivery_count: int


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


class WorkspaceInvitationBlockingReason(StrEnum):
    WORKSPACE_INACTIVE = "workspace_inactive"
    FORBIDDEN = "invitation_management_forbidden"
    ROLE_FORBIDDEN = "invitation_role_forbidden"
    PENDING_EXISTS = "pending_invitation_exists"
    ALREADY_MEMBER = "already_member"
    MEMBER_DISABLED = "member_disabled"
    MEMBER_LIMIT_REACHED = "member_limit_reached"
    PENDING_LIMIT_REACHED = "pending_invitation_limit_reached"
    EMAIL_MISMATCH = "invitation_email_mismatch"


class WorkspaceInvitationCapabilitiesDto(ApplicationModel):
    can_revoke: bool


class WorkspaceInvitationItemDto(ApplicationModel):
    id: UUID
    invitee_email: str
    role: WorkspaceRole
    status: WorkspaceInvitationStatus
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    capabilities: WorkspaceInvitationCapabilitiesDto
    blocking_reason_codes: list[WorkspaceInvitationBlockingReason]


class WorkspaceInvitationsCapabilitiesDto(ApplicationModel):
    can_create: bool
    assignable_roles: list[WorkspaceRole]


class WorkspaceInvitationsDto(ApplicationModel):
    workspace_id: UUID
    items: list[WorkspaceInvitationItemDto]
    capabilities: WorkspaceInvitationsCapabilitiesDto


class WorkspaceActivitySummaryCode(StrEnum):
    WORKSPACE_CREATED = "workspace_created"
    WORKSPACE_UPDATED = "workspace_updated"
    WORKSPACE_DEACTIVATED = "workspace_deactivated"
    WORKSPACE_RESTORED = "workspace_restored"
    INVITATION_CREATED = "invitation_created"
    INVITATION_ACCEPTED = "invitation_accepted"
    INVITATION_REVOKED = "invitation_revoked"
    MEMBER_ROLE_CHANGED = "member_role_changed"
    MEMBER_DISABLED = "member_disabled"
    MEMBER_REACTIVATED = "member_reactivated"
    MEMBER_LEFT = "member_left"
    OWNERSHIP_TRANSFERRED = "ownership_transferred"
    MANUAL_OPERATION_CREATED = "manual_operation_created"
    MANUAL_OPERATION_UPDATED = "manual_operation_updated"
    MANUAL_OPERATION_CANCELLED = "manual_operation_cancelled"
    MANUAL_OPERATION_RESTORED = "manual_operation_restored"
    MANUAL_OPERATION_DELETED = "manual_operation_deleted"
    IMPORT_REVIEW_ITEM_CONFIRMED = "import_review_item_confirmed"
    IMPORT_REVIEW_TRANSFER_CREATED = "import_review_transfer_created"
    IMPORT_REVIEW_OPERATION_LINKED = "import_review_operation_linked"
    IMPORT_REVIEW_POSTING_UNDONE = "import_review_posting_undone"
    IMPORT_REVIEW_OPERATION_UNLINKED = "import_review_operation_unlinked"
    IMPORTED_OPERATION_UPDATED = "imported_operation_updated"
    DEBT_CREATED = "debt_created"
    DEBT_PAYMENT_RECORDED = "debt_payment_recorded"
    DEBT_PAYMENT_UNDONE = "debt_payment_undone"
    DEBT_UPDATED = "debt_updated"
    DEBT_ARCHIVED = "debt_archived"
    DEBT_RESTORED = "debt_restored"
    DEBT_DELETED = "debt_deleted"
    DOCUMENT_UPLOADED = "document_uploaded"


class WorkspaceActivityScope(StrEnum):
    ALL = "all"
    FINANCE = "finance"
    TEAM = "team"


class WorkspaceActivityItemScope(StrEnum):
    FINANCE = "finance"
    TEAM = "team"


class WorkspaceActivityEntityType(StrEnum):
    WORKSPACE = "workspace"
    OPERATION = "operation"
    DEBT = "debt"
    UPLOADED_DOCUMENT = "uploaded_document"


class WorkspaceActivityActorDto(ApplicationModel):
    id: UUID
    display_name: str


class WorkspaceActivityEntityDto(ApplicationModel):
    type: WorkspaceActivityEntityType
    id: UUID
    display_label: str | None
    is_available: bool


class WorkspaceActivityDetailsDto(ApplicationModel):
    payload_version: int | None = None
    display_label: str | None = None
    operation_type: OperationType | None = None
    document_id: UUID | None = None
    item_id: UUID | None = None
    affected_item_count: int | None = None
    affected_document_count: int | None = None
    debt_kind: DebtKind | None = None
    payment_id: UUID | None = None
    display_filename: str | None = None
    role: WorkspaceRole | None = None
    invitee_email: str | None = None
    old_role: WorkspaceRole | None = None
    new_role: WorkspaceRole | None = None
    old_status: WorkspaceMemberStatus | None = None
    new_status: WorkspaceMemberStatus | None = None
    old_name: str | None = None
    new_name: str | None = None
    old_type: WorkspaceType | None = None
    new_type: WorkspaceType | None = None
    old_default_currency: str | None = None
    new_default_currency: str | None = None
    moved_session_count: int | None = None
    revoked_invitation_count: int | None = None


class WorkspaceActivityItemDto(ApplicationModel):
    id: UUID
    event_type: WorkspaceAuditEventType
    scope: WorkspaceActivityItemScope
    actor: WorkspaceActivityActorDto | None
    target: WorkspaceActivityActorDto | None
    entity: WorkspaceActivityEntityDto | None
    summary_code: WorkspaceActivitySummaryCode
    details: WorkspaceActivityDetailsDto
    created_at: datetime


class WorkspaceActivityCursorDto(ApplicationModel):
    before_created_at: datetime
    before_id: UUID
    scope: WorkspaceActivityScope


class WorkspaceActivityDto(ApplicationModel):
    workspace_id: UUID
    items: list[WorkspaceActivityItemDto]
    next_cursor: WorkspaceActivityCursorDto | None
