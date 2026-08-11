from enum import StrEnum


class WorkspaceType(StrEnum):
    PERSONAL = "personal"
    FAMILY = "family"
    BUSINESS = "business"
    PROPERTY_MANAGEMENT = "property_management"
    PROJECT = "project"
    OTHER = "other"


class WorkspaceRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
    UPLOADER = "uploader"
    ANALYST = "analyst"


class WorkspaceMemberStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DISABLED = "disabled"
    REMOVED = "removed"


class WorkspaceInvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class WorkspaceAuditEventType(StrEnum):
    WORKSPACE_CREATED = "workspace_created"
    WORKSPACE_UPDATED = "workspace_updated"
    WORKSPACE_DEACTIVATED = "workspace_deactivated"
    WORKSPACE_RESTORED = "workspace_restored"
    OWNERSHIP_TRANSFERRED = "ownership_transferred"
    INVITATION_CREATED = "invitation_created"
    INVITATION_ACCEPTED = "invitation_accepted"
    INVITATION_REVOKED = "invitation_revoked"
    MEMBER_ROLE_CHANGED = "member_role_changed"
    MEMBER_DISABLED = "member_disabled"
    MEMBER_REACTIVATED = "member_reactivated"
    MEMBER_LEFT = "member_left"
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
