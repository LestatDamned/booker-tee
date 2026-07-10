from dataclasses import dataclass

from app.features.workspaces.models import (
    Workspace,
    WorkspaceAuditEvent,
    WorkspaceInvitation,
    WorkspaceMember,
    WorkspaceRole,
    WorkspaceType,
)
from app.shared.ui.actions import ActionVM


@dataclass(frozen=True)
class WorkspaceCreateFormVM:
    name: str
    workspace_type: WorkspaceType
    default_currency: str


@dataclass(frozen=True)
class WorkspaceRowVM:
    workspace: Workspace
    anchor_id: str
    form_id: str
    edit_summary_id: str
    title: str
    type_label: str
    default_currency_label: str
    status_label: str
    status_tone: str
    is_current: bool
    edit_panel_open: bool
    select_action: ActionVM | None
    edit_toggle_action: ActionVM | None
    save_action: ActionVM | None


@dataclass(frozen=True)
class WorkspaceMemberRowVM:
    member: WorkspaceMember
    anchor_id: str
    form_id: str
    edit_summary_id: str
    title: str
    email_label: str
    role_label: str
    status_label: str
    status_tone: str
    role_options: list[WorkspaceRole]
    edit_panel_open: bool
    edit_toggle_action: ActionVM | None
    save_role_action: ActionVM | None
    lifecycle_action: ActionVM | None


@dataclass(frozen=True)
class WorkspaceInvitationRowVM:
    invitation: WorkspaceInvitation
    anchor_id: str
    title: str
    role_label: str
    status_label: str
    status_tone: str
    expires_label: str
    revoke_action: ActionVM


@dataclass(frozen=True)
class WorkspaceAuditEventRowVM:
    event: WorkspaceAuditEvent
    anchor_id: str
    title: str
    date_label: str
    meta_labels: list[str]
    detail_labels: list[str]


@dataclass(frozen=True)
class WorkspacesPageVM:
    workspace_rows: list[WorkspaceRowVM]
    current_workspace_row: WorkspaceRowVM | None
    other_workspace_rows: list[WorkspaceRowVM]
    other_workspace_count_label: str
    workspace_count_label: str
    member_rows: list[WorkspaceMemberRowVM]
    member_count_label: str
    invitation_rows: list[WorkspaceInvitationRowVM]
    invitation_count_label: str
    audit_event_rows: list[WorkspaceAuditEventRowVM]
    workspace_types: list[WorkspaceType]
    create_form: WorkspaceCreateFormVM
    create_form_id: str
    create_label: str
    create_panel_open: bool
    create_submit_action: ActionVM
    invitation_create_form_id: str
    invitation_create_label: str
    invitation_create_submit_action: ActionVM
