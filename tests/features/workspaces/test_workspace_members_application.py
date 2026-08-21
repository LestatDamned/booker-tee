from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from workspace_test_support import WorkspaceTestSession

from app.features.workspaces.application import members as member_application
from app.features.workspaces.application.members import WorkspaceMemberService
from app.features.workspaces.commands import (
    TransitionWorkspaceMemberCommand,
    UpdateWorkspaceMemberRoleApiCommand,
)
from app.features.workspaces.domain.types import WorkspaceMemberStatus, WorkspaceRole
from app.features.workspaces.errors import (
    WorkspaceMemberConflictError,
    WorkspaceMemberDirectoryForbiddenError,
    WorkspaceMemberTransitionError,
    WorkspaceNotFoundError,
)
from app.features.workspaces.models import WorkspaceMember


async def test_member_directory_masks_foreign_workspace(monkeypatch) -> None:
    session, service, repositories = service_with_members(monkeypatch)
    repositories.workspaces.visible_actor = None

    with pytest.raises(WorkspaceNotFoundError):
        await service.read(actor_user_id=uuid4(), workspace_id=uuid4())

    assert session.commit_count == 0
    assert repositories.workspaces.list_calls == []


async def test_member_directory_rejects_non_manager_before_loading_emails(monkeypatch) -> None:
    actor_id = uuid4()
    workspace_id = uuid4()
    actor = member(workspace_id, actor_id, WorkspaceRole.EDITOR, name="Editor")
    workspace = SimpleNamespace(id=workspace_id, is_active=True, owner_id=uuid4())
    actor.workspace = workspace
    _, service, repositories = service_with_members(
        monkeypatch,
        actor=actor,
        workspace=workspace,
        members=[actor],
    )

    with pytest.raises(WorkspaceMemberDirectoryForbiddenError):
        await service.read(actor_user_id=actor_id, workspace_id=workspace_id)

    assert repositories.workspaces.list_calls == []


async def test_foreign_member_id_is_masked(monkeypatch) -> None:
    actor_id = uuid4()
    workspace_id = uuid4()
    actor = member(workspace_id, actor_id, WorkspaceRole.OWNER, name="Owner")
    workspace = SimpleNamespace(id=workspace_id, is_active=True, owner_id=actor_id)
    actor.workspace = workspace
    foreign_member = member(uuid4(), uuid4(), WorkspaceRole.EDITOR, name="Foreign")
    session, service, _repositories = service_with_members(
        monkeypatch,
        actor=actor,
        workspace=workspace,
        members=[foreign_member],
    )

    with pytest.raises(WorkspaceNotFoundError, match="Участник не найден"):
        await service.update_role(
            actor_user_id=actor_id,
            workspace_id=workspace_id,
            command=UpdateWorkspaceMemberRoleApiCommand(
                member_id=foreign_member.id,
                role=WorkspaceRole.VIEWER,
                expected_updated_at=foreign_member.updated_at,
            ),
        )

    assert session.rollback_count == 1


@pytest.mark.parametrize(
    ("actor_role", "target_role", "new_role", "self_target", "reason"),
    [
        pytest.param(
            WorkspaceRole.OWNER,
            WorkspaceRole.OWNER,
            WorkspaceRole.VIEWER,
            True,
            "member_self",
            id="self-role-change",
        ),
        pytest.param(
            WorkspaceRole.ADMIN,
            WorkspaceRole.EDITOR,
            WorkspaceRole.ADMIN,
            False,
            "member_management_forbidden",
            id="admin-promotes-to-admin",
        ),
    ],
)
async def test_role_update_enforces_member_boundaries(
    monkeypatch,
    actor_role: WorkspaceRole,
    target_role: WorkspaceRole,
    new_role: WorkspaceRole,
    self_target: bool,
    reason: str,
) -> None:
    actor_id = uuid4()
    workspace_id = uuid4()
    actor = member(workspace_id, actor_id, actor_role, name="Actor")
    target = actor if self_target else member(workspace_id, uuid4(), target_role, name="Target")
    workspace = SimpleNamespace(id=workspace_id, is_active=True, owner_id=actor_id)
    actor.workspace = workspace
    session, service, _repositories = service_with_members(
        monkeypatch,
        actor=actor,
        workspace=workspace,
        members=[actor] if self_target else [actor, target],
    )

    with pytest.raises(WorkspaceMemberTransitionError) as error:
        await service.update_role(
            actor_user_id=actor_id,
            workspace_id=workspace_id,
            command=UpdateWorkspaceMemberRoleApiCommand(
                member_id=target.id,
                role=new_role,
                expected_updated_at=target.updated_at,
            ),
        )

    assert error.value.reason_codes == [reason]
    assert target.role == target_role
    assert session.rollback_count == 1


async def test_owner_member_cannot_be_disabled(monkeypatch) -> None:
    actor_id = uuid4()
    workspace_id = uuid4()
    actor = member(workspace_id, actor_id, WorkspaceRole.OWNER, name="Actor")
    target = member(workspace_id, uuid4(), WorkspaceRole.OWNER, name="Owner")
    workspace = SimpleNamespace(id=workspace_id, is_active=True, owner_id=actor_id)
    actor.workspace = workspace
    session, service, _repositories = service_with_members(
        monkeypatch,
        actor=actor,
        workspace=workspace,
        members=[actor, target],
    )

    with pytest.raises(WorkspaceMemberTransitionError) as error:
        await service.disable(
            actor_user_id=actor_id,
            workspace_id=workspace_id,
            command=TransitionWorkspaceMemberCommand(
                member_id=target.id,
                expected_updated_at=target.updated_at,
            ),
        )

    assert error.value.reason_codes == ["member_owner"]
    assert target.status == WorkspaceMemberStatus.ACTIVE
    assert session.rollback_count == 1


async def test_owner_receives_actions_but_owner_and_self_stay_protected(monkeypatch) -> None:
    actor_id = uuid4()
    workspace_id = uuid4()
    actor = member(workspace_id, actor_id, WorkspaceRole.OWNER, name="Owner")
    target = member(workspace_id, uuid4(), WorkspaceRole.EDITOR, name="Editor")
    workspace = SimpleNamespace(id=workspace_id, is_active=True, owner_id=actor_id)
    actor.workspace = workspace
    session, service, repositories = service_with_members(
        monkeypatch,
        actor=actor,
        workspace=workspace,
        members=[actor, target],
    )

    result = await service.read(actor_user_id=actor_id, workspace_id=workspace_id)

    owner_item, target_item = result.items
    assert owner_item.is_self is True
    assert owner_item.capabilities.can_update_role is False
    assert owner_item.capabilities.can_disable is False
    assert target_item.capabilities.can_update_role is True
    assert target_item.capabilities.can_disable is True
    assert WorkspaceRole.ADMIN in target_item.capabilities.assignable_roles
    assert session.commit_count == 0
    assert repositories.workspaces.list_calls == [(workspace_id, 100)]


async def test_disable_rejects_stale_snapshot_before_revoking_access(monkeypatch) -> None:
    actor_id = uuid4()
    workspace_id = uuid4()
    actor = member(workspace_id, actor_id, WorkspaceRole.OWNER, name="Owner")
    target = member(workspace_id, uuid4(), WorkspaceRole.EDITOR, name="Editor")
    workspace = SimpleNamespace(id=workspace_id, is_active=True, owner_id=actor_id)
    actor.workspace = workspace
    session, service, repositories = service_with_members(
        monkeypatch,
        actor=actor,
        workspace=workspace,
        members=[actor, target],
    )

    with pytest.raises(WorkspaceMemberConflictError):
        await service.disable(
            actor_user_id=actor_id,
            workspace_id=workspace_id,
            command=TransitionWorkspaceMemberCommand(
                member_id=target.id,
                expected_updated_at=target.updated_at - timedelta(seconds=1),
            ),
        )

    assert target.status == WorkspaceMemberStatus.ACTIVE
    assert session.rollback_count == 1
    assert repositories.users.moves == []
    assert repositories.chat.revocations == []


async def test_disable_moves_sessions_and_revokes_user_chat_state(monkeypatch) -> None:
    actor_id = uuid4()
    workspace_id = uuid4()
    fallback_workspace_id = uuid4()
    actor = member(workspace_id, actor_id, WorkspaceRole.OWNER, name="Owner")
    target = member(workspace_id, uuid4(), WorkspaceRole.ADMIN, name="Admin")
    workspace = SimpleNamespace(id=workspace_id, is_active=True, owner_id=actor_id)
    actor.workspace = workspace
    session, service, repositories = service_with_members(
        monkeypatch,
        actor=actor,
        workspace=workspace,
        members=[actor, target],
    )
    repositories.workspaces.fallback = SimpleNamespace(workspace_id=fallback_workspace_id)

    result = await service.disable(
        actor_user_id=actor_id,
        workspace_id=workspace_id,
        command=TransitionWorkspaceMemberCommand(
            member_id=target.id,
            expected_updated_at=target.updated_at,
        ),
    )

    assert result.items[1].status == WorkspaceMemberStatus.DISABLED
    assert session.commit_count == 1
    assert repositories.users.moves == [(target.user_id, workspace_id, fallback_workspace_id)]
    assert repositories.chat.revocations[0][:2] == (workspace_id, target.user_id)
    assert repositories.workspaces.audit_events[0]["target_user_id"] == target.user_id


class FakeWorkspaceRepository:
    def __init__(self, session: WorkspaceTestSession) -> None:
        self.visible_actor: Any = None
        self.actor: Any = None
        self.workspace: Any = None
        self.members: list[Any] = []
        self.fallback: Any = None
        self.list_calls: list[tuple[UUID, int | None]] = []
        self.audit_events: list[dict[str, Any]] = []

    async def get_visible_membership_for_user(self, **values):
        return self.visible_actor

    async def lock_for_update(self, workspace_id):
        return self.workspace if self.workspace and self.workspace.id == workspace_id else None

    async def get_membership_for_update(self, **values):
        return self.actor

    async def get_member_by_id_for_update(self, *, workspace_id, member_id):
        return next(
            (
                item
                for item in self.members
                if item.id == member_id and item.workspace_id == workspace_id
            ),
            None,
        )

    async def list_members_for_workspace(self, workspace_id, *, limit=None):
        self.list_calls.append((workspace_id, limit))
        return self.members

    async def get_first_active_membership_for_user_excluding(self, **values):
        return self.fallback

    async def create_audit_event(self, **values):
        self.audit_events.append(values)
        return SimpleNamespace(**values)


class FakeUserRepository:
    def __init__(self, session: WorkspaceTestSession) -> None:
        self.moves: list[tuple[UUID, UUID, UUID | None]] = []

    async def move_active_workspace_sessions(
        self, *, user_id, from_workspace_id, to_workspace_id
    ) -> None:
        self.moves.append((user_id, from_workspace_id, to_workspace_id))


class FakeChatRepository:
    def __init__(self, session: WorkspaceTestSession) -> None:
        self.revocations: list[tuple[UUID, UUID, datetime]] = []

    async def revoke_workspace_access_for_user(self, *, workspace_id, user_id, revoked_at) -> None:
        self.revocations.append((workspace_id, user_id, revoked_at))


class Repositories:
    def __init__(self) -> None:
        self.workspaces: FakeWorkspaceRepository
        self.users: FakeUserRepository
        self.chat: FakeChatRepository


def service_with_members(
    monkeypatch,
    *,
    actor=None,
    workspace=None,
    members=None,
):
    repositories = Repositories()

    class WorkspaceRepositoryFactory(FakeWorkspaceRepository):
        def __init__(self, session):
            super().__init__(session)
            repositories.workspaces = self

    class UserRepositoryFactory(FakeUserRepository):
        def __init__(self, session):
            super().__init__(session)
            repositories.users = self

    class ChatRepositoryFactory(FakeChatRepository):
        def __init__(self, session):
            super().__init__(session)
            repositories.chat = self

    monkeypatch.setattr(member_application, "WorkspaceRepository", WorkspaceRepositoryFactory)
    monkeypatch.setattr(member_application, "UserRepository", UserRepositoryFactory)
    monkeypatch.setattr(member_application, "ChatIntegrationRepository", ChatRepositoryFactory)
    session = WorkspaceTestSession()
    service = WorkspaceMemberService(cast(AsyncSession, session))
    repositories.workspaces.visible_actor = actor
    repositories.workspaces.actor = actor
    repositories.workspaces.workspace = workspace
    repositories.workspaces.members = members or []
    return session, service, repositories


def member(
    workspace_id: UUID,
    user_id: UUID,
    role: WorkspaceRole,
    *,
    name: str,
) -> Any:
    now = datetime(2026, 8, 3, 12, tzinfo=UTC)
    return cast(
        WorkspaceMember,
        SimpleNamespace(
            id=uuid4(),
            workspace_id=workspace_id,
            user_id=user_id,
            user=SimpleNamespace(name=name, email=f"{name.lower()}@example.test"),
            role=role,
            status=WorkspaceMemberStatus.ACTIVE,
            joined_at=now,
            updated_at=now,
        ),
    )
