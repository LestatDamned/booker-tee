import asyncio
import os
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.features.users.models import User
from app.features.workspaces.application.settings import WorkspaceSettingsService
from app.features.workspaces.commands import UpdateWorkspaceSettingsCommand
from app.features.workspaces.domain.types import (
    WorkspaceAuditEventType,
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.errors import (
    WorkspaceNotFoundError,
    WorkspaceUpdateConflictError,
)
from app.features.workspaces.models import Workspace, WorkspaceAuditEvent, WorkspaceMember

TEST_DATABASE_URL = os.getenv("BOOKER_TEE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="BOOKER_TEE_TEST_DATABASE_URL is required for PostgreSQL settings tests.",
)


async def test_postgres_settings_lock_allows_one_expected_snapshot_winner() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    seed = await seed_settings(sessions)

    async def update_name(name: str):
        async with sessions() as session:
            try:
                return await WorkspaceSettingsService(session).update(
                    actor_user_id=seed.owner_id,
                    workspace_id=seed.workspace_id,
                    command=UpdateWorkspaceSettingsCommand(
                        name=name,
                        workspace_type=WorkspaceType.FAMILY,
                        default_currency="USD",
                        expected_updated_at=seed.updated_at,
                    ),
                )
            except WorkspaceUpdateConflictError as error:
                return error

    try:
        results = await asyncio.gather(
            update_name("Победитель A"),
            update_name("Победитель B"),
        )
        successes = [result for result in results if not isinstance(result, BaseException)]
        conflicts = [
            result for result in results if isinstance(result, WorkspaceUpdateConflictError)
        ]
        async with sessions() as session:
            workspace = await session.get(Workspace, seed.workspace_id)
            audit_count = await session.scalar(
                select(func.count())
                .select_from(WorkspaceAuditEvent)
                .where(
                    WorkspaceAuditEvent.workspace_id == seed.workspace_id,
                    WorkspaceAuditEvent.event_type == WorkspaceAuditEventType.WORKSPACE_UPDATED,
                )
            )
        assert workspace is not None
        assert len(successes) == 1
        assert len(conflicts) == 1
        assert workspace.name in {"Победитель A", "Победитель B"}
        assert workspace.type == WorkspaceType.FAMILY
        assert workspace.default_currency == "USD"
        assert audit_count == 1
    finally:
        await delete_settings_seed(sessions, seed)
        await engine.dispose()


async def test_postgres_settings_masks_foreign_and_missing_workspace() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    seed = await seed_settings(sessions)

    try:
        async with sessions() as session:
            service = WorkspaceSettingsService(session)
            with pytest.raises(WorkspaceNotFoundError) as foreign:
                await service.read(
                    actor_user_id=seed.foreign_user_id,
                    workspace_id=seed.workspace_id,
                )
            with pytest.raises(WorkspaceNotFoundError) as missing:
                await service.read(
                    actor_user_id=seed.foreign_user_id,
                    workspace_id=uuid4(),
                )
        assert str(foreign.value) == str(missing.value)
    finally:
        await delete_settings_seed(sessions, seed)
        await engine.dispose()


class SettingsSeed:
    def __init__(
        self,
        *,
        foreign_user_id: UUID,
        owner_id: UUID,
        updated_at,
        workspace_id: UUID,
    ) -> None:
        self.foreign_user_id = foreign_user_id
        self.owner_id = owner_id
        self.updated_at = updated_at
        self.workspace_id = workspace_id


async def seed_settings(sessions: async_sessionmaker[Any]) -> SettingsSeed:
    owner_id = uuid4()
    foreign_user_id = uuid4()
    workspace_id = uuid4()
    async with sessions() as session:
        session.add_all(
            [
                User(
                    id=owner_id,
                    email=f"workspace-settings-owner-{owner_id}@example.test",
                    password_hash="hash",
                    name="Settings owner",
                ),
                User(
                    id=foreign_user_id,
                    email=f"workspace-settings-foreign-{foreign_user_id}@example.test",
                    password_hash="hash",
                    name="Foreign user",
                ),
            ]
        )
        workspace = Workspace(
            id=workspace_id,
            owner_id=owner_id,
            name="Настройки",
            type=WorkspaceType.PERSONAL,
            default_currency="RUB",
        )
        session.add(workspace)
        session.add(
            WorkspaceMember(
                workspace_id=workspace_id,
                user_id=owner_id,
                role=WorkspaceRole.OWNER,
                status=WorkspaceMemberStatus.ACTIVE,
            )
        )
        await session.commit()
        await session.refresh(workspace)
        return SettingsSeed(
            foreign_user_id=foreign_user_id,
            owner_id=owner_id,
            updated_at=workspace.updated_at,
            workspace_id=workspace_id,
        )


async def delete_settings_seed(
    sessions: async_sessionmaker[Any],
    seed: SettingsSeed,
) -> None:
    async with sessions() as session:
        await session.execute(delete(Workspace).where(Workspace.id == seed.workspace_id))
        await session.execute(
            delete(User).where(User.id.in_([seed.owner_id, seed.foreign_user_id]))
        )
        await session.commit()
