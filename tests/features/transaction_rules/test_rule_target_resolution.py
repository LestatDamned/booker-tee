from types import SimpleNamespace
from typing import cast
from unittest.mock import create_autospec
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import Account, AccountType
from app.features.accounts.repository import AccountRepository
from app.features.categories.models import Category, CategoryKind
from app.features.categories.repository import CategoryRepository
from app.features.properties.models import Property, PropertyStatus
from app.features.properties.repository import PropertyRepository
from app.features.transaction_rules.application.target_resolution import (
    TransactionRuleTargetResolver,
)
from app.features.transaction_rules.errors import (
    TransactionRuleActivationBlockedError,
    TransactionRuleValidationError,
)
from app.features.transaction_rules.models import TransactionRule


@pytest.mark.parametrize(
    ("target", "expected_field"),
    [
        pytest.param("category", "categoryId", id="category"),
        pytest.param("property", "propertyId", id="property"),
        pytest.param("account", "accountId", id="account"),
    ],
)
async def test_create_rejects_foreign_or_missing_target(
    target: str,
    expected_field: str,
) -> None:
    resolver = target_resolver()
    target_id = uuid4()

    with pytest.raises(TransactionRuleValidationError) as caught:
        await resolver.resolve_for_create(
            workspace_id=uuid4(),
            category_id=target_id if target == "category" else None,
            property_id=target_id if target == "property" else None,
            account_id=target_id if target == "account" else None,
        )

    assert caught.value.field == expected_field


async def test_update_can_retain_archived_targets() -> None:
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


@pytest.mark.parametrize(
    ("target", "expected_field"),
    [
        pytest.param("category", "categoryId", id="category"),
        pytest.param("property", "propertyId", id="property"),
        pytest.param("account", "accountId", id="account"),
    ],
)
async def test_activation_rejects_each_archived_target(
    target: str,
    expected_field: str,
) -> None:
    workspace_id = uuid4()
    category = Category(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Категория",
        kind=CategoryKind.EXPENSE,
        is_active=target != "category",
    )
    property_ = Property(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Объект",
        status=PropertyStatus.ARCHIVED if target == "property" else PropertyStatus.ACTIVE,
    )
    account = Account(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Счёт",
        type=AccountType.CARD,
        currency="RUB",
        is_active=target != "account",
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
    resolver = target_resolver(category=category, property_=property_, account=account)

    with pytest.raises(TransactionRuleActivationBlockedError) as caught:
        await resolver.validate_for_activation(workspace_id=workspace_id, rule=rule)

    assert caught.value.field == expected_field


def target_resolver(
    *,
    category: Category | None = None,
    property_: Property | None = None,
    account: Account | None = None,
) -> TransactionRuleTargetResolver:
    resolver = TransactionRuleTargetResolver(cast(AsyncSession, SimpleNamespace()))
    resolver.categories = create_autospec(CategoryRepository, instance=True)
    resolver.categories.get_for_workspace.return_value = category
    resolver.properties = create_autospec(PropertyRepository, instance=True)
    resolver.properties.get_for_workspace.return_value = property_
    resolver.accounts = create_autospec(AccountRepository, instance=True)
    resolver.accounts.get_for_workspace.return_value = account
    return resolver
