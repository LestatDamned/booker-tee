from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import FastAPI
from manual_ledger_support import api_context

from app.api.dependencies import get_api_request_context
from app.api.v1.workspaces.dependencies import (
    get_workspace_creator,
    get_workspace_directory_reader,
    get_workspace_session_switcher,
    get_workspace_settings_service,
)
from app.features.workspaces.application.creation import WorkspaceCreationResult
from app.features.workspaces.application.switching import WorkspaceSessionSwitchResult
from app.features.workspaces.commands import (
    CreateWorkspaceCommand,
    UpdateWorkspaceSettingsCommand,
)
from app.features.workspaces.domain.types import (
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
    WorkspaceLifecycleImpactDto,
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
    UUID,
    UUID,
]:
    context = api_context(role=WorkspaceRole.OWNER)
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
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_workspace_settings_service] = lambda: service
    return app, service, context.workspace.user.id, workspace_id
