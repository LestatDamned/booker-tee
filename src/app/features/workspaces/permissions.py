from dataclasses import dataclass

from app.features.workspaces.domain.types import WorkspaceMemberStatus, WorkspaceRole
from app.features.workspaces.models import WorkspaceMember

READ_ROLES = {
    WorkspaceRole.OWNER,
    WorkspaceRole.ADMIN,
    WorkspaceRole.EDITOR,
    WorkspaceRole.VIEWER,
    WorkspaceRole.UPLOADER,
    WorkspaceRole.ANALYST,
}
FINANCIAL_WRITERS = {
    WorkspaceRole.OWNER,
    WorkspaceRole.ADMIN,
    WorkspaceRole.EDITOR,
}
IMPORT_MANAGERS = {
    WorkspaceRole.OWNER,
    WorkspaceRole.ADMIN,
    WorkspaceRole.EDITOR,
    WorkspaceRole.UPLOADER,
}
RAW_IMPORT_READERS = {
    WorkspaceRole.OWNER,
    WorkspaceRole.ADMIN,
    WorkspaceRole.EDITOR,
    WorkspaceRole.UPLOADER,
    WorkspaceRole.VIEWER,
}
INVITABLE_ROLES = (
    WorkspaceRole.ADMIN,
    WorkspaceRole.EDITOR,
    WorkspaceRole.VIEWER,
    WorkspaceRole.UPLOADER,
    WorkspaceRole.ANALYST,
)
MANAGEABLE_MEMBER_ROLES = INVITABLE_ROLES
ADMIN_MANAGEABLE_MEMBER_ROLES = {
    WorkspaceRole.EDITOR,
    WorkspaceRole.VIEWER,
    WorkspaceRole.UPLOADER,
    WorkspaceRole.ANALYST,
}

INVITATION_MANAGERS = {
    WorkspaceRole.OWNER,
    WorkspaceRole.ADMIN,
}
MEMBER_DIRECTORY_READERS = INVITATION_MANAGERS
WORKSPACE_MANAGERS = {
    WorkspaceRole.OWNER,
}


@dataclass(frozen=True)
class WorkspacePermissionFlags:
    role: WorkspaceRole
    can_read_workspace: bool
    can_write_financial_data: bool
    can_manage_imports: bool
    can_view_raw_import_data: bool
    can_view_member_directory: bool
    can_manage_members: bool
    can_view_workspace_activity: bool
    can_manage_workspace: bool


def permission_flags_for(membership: WorkspaceMember) -> WorkspacePermissionFlags:
    return WorkspacePermissionFlags(
        role=membership.role,
        can_read_workspace=can_read_workspace(membership),
        can_write_financial_data=can_write_financial_data(membership),
        can_manage_imports=can_manage_imports(membership),
        can_view_raw_import_data=can_view_raw_import_data(membership),
        can_view_member_directory=can_view_member_directory(membership),
        can_manage_members=can_manage_members(membership),
        can_view_workspace_activity=can_view_workspace_activity(membership),
        can_manage_workspace=can_manage_workspace(membership),
    )


def has_active_role(membership: WorkspaceMember, roles: set[WorkspaceRole]) -> bool:
    return membership.status == WorkspaceMemberStatus.ACTIVE and membership.role in roles


def can_read_workspace(membership: WorkspaceMember) -> bool:
    return has_active_role(membership, READ_ROLES)


def can_write_financial_data(membership: WorkspaceMember) -> bool:
    return has_active_role(membership, FINANCIAL_WRITERS)


def can_manage_imports(membership: WorkspaceMember) -> bool:
    return has_active_role(membership, IMPORT_MANAGERS)


def can_view_raw_import_data(membership: WorkspaceMember) -> bool:
    return has_active_role(membership, RAW_IMPORT_READERS)


def can_view_member_directory(membership: WorkspaceMember) -> bool:
    return has_active_role(membership, MEMBER_DIRECTORY_READERS)


def can_manage_members(membership: WorkspaceMember) -> bool:
    return has_active_role(membership, INVITATION_MANAGERS)


def can_view_workspace_activity(membership: WorkspaceMember) -> bool:
    return can_view_member_directory(membership)


def can_manage_workspace(membership: WorkspaceMember) -> bool:
    return has_active_role(membership, WORKSPACE_MANAGERS)


def can_invite_members(membership: WorkspaceMember) -> bool:
    return can_manage_members(membership)


def can_assign_member_role(
    actor: WorkspaceMember,
    target: WorkspaceMember,
    role: WorkspaceRole,
) -> bool:
    if role not in MANAGEABLE_MEMBER_ROLES or target.role == WorkspaceRole.OWNER:
        return False
    if not can_manage_members(actor):
        return False
    if actor.role == WorkspaceRole.ADMIN:
        return (
            target.role in ADMIN_MANAGEABLE_MEMBER_ROLES and role in ADMIN_MANAGEABLE_MEMBER_ROLES
        )
    return actor.role == WorkspaceRole.OWNER


def can_disable_member(actor: WorkspaceMember, target: WorkspaceMember) -> bool:
    if not can_manage_members(actor):
        return False
    if actor.role == WorkspaceRole.ADMIN:
        return target.role in ADMIN_MANAGEABLE_MEMBER_ROLES
    return actor.role == WorkspaceRole.OWNER


def can_reactivate_member(actor: WorkspaceMember, target: WorkspaceMember) -> bool:
    if not can_manage_members(actor):
        return False
    if actor.role == WorkspaceRole.ADMIN:
        return target.role in ADMIN_MANAGEABLE_MEMBER_ROLES
    return actor.role == WorkspaceRole.OWNER


def ensure_invitable_role(role: WorkspaceRole) -> WorkspaceRole:
    if role not in INVITABLE_ROLES:
        msg = "Эту роль нельзя выдать через приглашение."
        raise ValueError(msg)
    return role
