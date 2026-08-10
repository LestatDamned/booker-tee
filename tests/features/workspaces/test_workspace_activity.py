import os
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.features.users.models import User
from app.features.workspaces.application.activity import (
    WorkspaceActivityService,
    activity_item,
)
from app.features.workspaces.domain.types import (
    WorkspaceAuditEventType,
    WorkspaceMemberStatus,
    WorkspaceRole,
)
from app.features.workspaces.errors import (
    WorkspaceActivityForbiddenError,
    WorkspaceNotFoundError,
)
from app.features.workspaces.models import Workspace, WorkspaceAuditEvent
from app.features.workspaces.repository import WorkspaceRepository


def test_activity_projection_supports_historical_actions_and_safe_details() -> None:
    actor = User(
        id=uuid4(),
        email="owner@example.test",
        password_hash="hash",
        name="Owner",
    )
    target = User(
        id=uuid4(),
        email="member@example.test",
        password_hash="hash",
        name=None,
    )
    event = WorkspaceAuditEvent(
        id=uuid4(),
        workspace_id=uuid4(),
        event_type=WorkspaceAuditEventType.WORKSPACE_UPDATED,
        actor_user_id=actor.id,
        target_user_id=target.id,
        entity_type="workspace",
        entity_id=uuid4(),
        details={
            "action": "ownership_transferred",
            "old_owner_id": str(actor.id),
            "new_owner_id": str(target.id),
            "secret": "must-not-leak",
        },
        created_at=datetime(2026, 8, 10, 10, 30, tzinfo=UTC),
    )
    event.actor = actor
    event.target_user = target

    item = activity_item(event)

    assert item.summary_code == "ownership_transferred"
    assert item.actor is not None and item.actor.display_name == "Owner"
    assert item.target is not None and item.target.display_name == "member@example.test"
    assert "secret" not in item.details.model_dump()
    assert "old_owner_id" not in item.details.model_dump()


async def test_activity_reader_authorizes_target_membership_and_builds_cursor() -> None:
    workspace_id = uuid4()
    actor_id = uuid4()
    event = WorkspaceAuditEvent(
        id=uuid4(),
        workspace_id=workspace_id,
        event_type=WorkspaceAuditEventType.WORKSPACE_CREATED,
        actor_user_id=None,
        entity_type="workspace",
        entity_id=workspace_id,
        details={},
        created_at=datetime(2026, 8, 10, 10, 30, tzinfo=UTC),
    )
    event.actor = None
    event.target_user = None
    service = WorkspaceActivityService(cast(Any, SimpleNamespace()))
    repository = SimpleNamespace(
        get_visible_membership_for_user=AsyncMock(
            return_value=SimpleNamespace(
                role=WorkspaceRole.OWNER,
                status=WorkspaceMemberStatus.ACTIVE,
            )
        ),
        list_recent_audit_events=AsyncMock(return_value=[event, event]),
    )
    cast(Any, service)._workspaces = repository

    result = await service.read(
        actor_user_id=actor_id,
        workspace_id=workspace_id,
        limit=1,
    )

    assert [item.id for item in result.items] == [event.id]
    assert result.next_cursor is not None
    assert result.next_cursor.before_id == event.id


@pytest.mark.parametrize(
    ("membership", "error_type"),
    [
        (None, WorkspaceNotFoundError),
        (
            SimpleNamespace(
                role=WorkspaceRole.EDITOR,
                status=WorkspaceMemberStatus.ACTIVE,
            ),
            WorkspaceActivityForbiddenError,
        ),
    ],
)
async def test_activity_reader_masks_foreign_and_forbids_known_non_manager(
    membership,
    error_type,
) -> None:
    service = WorkspaceActivityService(cast(Any, SimpleNamespace()))
    repository = SimpleNamespace(
        get_visible_membership_for_user=AsyncMock(return_value=membership),
        list_recent_audit_events=AsyncMock(),
    )
    cast(Any, service)._workspaces = repository

    with pytest.raises(error_type):
        await service.read(actor_user_id=uuid4(), workspace_id=uuid4())

    repository.list_recent_audit_events.assert_not_awaited()


@pytest.mark.skipif(
    not os.getenv("BOOKER_TEE_TEST_DATABASE_URL"),
    reason="BOOKER_TEE_TEST_DATABASE_URL is required for PostgreSQL activity tests.",
)
async def test_activity_keyset_paginates_equal_timestamps_without_gaps() -> None:
    database_url = os.environ["BOOKER_TEE_TEST_DATABASE_URL"]
    engine = create_async_engine(database_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    owner_id = uuid4()
    workspace_id = uuid4()
    created_at = datetime(2026, 8, 10, 10, 30, tzinfo=UTC)
    event_ids = [UUID(int=value) for value in (1, 2, 3)]
    try:
        async with sessions() as session:
            session.add(
                User(
                    id=owner_id,
                    email=f"activity-{owner_id}@example.test",
                    password_hash="hash",
                    name="Activity owner",
                )
            )
            session.add(Workspace(id=workspace_id, owner_id=owner_id, name="Activity"))
            session.add_all(
                WorkspaceAuditEvent(
                    id=event_id,
                    workspace_id=workspace_id,
                    event_type=WorkspaceAuditEventType.WORKSPACE_UPDATED,
                    actor_user_id=owner_id,
                    entity_type="workspace",
                    entity_id=workspace_id,
                    details={},
                    created_at=created_at,
                )
                for event_id in event_ids
            )
            await session.commit()

            repository = WorkspaceRepository(session)
            first = await repository.list_recent_audit_events(workspace_id, limit=2)
            second = await repository.list_recent_audit_events(
                workspace_id,
                limit=2,
                before_created_at=first[-1].created_at,
                before_id=first[-1].id,
            )

            assert [event.id for event in first + second] == list(reversed(event_ids))
    finally:
        async with sessions() as session:
            await session.execute(delete(Workspace).where(Workspace.id == workspace_id))
            await session.execute(delete(User).where(User.id == owner_id))
            await session.commit()
        await engine.dispose()
