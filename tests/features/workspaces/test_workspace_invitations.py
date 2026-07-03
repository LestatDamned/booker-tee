from datetime import timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.db.base import utc_now
from app.features.users.models import User
from app.features.workspaces import service as workspace_service
from app.features.workspaces.commands import CreateWorkspaceInvitationCommand
from app.features.workspaces.errors import WorkspaceError
from app.features.workspaces.models import (
    Workspace,
    WorkspaceAuditEventType,
    WorkspaceInvitationStatus,
    WorkspaceMember,
    WorkspaceMemberStatus,
    WorkspaceRole,
)
from app.features.workspaces.permissions import can_invite_members, ensure_invitable_role
from app.features.workspaces.service import WorkspaceContext, WorkspaceService
from app.features.workspaces.tokens import hash_invitation_token


def test_invitation_permissions_are_small_and_explicit() -> None:
    owner_membership = cast(
        WorkspaceMember,
        SimpleNamespace(
            role=WorkspaceRole.OWNER,
            status=WorkspaceMemberStatus.ACTIVE,
        ),
    )
    viewer_membership = cast(
        WorkspaceMember,
        SimpleNamespace(
            role=WorkspaceRole.VIEWER,
            status=WorkspaceMemberStatus.ACTIVE,
        ),
    )

    assert can_invite_members(owner_membership)
    assert not can_invite_members(viewer_membership)

    try:
        ensure_invitable_role(WorkspaceRole.OWNER)
    except ValueError:
        pass
    else:
        raise AssertionError("owner role was accepted for invite link")


async def test_create_invitation_stores_hash_and_returns_token_once(monkeypatch) -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.commit_count = 0

        async def commit(self) -> None:
            self.commit_count += 1

    class FakeWorkspaceRepository:
        def __init__(self, session: FakeSession) -> None:
            self.session = session
            self.created_invitation = None
            self.audit_events = []

        async def create_invitation(self, **values):
            self.created_invitation = SimpleNamespace(
                id=uuid4(),
                status=WorkspaceInvitationStatus.PENDING,
                **values,
            )
            return self.created_invitation

        async def create_audit_event(self, **values):
            event = SimpleNamespace(id=uuid4(), **values)
            self.audit_events.append(event)
            return event

    monkeypatch.setattr(workspace_service, "WorkspaceRepository", FakeWorkspaceRepository)

    session = FakeSession()
    workspace = SimpleNamespace(id=uuid4(), name="Family")
    owner = SimpleNamespace(id=uuid4(), email="owner@example.com")
    context = WorkspaceContext(
        user=cast(User, owner),
        workspace=cast(Workspace, workspace),
        membership=cast(
            WorkspaceMember,
            SimpleNamespace(
                role=WorkspaceRole.OWNER,
                status=WorkspaceMemberStatus.ACTIVE,
            ),
        ),
    )
    service = WorkspaceService(cast(AsyncSession, session), Settings(auth_secret_key="test"))

    created = await service.create_invitation(
        context=context,
        command=CreateWorkspaceInvitationCommand(role=WorkspaceRole.VIEWER),
    )

    assert session.commit_count == 1
    assert created.token
    assert created.invitation.token_hash == hash_invitation_token(created.token)
    assert created.invitation.token_hash != created.token
    assert created.invitation.workspace_id == workspace.id
    assert created.invitation.invited_by_user_id == owner.id
    assert created.invitation.expires_at > utc_now()
    repository = cast(Any, service.workspaces)
    assert repository.audit_events[0].event_type == WorkspaceAuditEventType.INVITATION_CREATED
    assert repository.audit_events[0].details == {"role": WorkspaceRole.VIEWER.value}


async def test_accept_invitation_creates_membership_and_consumes_token(monkeypatch) -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.commit_count = 0

        async def commit(self) -> None:
            self.commit_count += 1

    class FakeWorkspaceRepository:
        def __init__(self, session: FakeSession) -> None:
            self.session = session
            self.workspace_id = uuid4()
            self.invited_by_user_id = uuid4()
            self.invitation = SimpleNamespace(
                id=uuid4(),
                workspace_id=self.workspace_id,
                role=WorkspaceRole.EDITOR,
                status=WorkspaceInvitationStatus.PENDING,
                token_hash=hash_invitation_token("invite-token"),
                invited_by_user_id=self.invited_by_user_id,
                accepted_by_user_id=None,
                accepted_at=None,
                expires_at=utc_now() + timedelta(hours=1),
            )
            self.created_member = None
            self.audit_events = []

        async def get_invitation_by_token_hash(self, token_hash: str):
            if token_hash == self.invitation.token_hash:
                return self.invitation
            return None

        async def get_membership(self, *, user_id, workspace_id):
            return None

        async def create_member(self, **values):
            self.created_member = SimpleNamespace(
                id=uuid4(),
                status=WorkspaceMemberStatus.ACTIVE,
                **values,
            )
            return self.created_member

        async def create_audit_event(self, **values):
            event = SimpleNamespace(id=uuid4(), **values)
            self.audit_events.append(event)
            return event

    monkeypatch.setattr(workspace_service, "WorkspaceRepository", FakeWorkspaceRepository)

    session = FakeSession()
    user = SimpleNamespace(id=uuid4(), email="member@example.com")
    current_workspace = SimpleNamespace(id=uuid4(), name="Personal")
    context = WorkspaceContext(
        user=cast(User, user),
        workspace=cast(Workspace, current_workspace),
        membership=cast(
            WorkspaceMember,
            SimpleNamespace(
                role=WorkspaceRole.OWNER,
                status=WorkspaceMemberStatus.ACTIVE,
            ),
        ),
    )
    service = WorkspaceService(cast(AsyncSession, session), Settings(auth_secret_key="test"))

    membership = await service.accept_invitation(
        context=context,
        invitation_token="invite-token",
    )

    assert session.commit_count == 1
    assert membership.user_id == user.id
    assert membership.role == WorkspaceRole.EDITOR
    repository = cast(Any, service.workspaces)
    assert membership.invited_by_user_id == repository.invited_by_user_id
    assert repository.invitation.status == WorkspaceInvitationStatus.ACCEPTED
    assert repository.invitation.accepted_by_user_id == user.id
    assert repository.invitation.accepted_at is not None
    assert repository.audit_events[0].event_type == WorkspaceAuditEventType.INVITATION_ACCEPTED
    assert repository.audit_events[0].target_user_id == user.id


async def test_expired_invitation_is_marked_expired(monkeypatch) -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.commit_count = 0

        async def commit(self) -> None:
            self.commit_count += 1

    class FakeWorkspaceRepository:
        def __init__(self, session: FakeSession) -> None:
            self.invitation = SimpleNamespace(
                id=uuid4(),
                status=WorkspaceInvitationStatus.PENDING,
                token_hash=hash_invitation_token("expired-token"),
                expires_at=utc_now() - timedelta(minutes=1),
            )

        async def get_invitation_by_token_hash(self, token_hash: str):
            if token_hash == self.invitation.token_hash:
                return self.invitation
            return None

    monkeypatch.setattr(workspace_service, "WorkspaceRepository", FakeWorkspaceRepository)

    session = FakeSession()
    service = WorkspaceService(cast(AsyncSession, session), Settings(auth_secret_key="test"))

    try:
        await service.preview_invitation("expired-token")
    except WorkspaceError as exc:
        assert "истек" in str(exc)
    else:
        raise AssertionError("expired invitation was accepted")

    assert session.commit_count == 1
    assert cast(Any, service.workspaces).invitation.status == WorkspaceInvitationStatus.EXPIRED
