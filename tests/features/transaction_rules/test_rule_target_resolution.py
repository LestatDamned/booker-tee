from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import Account, AccountType
from app.features.categories.models import Category, CategoryKind
from app.features.properties.models import Property, PropertyStatus
from app.features.transaction_rules.application.target_resolution import (
    TransactionRuleTargetResolver,
)
from app.features.transaction_rules.errors import (
    TransactionRuleActivationBlockedError,
    TransactionRuleValidationError,
)
from app.features.transaction_rules.models import TransactionRule


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["category", "property", "account"])
async def test_create_rejects_foreign_or_missing_target(target: str) -> None:
    resolver = target_resolver()
    setattr(
        resolver,
        f"{target}s" if target != "property" else "properties",
        SimpleNamespace(get_for_workspace=AsyncMock(return_value=None)),
    )
    target_id = uuid4()

    with pytest.raises(TransactionRuleValidationError):
        await resolver.resolve_for_create(
            workspace_id=uuid4(),
            category_id=target_id if target == "category" else None,
            property_id=target_id if target == "property" else None,
            account_id=target_id if target == "account" else None,
        )


@pytest.mark.asyncio
async def test_update_can_retain_archived_targets_but_activation_revalidates_them() -> None:
    workspace_id = uuid4()
    category = Category(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Архив",
        kind=CategoryKind.EXPENSE,
        is_active=False,
    )
    property_ = Property(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Старый объект",
        status=PropertyStatus.ARCHIVED,
    )
    account = Account(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Старый счёт",
        type=AccountType.CARD,
        currency="RUB",
        is_active=False,
    )
    rule = TransactionRule(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Rule",
        pattern="RULE",
        category_id=category.id,
        property_id=property_.id,
        account_id=account.id,
        is_active=False,
    )
    resolver = target_resolver(
        category=category,
        property_=property_,
        account=account,
    )

    targets = await resolver.resolve_for_update(
        workspace_id=workspace_id,
        rule=rule,
        category_id=category.id,
        property_id=property_.id,
    )

    assert targets.category is category
    assert targets.property is property_
    assert targets.account is account
    with pytest.raises(TransactionRuleActivationBlockedError):
        await resolver.validate_for_activation(workspace_id=workspace_id, rule=rule)


def target_resolver(
    *,
    category: Category | None = None,
    property_: Property | None = None,
    account: Account | None = None,
) -> TransactionRuleTargetResolver:
    resolver = TransactionRuleTargetResolver(cast(AsyncSession, SimpleNamespace()))
    resolver.categories = cast(
        Any,
        SimpleNamespace(get_for_workspace=AsyncMock(return_value=category)),
    )
    resolver.properties = cast(
        Any,
        SimpleNamespace(get_for_workspace=AsyncMock(return_value=property_)),
    )
    resolver.accounts = cast(
        Any,
        SimpleNamespace(get_for_workspace=AsyncMock(return_value=account)),
    )
    return resolver
