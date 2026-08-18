from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.chat_integrations.repository import WorkspaceRuntimeDeactivationCounts
from app.features.workspaces.application import lifecycle
from app.features.workspaces.commands import TransitionWorkspaceLifecycleCommand
from app.features.workspaces.domain.types import WorkspaceMemberStatus, WorkspaceRole
from app.features.workspaces.errors import (
    WorkspaceLifecycleConflictError,
    WorkspaceLifecycleTransitionError,
)


async def test_deactivate_moves_sessions_and_disables_runtime_in_one_commit(monkeypatch) -> None:
    harness = lifecycle_harness(monkeypatch)

    result = await lifecycle.WorkspaceLifecycleService(
        cast(AsyncSession, harness.session)
    ).deactivate(
        actor=harness.actor,
        session_token="session-token",
        workspace_id=harness.workspace.id,
        command=command(harness),
    )

    assert harness.workspace.is_active is False
    assert harness.workspace.archived_at is not None
    assert harness.users.moves == [
        (harness.actor.id, harness.workspace.id, harness.actor_fallback.workspace_id),
        (harness.other_user_id, harness.workspace.id, harness.other_fallback.workspace_id),
    ]
    assert harness.workspaces.revoked == [harness.workspace.id]
    assert harness.chat.deactivated == [harness.workspace.id]
    assert result.membership is harness.actor_fallback
    assert result.impact.model_dump() == {
        "moved_session_count": 2,
        "revoked_invitation_count": 3,
        "disabled_integration_connection_count": 4,
        "disabled_chat_conversation_binding_count": 5,
        "disabled_chat_identity_binding_count": 6,
        "consumed_chat_conversation_state_count": 7,
        "failed_integration_delivery_count": 8,
    }
    assert harness.session.commit_count == 1
    assert harness.session.rollback_count == 0
    assert harness.workspaces.audit_events[0]["details"]["action"] == "workspace_deactivated"


async def test_deactivate_requires_fallback_before_any_runtime_change(monkeypatch) -> None:
    harness = lifecycle_harness(monkeypatch, missing_other_fallback=True)

    with pytest.raises(WorkspaceLifecycleTransitionError) as error:
        await lifecycle.WorkspaceLifecycleService(cast(AsyncSession, harness.session)).deactivate(
            actor=harness.actor,
            session_token="session-token",
            workspace_id=harness.workspace.id,
            command=command(harness),
        )

    assert error.value.reason_codes == ["workspace_fallback_required"]
    assert harness.workspace.is_active is True
    assert harness.session.flush_count == 0
    assert harness.session.commit_count == 0
    assert harness.session.rollback_count == 1
    assert harness.workspaces.revoked == []
    assert harness.chat.deactivated == []


async def test_restore_only_reactivates_workspace_and_rejects_stale_snapshot(monkeypatch) -> None:
    harness = lifecycle_harness(monkeypatch, active=False, actor_current_target=False)
    service = lifecycle.WorkspaceLifecycleService(cast(AsyncSession, harness.session))

    with pytest.raises(WorkspaceLifecycleConflictError):
        await service.restore(
            actor=harness.actor,
            session_token="session-token",
            workspace_id=harness.workspace.id,
            command=TransitionWorkspaceLifecycleCommand(
                expected_workspace_updated_at=harness.workspace.updated_at - timedelta(seconds=1),
                expected_current_workspace_id=harness.actor_session.current_workspace_id,
            ),
        )

    result = await service.restore(
        actor=harness.actor,
        session_token="session-token",
        workspace_id=harness.workspace.id,
        command=command(harness),
    )

    assert harness.workspace.is_active is True
    assert harness.workspace.archived_at is None
    assert result.membership is harness.actor_fallback
    assert all(value == 0 for value in result.impact.model_dump().values())
    assert harness.workspaces.revoked == []
    assert harness.chat.deactivated == []
    assert harness.session.commit_count == 1
    assert harness.session.rollback_count == 1


def command(harness) -> TransitionWorkspaceLifecycleCommand:
    return TransitionWorkspaceLifecycleCommand(
        expected_workspace_updated_at=harness.workspace.updated_at,
        expected_current_workspace_id=harness.actor_session.current_workspace_id,
    )


class FakeSession:
    def __init__(self) -> None:
        self.commit_count = 0
        self.flush_count = 0
        self.rollback_count = 0

    async def commit(self) -> None:
        self.commit_count += 1

    async def flush(self) -> None:
        self.flush_count += 1

    async def rollback(self) -> None:
        self.rollback_count += 1


def lifecycle_harness(
    monkeypatch,
    *,
    active: bool = True,
    actor_current_target: bool = True,
    missing_other_fallback: bool = False,
):
    actor = SimpleNamespace(id=uuid4())
    other_user_id = uuid4()
    workspace = SimpleNamespace(
        id=uuid4(),
        owner_id=actor.id,
        is_active=active,
        archived_at=None if active else datetime(2026, 8, 3, tzinfo=UTC),
        updated_at=datetime(2026, 8, 4, tzinfo=UTC),
    )
    actor_fallback = membership(actor.id, uuid4())
    other_fallback = membership(other_user_id, uuid4())
    actor_session = SimpleNamespace(
        user_id=actor.id,
        current_workspace_id=(
            workspace.id if actor_current_target else actor_fallback.workspace_id
        ),
    )
    sessions = [
        actor_session,
        SimpleNamespace(user_id=other_user_id, current_workspace_id=workspace.id),
    ]
    owner_membership = SimpleNamespace(
        user_id=actor.id,
        workspace_id=workspace.id,
        workspace=workspace,
        status=WorkspaceMemberStatus.ACTIVE,
        role=WorkspaceRole.OWNER,
    )

    class Workspaces:
        def __init__(self, _session) -> None:
            self.revoked: list[UUID] = []
            self.audit_events = []

        async def lock_for_update(self, workspace_id):
            assert workspace_id == workspace.id
            return workspace

        async def get_membership_for_update(self, **_kwargs):
            return owner_membership

        async def get_first_active_membership_for_user_excluding_for_update(
            self, *, user_id, **_kwargs
        ):
            if user_id == actor.id:
                return actor_fallback
            return None if missing_other_fallback else other_fallback

        async def get_active_membership_for_update(self, *, workspace_id, **_kwargs):
            return actor_fallback if workspace_id == actor_fallback.workspace_id else None

        async def revoke_pending_invitations(self, workspace_id, **_kwargs):
            self.revoked.append(workspace_id)
            return 3

        async def create_audit_event(self, **values):
            self.audit_events.append(values)
            return SimpleNamespace(**values)

    class Users:
        def __init__(self, _session) -> None:
            self.moves = []

        async def get_active_session_for_update(self, *_args, **_kwargs):
            return actor_session

        async def list_active_sessions_for_workspace_for_update(self, workspace_id):
            assert workspace_id == workspace.id
            return sessions

        async def move_active_workspace_sessions(
            self, *, user_id, from_workspace_id, to_workspace_id
        ):
            self.moves.append((user_id, from_workspace_id, to_workspace_id))

    class Chat:
        def __init__(self, _session) -> None:
            self.deactivated: list[UUID] = []

        async def deactivate_workspace_runtime(self, workspace_id, **_kwargs):
            self.deactivated.append(workspace_id)
            return WorkspaceRuntimeDeactivationCounts(4, 5, 6, 7, 8)

    session = FakeSession()
    workspaces = Workspaces(session)
    users = Users(session)
    chat = Chat(session)
    monkeypatch.setattr(lifecycle, "WorkspaceRepository", lambda _session: workspaces)
    monkeypatch.setattr(lifecycle, "UserRepository", lambda _session: users)
    monkeypatch.setattr(lifecycle, "ChatIntegrationRepository", lambda _session: chat)
    return SimpleNamespace(
        actor=actor,
        actor_fallback=actor_fallback,
        actor_session=actor_session,
        chat=chat,
        other_fallback=other_fallback,
        other_user_id=other_user_id,
        session=session,
        users=users,
        workspace=workspace,
        workspaces=workspaces,
    )


def membership(user_id: UUID, workspace_id: UUID):
    fallback_workspace = SimpleNamespace(id=workspace_id, is_active=True)
    return SimpleNamespace(
        user_id=user_id,
        workspace_id=workspace_id,
        workspace=fallback_workspace,
        status=WorkspaceMemberStatus.ACTIVE,
        role=WorkspaceRole.OWNER,
    )
