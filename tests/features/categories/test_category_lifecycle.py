from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.categories.models import Category, CategoryKind
from app.features.categories.service import (
    CategoryArchiveBlockedError,
    CategoryDeleteBlockedError,
    CategoryLifecycleConflictError,
    CategoryNotFoundError,
    CategoryService,
)


@pytest.mark.asyncio
async def test_archive_blocks_active_rules_without_changing_history() -> None:
    category, service, session, repository = category_service(is_active=True)
    repository.count_active_rules_by_category.return_value = {category.id: 2}

    with pytest.raises(CategoryArchiveBlockedError) as blocked:
        await service.set_active(
            workspace_id=category.workspace_id,
            category_id=category.id,
            is_active=False,
            expected_status=True,
            expected_updated_at=category.updated_at,
        )

    assert blocked.value.active_rule_count == 2
    assert category.is_active
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_lifecycle_rejects_missing_wrong_state_and_stale_snapshot() -> None:
    category, service, session, repository = category_service(is_active=True)

    with pytest.raises(CategoryLifecycleConflictError):
        await service.set_active(
            workspace_id=category.workspace_id,
            category_id=category.id,
            is_active=False,
            expected_status=False,
            expected_updated_at=category.updated_at,
        )
    with pytest.raises(CategoryLifecycleConflictError):
        await service.set_active(
            workspace_id=category.workspace_id,
            category_id=category.id,
            is_active=False,
            expected_status=True,
            expected_updated_at=category.updated_at - timedelta(seconds=1),
        )

    repository.get_for_workspace.return_value = None
    with pytest.raises(CategoryNotFoundError):
        await service.set_active(
            workspace_id=uuid4(),
            category_id=category.id,
            is_active=False,
            expected_status=True,
            expected_updated_at=category.updated_at,
        )
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_archive_and_restore_only_change_reference_availability() -> None:
    category, service, session, repository = category_service(is_active=True)

    archived = await service.set_active(
        workspace_id=category.workspace_id,
        category_id=category.id,
        is_active=False,
        expected_status=True,
        expected_updated_at=category.updated_at,
    )
    restored = await service.set_active(
        workspace_id=category.workspace_id,
        category_id=category.id,
        is_active=True,
        expected_status=False,
        expected_updated_at=category.updated_at,
    )

    assert archived is category
    assert restored is category
    assert category.is_active
    assert session.commit.await_count == 2
    assert session.refresh.await_count == 2
    repository.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_blocks_every_financial_and_reference_dependency() -> None:
    category, service, session, repository = category_service(is_active=False)
    repository.count_all_operations_by_category.return_value = {category.id: 2}
    repository.count_rules_by_category.return_value = {category.id: 3}
    repository.count_raw_suggestions_by_category.return_value = {category.id: 4}
    repository.count_child_categories_by_parent.return_value = {category.id: 1}

    with pytest.raises(CategoryDeleteBlockedError) as blocked:
        await service.delete_archived_custom(
            workspace_id=category.workspace_id,
            category_id=category.id,
            expected_status=False,
            expected_updated_at=category.updated_at,
        )

    assert blocked.value.dependencies.operation_count == 2
    assert blocked.value.dependencies.rule_count == 3
    assert blocked.value.dependencies.raw_suggestion_count == 4
    assert blocked.value.dependencies.child_category_count == 1
    repository.delete.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_removes_only_unused_archived_custom_category() -> None:
    category, service, session, repository = category_service(is_active=False)

    deleted = await service.delete_archived_custom(
        workspace_id=category.workspace_id,
        category_id=category.id,
        expected_status=False,
        expected_updated_at=category.updated_at,
    )

    assert deleted.id == category.id
    assert deleted.name == category.name
    repository.delete.assert_awaited_once_with(category)
    session.commit.assert_awaited_once()


def category_service(
    *,
    is_active: bool,
) -> tuple[Category, CategoryService, Any, Any]:
    workspace_id = uuid4()
    category = Category(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Продукты",
        kind=CategoryKind.EXPENSE,
        is_active=is_active,
        is_system=False,
        updated_at=datetime(2026, 8, 1, 8, 30, tzinfo=UTC),
    )
    session = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    repository = SimpleNamespace(
        get_for_workspace=AsyncMock(return_value=category),
        count_active_rules_by_category=AsyncMock(return_value={}),
        count_all_operations_by_category=AsyncMock(return_value={}),
        count_rules_by_category=AsyncMock(return_value={}),
        count_raw_suggestions_by_category=AsyncMock(return_value={}),
        count_child_categories_by_parent=AsyncMock(return_value={}),
        delete=AsyncMock(),
    )
    service = CategoryService(cast(AsyncSession, session))
    service.categories = cast(Any, repository)
    return category, service, session, repository
