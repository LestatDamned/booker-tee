from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import FastAPI
from manual_ledger_support import api_context

from app.api.dependencies import get_api_request_context
from app.api.v1.workspaces.dependencies import (
    get_workspace_creator,
    get_workspace_directory_reader,
    get_workspace_invitation_service,
    get_workspace_lifecycle_service,
    get_workspace_member_service,
    get_workspace_ownership_service,
    get_workspace_session_switcher,
    get_workspace_settings_service,
)
from app.features.workspaces.application.creation import WorkspaceCreationResult
from app.features.workspaces.application.invitations import CreatedWorkspaceInvitationResult
from app.features.workspaces.application.lifecycle import WorkspaceLifecycleResult
from app.features.workspaces.application.ownership import (
    WorkspaceLeaveResult,
    WorkspaceOwnershipTransferResult,
)
from app.features.workspaces.application.switching import WorkspaceSessionSwitchResult
from app.features.workspaces.commands import (
    CreateWorkspaceCommand,
    TransitionWorkspaceLifecycleCommand,
    TransitionWorkspaceMemberCommand,
    UpdateWorkspaceMemberRoleApiCommand,
    UpdateWorkspaceSettingsCommand,
)
from app.features.workspaces.domain.types import (
    WorkspaceInvitationStatus,
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.errors import WorkspaceError
from app.features.workspaces.models import Workspace, WorkspaceMember
from app.features.workspaces.schemas import (
    WorkspaceBlockingReason,
    WorkspaceDirectoryCapabilitiesDto,
    WorkspaceDirectoryDto,
    WorkspaceDirectoryItemCapabilitiesDto,
    WorkspaceDirectoryItemDto,
    WorkspaceInvitationCapabilitiesDto,
    WorkspaceInvitationItemDto,
    WorkspaceInvitationsCapabilitiesDto,
    WorkspaceInvitationsDto,
    WorkspaceLifecycleImpactDto,
    WorkspaceLifecycleMutationImpactDto,
    WorkspaceMemberCapabilitiesDto,
    WorkspaceMemberItemDto,
    WorkspaceMembersCapabilitiesDto,
    WorkspaceMembersDto,
    WorkspaceMembershipDto,
    WorkspaceOptionDto,
    WorkspaceSettingsCapabilitiesDto,
    WorkspaceSettingsDto,
    WorkspaceSettingsItemDto,
)
from app.main import create_app


class WorkspaceDirectoryReaderStub:
    def __init__(self, directory: WorkspaceDirectoryDto) -> None:
        self.directory = directory
        self.calls: list[tuple[UUID, UUID]] = []

    async def read_for_user(
        self,
        *,
        user_id: UUID,
        current_workspace_id: UUID,
    ) -> WorkspaceDirectoryDto:
        self.calls.append((user_id, current_workspace_id))
        return self.directory


class WorkspaceCreatorStub:
    def __init__(self, result: WorkspaceCreationResult) -> None:
        self.result = result
        self.calls: list[tuple[UUID, str, CreateWorkspaceCommand, UUID]] = []
        self.error: WorkspaceError | None = None

    async def create(
        self,
        *,
        actor,
        session_token: str,
        command: CreateWorkspaceCommand,
        idempotency_key: UUID,
    ) -> WorkspaceCreationResult:
        self.calls.append((actor.id, session_token, command, idempotency_key))
        if self.error is not None:
            raise self.error
        return self.result


class WorkspaceSessionSwitcherStub:
    def __init__(self, result: WorkspaceSessionSwitchResult) -> None:
        self.result = result
        self.calls: list[tuple[UUID, str, UUID, UUID]] = []
        self.error: WorkspaceError | None = None

    async def switch(
        self,
        *,
        actor,
        session_token: str,
        target_workspace_id: UUID,
        expected_current_workspace_id: UUID,
    ) -> WorkspaceSessionSwitchResult:
        self.calls.append(
            (
                actor.id,
                session_token,
                target_workspace_id,
                expected_current_workspace_id,
            )
        )
        if self.error is not None:
            raise self.error
        return self.result


class WorkspaceSettingsServiceStub:
    def __init__(self, settings: WorkspaceSettingsDto) -> None:
        self.settings = settings
        self.read_calls: list[tuple[UUID, UUID]] = []
        self.update_calls: list[tuple[UUID, UUID, UpdateWorkspaceSettingsCommand]] = []
        self.read_error: WorkspaceError | None = None
        self.update_error: WorkspaceError | None = None

    async def read(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
    ) -> WorkspaceSettingsDto:
        self.read_calls.append((actor_user_id, workspace_id))
        if self.read_error is not None:
            raise self.read_error
        return self.settings

    async def update(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        command: UpdateWorkspaceSettingsCommand,
    ) -> WorkspaceSettingsDto:
        self.update_calls.append((actor_user_id, workspace_id, command))
        if self.update_error is not None:
            raise self.update_error
        return self.settings


class WorkspaceLifecycleServiceStub:
    def __init__(self, result: WorkspaceLifecycleResult) -> None:
        self.result = result
        self.calls: list[tuple[str, UUID, str, UUID, TransitionWorkspaceLifecycleCommand]] = []
        self.error: WorkspaceError | None = None

    async def deactivate(self, *, actor, session_token, workspace_id, command):
        return await self._transition("deactivate", actor, session_token, workspace_id, command)

    async def restore(self, *, actor, session_token, workspace_id, command):
        return await self._transition("restore", actor, session_token, workspace_id, command)

    async def _transition(self, action, actor, session_token, workspace_id, command):
        self.calls.append((action, actor.id, session_token, workspace_id, command))
        if self.error is not None:
            raise self.error
        return self.result


class WorkspaceMemberServiceStub:
    def __init__(self, members: WorkspaceMembersDto) -> None:
        self.members = members
        self.read_calls: list[tuple[UUID, UUID]] = []
        self.role_calls: list[tuple[UUID, UUID, UpdateWorkspaceMemberRoleApiCommand]] = []
        self.transition_calls: list[tuple[str, UUID, UUID, TransitionWorkspaceMemberCommand]] = []
        self.error: WorkspaceError | None = None

    async def read(self, *, actor_user_id: UUID, workspace_id: UUID) -> WorkspaceMembersDto:
        self.read_calls.append((actor_user_id, workspace_id))
        if self.error:
            raise self.error
        return self.members

    async def update_role(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        command: UpdateWorkspaceMemberRoleApiCommand,
    ) -> WorkspaceMembersDto:
        self.role_calls.append((actor_user_id, workspace_id, command))
        if self.error:
            raise self.error
        return self.members

    async def disable(self, *, actor_user_id, workspace_id, command):
        self.transition_calls.append(("disable", actor_user_id, workspace_id, command))
        if self.error:
            raise self.error
        return self.members

    async def reactivate(self, *, actor_user_id, workspace_id, command):
        self.transition_calls.append(("reactivate", actor_user_id, workspace_id, command))
        if self.error:
            raise self.error
        return self.members


class WorkspaceOwnershipServiceStub:
    def __init__(self, transfer_result, leave_result) -> None:
        self.transfer_result = transfer_result
        self.leave_result = leave_result
        self.transfer_calls = []
        self.leave_calls = []
        self.error: WorkspaceError | None = None

    async def transfer(self, *, actor, session_token, workspace_id, command):
        self.transfer_calls.append((actor.id, session_token, workspace_id, command))
        if self.error:
            raise self.error
        return self.transfer_result

    async def leave(self, *, actor, session_token, workspace_id, command):
        self.leave_calls.append((actor.id, session_token, workspace_id, command))
        if self.error:
            raise self.error
        return self.leave_result


class WorkspaceInvitationServiceStub:
    def __init__(self, invitations: WorkspaceInvitationsDto) -> None:
        self.invitations = invitations
        self.read_calls = []
        self.create_calls = []
        self.revoke_calls = []
        self.error: WorkspaceError | None = None

    async def read(self, *, actor_user_id, workspace_id):
        self.read_calls.append((actor_user_id, workspace_id))
        if self.error:
            raise self.error
        return self.invitations

    async def create(self, *, actor_user_id, workspace_id, email, role, idempotency_key):
        self.create_calls.append((actor_user_id, workspace_id, email, role, idempotency_key))
        if self.error:
            raise self.error
        return CreatedWorkspaceInvitationResult(
            invitation=self.invitations.items[0],
            invitations=self.invitations,
            token="one-time-invitation-token",
            replayed=False,
        )

    async def revoke(
        self,
        *,
        actor_user_id,
        workspace_id,
        invitation_id,
        expected_updated_at,
    ):
        self.revoke_calls.append((actor_user_id, workspace_id, invitation_id, expected_updated_at))
        if self.error:
            raise self.error
        return self.invitations.model_copy(update={"items": []})


def workspaces_app() -> tuple[
    FastAPI,
    WorkspaceDirectoryReaderStub,
    WorkspaceCreatorStub,
    WorkspaceSessionSwitcherStub,
]:
    context = api_context(role=WorkspaceRole.OWNER)
    context = context.__class__(
        workspace=context.workspace,
        csrf_token=context.csrf_token,
        session_token="workspace-session-token",
    )
    updated_at = datetime(2026, 8, 3, 8, 30, tzinfo=UTC)
    current = workspace_item(
        workspace_id=context.workspace.workspace.id,
        name="Дом",
        role=WorkspaceRole.OWNER,
        current=True,
        updated_at=updated_at,
    )
    target = workspace_item(
        workspace_id=uuid4(),
        name="Семейный бюджет",
        role=WorkspaceRole.EDITOR,
        current=False,
        updated_at=updated_at,
        workspace_type=WorkspaceType.FAMILY,
    )
    directory = WorkspaceDirectoryDto(
        current_workspace_id=current.id,
        items=[current, target],
        capabilities=WorkspaceDirectoryCapabilitiesDto(can_create=True),
        workspace_type_options=[
            WorkspaceOptionDto(value="personal", label="Личное"),
            WorkspaceOptionDto(value="family", label="Семейное"),
        ],
        currency_options=[WorkspaceOptionDto(value="RUB", label="RUB — российский рубль")],
    )
    result_workspace = Workspace(
        id=target.id,
        owner_id=context.workspace.user.id,
        name=target.name,
        type=target.type,
        default_currency=target.default_currency,
        is_active=True,
        created_at=updated_at,
        updated_at=updated_at,
    )
    result_membership = WorkspaceMember(
        workspace_id=result_workspace.id,
        user_id=context.workspace.user.id,
        role=WorkspaceRole.OWNER,
        status=WorkspaceMemberStatus.ACTIVE,
        updated_at=updated_at,
    )
    result_membership.workspace = result_workspace
    creator = WorkspaceCreatorStub(
        WorkspaceCreationResult(
            user=context.workspace.user,
            workspace=result_workspace,
            membership=result_membership,
            replayed=False,
        )
    )
    switcher = WorkspaceSessionSwitcherStub(
        WorkspaceSessionSwitchResult(
            user=context.workspace.user,
            workspace=result_workspace,
            membership=result_membership,
        )
    )
    reader = WorkspaceDirectoryReaderStub(directory)
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_workspace_directory_reader] = lambda: reader
    app.dependency_overrides[get_workspace_creator] = lambda: creator
    app.dependency_overrides[get_workspace_session_switcher] = lambda: switcher
    return app, reader, creator, switcher


def workspace_item(
    *,
    workspace_id: UUID,
    name: str,
    role: WorkspaceRole,
    current: bool,
    updated_at: datetime,
    workspace_type: WorkspaceType = WorkspaceType.PERSONAL,
) -> WorkspaceDirectoryItemDto:
    return WorkspaceDirectoryItemDto(
        id=workspace_id,
        name=name,
        type=workspace_type,
        default_currency="RUB",
        is_active=True,
        archived_at=None,
        updated_at=updated_at,
        membership=WorkspaceMembershipDto(
            role=role,
            status=WorkspaceMemberStatus.ACTIVE,
            updated_at=updated_at,
        ),
        is_current=current,
        capabilities=WorkspaceDirectoryItemCapabilitiesDto(
            can_select=not current,
            can_update=role == WorkspaceRole.OWNER,
            can_manage_members=role == WorkspaceRole.OWNER,
            can_invite=role == WorkspaceRole.OWNER,
            can_leave=role != WorkspaceRole.OWNER,
            can_deactivate=role == WorkspaceRole.OWNER,
            can_restore=False,
        ),
        blocking_reason_codes=[WorkspaceBlockingReason.CURRENT] if current else [],
    )


def workspace_settings_app() -> tuple[
    FastAPI,
    WorkspaceSettingsServiceStub,
    WorkspaceLifecycleServiceStub,
    UUID,
    UUID,
]:
    context = api_context(role=WorkspaceRole.OWNER)
    context = context.__class__(
        workspace=context.workspace,
        csrf_token=context.csrf_token,
        session_token="workspace-session-token",
    )
    workspace_id = uuid4()
    updated_at = datetime(2026, 8, 3, 9, 30, tzinfo=UTC)
    settings = WorkspaceSettingsDto(
        workspace=WorkspaceSettingsItemDto(
            id=workspace_id,
            name="Семейный бюджет",
            type=WorkspaceType.FAMILY,
            default_currency="RUB",
            is_active=True,
            archived_at=None,
            updated_at=updated_at,
            membership=WorkspaceMembershipDto(
                role=WorkspaceRole.OWNER,
                status=WorkspaceMemberStatus.ACTIVE,
                updated_at=updated_at,
            ),
            capabilities=WorkspaceSettingsCapabilitiesDto(
                can_view_member_directory=True,
                can_view_workspace_activity=True,
                can_update=True,
                can_manage_members=True,
                can_invite=True,
                can_deactivate=False,
                can_restore=False,
            ),
            blocking_reason_codes=[],
        ),
        workspace_type_options=[
            WorkspaceOptionDto(value="personal", label="Личное"),
            WorkspaceOptionDto(value="family", label="Семейное"),
        ],
        currency_options=[
            WorkspaceOptionDto(value="RUB", label="RUB — российский рубль"),
            WorkspaceOptionDto(value="USD", label="USD — доллар США"),
        ],
        lifecycle_impact=WorkspaceLifecycleImpactDto(
            financial_history_preserved=True,
            current_session_count=2,
            pending_invitation_count=1,
            active_integration_connection_count=1,
            active_chat_identity_binding_count=2,
        ),
    )
    service = WorkspaceSettingsServiceStub(settings)
    lifecycle_service = WorkspaceLifecycleServiceStub(
        WorkspaceLifecycleResult(
            user=context.workspace.user,
            workspace=context.workspace.workspace,
            membership=context.workspace.membership,
            impact=WorkspaceLifecycleMutationImpactDto(
                moved_session_count=2,
                revoked_invitation_count=1,
                disabled_integration_connection_count=1,
                disabled_chat_conversation_binding_count=1,
                disabled_chat_identity_binding_count=2,
                consumed_chat_conversation_state_count=1,
                failed_integration_delivery_count=1,
            ),
        )
    )
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_workspace_settings_service] = lambda: service
    app.dependency_overrides[get_workspace_lifecycle_service] = lambda: lifecycle_service
    return app, service, lifecycle_service, context.workspace.user.id, workspace_id


def workspace_members_app(
    role: WorkspaceRole = WorkspaceRole.OWNER,
) -> tuple[FastAPI, WorkspaceMemberServiceStub, UUID, UUID]:
    context = api_context(role=role)
    workspace_id = uuid4()
    target_user_id = uuid4()
    updated_at = datetime(2026, 8, 3, 11, 30, tzinfo=UTC)
    target = WorkspaceMemberItemDto(
        id=uuid4(),
        user_id=target_user_id,
        name="Анна",
        email="anna@example.test",
        role=WorkspaceRole.EDITOR,
        status=WorkspaceMemberStatus.ACTIVE,
        joined_at=updated_at,
        updated_at=updated_at,
        is_self=False,
        capabilities=WorkspaceMemberCapabilitiesDto(
            can_update_role=True,
            can_disable=True,
            can_reactivate=False,
            can_transfer_ownership=True,
            can_leave=False,
            assignable_roles=[WorkspaceRole.ADMIN, WorkspaceRole.EDITOR, WorkspaceRole.VIEWER],
        ),
        blocking_reason_codes=[],
    )
    service = WorkspaceMemberServiceStub(
        WorkspaceMembersDto(
            workspace_id=workspace_id,
            items=[target],
            capabilities=WorkspaceMembersCapabilitiesDto(can_manage_members=True),
        )
    )
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_workspace_member_service] = lambda: service
    return app, service, context.workspace.user.id, workspace_id


def workspace_invitations_app(
    role: WorkspaceRole = WorkspaceRole.OWNER,
) -> tuple[
    FastAPI,
    WorkspaceInvitationServiceStub,
    UUID,
    UUID,
]:
    context = api_context(role=role)
    workspace_id = uuid4()
    updated_at = datetime(2026, 8, 4, 9, 30, tzinfo=UTC)
    item = WorkspaceInvitationItemDto(
        id=uuid4(),
        invitee_email="invitee@example.test",
        role=WorkspaceRole.VIEWER,
        status=WorkspaceInvitationStatus.PENDING,
        expires_at=datetime(2026, 8, 7, 9, 30, tzinfo=UTC),
        created_at=updated_at,
        updated_at=updated_at,
        capabilities=WorkspaceInvitationCapabilitiesDto(can_revoke=True),
        blocking_reason_codes=[],
    )
    service = WorkspaceInvitationServiceStub(
        WorkspaceInvitationsDto(
            workspace_id=workspace_id,
            items=[item],
            capabilities=WorkspaceInvitationsCapabilitiesDto(
                can_create=True,
                assignable_roles=[WorkspaceRole.EDITOR, WorkspaceRole.VIEWER],
            ),
        )
    )
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_workspace_invitation_service] = lambda: service
    return app, service, context.workspace.user.id, workspace_id


def workspace_ownership_app() -> tuple[FastAPI, WorkspaceOwnershipServiceStub, UUID, UUID, UUID]:
    context = api_context(role=WorkspaceRole.OWNER)
    context = context.__class__(
        workspace=context.workspace,
        csrf_token=context.csrf_token,
        session_token="workspace-session-token",
    )
    workspace = context.workspace.workspace
    owner_membership = context.workspace.membership
    recipient_id = uuid4()
    updated_at = datetime(2026, 8, 3, 12, tzinfo=UTC)
    workspace.updated_at = updated_at
    owner_membership.updated_at = updated_at
    members = WorkspaceMembersDto(
        workspace_id=workspace.id,
        items=[],
        capabilities=WorkspaceMembersCapabilitiesDto(can_manage_members=True),
    )
    fallback = Workspace(
        id=uuid4(),
        owner_id=context.workspace.user.id,
        name="Запасное пространство",
        type=WorkspaceType.PERSONAL,
        default_currency="RUB",
        is_active=True,
        created_at=updated_at,
        updated_at=updated_at,
    )
    fallback_membership = WorkspaceMember(
        workspace_id=fallback.id,
        user_id=context.workspace.user.id,
        role=WorkspaceRole.OWNER,
        status=WorkspaceMemberStatus.ACTIVE,
        updated_at=updated_at,
    )
    service = WorkspaceOwnershipServiceStub(
        WorkspaceOwnershipTransferResult(
            user=context.workspace.user,
            workspace=workspace,
            membership=owner_membership,
            members=members,
        ),
        WorkspaceLeaveResult(
            user=context.workspace.user,
            workspace=fallback,
            membership=fallback_membership,
        ),
    )
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_workspace_ownership_service] = lambda: service
    return app, service, context.workspace.user.id, workspace.id, recipient_id
