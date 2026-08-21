import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.security import hash_session_token
from app.core.settings import Settings
from app.db.base import utc_now
from app.features.users.models import User, UserSession
from app.features.workspaces.application.invitations import (
    AcceptedWorkspaceInvitation,
    WorkspaceInvitationService,
)
from app.features.workspaces.errors import WorkspaceInvitationTransitionError
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
from app.features.workspaces.tokens import hash_invitation_token

TEST_DATABASE_URL = os.getenv("BOOKER_TEE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="BOOKER_TEE_TEST_DATABASE_URL is required for PostgreSQL concurrency tests.",
)


async def test_postgres_concurrent_invitation_accept_has_exactly_one_winner(
    postgres_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_sessions
    seed = await seed_invitation_race(sessions, invitee_count=1)

    async def accept_once(invitee: ActorIds) -> AcceptedWorkspaceInvitation:
        async with sessions() as session:
            assert invitee.session_token is not None
            return await WorkspaceInvitationService(session, workspace_test_settings()).accept(
                actor_user_id=invitee.user_id,
                invitation_token=seed.token,
                session_token=invitee.session_token,
            )

    try:
        invitee = seed.invitees[0]
        results = await asyncio.wait_for(
            asyncio.gather(
                accept_once(invitee),
                accept_once(invitee),
                return_exceptions=True,
            ),
            timeout=10,
        )
        successful_accepts = sum(not isinstance(result, BaseException) for result in results)

        async with sessions() as session:
            accepted_members = await session.scalar(
                select(func.count())
                .select_from(WorkspaceMember)
                .where(
                    WorkspaceMember.workspace_id == seed.target_workspace_id,
                    WorkspaceMember.user_id.in_([invitee.user_id for invitee in seed.invitees]),
                    WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
                )
            )
            switched_sessions = await session.scalar(
                select(func.count())
                .select_from(UserSession)
                .where(
                    UserSession.user_id.in_([invitee.user_id for invitee in seed.invitees]),
                    UserSession.current_workspace_id == seed.target_workspace_id,
                )
            )

        assert (successful_accepts, accepted_members, switched_sessions) == (1, 1, 1)
    finally:
        await delete_invitation_race(sessions, seed)


async def test_postgres_concurrent_invitation_create_keeps_one_pending_row(
    postgres_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_sessions
    seed = await seed_invitation_race(sessions, invitee_count=1)
    email = f"concurrent-invite-{uuid4()}@example.test"

    async def create_once() -> object:
        async with sessions() as session:
            return await WorkspaceInvitationService(session, workspace_test_settings()).create(
                actor_user_id=seed.owner.user_id,
                workspace_id=seed.target_workspace_id,
                email=email,
                role=WorkspaceRole.EDITOR,
                idempotency_key=uuid4(),
            )

    try:
        results = await asyncio.wait_for(
            asyncio.gather(create_once(), create_once(), return_exceptions=True),
            timeout=10,
        )
        assert sum(not isinstance(result, BaseException) for result in results) == 1
        assert (
            sum(isinstance(result, WorkspaceInvitationTransitionError) for result in results) == 1
        )

        async with sessions() as session:
            pending = await session.scalar(
                select(func.count())
                .select_from(WorkspaceInvitation)
                .where(
                    WorkspaceInvitation.workspace_id == seed.target_workspace_id,
                    WorkspaceInvitation.invitee_email == email,
                    WorkspaceInvitation.status == WorkspaceInvitationStatus.PENDING,
                )
            )
            audit_events = await session.scalar(
                select(func.count())
                .select_from(WorkspaceAuditEvent)
                .where(
                    WorkspaceAuditEvent.workspace_id == seed.target_workspace_id,
                    WorkspaceAuditEvent.event_type == "invitation_created",
                    WorkspaceAuditEvent.details["invitee_email"].as_string() == email,
                )
            )

        assert (pending, audit_events) == (1, 1)
    finally:
        await delete_invitation_race(sessions, seed)


async def test_postgres_invitation_accept_and_revoke_have_exactly_one_winner(
    postgres_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_sessions
    seed = await seed_invitation_race(sessions, invitee_count=1)

    async def accept_once() -> AcceptedWorkspaceInvitation:
        async with sessions() as session:
            invitee = seed.invitees[0]
            assert invitee.session_token is not None
            return await WorkspaceInvitationService(session, workspace_test_settings()).accept(
                actor_user_id=invitee.user_id,
                invitation_token=seed.token,
                session_token=invitee.session_token,
            )

    async def revoke_once() -> None:
        async with sessions() as session:
            await WorkspaceInvitationService(session, workspace_test_settings()).revoke(
                actor_user_id=seed.owner.user_id,
                workspace_id=seed.target_workspace_id,
                invitation_id=seed.invitation_id,
                expected_updated_at=seed.invitation_updated_at,
            )

    try:
        results = await asyncio.gather(
            accept_once(),
            revoke_once(),
            return_exceptions=True,
        )
        successful_transitions = sum(not isinstance(result, BaseException) for result in results)
        assert successful_transitions == 1
    finally:
        await delete_invitation_race(sessions, seed)


@dataclass(frozen=True)
class ActorIds:
    user_id: UUID
    workspace_id: UUID
    member_id: UUID
    session_token: str | None = None


@dataclass(frozen=True)
class InvitationRaceSeed:
    owner: ActorIds
    invitees: tuple[ActorIds, ...]
    target_workspace_id: UUID
    invitation_id: UUID
    invitation_updated_at: datetime
    token: str
    user_ids: tuple[UUID, ...]
    workspace_ids: tuple[UUID, ...]


async def seed_invitation_race(
    sessions: async_sessionmaker[Any],
    *,
    invitee_count: int,
) -> InvitationRaceSeed:
    owner_user_id = uuid4()
    target_workspace_id = uuid4()
    owner_member_id = uuid4()
    invitation_id = uuid4()
    token = f"postgres-invitation-{invitation_id}"
    invitees: list[ActorIds] = []
    user_sessions: list[UserSession] = []
    users = [
        User(
            id=owner_user_id,
            email=f"workspace-owner-{owner_user_id}@example.test",
            password_hash="hash",
            name="Workspace owner",
        )
    ]
    workspaces = [
        Workspace(
            id=target_workspace_id,
            owner_id=owner_user_id,
            name="Invitation race",
            type=WorkspaceType.FAMILY,
            default_currency="RUB",
        )
    ]
    members = [
        WorkspaceMember(
            id=owner_member_id,
            workspace_id=target_workspace_id,
            user_id=owner_user_id,
            role=WorkspaceRole.OWNER,
            status=WorkspaceMemberStatus.ACTIVE,
        )
    ]

    for index in range(invitee_count):
        user_id = uuid4()
        workspace_id = uuid4()
        member_id = uuid4()
        session_token = f"postgres-session-{user_id}"
        users.append(
            User(
                id=user_id,
                email=f"workspace-invitee-{index}-{user_id}@example.test",
                password_hash="hash",
                name=f"Invitee {index}",
                email_verified_at=utc_now(),
            )
        )
        workspaces.append(
            Workspace(
                id=workspace_id,
                owner_id=user_id,
                name=f"Invitee {index} personal",
                type=WorkspaceType.PERSONAL,
                default_currency="RUB",
            )
        )
        members.append(
            WorkspaceMember(
                id=member_id,
                workspace_id=workspace_id,
                user_id=user_id,
                role=WorkspaceRole.OWNER,
                status=WorkspaceMemberStatus.ACTIVE,
            )
        )
        invitees.append(
            ActorIds(
                user_id=user_id,
                workspace_id=workspace_id,
                member_id=member_id,
                session_token=session_token,
            )
        )
        user_sessions.append(
            UserSession(
                user_id=user_id,
                current_workspace_id=workspace_id,
                session_token_hash=hash_session_token(session_token),
                expires_at=utc_now() + timedelta(hours=1),
            )
        )

    invitation = WorkspaceInvitation(
        id=invitation_id,
        workspace_id=target_workspace_id,
        invitee_email=users[1].email,
        role=WorkspaceRole.VIEWER,
        status=WorkspaceInvitationStatus.PENDING,
        token_hash=hash_invitation_token(token),
        invited_by_user_id=owner_user_id,
        expires_at=utc_now() + timedelta(hours=1),
    )
    async with sessions() as session:
        session.add_all([*users, *workspaces, *members, *user_sessions])
        session.add(invitation)
        await session.commit()
        await session.refresh(invitation)

    return InvitationRaceSeed(
        owner=ActorIds(
            user_id=owner_user_id,
            workspace_id=target_workspace_id,
            member_id=owner_member_id,
        ),
        invitees=tuple(invitees),
        target_workspace_id=target_workspace_id,
        invitation_id=invitation_id,
        invitation_updated_at=invitation.updated_at,
        token=token,
        user_ids=tuple(user.id for user in users),
        workspace_ids=tuple(workspace.id for workspace in workspaces),
    )


async def delete_invitation_race(
    sessions: async_sessionmaker[Any],
    seed: InvitationRaceSeed,
) -> None:
    async with sessions() as session:
        await session.execute(delete(Workspace).where(Workspace.id.in_(seed.workspace_ids)))
        await session.execute(delete(User).where(User.id.in_(seed.user_ids)))
        await session.commit()


def workspace_test_settings() -> Settings:
    return Settings(auth_secret_key="postgres-workspace-concurrency-secret")
