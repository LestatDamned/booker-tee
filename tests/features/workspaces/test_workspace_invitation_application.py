from datetime import timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.db.base import utc_now
from app.features.workspaces.application.invitations import (
    PUBLIC_INVITATION_UNAVAILABLE,
    WorkspaceInvitationService,
)
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
            workspace=SimpleNamespace(
                id=workspace_id,
                name="Family",
                is_active=True,
            ),
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
        get_invitation_by_token_hash=AsyncMock(),
        get_invitation_by_token_hash_for_update=AsyncMock(),
        get_membership=AsyncMock(),
        create_member=AsyncMock(),
    )
    users = SimpleNamespace(get_active_session_by_token_hash_for_update=AsyncMock())
    service._workspaces = cast(Any, repository)
    service._users = cast(Any, users)
    return service, session, repository, users


async def test_create_is_idempotent_and_returns_only_hashed_persistence() -> None:
    service, session, repository, _users = service_with_repo()
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
    service, _session, repository, _users = service_with_repo()
    workspace, actor = actor_context(WorkspaceRole.VIEWER)
    repository.get_visible_membership_for_user.return_value = actor

    result = await service.read(actor_user_id=actor.user_id, workspace_id=workspace.id)

    assert result.items == []
    assert result.capabilities.can_create is False
    assert result.capabilities.assignable_roles == []
    repository.list_pending_invitations.assert_not_awaited()


async def test_admin_cannot_create_or_revoke_admin_invitation() -> None:
    service, session, repository, _users = service_with_repo()
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
    service, _session, repository, _users = service_with_repo()
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


async def test_public_preview_has_one_safe_unavailable_outcome() -> None:
    service, _session, repository, _users = service_with_repo()
    target = invitation(uuid4(), uuid4())
    repository.get_invitation_by_token_hash.side_effect = [target, None]

    preview = await service.preview(invitation_token="usable-token")

    assert preview.workspace_name == "Family"
    assert preview.role == WorkspaceRole.VIEWER
    with pytest.raises(WorkspaceInvitationNotFoundError) as error:
        await service.preview(invitation_token="invalid-token")
    assert str(error.value) == PUBLIC_INVITATION_UNAVAILABLE


@pytest.mark.parametrize(
    ("status", "expires_in", "workspace_active", "role"),
    [
        (WorkspaceInvitationStatus.ACCEPTED, timedelta(hours=1), True, WorkspaceRole.VIEWER),
        (WorkspaceInvitationStatus.REVOKED, timedelta(hours=1), True, WorkspaceRole.VIEWER),
        (WorkspaceInvitationStatus.PENDING, timedelta(seconds=-1), True, WorkspaceRole.VIEWER),
        (WorkspaceInvitationStatus.PENDING, timedelta(hours=1), False, WorkspaceRole.VIEWER),
        (WorkspaceInvitationStatus.PENDING, timedelta(hours=1), True, WorkspaceRole.OWNER),
    ],
)
async def test_public_preview_masks_every_unusable_credential_state(
    status: WorkspaceInvitationStatus,
    expires_in: timedelta,
    workspace_active: bool,
    role: WorkspaceRole,
) -> None:
    service, _session, repository, _users = service_with_repo()
    target = invitation(uuid4(), uuid4(), role)
    target.status = status
    target.expires_at = utc_now() + expires_in
    target.workspace.is_active = workspace_active
    repository.get_invitation_by_token_hash.return_value = target

    with pytest.raises(WorkspaceInvitationNotFoundError) as error:
        await service.preview(invitation_token="private-token")

    assert str(error.value) == PUBLIC_INVITATION_UNAVAILABLE


async def test_accept_consumes_invitation_and_switches_session_atomically() -> None:
    service, session, repository, users = service_with_repo()
    target = invitation(uuid4(), uuid4(), WorkspaceRole.EDITOR)
    user_id = uuid4()
    user_session = SimpleNamespace(current_workspace_id=uuid4(), last_seen_at=utc_now())
    repository.get_invitation_by_token_hash.return_value = target
    repository.lock_for_update.return_value = target.workspace
    repository.get_invitation_by_token_hash_for_update.return_value = target
    repository.get_membership.return_value = None
    repository.create_member.return_value = SimpleNamespace(id=uuid4())
    users.get_active_session_by_token_hash_for_update.return_value = user_session

    result = await service.accept(
        actor_user_id=user_id,
        invitation_token="usable-token",
        session_token="session-token",
    )

    assert result.workspace_id == target.workspace_id
    assert target.status == WorkspaceInvitationStatus.ACCEPTED
    assert target.accepted_by_user_id == user_id
    assert user_session.current_workspace_id == target.workspace_id
    repository.create_member.assert_awaited_once()
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


async def test_accept_does_not_consume_invitation_for_existing_membership() -> None:
    service, session, repository, users = service_with_repo()
    target = invitation(uuid4(), uuid4())
    user_session = SimpleNamespace(current_workspace_id=uuid4(), last_seen_at=utc_now())
    repository.get_invitation_by_token_hash.return_value = target
    repository.lock_for_update.return_value = target.workspace
    repository.get_invitation_by_token_hash_for_update.return_value = target
    repository.get_membership.return_value = SimpleNamespace(status=WorkspaceMemberStatus.DISABLED)
    users.get_active_session_by_token_hash_for_update.return_value = user_session

    with pytest.raises(WorkspaceInvitationNotFoundError) as error:
        await service.accept(
            actor_user_id=uuid4(),
            invitation_token="usable-token",
            session_token="session-token",
        )

    assert str(error.value) == PUBLIC_INVITATION_UNAVAILABLE
    assert target.status == WorkspaceInvitationStatus.PENDING
    assert user_session.current_workspace_id != target.workspace_id
    repository.create_member.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()
