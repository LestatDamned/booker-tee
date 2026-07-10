from dataclasses import dataclass

from app.features.workspaces.models import Workspace, WorkspaceType
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
class WorkspacesPageVM:
    workspace_rows: list[WorkspaceRowVM]
    workspace_count_label: str
    workspace_types: list[WorkspaceType]
    create_form: WorkspaceCreateFormVM
    create_form_id: str
    create_label: str
    create_panel_open: bool
    create_submit_action: ActionVM
