import os
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.features.ledger.domain.types import OperationType
from app.features.users.models import User
from app.features.workspaces.activity_repository import WorkspaceActivityRepository
from app.features.workspaces.application.activity import (
    ACTIVITY_EVENT_TYPES_BY_SCOPE,
    ACTIVITY_ITEM_SCOPE_BY_EVENT_TYPE,
    FINANCE_ACTIVITY_EVENT_TYPES,
    TEAM_ACTIVITY_EVENT_TYPES,
    WorkspaceActivityService,
    activity_item,
)
from app.features.workspaces.application.activity_details import (
    ManualOperationCreatedActivityDetails,
)
from app.features.workspaces.application.activity_writer import WorkspaceActivityWriter
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
from app.features.workspaces.schemas import (
    WorkspaceActivityEntityType,
    WorkspaceActivityScope,
    WorkspaceActivitySummaryCode,
)
from app.features.workspaces.service import WorkspaceContext


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


def test_activity_projection_allows_only_safe_import_details() -> None:
    document_id = uuid4()
    item_id = uuid4()
    event = WorkspaceAuditEvent(
        id=uuid4(),
        workspace_id=uuid4(),
        event_type=WorkspaceAuditEventType.IMPORT_REVIEW_ITEM_CONFIRMED,
        actor_user_id=None,
        entity_type="operation",
        entity_id=uuid4(),
        details={
            "payload_version": 1,
            "document_id": str(document_id),
            "item_id": str(item_id),
            "affected_item_count": 2,
            "raw_text": "must-not-leak",
        },
        created_at=datetime(2026, 8, 10, 10, 30, tzinfo=UTC),
    )
    event.actor = None
    event.target_user = None

    item = activity_item(event)

    assert item.summary_code == "import_review_item_confirmed"
    assert item.details.document_id == document_id
    assert item.details.item_id == item_id
    assert item.details.affected_item_count == 2
    assert "raw_text" not in item.details.model_dump()


def test_activity_projection_supports_debt_payment_details() -> None:
    payment_id = uuid4()
    event = WorkspaceAuditEvent(
        id=uuid4(),
        workspace_id=uuid4(),
        event_type=WorkspaceAuditEventType.DEBT_PAYMENT_RECORDED,
        actor_user_id=None,
        entity_type="debt",
        entity_id=uuid4(),
        details={
            "payload_version": 1,
            "payment_id": str(payment_id),
        },
        created_at=datetime(2026, 8, 10, 10, 30, tzinfo=UTC),
    )
    event.actor = None
    event.target_user = None

    item = activity_item(event)

    assert item.summary_code == "debt_payment_recorded"
    assert item.details.payment_id == payment_id


def test_activity_projection_allows_only_sanitized_document_filename() -> None:
    event = WorkspaceAuditEvent(
        id=uuid4(),
        workspace_id=uuid4(),
        event_type=WorkspaceAuditEventType.DOCUMENT_UPLOADED,
        actor_user_id=None,
        entity_type="uploaded_document",
        entity_id=uuid4(),
        details={
            "payload_version": 1,
            "display_filename": "statement.pdf",
            "storage_key": "must-not-leak",
        },
        created_at=datetime(2026, 8, 10, 10, 30, tzinfo=UTC),
    )
    event.actor = None
    event.target_user = None

    item = activity_item(event)

    assert item.summary_code == "document_uploaded"
    assert item.details.display_filename == "statement.pdf"
    assert "storage_key" not in item.details.model_dump()


def test_activity_projection_mapping_covers_every_visible_event() -> None:
    visible_events = set(WorkspaceAuditEventType)

    assert TEAM_ACTIVITY_EVENT_TYPES.isdisjoint(FINANCE_ACTIVITY_EVENT_TYPES)
    assert TEAM_ACTIVITY_EVENT_TYPES | FINANCE_ACTIVITY_EVENT_TYPES == visible_events
    assert ACTIVITY_EVENT_TYPES_BY_SCOPE == {
        WorkspaceActivityScope.ALL: None,
        WorkspaceActivityScope.FINANCE: FINANCE_ACTIVITY_EVENT_TYPES,
        WorkspaceActivityScope.TEAM: TEAM_ACTIVITY_EVENT_TYPES,
    }
    assert set(ACTIVITY_ITEM_SCOPE_BY_EVENT_TYPE) == visible_events
    assert {code.value for code in WorkspaceActivitySummaryCode} == {
        event.value for event in visible_events
    }


def test_activity_projection_exposes_safe_available_entity_reference() -> None:
    operation_id = uuid4()
    event = WorkspaceAuditEvent(
        id=uuid4(),
        workspace_id=uuid4(),
        event_type=WorkspaceAuditEventType.MANUAL_OPERATION_CREATED,
        actor_user_id=None,
        entity_type="operation",
        entity_id=operation_id,
        details={"display_label": "Аренда"},
        created_at=datetime(2026, 8, 10, 10, 30, tzinfo=UTC),
    )
    event.actor = None
    event.target_user = None

    item = activity_item(
        event,
        frozenset({(WorkspaceActivityEntityType.OPERATION, operation_id)}),
    )

    assert item.scope == "finance"
    assert item.entity is not None
    assert item.entity.model_dump() == {
        "type": WorkspaceActivityEntityType.OPERATION,
        "id": operation_id,
        "display_label": "Аренда",
        "is_available": True,
    }


async def test_manual_activity_writer_uses_authenticated_actor_and_typed_details() -> None:
    workspace_id = uuid4()
    actor_id = uuid4()
    operation_id = uuid4()
    repository = SimpleNamespace(append=AsyncMock())
    writer = WorkspaceActivityWriter(cast(Any, repository))

    await writer.manual_operation_created(
        context=cast(
            WorkspaceContext,
            SimpleNamespace(
                workspace=SimpleNamespace(id=workspace_id),
                user=SimpleNamespace(id=actor_id),
            ),
        ),
        operation_id=operation_id,
        details=ManualOperationCreatedActivityDetails(
            display_label="Доход",
            operation_type=OperationType.INCOME,
        ),
    )

    repository.append.assert_awaited_once_with(
        workspace_id=workspace_id,
        event_type=WorkspaceAuditEventType.MANUAL_OPERATION_CREATED,
        actor_user_id=actor_id,
        entity_type="operation",
        entity_id=operation_id,
        details={
            "payload_version": 1,
            "display_label": "Доход",
            "operation_type": "income",
        },
    )


async def test_activity_reader_authorizes_target_membership_and_builds_cursor() -> None:
    workspace_id = uuid4()
    actor_id = uuid4()
    event = WorkspaceAuditEvent(
        id=uuid4(),
        workspace_id=workspace_id,
        event_type=WorkspaceAuditEventType.MANUAL_OPERATION_CREATED,
        actor_user_id=None,
        entity_type="operation",
        entity_id=uuid4(),
        details={"display_label": "Удалённая операция"},
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
        list_recent=AsyncMock(return_value=[event, event]),
        available_entity_keys=AsyncMock(return_value=frozenset()),
    )
    cast(Any, service)._workspaces = repository
    cast(Any, service)._activity = repository

    result = await service.read(
        actor_user_id=actor_id,
        workspace_id=workspace_id,
        limit=1,
        scope=WorkspaceActivityScope.FINANCE,
    )

    assert [item.id for item in result.items] == [event.id]
    assert result.next_cursor is not None
    assert result.next_cursor.before_id == event.id
    assert result.items[0].entity is not None
    assert result.items[0].entity.is_available is False
    assert result.next_cursor.scope == WorkspaceActivityScope.FINANCE
    repository.list_recent.assert_awaited_once()
    assert repository.list_recent.await_args.kwargs["event_types"] == (
        ACTIVITY_EVENT_TYPES_BY_SCOPE[WorkspaceActivityScope.FINANCE]
    )
    repository.available_entity_keys.assert_awaited_once_with(
        workspace_id,
        {WorkspaceActivityEntityType.OPERATION: {event.entity_id}},
    )


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
        list_recent=AsyncMock(),
    )
    cast(Any, service)._workspaces = repository
    cast(Any, service)._activity = repository

    with pytest.raises(error_type):
        await service.read(actor_user_id=uuid4(), workspace_id=uuid4())

    repository.list_recent.assert_not_awaited()


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

            repository = WorkspaceActivityRepository(session)
            first = await repository.list_recent(workspace_id, limit=2)
            second = await repository.list_recent(
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
