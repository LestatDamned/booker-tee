from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.workspaces import service as workspace_service
from app.features.workspaces.models import (
    WorkspaceAuditEventType,
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.service import WorkspaceService


async def test_context_resolution_falls_back_and_commits_on_read(monkeypatch) -> None:
    requested_workspace_id = uuid4()
    fallback_workspace = SimpleNamespace(id=uuid4(), name="Fallback")
    fallback_membership = SimpleNamespace(
        workspace=fallback_workspace,
        workspace_id=fallback_workspace.id,
        role=WorkspaceRole.VIEWER,
        status=WorkspaceMemberStatus.ACTIVE,
    )

    session, service = context_service(
        monkeypatch,
        requested_membership=None,
        fallback_membership=fallback_membership,
    )

    context = await service.resolve_context(
        user_id=cast(Any, service.users).user.id,
        workspace_id=requested_workspace_id,
    )

    assert context.workspace.id == fallback_workspace.id
    assert session.commit_count == 1
    assert cast(Any, service.workspaces).active_membership_requests == [requested_workspace_id]


async def test_context_resolution_silently_creates_personal_workspace_on_read(monkeypatch) -> None:
    session, service = context_service(
        monkeypatch,
        requested_membership=None,
        fallback_membership=None,
    )

    context = await service.resolve_context(user_id=cast(Any, service.users).user.id)

    repository = cast(Any, service.workspaces)
    assert context.workspace.type == WorkspaceType.PERSONAL
    assert session.commit_count == 1
    assert repository.personal_create_count == 1
    assert repository.audit_events[0].event_type == WorkspaceAuditEventType.WORKSPACE_CREATED


def context_service(
    monkeypatch,
    *,
    requested_membership: SimpleNamespace | None,
    fallback_membership: SimpleNamespace | None,
) -> tuple[Any, WorkspaceService]:
    class FakeSession:
        def __init__(self) -> None:
            self.commit_count = 0

        async def commit(self) -> None:
            self.commit_count += 1

    class FakeUserRepository:
        def __init__(self, session: FakeSession) -> None:
            self.session = session
            self.user = SimpleNamespace(id=uuid4(), email="actor@example.test")

        async def get_active(self, user_id):
            return self.user if user_id == self.user.id else None

    class FakeWorkspaceRepository:
        def __init__(self, session: FakeSession) -> None:
            self.session = session
            self.active_membership_requests = []
            self.personal_create_count = 0
            self.audit_events = []

        async def get_active_membership(self, *, user_id, workspace_id):
            self.active_membership_requests.append(workspace_id)
            return requested_membership

        async def get_first_active_membership_for_user(self, user_id):
            return fallback_membership

        async def create_personal_workspace_with_owner_membership(self, user_id):
            self.personal_create_count += 1
            workspace = SimpleNamespace(
                id=uuid4(),
                owner_id=user_id,
                name="Personal",
                type=WorkspaceType.PERSONAL,
                default_currency="RUB",
            )
            membership = SimpleNamespace(
                id=uuid4(),
                workspace=workspace,
                workspace_id=workspace.id,
                user_id=user_id,
                role=WorkspaceRole.OWNER,
                status=WorkspaceMemberStatus.ACTIVE,
            )
            return workspace, membership

        async def create_audit_event(self, **values):
            event = SimpleNamespace(id=uuid4(), **values)
            self.audit_events.append(event)
            return event

    monkeypatch.setattr(workspace_service, "UserRepository", FakeUserRepository)
    monkeypatch.setattr(workspace_service, "WorkspaceRepository", FakeWorkspaceRepository)

    session = FakeSession()
    service = WorkspaceService(
        cast(AsyncSession, session),
        Settings(auth_secret_key="test-secret"),
    )
    return session, service
