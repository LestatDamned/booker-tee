from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.db.base import utc_now
from app.features.workspaces.application.invitations import WorkspaceInvitationService
from app.features.workspaces.domain.types import (
    WorkspaceInvitationStatus,
    WorkspaceMemberStatus,
    WorkspaceRole,
)
from app.features.workspaces.errors import (
    WorkspaceInvitationNotFoundError,
    WorkspaceInvitationTransitionError,
)
from app.features.workspaces.models import Workspace, WorkspaceInvitation, WorkspaceMember
from app.features.workspaces.tokens import hash_invitation_token


def actor_context(role: WorkspaceRole = WorkspaceRole.OWNER):
    workspace = cast(
        Workspace,
        SimpleNamespace(id=uuid4(), is_active=True),
    )
    actor = cast(
        WorkspaceMember,
        SimpleNamespace(
            user_id=uuid4(),
            workspace_id=workspace.id,
            workspace=workspace,
            role=role,
            status=WorkspaceMemberStatus.ACTIVE,
        ),
    )
    return workspace, actor


def invitation(workspace_id, actor_user_id, role=WorkspaceRole.VIEWER):
    now = utc_now()
    return cast(
        WorkspaceInvitation,
        SimpleNamespace(
            id=uuid4(),
            workspace_id=workspace_id,
            invited_by_user_id=actor_user_id,
            role=role,
            status=WorkspaceInvitationStatus.PENDING,
            token_hash="hash",
            expires_at=now.replace(year=now.year + 1),
            created_at=now,
            updated_at=now,
            revoked_at=None,
        ),
    )


def service_with_repo():
    session = SimpleNamespace(
        commit=AsyncMock(),
        flush=AsyncMock(),
        rollback=AsyncMock(),
    )
    service = WorkspaceInvitationService(
        cast(AsyncSession, session),
        Settings(auth_secret_key="invitation-test-secret"),
    )
    repository = SimpleNamespace(
        lock_for_update=AsyncMock(),
        get_membership_for_update=AsyncMock(),
        get_visible_membership_for_user=AsyncMock(),
        get_invitation=AsyncMock(),
        get_invitation_for_update=AsyncMock(),
        create_invitation=AsyncMock(),
        create_audit_event=AsyncMock(),
        list_pending_invitations=AsyncMock(),
    )
    service._workspaces = cast(Any, repository)
    return service, session, repository


async def test_create_is_idempotent_and_returns_only_hashed_persistence() -> None:
    service, session, repository = service_with_repo()
    workspace, actor = actor_context()
    created = invitation(workspace.id, actor.user_id)
    repository.lock_for_update.return_value = workspace
    repository.get_membership_for_update.return_value = actor
    repository.get_invitation.side_effect = [None, created]
    repository.create_invitation.return_value = created
    repository.list_pending_invitations.return_value = [created]
    key = uuid4()

    first = await service.create(
        actor_user_id=actor.user_id,
        workspace_id=workspace.id,
        role=WorkspaceRole.VIEWER,
        idempotency_key=key,
    )
    created.token_hash = hash_invitation_token(first.token)
    second = await service.create(
        actor_user_id=actor.user_id,
        workspace_id=workspace.id,
        role=WorkspaceRole.VIEWER,
        idempotency_key=key,
    )

    assert first.token == second.token
    assert first.replayed is False
    assert second.replayed is True
    assert created.token_hash != first.token
    repository.create_invitation.assert_awaited_once()
    assert session.commit.await_count == 2


async def test_viewer_sees_no_invitation_identity_or_capabilities() -> None:
    service, _session, repository = service_with_repo()
    workspace, actor = actor_context(WorkspaceRole.VIEWER)
    repository.get_visible_membership_for_user.return_value = actor

    result = await service.read(actor_user_id=actor.user_id, workspace_id=workspace.id)

    assert result.items == []
    assert result.capabilities.can_create is False
    assert result.capabilities.assignable_roles == []
    repository.list_pending_invitations.assert_not_awaited()


async def test_admin_cannot_create_or_revoke_admin_invitation() -> None:
    service, session, repository = service_with_repo()
    workspace, actor = actor_context(WorkspaceRole.ADMIN)
    repository.lock_for_update.return_value = workspace
    repository.get_membership_for_update.return_value = actor

    with pytest.raises(WorkspaceInvitationTransitionError) as create_error:
        await service.create(
            actor_user_id=actor.user_id,
            workspace_id=workspace.id,
            role=WorkspaceRole.ADMIN,
            idempotency_key=uuid4(),
        )
    assert create_error.value.reason_codes == ["invitation_role_forbidden"]

    target = invitation(workspace.id, uuid4(), WorkspaceRole.ADMIN)
    repository.get_invitation_for_update.return_value = target
    with pytest.raises(WorkspaceInvitationTransitionError):
        await service.revoke(
            actor_user_id=actor.user_id,
            workspace_id=workspace.id,
            invitation_id=target.id,
            expected_updated_at=target.updated_at,
        )
    assert session.rollback.await_count == 2


async def test_foreign_invitation_id_is_masked() -> None:
    service, _session, repository = service_with_repo()
    workspace, actor = actor_context()
    repository.lock_for_update.return_value = workspace
    repository.get_membership_for_update.return_value = actor
    repository.get_invitation_for_update.return_value = None

    with pytest.raises(WorkspaceInvitationNotFoundError):
        await service.revoke(
            actor_user_id=actor.user_id,
            workspace_id=workspace.id,
            invitation_id=uuid4(),
            expected_updated_at=utc_now(),
        )
