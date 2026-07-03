from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.users.models import User
from app.features.workspaces import service as workspace_service
from app.features.workspaces.commands import UpdateWorkspaceMemberRoleCommand
from app.features.workspaces.errors import WorkspaceError
from app.features.workspaces.models import (
    Workspace,
    WorkspaceAuditEventType,
    WorkspaceMember,
    WorkspaceMemberStatus,
    WorkspaceRole,
)
from app.features.workspaces.service import WorkspaceContext, WorkspaceService


async def test_member_role_update_rejects_self(monkeypatch) -> None:
    user_id = uuid4()
    target_member = fake_member(user_id=user_id, role=WorkspaceRole.EDITOR)
    session, service = service_with_member(monkeypatch, target_member, actor_user_id=user_id)

    try:
        await service.update_member_role(
            context=owner_context(user_id=user_id),
            command=UpdateWorkspaceMemberRoleCommand(
                member_id=target_member.id,
                role=WorkspaceRole.VIEWER,
            ),
        )
    except WorkspaceError as exc:
        assert "собственную роль" in str(exc)
    else:
        raise AssertionError("user was allowed to change own role")

    assert session.commit_count == 0
    assert target_member.role == WorkspaceRole.EDITOR


async def test_member_disable_rejects_last_active_owner(monkeypatch) -> None:
    target_member = fake_member(role=WorkspaceRole.OWNER)
    session, service = service_with_member(
        monkeypatch,
        target_member,
        active_owner_count=1,
    )

    try:
        await service.disable_member(
            context=owner_context(),
            member_id=target_member.id,
        )
    except WorkspaceError as exc:
        assert "последнего владельца" in str(exc)
    else:
        raise AssertionError("last owner was disabled")

    assert session.commit_count == 0
    assert target_member.status == WorkspaceMemberStatus.ACTIVE


async def test_admin_cannot_promote_member_to_admin(monkeypatch) -> None:
    target_member = fake_member(role=WorkspaceRole.EDITOR)
    session, service = service_with_member(monkeypatch, target_member)

    try:
        await service.update_member_role(
            context=admin_context(),
            command=UpdateWorkspaceMemberRoleCommand(
                member_id=target_member.id,
                role=WorkspaceRole.ADMIN,
            ),
        )
    except WorkspaceError as exc:
        assert "изменения роли" in str(exc)
    else:
        raise AssertionError("admin promoted another member to admin")

    assert session.commit_count == 0
    assert target_member.role == WorkspaceRole.EDITOR


async def test_owner_can_disable_non_owner_member(monkeypatch) -> None:
    target_member = fake_member(role=WorkspaceRole.ADMIN)
    session, service = service_with_member(monkeypatch, target_member)

    member = await service.disable_member(
        context=owner_context(),
        member_id=target_member.id,
    )

    assert session.commit_count == 1
    assert member.status == WorkspaceMemberStatus.DISABLED
    repository = cast(Any, service.workspaces)
    assert repository.audit_events[0].event_type == WorkspaceAuditEventType.MEMBER_DISABLED
    assert repository.audit_events[0].target_user_id == target_member.user_id


def service_with_member(
    monkeypatch,
    target_member: SimpleNamespace,
    *,
    actor_user_id=None,
    active_owner_count: int = 2,
):
    class FakeSession:
        def __init__(self) -> None:
            self.commit_count = 0

        async def commit(self) -> None:
            self.commit_count += 1

    class FakeWorkspaceRepository:
        def __init__(self, session: FakeSession) -> None:
            self.session = session
            self.audit_events = []

        async def get_member_by_id(self, *, workspace_id, member_id):
            if member_id == target_member.id:
                return target_member
            return None

        async def count_active_owners(self, workspace_id):
            return active_owner_count

        async def create_audit_event(self, **values):
            event = SimpleNamespace(id=uuid4(), **values)
            self.audit_events.append(event)
            return event

    monkeypatch.setattr(workspace_service, "WorkspaceRepository", FakeWorkspaceRepository)

    session = FakeSession()
    service = WorkspaceService(cast(AsyncSession, session), Settings(auth_secret_key="test"))
    return session, service


def owner_context(user_id=None) -> WorkspaceContext:
    return context_with_actor(
        user_id=user_id or uuid4(),
        role=WorkspaceRole.OWNER,
    )


def admin_context() -> WorkspaceContext:
    return context_with_actor(
        user_id=uuid4(),
        role=WorkspaceRole.ADMIN,
    )


def context_with_actor(*, user_id, role: WorkspaceRole) -> WorkspaceContext:
    workspace_id = uuid4()
    return WorkspaceContext(
        user=cast(User, SimpleNamespace(id=user_id, email="actor@example.com")),
        workspace=cast(Workspace, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(
            WorkspaceMember,
            SimpleNamespace(
                id=uuid4(),
                workspace_id=workspace_id,
                user_id=user_id,
                role=role,
                status=WorkspaceMemberStatus.ACTIVE,
            ),
        ),
    )


def fake_member(
    *,
    user_id=None,
    role: WorkspaceRole,
    status: WorkspaceMemberStatus = WorkspaceMemberStatus.ACTIVE,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        workspace_id=uuid4(),
        user_id=user_id or uuid4(),
        role=role,
        status=status,
    )
