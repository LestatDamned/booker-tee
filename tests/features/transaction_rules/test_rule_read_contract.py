from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.transaction_rules.application.rule_queries import TransactionRuleListResult
from app.features.transaction_rules.router import build_rules_page
from app.features.workspaces.service import WorkspaceContext


@pytest.mark.asyncio
async def test_rules_page_read_is_side_effect_free() -> None:
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    categories = SimpleNamespace(
        list_active=AsyncMock(return_value=[]),
        list_or_seed_defaults=AsyncMock(),
    )
    properties = SimpleNamespace(list_active=AsyncMock(return_value=[]))
    query = SimpleNamespace(
        list_rules_for_page=AsyncMock(
            return_value=TransactionRuleListResult(
                rules=[],
                total_count=0,
                filtered_count=0,
                active_count=0,
                inactive_count=0,
                limit=50,
            )
        )
    )
    context = SimpleNamespace(
        workspace=SimpleNamespace(id=uuid4(), type="personal"),
    )

    with (
        patch(
            "app.features.transaction_rules.router.CategoryService",
            return_value=categories,
        ),
        patch(
            "app.features.transaction_rules.router.PropertyService",
            return_value=properties,
        ),
        patch(
            "app.features.transaction_rules.router.TransactionRuleQueryUseCase",
            return_value=query,
        ),
    ):
        await build_rules_page(
            session=cast(AsyncSession, session),
            context=cast(WorkspaceContext, context),
            can_write=True,
        )

    categories.list_active.assert_awaited_once_with(context.workspace.id)
    categories.list_or_seed_defaults.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()
