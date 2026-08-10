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
