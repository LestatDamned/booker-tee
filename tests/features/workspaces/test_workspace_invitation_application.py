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
    WorkspaceMemberDirectoryForbiddenError,
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


def invitation(
    workspace_id,
    actor_user_id,
    role=WorkspaceRole.VIEWER,
    invitee_email="invitee@example.test",
):
    now = utc_now()
    return cast(
        WorkspaceInvitation,
        SimpleNamespace(
            id=uuid4(),
            workspace_id=workspace_id,
            invitee_email=invitee_email,
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
        get_invitation=AsyncMock(return_value=None),
        get_invitation_for_update=AsyncMock(),
        create_invitation=AsyncMock(),
        create_audit_event=AsyncMock(),
        list_pending_invitations=AsyncMock(),
        get_invitation_by_token_hash=AsyncMock(),
        get_invitation_by_token_hash_for_update=AsyncMock(),
        get_any_membership_for_update=AsyncMock(return_value=None),
        get_member_by_email=AsyncMock(return_value=None),
        get_pending_invitation_for_email=AsyncMock(return_value=None),
        expire_pending_invitations_for_email=AsyncMock(),
        count_supported_members=AsyncMock(return_value=1),
        count_pending_invitations=AsyncMock(return_value=0),
        create_member=AsyncMock(),
    )
    users = SimpleNamespace(
        get_active_session_for_update=AsyncMock(),
        get_for_update=AsyncMock(),
    )
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
    repository.count_supported_members.return_value = 99
    repository.count_pending_invitations.return_value = 99
    key = uuid4()

    first = await service.create(
        actor_user_id=actor.user_id,
        workspace_id=workspace.id,
        email="Invitee@Example.Test",
        role=WorkspaceRole.VIEWER,
        idempotency_key=key,
    )
    created.token_hash = hash_invitation_token(first.token)
    second = await service.create(
        actor_user_id=actor.user_id,
        workspace_id=workspace.id,
        email="invitee@example.test",
        role=WorkspaceRole.VIEWER,
        idempotency_key=key,
    )

    assert first.token == second.token
    assert first.replayed is False
    assert second.replayed is True
    assert created.token_hash != first.token
    repository.create_invitation.assert_awaited_once()
    assert session.commit.await_count == 2


async def test_viewer_cannot_read_invitation_directory() -> None:
    service, _session, repository, _users = service_with_repo()
    workspace, actor = actor_context(WorkspaceRole.VIEWER)
    repository.get_visible_membership_for_user.return_value = actor

    with pytest.raises(WorkspaceMemberDirectoryForbiddenError):
        await service.read(actor_user_id=actor.user_id, workspace_id=workspace.id)

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
            email="invitee@example.test",
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
    actor = SimpleNamespace(
        id=user_id,
        email=target.invitee_email,
        email_verified_at=utc_now(),
        is_active=True,
        deactivated_at=None,
    )
    user_session = SimpleNamespace(current_workspace_id=uuid4(), last_seen_at=utc_now())
    repository.get_invitation_by_token_hash.return_value = target
    repository.lock_for_update.return_value = target.workspace
    repository.get_invitation_by_token_hash_for_update.return_value = target
    repository.get_any_membership_for_update.return_value = None
    repository.create_member.return_value = SimpleNamespace(id=uuid4())
    users.get_active_session_for_update.return_value = user_session
    users.get_for_update.return_value = actor

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
    actor_id = uuid4()
    actor = SimpleNamespace(
        id=actor_id,
        email=target.invitee_email,
        email_verified_at=utc_now(),
        is_active=True,
        deactivated_at=None,
    )
    user_session = SimpleNamespace(current_workspace_id=uuid4(), last_seen_at=utc_now())
    repository.get_invitation_by_token_hash.return_value = target
    repository.lock_for_update.return_value = target.workspace
    repository.get_invitation_by_token_hash_for_update.return_value = target
    repository.get_any_membership_for_update.return_value = SimpleNamespace(
        status=WorkspaceMemberStatus.DISABLED
    )
    users.get_active_session_for_update.return_value = user_session
    users.get_for_update.return_value = actor

    with pytest.raises(WorkspaceInvitationTransitionError) as error:
        await service.accept(
            actor_user_id=actor_id,
            invitation_token="usable-token",
            session_token="session-token",
        )

    assert error.value.reason_codes == ["member_disabled"]
    assert target.status == WorkspaceInvitationStatus.PENDING
    assert user_session.current_workspace_id != target.workspace_id
    repository.create_member.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()


async def test_accept_rejects_a_different_verified_email() -> None:
    service, session, repository, users = service_with_repo()
    target = invitation(uuid4(), uuid4())
    actor_id = uuid4()
    repository.get_invitation_by_token_hash.return_value = target
    repository.lock_for_update.return_value = target.workspace
    repository.get_invitation_by_token_hash_for_update.return_value = target
    users.get_active_session_for_update.return_value = SimpleNamespace()
    users.get_for_update.return_value = SimpleNamespace(
        id=actor_id,
        email="other@example.test",
        email_verified_at=utc_now(),
        is_active=True,
        deactivated_at=None,
    )

    with pytest.raises(WorkspaceInvitationTransitionError) as error:
        await service.accept(
            actor_user_id=actor_id,
            invitation_token="usable-token",
            session_token="session-token",
        )

    assert error.value.reason_codes == ["invitation_email_mismatch"]
    repository.create_member.assert_not_awaited()
    session.rollback.assert_awaited_once()


async def test_accept_recovers_removed_membership() -> None:
    service, session, repository, users = service_with_repo()
    target = invitation(uuid4(), uuid4(), WorkspaceRole.EDITOR)
    actor_id = uuid4()
    removed = SimpleNamespace(
        status=WorkspaceMemberStatus.REMOVED,
        role=WorkspaceRole.VIEWER,
        invited_by_user_id=None,
        joined_at=None,
    )
    user_session = SimpleNamespace(current_workspace_id=uuid4(), last_seen_at=utc_now())
    repository.get_invitation_by_token_hash.return_value = target
    repository.lock_for_update.return_value = target.workspace
    repository.get_invitation_by_token_hash_for_update.return_value = target
    repository.get_any_membership_for_update.return_value = removed
    repository.count_supported_members.return_value = 99
    users.get_active_session_for_update.return_value = user_session
    users.get_for_update.return_value = SimpleNamespace(
        id=actor_id,
        email=target.invitee_email,
        email_verified_at=utc_now(),
        is_active=True,
        deactivated_at=None,
    )

    await service.accept(
        actor_user_id=actor_id,
        invitation_token="usable-token",
        session_token="session-token",
    )

    assert removed.status == WorkspaceMemberStatus.ACTIVE
    assert removed.role == WorkspaceRole.EDITOR
    assert removed.invited_by_user_id == target.invited_by_user_id
    repository.create_member.assert_not_awaited()
    session.commit.assert_awaited_once()


async def test_accept_rejects_removed_membership_when_it_would_be_member_101() -> None:
    service, session, repository, users = service_with_repo()
    target = invitation(uuid4(), uuid4(), WorkspaceRole.EDITOR)
    actor_id = uuid4()
    removed = SimpleNamespace(
        status=WorkspaceMemberStatus.REMOVED,
        role=WorkspaceRole.VIEWER,
        invited_by_user_id=None,
        joined_at=None,
    )
    repository.get_invitation_by_token_hash.return_value = target
    repository.lock_for_update.return_value = target.workspace
    repository.get_invitation_by_token_hash_for_update.return_value = target
    repository.get_any_membership_for_update.return_value = removed
    repository.count_supported_members.return_value = 100
    users.get_active_session_for_update.return_value = SimpleNamespace()
    users.get_for_update.return_value = SimpleNamespace(
        id=actor_id,
        email=target.invitee_email,
        email_verified_at=utc_now(),
        is_active=True,
        deactivated_at=None,
    )

    with pytest.raises(WorkspaceInvitationTransitionError) as error:
        await service.accept(
            actor_user_id=actor_id,
            invitation_token="usable-token",
            session_token="session-token",
        )

    assert error.value.reason_codes == ["member_limit_reached"]
    assert removed.status == WorkspaceMemberStatus.REMOVED
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()


async def test_create_rejects_existing_pending_email() -> None:
    service, session, repository, _users = service_with_repo()
    workspace, actor = actor_context()
    repository.lock_for_update.return_value = workspace
    repository.get_membership_for_update.return_value = actor
    repository.get_pending_invitation_for_email.return_value = invitation(
        workspace.id, actor.user_id
    )

    with pytest.raises(WorkspaceInvitationTransitionError) as error:
        await service.create(
            actor_user_id=actor.user_id,
            workspace_id=workspace.id,
            email="invitee@example.test",
            role=WorkspaceRole.VIEWER,
            idempotency_key=uuid4(),
        )

    assert error.value.reason_codes == ["pending_invitation_exists"]
    repository.create_invitation.assert_not_awaited()
    session.rollback.assert_awaited_once()


@pytest.mark.parametrize(
    ("supported_members", "pending_invitations", "reason"),
    [
        (100, 0, "member_limit_reached"),
        (99, 100, "pending_invitation_limit_reached"),
    ],
)
async def test_create_rejects_invitation_101_with_stable_reason(
    supported_members: int,
    pending_invitations: int,
    reason: str,
) -> None:
    service, session, repository, _users = service_with_repo()
    workspace, actor = actor_context()
    repository.lock_for_update.return_value = workspace
    repository.get_membership_for_update.return_value = actor
    repository.count_supported_members.return_value = supported_members
    repository.count_pending_invitations.return_value = pending_invitations

    with pytest.raises(WorkspaceInvitationTransitionError) as error:
        await service.create(
            actor_user_id=actor.user_id,
            workspace_id=workspace.id,
            email="limit@example.test",
            role=WorkspaceRole.VIEWER,
            idempotency_key=uuid4(),
        )

    assert error.value.reason_codes == [reason]
    repository.create_invitation.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()
