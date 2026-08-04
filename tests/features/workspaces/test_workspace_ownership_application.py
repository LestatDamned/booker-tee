from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import User
from app.features.workspaces.application import ownership as ownership_application
from app.features.workspaces.application.ownership import WorkspaceOwnershipService
from app.features.workspaces.commands import (
    LeaveWorkspaceCommand,
    TransferWorkspaceOwnershipCommand,
)
from app.features.workspaces.domain.types import WorkspaceMemberStatus, WorkspaceRole
from app.features.workspaces.errors import (
    WorkspaceMemberTransitionError,
    WorkspaceOwnershipTransferConflictError,
)
from app.features.workspaces.schemas import (
    WorkspaceMembersCapabilitiesDto,
    WorkspaceMembersDto,
)


async def test_transfer_moves_authoritative_owner_atomically(monkeypatch) -> None:
    fixture = ownership_fixture(monkeypatch)

    result = await fixture.service.transfer(
        actor=fixture.actor,
        session_token="session-token",
        workspace_id=fixture.workspace.id,
        command=TransferWorkspaceOwnershipCommand(
            recipient_member_id=fixture.recipient.id,
            expected_workspace_updated_at=fixture.workspace.updated_at,
            expected_recipient_updated_at=fixture.recipient.updated_at,
        ),
    )

    assert fixture.workspace.owner_id == fixture.recipient.user_id
    assert fixture.owner.role == WorkspaceRole.ADMIN
    assert fixture.recipient.role == WorkspaceRole.OWNER
    assert result.members.workspace_id == fixture.workspace.id
    assert fixture.session.commit_count == 1
    assert fixture.workspaces.audit_events[0]["details"]["action"] == "ownership_transferred"


async def test_transfer_rejects_stale_snapshot_before_mutation(monkeypatch) -> None:
    fixture = ownership_fixture(monkeypatch)

    with pytest.raises(WorkspaceOwnershipTransferConflictError):
        await fixture.service.transfer(
            actor=fixture.actor,
            session_token="session-token",
            workspace_id=fixture.workspace.id,
            command=TransferWorkspaceOwnershipCommand(
                recipient_member_id=fixture.recipient.id,
                expected_workspace_updated_at=datetime(2025, 1, 1, tzinfo=UTC),
                expected_recipient_updated_at=fixture.recipient.updated_at,
            ),
        )

    assert fixture.workspace.owner_id == fixture.owner.user_id
    assert fixture.owner.role == WorkspaceRole.OWNER
    assert fixture.session.rollback_count == 1


async def test_leave_current_workspace_moves_sessions_and_revokes_chat(monkeypatch) -> None:
    fixture = ownership_fixture(monkeypatch, actor_is_owner=False)

    result = await fixture.service.leave(
        actor=fixture.actor,
        session_token="session-token",
        workspace_id=fixture.workspace.id,
        command=LeaveWorkspaceCommand(
            expected_member_updated_at=fixture.owner.updated_at,
            expected_current_workspace_id=fixture.workspace.id,
        ),
    )

    assert fixture.owner.status == WorkspaceMemberStatus.REMOVED
    assert result.workspace.id == fixture.fallback.workspace_id
    assert fixture.users.moves == [
        (fixture.actor.id, fixture.workspace.id, fixture.fallback.workspace_id)
    ]
    assert fixture.chat.revocations == [(fixture.workspace.id, fixture.actor.id)]
    assert fixture.session.commit_count == 1


async def test_owner_must_transfer_before_leaving(monkeypatch) -> None:
    fixture = ownership_fixture(monkeypatch)

    with pytest.raises(WorkspaceMemberTransitionError) as caught:
        await fixture.service.leave(
            actor=fixture.actor,
            session_token="session-token",
            workspace_id=fixture.workspace.id,
            command=LeaveWorkspaceCommand(
                expected_member_updated_at=fixture.owner.updated_at,
                expected_current_workspace_id=fixture.workspace.id,
            ),
        )

    assert caught.value.reason_codes == ["last_owner_required"]
    assert fixture.owner.status == WorkspaceMemberStatus.ACTIVE


class FakeSession:
    def __init__(self) -> None:
        self.commit_count = 0
        self.rollback_count = 0

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commit_count += 1

    async def rollback(self) -> None:
        self.rollback_count += 1


class FakeWorkspaceRepository:
    def __init__(self, session: FakeSession) -> None:
        self.workspace: Any = None
        self.members: list[Any] = []
        self.fallback: Any = None
        self.audit_events: list[dict[str, Any]] = []

    async def lock_for_update(self, workspace_id):
        return self.workspace if self.workspace.id == workspace_id else None

    async def list_members_for_workspace_for_update(self, workspace_id):
        return [member for member in self.members if member.workspace_id == workspace_id]

    async def get_membership_for_update(self, *, user_id, workspace_id):
        return next(
            (
                member
                for member in self.members
                if member.user_id == user_id and member.workspace_id == workspace_id
            ),
            None,
        )

    async def get_first_active_membership_for_user_excluding_for_update(self, **values):
        return self.fallback

    async def get_active_membership_for_update(self, **values):
        return self.fallback

    async def create_audit_event(self, **values):
        self.audit_events.append(values)
        return SimpleNamespace(**values)


class FakeUserRepository:
    def __init__(self, session: FakeSession) -> None:
        self.user_session: Any = None
        self.moves: list[tuple[UUID, UUID, UUID]] = []

    async def get_active_session_by_token_hash_for_update(self, *args, **kwargs):
        return self.user_session

    async def move_active_workspace_sessions(
        self, *, user_id, from_workspace_id, to_workspace_id
    ) -> None:
        self.moves.append((user_id, from_workspace_id, to_workspace_id))


class FakeChatRepository:
    def __init__(self, session: FakeSession) -> None:
        self.revocations: list[tuple[UUID, UUID]] = []

    async def revoke_workspace_access_for_user(self, *, workspace_id, user_id, revoked_at):
        self.revocations.append((workspace_id, user_id))


class FakeMemberService:
    def __init__(self, session: FakeSession) -> None:
        return None

    async def read(self, *, actor_user_id, workspace_id):
        return WorkspaceMembersDto(
            workspace_id=workspace_id,
            items=[],
            capabilities=WorkspaceMembersCapabilitiesDto(can_manage_members=True),
        )


class OwnershipFixture:
    service: WorkspaceOwnershipService
    session: FakeSession
    actor: User
    workspace: Any
    owner: Any
    recipient: Any
    fallback: Any
    workspaces: FakeWorkspaceRepository
    users: FakeUserRepository
    chat: FakeChatRepository


def ownership_fixture(monkeypatch, *, actor_is_owner: bool = True) -> OwnershipFixture:
    fixture = OwnershipFixture()

    class WorkspaceRepositoryFactory(FakeWorkspaceRepository):
        def __init__(self, session):
            super().__init__(session)
            fixture.workspaces = self

    class UserRepositoryFactory(FakeUserRepository):
        def __init__(self, session):
            super().__init__(session)
            fixture.users = self

    class ChatRepositoryFactory(FakeChatRepository):
        def __init__(self, session):
            super().__init__(session)
            fixture.chat = self

    monkeypatch.setattr(ownership_application, "WorkspaceRepository", WorkspaceRepositoryFactory)
    monkeypatch.setattr(ownership_application, "UserRepository", UserRepositoryFactory)
    monkeypatch.setattr(ownership_application, "ChatIntegrationRepository", ChatRepositoryFactory)
    monkeypatch.setattr(ownership_application, "WorkspaceMemberService", FakeMemberService)

    now = datetime(2026, 8, 3, 12, tzinfo=UTC)
    actor_id = uuid4()
    workspace_id = uuid4()
    recipient_user_id = uuid4()
    fixture.actor = cast(User, SimpleNamespace(id=actor_id, email="actor@example.test"))
    fixture.workspace = SimpleNamespace(
        id=workspace_id,
        owner_id=actor_id if actor_is_owner else recipient_user_id,
        is_active=True,
        updated_at=now,
    )
    fixture.owner = SimpleNamespace(
        id=uuid4(),
        workspace_id=workspace_id,
        user_id=actor_id,
        role=WorkspaceRole.OWNER if actor_is_owner else WorkspaceRole.EDITOR,
        status=WorkspaceMemberStatus.ACTIVE,
        updated_at=now,
    )
    fixture.recipient = SimpleNamespace(
        id=uuid4(),
        workspace_id=workspace_id,
        user_id=recipient_user_id,
        role=WorkspaceRole.EDITOR if actor_is_owner else WorkspaceRole.OWNER,
        status=WorkspaceMemberStatus.ACTIVE,
        updated_at=now,
    )
    fallback_workspace = SimpleNamespace(id=uuid4(), name="Fallback")
    fixture.fallback = SimpleNamespace(
        workspace_id=fallback_workspace.id,
        workspace=fallback_workspace,
        role=WorkspaceRole.OWNER,
        status=WorkspaceMemberStatus.ACTIVE,
    )
    fixture.session = FakeSession()
    fixture.service = WorkspaceOwnershipService(cast(AsyncSession, fixture.session))
    fixture.workspaces.workspace = fixture.workspace
    fixture.workspaces.members = [fixture.owner, fixture.recipient]
    fixture.workspaces.fallback = fixture.fallback
    fixture.users.user_session = SimpleNamespace(
        current_workspace_id=workspace_id,
        last_seen_at=now,
    )
    return fixture
