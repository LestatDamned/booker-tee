import asyncio
import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import hash_session_token
from app.core.settings import Settings
from app.db.base import utc_now
from app.features.users.models import User, UserSession
from app.features.workspaces.application.invitations import (
    AcceptedWorkspaceInvitation,
    WorkspaceInvitationService,
)
from app.features.workspaces.models import (
    Workspace,
    WorkspaceInvitation,
    WorkspaceInvitationStatus,
    WorkspaceMember,
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.service import WorkspaceContext, WorkspaceService
from app.features.workspaces.tokens import hash_invitation_token

TEST_DATABASE_URL = os.getenv("BOOKER_TEE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="BOOKER_TEE_TEST_DATABASE_URL is required for PostgreSQL concurrency tests.",
)


@pytest.mark.asyncio
async def test_postgres_concurrent_invitation_accept_has_exactly_one_winner() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    seed = await seed_invitation_race(sessions, invitee_count=2)

    async def accept_once(invitee: ActorIds) -> AcceptedWorkspaceInvitation:
        async with sessions() as session:
            assert invitee.session_token is not None
            return await WorkspaceInvitationService(session, workspace_test_settings()).accept(
                actor_user_id=invitee.user_id,
                invitation_token=seed.token,
                session_token=invitee.session_token,
            )

    try:
        results = await asyncio.gather(
            *(accept_once(invitee) for invitee in seed.invitees),
            return_exceptions=True,
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
        await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_invitation_accept_and_revoke_have_exactly_one_winner() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
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
            context = await load_context(session, seed.owner)
            await WorkspaceService(session, workspace_test_settings()).revoke_invitation(
                context=context,
                invitation_id=seed.invitation_id,
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
        await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_legacy_owner_disable_preserves_all_owners() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    seed = await seed_owner_race(sessions)

    async def disable_other(actor: ActorIds, target_member_id: UUID) -> WorkspaceMember:
        async with sessions() as session:
            context = await load_context(session, actor)
            return await WorkspaceService(session, workspace_test_settings()).disable_member(
                context=context,
                member_id=target_member_id,
            )

    try:
        results = await asyncio.gather(
            disable_other(seed.first, seed.second.member_id),
            disable_other(seed.second, seed.first.member_id),
            return_exceptions=True,
        )
        successful_disables = sum(not isinstance(result, BaseException) for result in results)

        async with sessions() as session:
            active_owners = await session.scalar(
                select(func.count())
                .select_from(WorkspaceMember)
                .where(
                    WorkspaceMember.workspace_id == seed.workspace_id,
                    WorkspaceMember.role == WorkspaceRole.OWNER,
                    WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
                )
            )

        assert successful_disables == 0
        assert active_owners == 2
    finally:
        await delete_owner_race(sessions, seed)
        await engine.dispose()


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
    token: str
    user_ids: tuple[UUID, ...]
    workspace_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class OwnerRaceSeed:
    first: ActorIds
    second: ActorIds
    workspace_id: UUID
    user_ids: tuple[UUID, UUID]


async def load_context(session: AsyncSession, actor: ActorIds) -> WorkspaceContext:
    user = await session.get(User, actor.user_id)
    workspace = await session.get(Workspace, actor.workspace_id)
    membership = await session.get(WorkspaceMember, actor.member_id)
    assert user is not None and workspace is not None and membership is not None
    return WorkspaceContext(user=user, workspace=workspace, membership=membership)


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

    async with sessions() as session:
        session.add_all([*users, *workspaces, *members, *user_sessions])
        session.add(
            WorkspaceInvitation(
                id=invitation_id,
                workspace_id=target_workspace_id,
                invitee_email=users[1].email,
                role=WorkspaceRole.VIEWER,
                status=WorkspaceInvitationStatus.PENDING,
                token_hash=hash_invitation_token(token),
                invited_by_user_id=owner_user_id,
                expires_at=utc_now() + timedelta(hours=1),
            )
        )
        await session.commit()

    return InvitationRaceSeed(
        owner=ActorIds(
            user_id=owner_user_id,
            workspace_id=target_workspace_id,
            member_id=owner_member_id,
        ),
        invitees=tuple(invitees),
        target_workspace_id=target_workspace_id,
        invitation_id=invitation_id,
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


async def seed_owner_race(sessions: async_sessionmaker[Any]) -> OwnerRaceSeed:
    first_user_id = uuid4()
    second_user_id = uuid4()
    workspace_id = uuid4()
    first_member_id = uuid4()
    second_member_id = uuid4()
    first = ActorIds(first_user_id, workspace_id, first_member_id)
    second = ActorIds(second_user_id, workspace_id, second_member_id)

    async with sessions() as session:
        session.add_all(
            [
                User(
                    id=first_user_id,
                    email=f"workspace-owner-first-{first_user_id}@example.test",
                    password_hash="hash",
                    name="First owner",
                ),
                User(
                    id=second_user_id,
                    email=f"workspace-owner-second-{second_user_id}@example.test",
                    password_hash="hash",
                    name="Second owner",
                ),
                Workspace(
                    id=workspace_id,
                    owner_id=first_user_id,
                    name="Owner race",
                    type=WorkspaceType.FAMILY,
                    default_currency="RUB",
                ),
                WorkspaceMember(
                    id=first_member_id,
                    workspace_id=workspace_id,
                    user_id=first_user_id,
                    role=WorkspaceRole.OWNER,
                    status=WorkspaceMemberStatus.ACTIVE,
                ),
                WorkspaceMember(
                    id=second_member_id,
                    workspace_id=workspace_id,
                    user_id=second_user_id,
                    role=WorkspaceRole.OWNER,
                    status=WorkspaceMemberStatus.ACTIVE,
                ),
            ]
        )
        await session.commit()

    return OwnerRaceSeed(
        first=first,
        second=second,
        workspace_id=workspace_id,
        user_ids=(first_user_id, second_user_id),
    )


async def delete_owner_race(
    sessions: async_sessionmaker[Any],
    seed: OwnerRaceSeed,
) -> None:
    async with sessions() as session:
        await session.execute(delete(Workspace).where(Workspace.id == seed.workspace_id))
        await session.execute(delete(User).where(User.id.in_(seed.user_ids)))
        await session.commit()


def workspace_test_settings() -> Settings:
    return Settings(auth_secret_key="postgres-workspace-concurrency-secret")
