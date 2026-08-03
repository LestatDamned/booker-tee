import asyncio
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.users.models import User
from app.features.workspaces import service as workspace_service
from app.features.workspaces.models import (
    Workspace,
    WorkspaceMember,
    WorkspaceMemberStatus,
    WorkspaceRole,
)
from app.features.workspaces.service import WorkspaceContext, WorkspaceService


@pytest.mark.xfail(
    strict=True,
    reason="Last-owner count and member mutation are not serialized yet (ADR-0006/D8).",
)
async def test_concurrent_owner_disable_has_exactly_one_winner(monkeypatch) -> None:
    workspace_id = uuid4()
    first_user_id = uuid4()
    second_user_id = uuid4()
    members = {
        first_user_id: owner_member(workspace_id=workspace_id, user_id=first_user_id),
        second_user_id: owner_member(workspace_id=workspace_id, user_id=second_user_id),
    }
    both_invocations_counted_owners = asyncio.Event()
    arrival_lock = asyncio.Lock()
    arrival_count = 0

    class FakeSession:
        async def commit(self) -> None:
            return None

    class FakeWorkspaceRepository:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

        async def get_member_by_id(
            self,
            *,
            workspace_id: UUID,
            member_id: UUID,
        ) -> SimpleNamespace | None:
            return next(
                (
                    member
                    for member in members.values()
                    if member.workspace_id == workspace_id and member.id == member_id
                ),
                None,
            )

        async def count_active_owners(self, counted_workspace_id: UUID) -> int:
            nonlocal arrival_count
            count = sum(
                member.workspace_id == counted_workspace_id
                and member.role == WorkspaceRole.OWNER
                and member.status == WorkspaceMemberStatus.ACTIVE
                for member in members.values()
            )
            async with arrival_lock:
                arrival_count += 1
                if arrival_count == 2:
                    both_invocations_counted_owners.set()
            await asyncio.wait_for(both_invocations_counted_owners.wait(), timeout=1)
            return count

        async def create_audit_event(self, **values: object) -> SimpleNamespace:
            return SimpleNamespace(id=uuid4(), **values)

    monkeypatch.setattr(workspace_service, "WorkspaceRepository", FakeWorkspaceRepository)

    async def disable_other(actor_user_id: UUID, target_user_id: UUID) -> WorkspaceMember:
        actor_membership = members[actor_user_id]
        service = WorkspaceService(
            cast(AsyncSession, FakeSession()),
            Settings(auth_secret_key="test-secret"),
        )
        return await service.disable_member(
            context=WorkspaceContext(
                user=cast(
                    User,
                    SimpleNamespace(id=actor_user_id, email="owner@example.test"),
                ),
                workspace=cast(
                    Workspace,
                    SimpleNamespace(id=workspace_id, name="Shared"),
                ),
                membership=cast(WorkspaceMember, actor_membership),
            ),
            member_id=members[target_user_id].id,
        )

    results = await asyncio.gather(
        disable_other(first_user_id, second_user_id),
        disable_other(second_user_id, first_user_id),
        return_exceptions=True,
    )

    successful_disables = sum(not isinstance(result, BaseException) for result in results)
    active_owners = sum(
        member.status == WorkspaceMemberStatus.ACTIVE for member in members.values()
    )
    assert successful_disables == 1
    assert active_owners == 1


def owner_member(*, workspace_id: UUID, user_id: UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        workspace_id=workspace_id,
        user_id=user_id,
        role=WorkspaceRole.OWNER,
        status=WorkspaceMemberStatus.ACTIVE,
    )
