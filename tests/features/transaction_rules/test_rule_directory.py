from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.features.accounts.models import Account
from app.features.categories.models import Category, CategoryKind
from app.features.ledger.models import OperationType
from app.features.properties.models import Property, PropertyStatus
from app.features.transaction_rules.application.directory import (
    TransactionRuleDirectoryReader,
    enable_blocked_reason,
)
from app.features.transaction_rules.models import (
    MoneyDirection,
    TransactionRule,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)
from app.features.transaction_rules.repository import (
    TransactionRuleDirectoryResult,
    TransactionRuleDirectoryRow,
)
from app.features.transaction_rules.schemas import (
    TransactionRuleDirectoryStatus,
    TransactionRuleEnableBlockedReason,
)


class TransactionRuleDirectorySourceStub:
    def __init__(self, result: TransactionRuleDirectoryResult) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []
        self.categories: list[Category] = []
        self.properties: list[Property] = []
        self.category_calls: list[tuple[UUID, set[UUID]]] = []
        self.property_calls: list[tuple[UUID, set[UUID]]] = []
        self.target_rule: TransactionRule | None = None
        self.target_suggestion_count = 0

    async def read_directory(self, **kwargs: object) -> TransactionRuleDirectoryResult:
        self.calls.append(kwargs)
        return self.result

    async def list_directory_categories(
        self,
        *,
        workspace_id: UUID,
        current_ids: set[UUID],
    ) -> list[Category]:
        self.category_calls.append((workspace_id, current_ids))
        return self.categories

    async def list_directory_properties(
        self,
        *,
        workspace_id: UUID,
        current_ids: set[UUID],
    ) -> list[Property]:
        self.property_calls.append((workspace_id, current_ids))
        return self.properties

    async def get_for_workspace(
        self,
        workspace_id: UUID,
        rule_id: UUID,
    ) -> TransactionRule | None:
        if self.target_rule is None or self.target_rule.workspace_id != workspace_id:
            return None
        return self.target_rule if self.target_rule.id == rule_id else None

    async def count_direct_raw_suggestions(
        self,
        *,
        workspace_id: UUID,
        rule_id: UUID,
    ) -> int:
        assert self.target_rule is not None
        assert (workspace_id, rule_id) == (
            self.target_rule.workspace_id,
            self.target_rule.id,
        )
        return self.target_suggestion_count


@pytest.mark.parametrize(
    ("attribute", "reference", "expected"),
    [
        pytest.param(
            "category",
            Category(
                workspace_id=uuid4(),
                name="Архивная категория",
                kind=CategoryKind.EXPENSE,
                is_active=False,
            ),
            TransactionRuleEnableBlockedReason.CATEGORY_INACTIVE,
            id="category",
        ),
        pytest.param(
            "property",
            Property(
                workspace_id=uuid4(),
                name="Архивный объект",
                status=PropertyStatus.ARCHIVED,
            ),
            TransactionRuleEnableBlockedReason.PROPERTY_ARCHIVED,
            id="property",
        ),
        pytest.param(
            "account",
            Account(
                workspace_id=uuid4(),
                name="Архивный счёт",
                currency="RUB",
                is_active=False,
            ),
            TransactionRuleEnableBlockedReason.ACCOUNT_UNAVAILABLE,
            id="account",
        ),
    ],
)
def test_enable_blocked_reason_identifies_each_unavailable_target(
    attribute: str,
    reference: Category | Property | Account,
    expected: TransactionRuleEnableBlockedReason,
) -> None:
    rule = transaction_rule(reference.workspace_id)
    setattr(rule, attribute, reference)

    assert enable_blocked_reason(rule) == expected


async def test_directory_projects_complete_rule_meaning_and_archived_references() -> None:
    workspace_id = uuid4()
    category = Category(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Старые покупки",
        kind=CategoryKind.EXPENSE,
        is_active=False,
    )
    property_ = Property(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Квартира",
        status=PropertyStatus.ARCHIVED,
    )
    account = Account(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Карта",
        currency="RUB",
        is_active=True,
    )
    rule = transaction_rule(workspace_id)
    rule.category_id = category.id
    rule.property_id = property_.id
    rule.account_id = account.id
    rule.category = category
    rule.property = property_
    rule.account = account
    source = TransactionRuleDirectorySourceStub(
        TransactionRuleDirectoryResult(
            rows=[TransactionRuleDirectoryRow(rule=rule, direct_raw_suggestion_count=4)],
            page=1,
            total=1,
            all_count=1,
            active_count=0,
            disabled_count=1,
        )
    )
    source.categories = [category]
    source.properties = [property_]

    directory = await TransactionRuleDirectoryReader(source).read(
        workspace_id=workspace_id,
        can_write=True,
        search="ozon",
        category_id=category.id,
        status=TransactionRuleDirectoryStatus.DISABLED,
        page=1,
        page_size=50,
    )

    item = directory.items[0]
    assert item.condition.pattern == "OZON"
    assert item.condition.account is not None
    assert item.condition.amount_min == Decimal("100.00")
    assert item.outcome.category is not None
    assert item.outcome.category.is_active is False
    assert item.outcome.property is not None
    assert item.outcome.property.is_active is False
    assert item.outcome.affects_profit is True
    assert item.usage.direct_raw_suggestion_count == 4
    assert item.capabilities.enable_blocked_reason_code == "category_inactive"
    assert item.capabilities.delete_blocked_reason_code == "raw_suggestions"
    assert not item.capabilities.can_enable
    assert not item.capabilities.can_delete
    assert directory.references.categories[0].is_active is False
    assert source.calls[0]["workspace_id"] == workspace_id
    assert source.category_calls == [(workspace_id, {category.id})]
    assert source.property_calls == [(workspace_id, {property_.id})]


async def test_viewer_directory_is_read_only_and_read_has_no_mutation_dependency() -> None:
    workspace_id = uuid4()
    rule = transaction_rule(workspace_id, is_active=True)
    source = TransactionRuleDirectorySourceStub(
        TransactionRuleDirectoryResult(
            rows=[TransactionRuleDirectoryRow(rule=rule, direct_raw_suggestion_count=0)],
            page=1,
            total=1,
            all_count=1,
            active_count=1,
            disabled_count=0,
        )
    )

    directory = await TransactionRuleDirectoryReader(source).read(
        workspace_id=workspace_id,
        can_write=False,
        search=None,
        category_id=None,
        status=TransactionRuleDirectoryStatus.ALL,
        page=1,
        page_size=50,
    )

    assert directory.capabilities.readonly_reason_code == "financial_write_forbidden"
    assert not directory.capabilities.can_create
    assert not directory.capabilities.can_seed_defaults
    capabilities = directory.items[0].capabilities
    assert not capabilities.can_update
    assert not capabilities.can_enable
    assert not capabilities.can_disable
    assert not capabilities.can_delete


async def test_directory_returns_a_target_outside_the_current_page() -> None:
    workspace_id = uuid4()
    page_rule = transaction_rule(workspace_id)
    target_rule = transaction_rule(workspace_id)
    source = TransactionRuleDirectorySourceStub(
        TransactionRuleDirectoryResult(
            rows=[TransactionRuleDirectoryRow(rule=page_rule, direct_raw_suggestion_count=0)],
            page=1,
            total=2,
            all_count=2,
            active_count=0,
            disabled_count=2,
        )
    )
    source.target_rule = target_rule
    source.target_suggestion_count = 3

    directory = await TransactionRuleDirectoryReader(source).read(
        workspace_id=workspace_id,
        can_write=True,
        search=None,
        category_id=None,
        status=TransactionRuleDirectoryStatus.ALL,
        page=1,
        page_size=1,
        target_rule_id=target_rule.id,
    )

    assert [item.id for item in directory.items] == [page_rule.id]
    assert directory.target_item is not None
    assert directory.target_item.id == target_rule.id
    assert directory.target_item.usage.direct_raw_suggestion_count == 3


def transaction_rule(workspace_id: UUID, *, is_active: bool = False) -> TransactionRule:
    return TransactionRule(
        id=uuid4(),
        workspace_id=workspace_id,
        name="OZON → Маркетплейсы",
        priority=20,
        is_active=is_active,
        pattern="OZON",
        match_type=TransactionRuleMatchType.CONTAINS,
        application_mode=TransactionRuleApplicationMode.SUGGEST,
        amount_min=Decimal("100.00"),
        amount_max=Decimal("500.00"),
        direction=MoneyDirection.OUTFLOW,
        target_operation_type=OperationType.EXPENSE,
        auto_description="Маркетплейс",
        affects_profit=True,
        updated_at=datetime(2026, 8, 2, 9, 0, tzinfo=UTC),
    )
