from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from workspace_test_support import WorkspaceTestSession

from app.features.workspaces.application import settings
from app.features.workspaces.commands import UpdateWorkspaceSettingsCommand
from app.features.workspaces.domain.types import (
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.errors import (
    WorkspaceNotFoundError,
    WorkspaceSettingsForbiddenError,
    WorkspaceUpdateConflictError,
)


async def test_settings_read_is_membership_scoped_and_hides_owner_impact_from_viewer(
    monkeypatch,
) -> None:
    harness = settings_harness(monkeypatch, role=WorkspaceRole.VIEWER)

    result = await settings.WorkspaceSettingsService(cast(AsyncSession, harness.session)).read(
        actor_user_id=harness.actor_id,
        workspace_id=harness.workspace.id,
    )

    assert harness.workspaces.read_calls == [(harness.actor_id, harness.workspace.id)]
    assert result.workspace.capabilities.can_update is False
    assert result.workspace.capabilities.can_manage_members is False
    assert result.lifecycle_impact is None
    assert harness.users.count_calls == []
    assert harness.chat.connection_count_calls == []


async def test_settings_read_masks_invisible_membership(monkeypatch) -> None:
    harness = settings_harness(monkeypatch)
    harness.workspaces.membership = None

    with pytest.raises(WorkspaceNotFoundError):
        await settings.WorkspaceSettingsService(cast(AsyncSession, harness.session)).read(
            actor_user_id=harness.actor_id,
            workspace_id=harness.workspace.id,
        )


async def test_owner_update_locks_validates_audits_and_returns_impact(monkeypatch) -> None:
    harness = settings_harness(monkeypatch)
    expected = harness.workspace.updated_at

    result = await settings.WorkspaceSettingsService(cast(AsyncSession, harness.session)).update(
        actor_user_id=harness.actor_id,
        workspace_id=harness.workspace.id,
        command=UpdateWorkspaceSettingsCommand(
            name="  Новый дом  ",
            workspace_type=WorkspaceType.FAMILY,
            default_currency=" usd ",
            expected_updated_at=expected,
        ),
    )

    assert harness.workspaces.lock_calls == [(harness.actor_id, harness.workspace.id)]
    assert harness.workspace.name == "Новый дом"
    assert harness.workspace.type == WorkspaceType.FAMILY
    assert harness.workspace.default_currency == "USD"
    assert harness.session.flush_count == 1
    assert harness.session.commit_count == 1
    assert harness.session.rollback_count == 0
    assert harness.workspaces.audit_events[0]["details"]["old_name"] == "Дом"
    assert result.lifecycle_impact is not None
    assert result.lifecycle_impact.current_session_count == 2
    assert result.lifecycle_impact.pending_invitation_count == 1


@pytest.mark.parametrize(
    ("role", "active", "updated_at_delta", "expected_error"),
    [
        pytest.param(
            WorkspaceRole.VIEWER,
            True,
            timedelta(0),
            WorkspaceSettingsForbiddenError,
            id="viewer-forbidden",
        ),
        pytest.param(
            WorkspaceRole.OWNER,
            False,
            timedelta(0),
            WorkspaceSettingsForbiddenError,
            id="inactive-workspace",
        ),
        pytest.param(
            WorkspaceRole.OWNER,
            True,
            timedelta(seconds=-1),
            WorkspaceUpdateConflictError,
            id="stale-snapshot",
        ),
    ],
)
async def test_settings_update_rejects_forbidden_inactive_and_stale(
    monkeypatch,
    role: WorkspaceRole,
    active: bool,
    updated_at_delta: timedelta,
    expected_error: type[Exception],
) -> None:
    harness = settings_harness(monkeypatch, role=role, active=active)
    expected_updated_at = harness.workspace.updated_at + updated_at_delta

    with pytest.raises(expected_error):
        await settings.WorkspaceSettingsService(cast(AsyncSession, harness.session)).update(
            actor_user_id=harness.actor_id,
            workspace_id=harness.workspace.id,
            command=UpdateWorkspaceSettingsCommand(
                name="Дом",
                workspace_type=WorkspaceType.PERSONAL,
                default_currency="RUB",
                expected_updated_at=expected_updated_at,
            ),
        )

    assert harness.session.commit_count == 0
    assert harness.session.rollback_count == 1
    assert harness.workspaces.audit_events == []


def settings_harness(
    monkeypatch,
    *,
    role: WorkspaceRole = WorkspaceRole.OWNER,
    active: bool = True,
):
    actor_id = uuid4()
    workspace = SimpleNamespace(
        id=uuid4(),
        owner_id=actor_id,
        name="Дом",
        type=WorkspaceType.PERSONAL,
        default_currency="RUB",
        is_active=active,
        archived_at=None,
        updated_at=datetime(2026, 8, 3, 10, 0, tzinfo=UTC),
    )
    membership = SimpleNamespace(
        workspace=workspace,
        workspace_id=workspace.id,
        user_id=actor_id,
        role=role,
        status=WorkspaceMemberStatus.ACTIVE,
        updated_at=datetime(2026, 8, 3, 9, 0, tzinfo=UTC),
    )

    class Workspaces:
        def __init__(self, session) -> None:
            self.membership = membership
            self.read_calls = []
            self.lock_calls = []
            self.audit_events = []

        async def get_visible_membership_for_user(self, *, user_id, workspace_id):
            self.read_calls.append((user_id, workspace_id))
            return self.membership

        async def get_visible_membership_for_user_for_update(self, *, user_id, workspace_id):
            self.lock_calls.append((user_id, workspace_id))
            return self.membership

        async def count_pending_invitations(self, workspace_id):
            return 1

        async def get_first_active_membership_for_user_excluding(self, **_kwargs):
            return SimpleNamespace(workspace_id=uuid4())

        async def create_audit_event(self, **values):
            self.audit_events.append(values)
            return SimpleNamespace(**values)

    class Users:
        def __init__(self, session) -> None:
            self.count_calls = []

        async def count_active_sessions_for_workspace(self, workspace_id):
            self.count_calls.append(workspace_id)
            return 2

    class Chat:
        def __init__(self, session) -> None:
            self.connection_count_calls = []
            self.identity_count_calls = []

        async def count_active_connections_for_workspace(self, workspace_id):
            self.connection_count_calls.append(workspace_id)
            return 3

        async def count_active_identity_bindings_for_workspace(self, workspace_id):
            self.identity_count_calls.append(workspace_id)
            return 4

    workspaces = Workspaces(None)
    users = Users(None)
    chat = Chat(None)
    monkeypatch.setattr(settings, "WorkspaceRepository", lambda session: workspaces)
    monkeypatch.setattr(settings, "UserRepository", lambda session: users)
    monkeypatch.setattr(settings, "ChatIntegrationRepository", lambda session: chat)
    return SimpleNamespace(
        actor_id=actor_id,
        chat=chat,
        membership=membership,
        session=WorkspaceTestSession(),
        users=users,
        workspace=workspace,
        workspaces=workspaces,
    )
