from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.db.base import utc_now
from app.features.users.models import User
from app.features.workspaces import service as workspace_service
from app.features.workspaces.commands import CreateWorkspaceInvitationCommand
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

        async def rollback(self) -> None:
            pass

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
