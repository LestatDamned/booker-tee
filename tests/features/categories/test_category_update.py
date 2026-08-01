from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.categories.models import Category, CategoryKind
from app.features.categories.service import CategoryService, CategoryUpdateConflictError


@pytest.mark.asyncio
async def test_category_update_rejects_stale_editor_before_mutation() -> None:
    workspace_id = uuid4()
    updated_at = datetime(2026, 8, 1, 8, 30, tzinfo=UTC)
    category = Category(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Продукты",
        kind=CategoryKind.EXPENSE,
        is_active=True,
        is_system=False,
        updated_at=updated_at,
    )
    commit = AsyncMock()
    refresh = AsyncMock()
    session = cast(
        AsyncSession,
        SimpleNamespace(commit=commit, refresh=refresh),
    )
    service = CategoryService(session)
    service.categories = cast(
        Any,
        SimpleNamespace(
            get_for_workspace=AsyncMock(return_value=category),
            get_by_name_for_workspace=AsyncMock(return_value=None),
        ),
    )

    with pytest.raises(CategoryUpdateConflictError):
        await service.update_custom(
            workspace_id=workspace_id,
            category_id=category.id,
            name="Еда",
            kind=CategoryKind.MIXED,
            notes="Покупки и возвраты",
            expected_updated_at=updated_at - timedelta(seconds=1),
        )

    assert category.name == "Продукты"
    assert category.kind == CategoryKind.EXPENSE
    commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_category_update_commits_without_rewriting_financial_history() -> None:
    workspace_id = uuid4()
    updated_at = datetime(2026, 8, 1, 8, 30, tzinfo=UTC)
    category = Category(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Продукты",
        kind=CategoryKind.EXPENSE,
        is_active=True,
        is_system=False,
        updated_at=updated_at,
    )
    commit = AsyncMock()
    refresh = AsyncMock()
    session = cast(
        AsyncSession,
        SimpleNamespace(commit=commit, refresh=refresh),
    )
    service = CategoryService(session)
    service.categories = cast(
        Any,
        SimpleNamespace(
            get_for_workspace=AsyncMock(return_value=category),
            get_by_name_for_workspace=AsyncMock(return_value=None),
        ),
    )

    result = await service.update_custom(
        workspace_id=workspace_id,
        category_id=category.id,
        name="  Еда и покупки ",
        kind=CategoryKind.MIXED,
        notes="  Покупки   и возвраты ",
        expected_updated_at=updated_at,
    )

    assert result is category
    assert category.name == "Еда и покупки"
    assert category.kind == CategoryKind.MIXED
    assert category.notes == "Покупки и возвраты"
    commit.assert_awaited_once()
    refresh.assert_awaited_once_with(category)
