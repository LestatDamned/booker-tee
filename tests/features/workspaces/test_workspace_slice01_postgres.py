import asyncio
import os
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import hash_session_token
from app.db.base import utc_now
from app.features.users.models import User, UserSession
from app.features.workspaces.application.creation import WorkspaceCreator
from app.features.workspaces.application.switching import WorkspaceSessionSwitcher
from app.features.workspaces.commands import CreateWorkspaceCommand
from app.features.workspaces.domain.types import (
    WorkspaceAuditEventType,
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.errors import WorkspaceSwitchConflictError
from app.features.workspaces.models import Workspace, WorkspaceAuditEvent, WorkspaceMember

TEST_DATABASE_URL = os.getenv("BOOKER_TEE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="BOOKER_TEE_TEST_DATABASE_URL is required for PostgreSQL Slice 1 tests.",
)


async def test_postgres_switch_lock_allows_one_expected_current_winner() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    seed = await seed_switch(sessions)

    async def switch(target_workspace_id: UUID):
        async with sessions() as session:
            actor = await session.get(User, seed.user_id)
            assert actor is not None
            try:
                return await WorkspaceSessionSwitcher(session).switch(
                    actor=actor,
                    session_token=seed.session_token,
                    target_workspace_id=target_workspace_id,
                    expected_current_workspace_id=seed.current_workspace_id,
                )
            except WorkspaceSwitchConflictError as error:
                return error

    try:
        results = await asyncio.gather(*(switch(target_id) for target_id in seed.target_ids))
        successes = [result for result in results if not isinstance(result, BaseException)]
        conflicts = [
            result for result in results if isinstance(result, WorkspaceSwitchConflictError)
        ]
        async with sessions() as session:
            persisted = await session.get(UserSession, seed.user_session_id)
            assert persisted is not None

        assert len(successes) == 1
        assert len(conflicts) == 1
        assert persisted.current_workspace_id in seed.target_ids
        assert conflicts[0].current_workspace_id == persisted.current_workspace_id
    finally:
        await delete_seed(sessions, seed.user_id, seed.workspace_ids)
        await engine.dispose()


async def test_postgres_concurrent_create_replays_one_committed_workspace() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    seed = await seed_switch(sessions, target_count=0)
    idempotency_key = uuid4()
    command = CreateWorkspaceCommand(
        name="Concurrent workspace",
        workspace_type=WorkspaceType.PROJECT,
        default_currency="RUB",
    )

    async def create_once():
        async with sessions() as session:
            actor = await session.get(User, seed.user_id)
            assert actor is not None
            return await WorkspaceCreator(session).create(
                actor=actor,
                session_token=seed.session_token,
                command=command,
                idempotency_key=idempotency_key,
            )

    created_workspace_id: UUID | None = None
    try:
        results = await asyncio.gather(create_once(), create_once())
        created_workspace_id = results[0].workspace.id
        assert results[1].workspace.id == created_workspace_id
        assert sorted(result.replayed for result in results) == [False, True]
        async with sessions() as session:
            workspace_count = await session.scalar(
                select(func.count())
                .select_from(Workspace)
                .where(Workspace.id == created_workspace_id)
            )
            membership_count = await session.scalar(
                select(func.count())
                .select_from(WorkspaceMember)
                .where(
                    WorkspaceMember.workspace_id == created_workspace_id,
                    WorkspaceMember.user_id == seed.user_id,
                )
            )
            audit_count = await session.scalar(
                select(func.count())
                .select_from(WorkspaceAuditEvent)
                .where(
                    WorkspaceAuditEvent.workspace_id == created_workspace_id,
                    WorkspaceAuditEvent.event_type == WorkspaceAuditEventType.WORKSPACE_CREATED,
                )
            )
            user_session = await session.get(UserSession, seed.user_session_id)
            assert user_session is not None

        assert (workspace_count, membership_count, audit_count) == (1, 1, 1)
        assert user_session.current_workspace_id == created_workspace_id
    finally:
        workspace_ids = (
            (*seed.workspace_ids, created_workspace_id)
            if created_workspace_id is not None
            else seed.workspace_ids
        )
        await delete_seed(sessions, seed.user_id, workspace_ids)
        await engine.dispose()


class SliceSeed:
    def __init__(
        self,
        *,
        user_id: UUID,
        user_session_id: UUID,
        session_token: str,
        current_workspace_id: UUID,
        target_ids: tuple[UUID, ...],
    ) -> None:
        self.user_id = user_id
        self.user_session_id = user_session_id
        self.session_token = session_token
        self.current_workspace_id = current_workspace_id
        self.target_ids = target_ids
        self.workspace_ids = (current_workspace_id, *target_ids)


async def seed_switch(
    sessions: async_sessionmaker[Any],
    *,
    target_count: int = 2,
) -> SliceSeed:
    user_id = uuid4()
    user_session_id = uuid4()
    current_workspace_id = uuid4()
    target_ids = tuple(uuid4() for _ in range(target_count))
    session_token = f"workspace-slice01-{user_session_id}"
    async with sessions() as session:
        session.add(
            User(
                id=user_id,
                email=f"workspace-slice01-{user_id}@example.test",
                password_hash="hash",
                name="Slice 1 actor",
            )
        )
        for index, workspace_id in enumerate((current_workspace_id, *target_ids)):
            session.add(
                Workspace(
                    id=workspace_id,
                    owner_id=user_id,
                    name=f"Workspace {index}",
                    type=WorkspaceType.PERSONAL,
                    default_currency="RUB",
                )
            )
            session.add(
                WorkspaceMember(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    role=WorkspaceRole.OWNER,
                    status=WorkspaceMemberStatus.ACTIVE,
                )
            )
        session.add(
            UserSession(
                id=user_session_id,
                user_id=user_id,
                current_workspace_id=current_workspace_id,
                session_token_hash=hash_session_token(session_token),
                expires_at=utc_now() + timedelta(hours=1),
            )
        )
        await session.commit()
    return SliceSeed(
        user_id=user_id,
        user_session_id=user_session_id,
        session_token=session_token,
        current_workspace_id=current_workspace_id,
        target_ids=target_ids,
    )


async def delete_seed(
    sessions: async_sessionmaker[Any],
    user_id: UUID,
    workspace_ids: tuple[UUID, ...],
) -> None:
    async with sessions() as session:
        await session.execute(delete(Workspace).where(Workspace.id.in_(workspace_ids)))
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()
