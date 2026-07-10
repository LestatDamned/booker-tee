from uuid import UUID

from app.features.workspaces.models import Workspace, WorkspaceType
from app.features.workspaces.presentation.models import (
    WorkspaceCreateFormVM,
    WorkspaceRowVM,
    WorkspacesPageVM,
)
from app.shared.ui.actions import ActionVM
from app.templating import ru_label


class WorkspacesPagePresenter:
    @staticmethod
    def build_index(
        workspaces: list[Workspace],
        *,
        current_workspace_id: UUID,
        current_default_currency: str,
        can_manage_workspace: bool,
        select_return_path: str,
    ) -> WorkspacesPageVM:
        create_form_id = "workspace-create-form"
        return WorkspacesPageVM(
            workspace_rows=[
                workspace_row_vm(
                    workspace,
                    current_workspace_id=current_workspace_id,
                    can_manage_workspace=can_manage_workspace,
                    select_return_path=select_return_path,
                )
                for workspace in workspaces
            ],
            workspace_count_label=f"{len(workspaces)} доступно",
            workspace_types=list(WorkspaceType),
            create_form=WorkspaceCreateFormVM(
                name="",
                workspace_type=WorkspaceType.PERSONAL,
                default_currency=current_default_currency,
            ),
            create_form_id=create_form_id,
            create_label="создать пространство",
            create_panel_open=not workspaces,
            create_submit_action=ActionVM(
                id="create-workspace",
                label="создать пространство",
                icon="plus",
                placement="primary",
                action_type="submit",
                form_id=create_form_id,
            ),
        )


def workspace_row_vm(
    workspace: Workspace,
    *,
    current_workspace_id: UUID,
    can_manage_workspace: bool,
    select_return_path: str,
) -> WorkspaceRowVM:
    is_current = workspace.id == current_workspace_id
    form_id = f"workspace-form-{workspace.id}"
    edit_summary_id = f"workspace-edit-toggle-{workspace.id}"
    return WorkspaceRowVM(
        workspace=workspace,
        anchor_id=f"workspace-{workspace.id}",
        form_id=form_id,
        edit_summary_id=edit_summary_id,
        title=workspace.name,
        type_label=ru_label(workspace.type),
        default_currency_label=workspace.default_currency,
        status_label="текущее" if is_current else "доступно",
        status_tone="active" if is_current else "muted",
        is_current=is_current,
        edit_panel_open=False,
        select_action=None
        if is_current
        else ActionVM(
            id="select-workspace",
            label="выбрать",
            icon="check",
            placement="primary",
            action_type="post",
            url=f"/workspaces/{workspace.id}/select",
            hidden_fields={"next": select_return_path},
        ),
        edit_toggle_action=ActionVM(
            id="edit-workspace",
            label="изменить пространство",
            icon="settings",
            placement="primary" if is_current else "secondary",
            action_type="panel_toggle",
            panel_id=edit_summary_id,
        )
        if can_manage_workspace
        else None,
        save_action=ActionVM(
            id="save-workspace",
            label="сохранить",
            icon="save",
            placement="primary",
            action_type="submit",
            form_id=form_id,
        )
        if can_manage_workspace
        else None,
    )
