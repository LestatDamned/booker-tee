from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.workspaces.application import creation, switching
from app.features.workspaces.commands import CreateWorkspaceCommand
from app.features.workspaces.domain.types import (
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.errors import (
    WorkspaceIdempotencyConflictError,
    WorkspaceNotFoundError,
    WorkspaceSwitchConflictError,
)


async def test_workspace_switch_locks_session_checks_expected_current_and_commits(
    monkeypatch,
) -> None:
    current_id = uuid4()
    target_id = uuid4()
    session, actor, user_session, membership, repositories = switch_harness(
        monkeypatch,
        current_id=current_id,
        target_id=target_id,
    )

    result = await switching.WorkspaceSessionSwitcher(cast(AsyncSession, session)).switch(
        actor=actor,
        session_token="session-token",
        target_workspace_id=target_id,
        expected_current_workspace_id=current_id,
    )

    assert repositories.users.lock_calls == [(actor.id, "session-token")]
    assert repositories.workspaces.workspace_lock_calls == [target_id]
    assert repositories.workspaces.membership_calls == [(actor.id, target_id)]
    assert user_session.current_workspace_id == target_id
    assert result.workspace.id == membership.workspace.id
    assert session.commit_count == 1
    assert session.rollback_count == 0


async def test_workspace_switch_rejects_stale_tab_before_target_lookup(monkeypatch) -> None:
    current_id = uuid4()
    session, actor, _, _, repositories = switch_harness(
        monkeypatch,
        current_id=current_id,
        target_id=uuid4(),
    )

    with pytest.raises(WorkspaceSwitchConflictError) as error:
        await switching.WorkspaceSessionSwitcher(cast(AsyncSession, session)).switch(
            actor=actor,
            session_token="session-token",
            target_workspace_id=uuid4(),
            expected_current_workspace_id=uuid4(),
        )

    assert error.value.current_workspace_id == current_id
    assert repositories.workspaces.membership_calls == []
    assert session.commit_count == 0
    assert session.rollback_count == 1


async def test_workspace_switch_masks_inactive_or_foreign_target(monkeypatch) -> None:
    current_id = uuid4()
    target_id = uuid4()
    session, actor, _, _, repositories = switch_harness(
        monkeypatch,
        current_id=current_id,
        target_id=target_id,
    )
    repositories.workspaces.membership = None

    with pytest.raises(WorkspaceNotFoundError):
        await switching.WorkspaceSessionSwitcher(cast(AsyncSession, session)).switch(
            actor=actor,
            session_token="session-token",
            target_workspace_id=target_id,
            expected_current_workspace_id=current_id,
        )

    assert session.commit_count == 0
    assert session.rollback_count == 1


async def test_workspace_create_commits_workspace_membership_audit_and_selection(
    monkeypatch,
) -> None:
    session, actor, repositories = creation_harness(monkeypatch)
    command = CreateWorkspaceCommand(
        name="  Семейный бюджет ",
        workspace_type=WorkspaceType.FAMILY,
        default_currency=" rub ",
    )
    key = uuid4()

    result = await creation.WorkspaceCreator(cast(AsyncSession, session)).create(
        actor=actor,
        session_token="session-token",
        command=command,
        idempotency_key=key,
    )

    created = repositories.workspaces.created[0]
    assert created.name == "Семейный бюджет"
    assert created.default_currency == "RUB"
    assert created.id == result.workspace.id
    assert repositories.workspaces.audit_events[0]["workspace_id"] == created.id
    assert repositories.users.user_session.current_workspace_id == created.id
    assert result.replayed is False
    assert session.commit_count == 1


async def test_workspace_create_replays_same_payload_without_duplicate(monkeypatch) -> None:
    session, actor, repositories = creation_harness(monkeypatch)
    command = CreateWorkspaceCommand(
        name="Дом",
        workspace_type=WorkspaceType.PERSONAL,
        default_currency="RUB",
    )
    key = uuid4()
    creator = creation.WorkspaceCreator(cast(AsyncSession, session))
    first = await creator.create(
        actor=actor,
        session_token="session-token",
        command=command,
        idempotency_key=key,
    )
    repositories.workspaces.existing = first.workspace

    replay = await creator.create(
        actor=actor,
        session_token="session-token",
        command=command,
        idempotency_key=key,
    )

    assert replay.workspace.id == first.workspace.id
    assert replay.replayed is True
    assert len(repositories.workspaces.created) == 1


async def test_workspace_create_rejects_changed_idempotency_payload(monkeypatch) -> None:
    session, actor, repositories = creation_harness(monkeypatch)
    repositories.workspaces.existing = SimpleNamespace(
        name="Дом",
        type=WorkspaceType.PERSONAL,
        default_currency="RUB",
    )

    with pytest.raises(WorkspaceIdempotencyConflictError):
        await creation.WorkspaceCreator(cast(AsyncSession, session)).create(
            actor=actor,
            session_token="session-token",
            command=CreateWorkspaceCommand(
                name="Другой дом",
                workspace_type=WorkspaceType.PERSONAL,
                default_currency="RUB",
            ),
            idempotency_key=uuid4(),
        )

    assert repositories.workspaces.created == []
    assert session.commit_count == 0


class FakeSession:
    def __init__(self) -> None:
        self.commit_count = 0
        self.rollback_count = 0

    async def commit(self) -> None:
        self.commit_count += 1

    async def rollback(self) -> None:
        self.rollback_count += 1


def switch_harness(monkeypatch, *, current_id: UUID, target_id: UUID):
    actor = SimpleNamespace(id=uuid4())
    user_session = SimpleNamespace(current_workspace_id=current_id, last_seen_at=None)
    workspace = SimpleNamespace(id=target_id, is_active=True)
    membership = SimpleNamespace(workspace_id=target_id, workspace=workspace)

    class Users:
        def __init__(self, session) -> None:
            self.lock_calls = []

        async def get_active_session_for_update(
            self,
            *,
            session_id,
            user_id,
        ):
            self.lock_calls.append((user_id, "session-token"))
            return user_session

    class Workspaces:
        def __init__(self, session) -> None:
            self.membership = membership
            self.membership_calls = []
            self.workspace_lock_calls = []

        async def lock_for_update(self, workspace_id):
            self.workspace_lock_calls.append(workspace_id)
            return workspace

        async def get_active_membership(self, *, user_id, workspace_id):
            self.membership_calls.append((user_id, workspace_id))
            return self.membership

    users = Users(None)
    workspaces = Workspaces(None)
    monkeypatch.setattr(switching, "UserRepository", lambda session: users)
    monkeypatch.setattr(switching, "WorkspaceRepository", lambda session: workspaces)
    return (
        FakeSession(),
        actor,
        user_session,
        membership,
        SimpleNamespace(users=users, workspaces=workspaces),
    )


def creation_harness(monkeypatch):
    actor = SimpleNamespace(id=uuid4())
    user_session = SimpleNamespace(current_workspace_id=uuid4(), last_seen_at=None)

    class Users:
        def __init__(self, session) -> None:
            self.user_session = user_session

        async def get_active_session_for_update(
            self,
            *,
            session_id,
            user_id,
        ):
            return self.user_session

    class Workspaces:
        def __init__(self, session) -> None:
            self.existing = None
            self.created = []
            self.memberships = {}
            self.audit_events = []

        async def get_for_owner(self, *, owner_id, workspace_id):
            return self.existing

        async def create_workspace_with_owner_membership(self, **values):
            workspace = SimpleNamespace(
                id=values["workspace_id"],
                owner_id=values["owner_id"],
                name=values["name"],
                type=values["workspace_type"],
                default_currency=values["default_currency"],
            )
            membership = SimpleNamespace(
                workspace_id=workspace.id,
                workspace=workspace,
                role=WorkspaceRole.OWNER,
                status=WorkspaceMemberStatus.ACTIVE,
            )
            self.created.append(workspace)
            self.memberships[workspace.id] = membership
            return workspace, membership

        async def create_audit_event(self, **values):
            self.audit_events.append(values)
            return SimpleNamespace(**values)

        async def get_active_membership(self, *, user_id, workspace_id):
            return self.memberships.get(workspace_id)

    users = Users(None)
    workspaces = Workspaces(None)
    monkeypatch.setattr(creation, "UserRepository", lambda session: users)
    monkeypatch.setattr(creation, "WorkspaceRepository", lambda session: workspaces)
    return FakeSession(), actor, SimpleNamespace(users=users, workspaces=workspaces)
