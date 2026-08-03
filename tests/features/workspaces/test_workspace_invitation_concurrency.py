import asyncio
from datetime import timedelta
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.db.base import utc_now
from app.features.users.models import User
from app.features.workspaces import service as workspace_service
from app.features.workspaces.models import (
    Workspace,
    WorkspaceInvitationStatus,
    WorkspaceMember,
    WorkspaceMemberStatus,
    WorkspaceRole,
)
from app.features.workspaces.service import WorkspaceContext, WorkspaceService
from app.features.workspaces.tokens import hash_invitation_token


@pytest.mark.xfail(
    strict=True,
    reason="Pending invitations are not locked during compare-and-consume yet (ADR-0006/D13).",
)
async def test_concurrent_invitation_accept_has_exactly_one_winner(monkeypatch) -> None:
    token = "shared-invitation-token"
    workspace_id = uuid4()
    invitation = SimpleNamespace(
        id=uuid4(),
        workspace_id=workspace_id,
        role=WorkspaceRole.VIEWER,
        status=WorkspaceInvitationStatus.PENDING,
        token_hash=hash_invitation_token(token),
        invited_by_user_id=uuid4(),
        accepted_by_user_id=None,
        accepted_at=None,
        expires_at=utc_now() + timedelta(hours=1),
    )
    created_members: dict[UUID, SimpleNamespace] = {}
    both_invocations_loaded_pending_invitation = asyncio.Event()
    arrival_lock = asyncio.Lock()
    arrival_count = 0

    class FakeSession:
        async def commit(self) -> None:
            return None

    class FakeWorkspaceRepository:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

        async def get_invitation_by_token_hash(self, token_hash: str) -> SimpleNamespace | None:
            return invitation if token_hash == invitation.token_hash else None

        async def get_membership(
            self,
            *,
            user_id: UUID,
            workspace_id: UUID,
        ) -> None:
            nonlocal arrival_count
            async with arrival_lock:
                arrival_count += 1
                if arrival_count == 2:
                    both_invocations_loaded_pending_invitation.set()
            await asyncio.wait_for(both_invocations_loaded_pending_invitation.wait(), timeout=1)
            return None

        async def create_member(self, **values: object) -> SimpleNamespace:
            member = SimpleNamespace(
                id=uuid4(),
                status=WorkspaceMemberStatus.ACTIVE,
                **values,
            )
            created_members[cast(UUID, member.user_id)] = member
            return member

        async def create_audit_event(self, **values: object) -> SimpleNamespace:
            return SimpleNamespace(id=uuid4(), **values)

    monkeypatch.setattr(workspace_service, "WorkspaceRepository", FakeWorkspaceRepository)

    async def accept_once(user_id: UUID) -> WorkspaceMember:
        service = WorkspaceService(
            cast(AsyncSession, FakeSession()),
            Settings(auth_secret_key="test-secret"),
        )
        return await service.accept_invitation(
            context=WorkspaceContext(
                user=cast(User, SimpleNamespace(id=user_id, email="invitee@example.test")),
                workspace=cast(
                    Workspace,
                    SimpleNamespace(id=uuid4(), name="Current workspace"),
                ),
                membership=cast(
                    WorkspaceMember,
                    SimpleNamespace(
                        role=WorkspaceRole.OWNER,
                        status=WorkspaceMemberStatus.ACTIVE,
                    ),
                ),
            ),
            invitation_token=token,
        )

    results = await asyncio.gather(
        accept_once(uuid4()),
        accept_once(uuid4()),
        return_exceptions=True,
    )

    successful_accepts = sum(not isinstance(result, BaseException) for result in results)
    assert successful_accepts == 1
    assert len(created_members) == 1
