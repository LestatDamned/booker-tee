import os
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.settings import Settings
from app.db.base import utc_now
from app.features.users.models import User
from app.features.workspaces.application.invitations import WorkspaceInvitationService
from app.features.workspaces.domain.types import (
    WorkspaceInvitationStatus,
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.errors import WorkspaceInvitationTransitionError
from app.features.workspaces.models import Workspace, WorkspaceInvitation, WorkspaceMember
from app.features.workspaces.repository import WorkspaceRepository

TEST_DATABASE_URL = os.getenv("BOOKER_TEE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="BOOKER_TEE_TEST_DATABASE_URL is required for PostgreSQL limit tests.",
)


async def test_postgres_workspace_limits_count_only_supported_rows() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    workspace_id = uuid4()
    users = [
        User(
            id=uuid4(),
            email=f"workspace-limit-{index}-{uuid4()}@example.test",
            password_hash="hash",
            name=f"Member {index}",
        )
        for index in range(101)
    ]
    user_ids = [user.id for user in users]
    owner_id = user_ids[0]
    now = utc_now()

    try:
        async with sessions() as session:
            session.add_all(users)
            session.add(
                Workspace(
                    id=workspace_id,
                    owner_id=owner_id,
                    name="Workspace limits",
                    type=WorkspaceType.FAMILY,
                    default_currency="RUB",
                )
            )
            session.add_all(
                WorkspaceMember(
                    workspace_id=workspace_id,
                    user_id=user.id,
                    role=WorkspaceRole.OWNER if index == 0 else WorkspaceRole.VIEWER,
                    status=(
                        WorkspaceMemberStatus.DISABLED
                        if index == 99
                        else WorkspaceMemberStatus.REMOVED
                        if index == 100
                        else WorkspaceMemberStatus.ACTIVE
                    ),
                )
                for index, user in enumerate(users)
            )
            session.add_all(
                WorkspaceInvitation(
                    workspace_id=workspace_id,
                    invitee_email=f"pending-{index}@example.test",
                    role=WorkspaceRole.VIEWER,
                    status=WorkspaceInvitationStatus.PENDING,
                    token_hash=uuid4().hex * 2,
                    invited_by_user_id=owner_id,
                    expires_at=now + timedelta(hours=1),
                )
                for index in range(100)
            )
            session.add_all(
                [
                    WorkspaceInvitation(
                        workspace_id=workspace_id,
                        invitee_email="expired@example.test",
                        role=WorkspaceRole.VIEWER,
                        status=WorkspaceInvitationStatus.PENDING,
                        token_hash=uuid4().hex * 2,
                        invited_by_user_id=owner_id,
                        expires_at=now - timedelta(seconds=1),
                    ),
                    WorkspaceInvitation(
                        workspace_id=workspace_id,
                        invitee_email="revoked@example.test",
                        role=WorkspaceRole.VIEWER,
                        status=WorkspaceInvitationStatus.REVOKED,
                        token_hash=uuid4().hex * 2,
                        invited_by_user_id=owner_id,
                        expires_at=now + timedelta(hours=1),
                    ),
                ]
            )
            await session.commit()

            repository = WorkspaceRepository(session)
            members = await repository.list_members_for_workspace(workspace_id, limit=100)
            invitations = await repository.list_pending_invitations(workspace_id, limit=100)

            assert await repository.count_supported_members(workspace_id) == 100
            assert await repository.count_pending_invitations(workspace_id) == 100
            assert len(members) == len(invitations) == 100
            assert {member.status for member in members} == {
                WorkspaceMemberStatus.ACTIVE,
                WorkspaceMemberStatus.DISABLED,
            }
            invitation_to_revoke_id = invitations[0].id

            service = WorkspaceInvitationService(
                session,
                Settings(auth_secret_key="workspace-limit-test-secret"),
            )
            with pytest.raises(WorkspaceInvitationTransitionError) as member_error:
                await service.create(
                    actor_user_id=owner_id,
                    workspace_id=workspace_id,
                    email="member-101@example.test",
                    role=WorkspaceRole.VIEWER,
                    idempotency_key=uuid4(),
                )
            assert member_error.value.reason_codes == ["member_limit_reached"]

            await session.execute(
                update(WorkspaceMember)
                .where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.user_id != owner_id,
                )
                .values(status=WorkspaceMemberStatus.REMOVED)
            )
            await session.execute(
                update(WorkspaceInvitation)
                .where(WorkspaceInvitation.id == invitation_to_revoke_id)
                .values(status=WorkspaceInvitationStatus.REVOKED)
            )
            await session.commit()

            created = await service.create(
                actor_user_id=owner_id,
                workspace_id=workspace_id,
                email="pending-100@example.test",
                role=WorkspaceRole.VIEWER,
                idempotency_key=uuid4(),
            )
            assert created.replayed is False
            assert len(created.invitations.items) == 100

            with pytest.raises(WorkspaceInvitationTransitionError) as pending_error:
                await service.create(
                    actor_user_id=owner_id,
                    workspace_id=workspace_id,
                    email="pending-101@example.test",
                    role=WorkspaceRole.VIEWER,
                    idempotency_key=uuid4(),
                )
            assert pending_error.value.reason_codes == ["pending_invitation_limit_reached"]
    finally:
        async with sessions() as session:
            await session.execute(delete(Workspace).where(Workspace.id == workspace_id))
            await session.execute(delete(User).where(User.id.in_(user_ids)))
            await session.commit()
        await engine.dispose()
