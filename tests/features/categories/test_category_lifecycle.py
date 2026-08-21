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


@pytest.mark.parametrize(
    ("expected_status", "updated_at_delta"),
    [
        pytest.param(False, timedelta(0), id="wrong-state"),
        pytest.param(True, timedelta(seconds=-1), id="stale-snapshot"),
    ],
)
async def test_lifecycle_rejects_conflicting_snapshot(
    expected_status: bool,
    updated_at_delta: timedelta,
) -> None:
    category, service, session, _repository = category_service(is_active=True)

    with pytest.raises(CategoryLifecycleConflictError):
        await service.set_active(
            workspace_id=category.workspace_id,
            category_id=category.id,
            is_active=False,
            expected_status=expected_status,
            expected_updated_at=category.updated_at + updated_at_delta,
        )

    assert category.is_active
    session.commit.assert_not_awaited()


async def test_lifecycle_masks_category_outside_workspace_as_not_found() -> None:
    category, service, session, repository = category_service(is_active=True)
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


async def test_archive_only_changes_reference_availability() -> None:
    category, service, session, repository = category_service(is_active=True)

    archived = await service.set_active(
        workspace_id=category.workspace_id,
        category_id=category.id,
        is_active=False,
        expected_status=True,
        expected_updated_at=category.updated_at,
    )

    assert archived is category
    assert category.is_active is False
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(category)
    repository.delete.assert_not_awaited()


async def test_restore_only_changes_reference_availability() -> None:
    category, service, session, repository = category_service(is_active=False)

    restored = await service.set_active(
        workspace_id=category.workspace_id,
        category_id=category.id,
        is_active=True,
        expected_status=False,
        expected_updated_at=category.updated_at,
    )

    assert restored is category
    assert category.is_active is True
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(category)
    repository.delete.assert_not_awaited()


@pytest.mark.parametrize(
    ("repository_method", "dependency_field", "count"),
    [
        pytest.param(
            "count_all_operations_by_category",
            "operation_count",
            2,
            id="operations",
        ),
        pytest.param("count_rules_by_category", "rule_count", 3, id="rules"),
        pytest.param(
            "count_raw_suggestions_by_category",
            "raw_suggestion_count",
            4,
            id="raw-suggestions",
        ),
        pytest.param(
            "count_child_categories_by_parent",
            "child_category_count",
            1,
            id="child-categories",
        ),
    ],
)
async def test_delete_blocks_each_financial_or_reference_dependency(
    repository_method: str,
    dependency_field: str,
    count: int,
) -> None:
    category, service, session, repository = category_service(is_active=False)
    getattr(repository, repository_method).return_value = {category.id: count}

    with pytest.raises(CategoryDeleteBlockedError) as blocked:
        await service.delete_archived_custom(
            workspace_id=category.workspace_id,
            category_id=category.id,
            expected_status=False,
            expected_updated_at=category.updated_at,
        )

    assert getattr(blocked.value.dependencies, dependency_field) == count
    repository.delete.assert_not_awaited()
    session.commit.assert_not_awaited()


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
