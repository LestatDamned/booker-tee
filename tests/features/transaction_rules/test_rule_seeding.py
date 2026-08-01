from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.categories.models import Category, CategoryKind
from app.features.transaction_rules.application import fixture_seeding
from app.features.transaction_rules.application.fixture_seeding import (
    DefaultMerchantRuleSeed,
    DefaultMerchantRuleSeeder,
)
from app.features.transaction_rules.models import (
    MoneyDirection,
    TransactionRule,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)


@pytest.mark.asyncio
async def test_seed_is_repeat_safe_and_never_mutates_existing_rule(monkeypatch) -> None:
    seed = DefaultMerchantRuleSeed("Продукты", CategoryKind.EXPENSE, "OZON")
    monkeypatch.setattr(fixture_seeding, "DEFAULT_MERCHANT_RULE_SEEDS", [seed])
    workspace_id = uuid4()
    category = Category(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Продукты",
        kind=CategoryKind.EXPENSE,
        is_active=True,
    )
    existing = TransactionRule(
        id=uuid4(),
        workspace_id=workspace_id,
        name="User OZON",
        is_active=False,
        pattern="OZON",
        match_type=TransactionRuleMatchType.EXACT,
        application_mode=TransactionRuleApplicationMode.SUGGEST,
        direction=MoneyDirection.ANY,
        category_id=category.id,
    )
    seeder, session, rules, categories, workspaces = seeder_with_mocks(
        rules=[existing],
        categories=[category],
    )

    result = await seeder.seed(context(workspace_id))

    assert result.created_rule_count == 0
    assert result.existing_rule_count == 1
    assert result.created_category_count == 0
    assert existing.name == "User OZON"
    assert existing.is_active is False
    assert existing.match_type == TransactionRuleMatchType.EXACT
    assert existing.application_mode == TransactionRuleApplicationMode.SUGGEST
    assert existing.direction == MoneyDirection.ANY
    rules.create.assert_not_awaited()
    categories.create.assert_not_awaited()
    workspaces.lock_for_update.assert_awaited_once_with(workspace_id)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_seed_creates_only_missing_category_and_rule(monkeypatch) -> None:
    seed = DefaultMerchantRuleSeed("Маркетплейсы", CategoryKind.EXPENSE, "OZON")
    monkeypatch.setattr(fixture_seeding, "DEFAULT_MERCHANT_RULE_SEEDS", [seed])
    workspace_id = uuid4()
    created_category = Category(
        id=uuid4(),
        workspace_id=workspace_id,
        name=seed.category_name,
        kind=seed.category_kind,
        is_active=True,
    )
    seeder, session, rules, categories, _workspaces = seeder_with_mocks(
        rules=[],
        categories=[],
    )
    categories.create.return_value = created_category
    rules.create.side_effect = lambda rule: rule

    result = await seeder.seed(context(workspace_id))

    assert result.created_rule_count == 1
    assert result.existing_rule_count == 0
    assert result.created_category_count == 1
    created_rule = result.created_rules[0]
    assert created_rule.workspace_id == workspace_id
    assert created_rule.category_id == created_category.id
    assert created_rule.application_mode == TransactionRuleApplicationMode.AUTO_APPLY
    session.commit.assert_awaited_once()


def seeder_with_mocks(
    *,
    rules: list[TransactionRule],
    categories: list[Category],
) -> tuple[DefaultMerchantRuleSeeder, Any, Any, Any, Any]:
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    rule_repository = SimpleNamespace(
        list_for_workspace=AsyncMock(return_value=rules),
        create=AsyncMock(),
    )
    category_repository = SimpleNamespace(
        list_for_workspace=AsyncMock(return_value=categories),
        create=AsyncMock(),
    )
    workspace_repository = SimpleNamespace(
        lock_for_update=AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    )
    seeder = DefaultMerchantRuleSeeder(cast(AsyncSession, session))
    seeder.rules = cast(Any, rule_repository)
    seeder.categories = cast(Any, category_repository)
    seeder.workspaces = cast(Any, workspace_repository)
    return seeder, session, rule_repository, category_repository, workspace_repository


def context(workspace_id):
    return SimpleNamespace(
        workspace=SimpleNamespace(id=workspace_id),
        user=SimpleNamespace(id=uuid4()),
    )
