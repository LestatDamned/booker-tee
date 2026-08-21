import asyncio
import os
from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.security import hash_session_token
from app.core.settings import Settings
from app.db.base import utc_now
from app.features.users.models import User, UserSession
from app.features.workspaces.application.invitations import WorkspaceInvitationService
from app.features.workspaces.application.lifecycle import WorkspaceLifecycleService
from app.features.workspaces.application.members import WorkspaceMemberService
from app.features.workspaces.commands import (
    TransitionWorkspaceLifecycleCommand,
    UpdateWorkspaceMemberRoleApiCommand,
)
from app.features.workspaces.errors import (
    WorkspaceInvitationTransitionError,
    WorkspaceMemberConflictError,
)
from app.features.workspaces.models import (
    Workspace,
    WorkspaceAuditEvent,
    WorkspaceInvitation,
    WorkspaceInvitationStatus,
    WorkspaceMember,
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)

TEST_DATABASE_URL = os.getenv("BOOKER_TEE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="BOOKER_TEE_TEST_DATABASE_URL is required for authority concurrency tests.",
)


async def test_postgres_concurrent_member_role_update_rejects_stale_writer(
    postgres_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_sessions
    owner_id, target_user_id, workspace_id, target_member_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )

    try:
        async with sessions() as session:
            session.add_all(
                [
                    User(
                        id=owner_id,
                        email=f"member-race-owner-{owner_id}@example.test",
                        password_hash="hash",
                    ),
                    User(
                        id=target_user_id,
                        email=f"member-race-target-{target_user_id}@example.test",
                        password_hash="hash",
                    ),
                    Workspace(
                        id=workspace_id,
                        owner_id=owner_id,
                        name="Member role race",
                        type=WorkspaceType.FAMILY,
                        default_currency="RUB",
                    ),
                    WorkspaceMember(
                        workspace_id=workspace_id,
                        user_id=owner_id,
                        role=WorkspaceRole.OWNER,
                        status=WorkspaceMemberStatus.ACTIVE,
                    ),
                    WorkspaceMember(
                        id=target_member_id,
                        workspace_id=workspace_id,
                        user_id=target_user_id,
                        role=WorkspaceRole.EDITOR,
                        status=WorkspaceMemberStatus.ACTIVE,
                    ),
                ]
            )
            await session.commit()
            target = await session.get(WorkspaceMember, target_member_id)
            assert target is not None
            expected_updated_at = target.updated_at

        async def update_role(role: WorkspaceRole) -> object:
            async with sessions() as session:
                return await WorkspaceMemberService(session).update_role(
                    actor_user_id=owner_id,
                    workspace_id=workspace_id,
                    command=UpdateWorkspaceMemberRoleApiCommand(
                        member_id=target_member_id,
                        role=role,
                        expected_updated_at=expected_updated_at,
                    ),
                )

        outcomes = await asyncio.wait_for(
            asyncio.gather(
                update_role(WorkspaceRole.ADMIN),
                update_role(WorkspaceRole.VIEWER),
                return_exceptions=True,
            ),
            timeout=10,
        )
        assert sum(not isinstance(outcome, BaseException) for outcome in outcomes) == 1
        assert sum(isinstance(outcome, WorkspaceMemberConflictError) for outcome in outcomes) == 1

        async with sessions() as session:
            target = await session.get(WorkspaceMember, target_member_id)
            audit_events = await session.scalar(
                select(func.count())
                .select_from(WorkspaceAuditEvent)
                .where(
                    WorkspaceAuditEvent.workspace_id == workspace_id,
                    WorkspaceAuditEvent.event_type == "member_role_changed",
                    WorkspaceAuditEvent.target_user_id == target_user_id,
                )
            )
        assert target is not None and target.role in {WorkspaceRole.ADMIN, WorkspaceRole.VIEWER}
        assert audit_events == 1
    finally:
        async with sessions() as session:
            await session.execute(delete(Workspace).where(Workspace.id == workspace_id))
            await session.execute(delete(User).where(User.id.in_([owner_id, target_user_id])))
            await session.commit()


async def test_postgres_deactivate_and_invite_leave_no_pending_access(
    postgres_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_sessions
    owner_id, workspace_id, fallback_id = uuid4(), uuid4(), uuid4()
    session_token = f"lifecycle-invite-race-{uuid4()}"
    email = f"lifecycle-invite-{uuid4()}@example.test"

    try:
        async with sessions() as session:
            session.add(
                User(
                    id=owner_id,
                    email=f"lifecycle-invite-owner-{owner_id}@example.test",
                    password_hash="hash",
                )
            )
            session.add_all(
                [
                    Workspace(
                        id=workspace_id,
                        owner_id=owner_id,
                        name="Lifecycle invite race",
                        type=WorkspaceType.FAMILY,
                        default_currency="RUB",
                    ),
                    Workspace(
                        id=fallback_id,
                        owner_id=owner_id,
                        name="Lifecycle fallback",
                        type=WorkspaceType.PERSONAL,
                        default_currency="RUB",
                    ),
                ]
            )
            session.add_all(
                [
                    WorkspaceMember(
                        workspace_id=workspace_id,
                        user_id=owner_id,
                        role=WorkspaceRole.OWNER,
                        status=WorkspaceMemberStatus.ACTIVE,
                    ),
                    WorkspaceMember(
                        workspace_id=fallback_id,
                        user_id=owner_id,
                        role=WorkspaceRole.OWNER,
                        status=WorkspaceMemberStatus.ACTIVE,
                    ),
                    UserSession(
                        user_id=owner_id,
                        current_workspace_id=workspace_id,
                        session_token_hash=hash_session_token(session_token),
                        expires_at=utc_now() + timedelta(hours=1),
                    ),
                ]
            )
            await session.commit()
            workspace = await session.get(Workspace, workspace_id)
            assert workspace is not None
            expected_updated_at = workspace.updated_at

        async def deactivate() -> object:
            async with sessions() as session:
                actor = await session.get(User, owner_id)
                assert actor is not None
                return await WorkspaceLifecycleService(session).deactivate(
                    actor=actor,
                    session_token=session_token,
                    workspace_id=workspace_id,
                    command=TransitionWorkspaceLifecycleCommand(
                        expected_workspace_updated_at=expected_updated_at,
                        expected_current_workspace_id=workspace_id,
                    ),
                )

        async def invite() -> object:
            async with sessions() as session:
                return await WorkspaceInvitationService(
                    session,
                    Settings(auth_secret_key="workspace-authority-concurrency-secret"),
                ).create(
                    actor_user_id=owner_id,
                    workspace_id=workspace_id,
                    email=email,
                    role=WorkspaceRole.VIEWER,
                    idempotency_key=uuid4(),
                )

        outcomes = await asyncio.wait_for(
            asyncio.gather(deactivate(), invite(), return_exceptions=True),
            timeout=10,
        )
        assert not isinstance(outcomes[0], BaseException)
        if isinstance(outcomes[1], BaseException):
            assert isinstance(outcomes[1], WorkspaceInvitationTransitionError)

        async with sessions() as session:
            workspace = await session.get(Workspace, workspace_id)
            current_session = await session.scalar(
                select(UserSession).where(UserSession.user_id == owner_id)
            )
            pending = await session.scalar(
                select(func.count())
                .select_from(WorkspaceInvitation)
                .where(
                    WorkspaceInvitation.workspace_id == workspace_id,
                    WorkspaceInvitation.status == WorkspaceInvitationStatus.PENDING,
                )
            )
        assert workspace is not None and workspace.is_active is False
        assert current_session is not None and current_session.current_workspace_id == fallback_id
        assert pending == 0
    finally:
        async with sessions() as session:
            await session.execute(
                delete(Workspace).where(Workspace.id.in_([workspace_id, fallback_id]))
            )
            await session.execute(delete(User).where(User.id == owner_id))
            await session.commit()
