from uuid import UUID

from app.features.workspaces.models import (
    Workspace,
    WorkspaceAuditEvent,
    WorkspaceInvitation,
    WorkspaceMember,
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.permissions import (
    can_assign_member_role,
    can_disable_member,
    can_reactivate_member,
)
from app.features.workspaces.presentation.models import (
    WorkspaceAuditEventRowVM,
    WorkspaceCreateFormVM,
    WorkspaceInvitationRowVM,
    WorkspaceMemberRowVM,
    WorkspaceRowVM,
    WorkspacesPageVM,
)
from app.shared.ui.actions import ActionVM
from app.templating import date_ru, ru_label, short_id


class WorkspacesPagePresenter:
    @staticmethod
    def build_index(
        workspaces: list[Workspace],
        *,
        members: list[WorkspaceMember],
        pending_invitations: list[WorkspaceInvitation],
        audit_events: list[WorkspaceAuditEvent],
        current_workspace_id: UUID,
        current_default_currency: str,
        current_user_id: UUID,
        actor_membership: WorkspaceMember,
        can_manage_workspace: bool,
        select_return_path: str,
        member_roles: tuple[WorkspaceRole, ...],
    ) -> WorkspacesPageVM:
        create_form_id = "workspace-create-form"
        invitation_create_form_id = "workspace-invitation-create-form"
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
            member_rows=[
                member_row_vm(
                    member,
                    current_workspace_id=current_workspace_id,
                    current_user_id=current_user_id,
                    actor_membership=actor_membership,
                    member_roles=member_roles,
                )
                for member in members
            ],
            member_count_label=member_count_label(len(members)),
            invitation_rows=[
                invitation_row_vm(
                    invitation,
                    current_workspace_id=current_workspace_id,
                )
                for invitation in pending_invitations
            ],
            invitation_count_label=invitation_count_label(len(pending_invitations)),
            audit_event_rows=[audit_event_row_vm(event) for event in audit_events],
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
            invitation_create_form_id=invitation_create_form_id,
            invitation_create_submit_action=ActionVM(
                id="create-invitation",
                label="создать ссылку-приглашение",
                icon="plus",
                placement="primary",
                action_type="submit",
                form_id=invitation_create_form_id,
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


def member_row_vm(
    member: WorkspaceMember,
    *,
    current_workspace_id: UUID,
    current_user_id: UUID,
    actor_membership: WorkspaceMember,
    member_roles: tuple[WorkspaceRole, ...],
) -> WorkspaceMemberRowVM:
    user = member.user
    title = user.name or user.email
    form_id = f"member-role-form-{member.id}"
    edit_summary_id = f"member-edit-toggle-{member.id}"
    is_self = member.user_id == current_user_id
    role_options = [
        role for role in member_roles if can_assign_member_role(actor_membership, member, role)
    ]
    can_edit_role = bool(role_options) and not is_self
    lifecycle_action = member_lifecycle_action(
        member,
        current_workspace_id=current_workspace_id,
        actor_membership=actor_membership,
        is_self=is_self,
    )
    return WorkspaceMemberRowVM(
        member=member,
        anchor_id=f"workspace-member-{member.id}",
        form_id=form_id,
        edit_summary_id=edit_summary_id,
        title=title,
        email_label=user.email,
        role_label=ru_label(member.role),
        status_label=ru_label(member.status),
        status_tone=member_status_tone(member.status),
        role_options=role_options,
        edit_panel_open=False,
        edit_toggle_action=ActionVM(
            id="edit-member-role",
            label="изменить роль",
            icon="settings",
            placement="primary" if lifecycle_action is None else "secondary",
            action_type="panel_toggle",
            panel_id=edit_summary_id,
        )
        if can_edit_role
        else None,
        save_role_action=ActionVM(
            id="save-member-role",
            label="сохранить роль",
            icon="save",
            placement="primary",
            action_type="submit",
            form_id=form_id,
        )
        if can_edit_role
        else None,
        lifecycle_action=lifecycle_action,
    )


def invitation_row_vm(
    invitation: WorkspaceInvitation,
    *,
    current_workspace_id: UUID,
) -> WorkspaceInvitationRowVM:
    return WorkspaceInvitationRowVM(
        invitation=invitation,
        anchor_id=f"workspace-invitation-{invitation.id}",
        title=f"Приглашение {short_id(invitation.id)}",
        role_label=ru_label(invitation.role),
        status_label=ru_label(invitation.status),
        status_tone="warning",
        expires_label=f"до {date_ru(invitation.expires_at)}",
        revoke_action=ActionVM(
            id="revoke-invitation",
            label="отозвать",
            icon="x",
            placement="danger",
            action_type="post",
            url=f"/workspaces/{current_workspace_id}/invitations/{invitation.id}/revoke",
            style="danger",
            confirm_message="Отозвать ссылку-приглашение?",
        ),
    )


def invitation_count_label(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        noun = "приглашение"
    elif count % 10 in {2, 3, 4} and count % 100 not in {12, 13, 14}:
        noun = "приглашения"
    else:
        noun = "приглашений"
    return f"{count} {noun}"


def audit_event_row_vm(event: WorkspaceAuditEvent) -> WorkspaceAuditEventRowVM:
    return WorkspaceAuditEventRowVM(
        event=event,
        anchor_id=f"workspace-audit-{event.id}",
        title=ru_label(event.event_type),
        date_label=date_ru(event.created_at),
        meta_labels=audit_event_meta_labels(event),
        detail_labels=audit_event_detail_labels(event),
    )


def audit_event_meta_labels(event: WorkspaceAuditEvent) -> list[str]:
    labels = []
    if event.actor:
        labels.append(f"кто: {event.actor.email}")
    if event.target_user:
        labels.append(f"кого: {event.target_user.email}")
    if event.entity_type:
        labels.append(audit_entity_type_label(event.entity_type))
    return labels


def audit_event_detail_labels(event: WorkspaceAuditEvent) -> list[str]:
    if not event.details:
        return []
    return [f"{ru_label(key)}: {ru_label(value)}" for key, value in event.details.items()]


def audit_entity_type_label(entity_type: str) -> str:
    if entity_type == "workspace":
        return "пространство"
    return ru_label(entity_type)


def member_status_tone(status: WorkspaceMemberStatus) -> str:
    if status == WorkspaceMemberStatus.ACTIVE:
        return "active"
    if status == WorkspaceMemberStatus.DISABLED:
        return "archived"
    if status == WorkspaceMemberStatus.PENDING:
        return "warning"
    return "muted"


def member_count_label(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        noun = "участник"
    elif count % 10 in {2, 3, 4} and count % 100 not in {12, 13, 14}:
        noun = "участника"
    else:
        noun = "участников"
    return f"{count} {noun}"


def member_lifecycle_action(
    member: WorkspaceMember,
    *,
    current_workspace_id: UUID,
    actor_membership: WorkspaceMember,
    is_self: bool,
) -> ActionVM | None:
    if is_self:
        return None
    if member.status == WorkspaceMemberStatus.ACTIVE:
        if not can_disable_member(actor_membership, member):
            return None
        return ActionVM(
            id="disable-member",
            label="отключить",
            icon="x",
            placement="danger",
            action_type="post",
            url=f"/workspaces/{current_workspace_id}/members/{member.id}/disable",
            style="danger",
            confirm_message="Отключить доступ участника к этому пространству?",
        )
    if member.status == WorkspaceMemberStatus.DISABLED:
        if not can_reactivate_member(actor_membership, member):
            return None
        return ActionVM(
            id="restore-member",
            label="восстановить",
            icon="rotate-ccw",
            placement="primary",
            action_type="post",
            url=f"/workspaces/{current_workspace_id}/members/{member.id}/reactivate",
        )
    return None
