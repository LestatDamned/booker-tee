from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.features.accounts.models import Account
from app.features.categories.application.detail import (
    CATEGORY_RULE_PREVIEW_LIMIT,
    CategoryDetailFilterError,
    CategoryDetailNotFoundError,
    CategoryDetailReader,
)
from app.features.categories.models import Category, CategoryKind
from app.features.categories.service import CategoryManagementRow
from app.features.ledger.models import MoneyEntry, Operation, OperationStatus, OperationType
from app.features.transaction_rules.models import (
    TransactionRule,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)


class CategorySourceStub:
    def __init__(self, row: CategoryManagementRow | None) -> None:
        self.row = row
        self.calls: list[tuple[UUID, UUID]] = []

    async def get_management_row(
        self,
        workspace_id: UUID,
        category_id: UUID,
    ) -> CategoryManagementRow | None:
        self.calls.append((workspace_id, category_id))
        return self.row


class CurrencySourceStub:
    async def list_workspace_currencies(self, workspace_id: UUID) -> list[str]:
        return ["USD", "RUB"]


class OperationSourceStub:
    def __init__(self, operations: list[Operation]) -> None:
        self.operations = operations
        self.summary_calls: list[dict[str, object]] = []
        self.page_calls: list[dict[str, object]] = []

    async def list_confirmed_operations(self, **kwargs: object) -> list[Operation]:
        self.summary_calls.append(kwargs)
        return self.operations

    async def list_confirmed_category_operations_page(self, **kwargs: object) -> list[Operation]:
        self.page_calls.append(kwargs)
        offset = kwargs["offset"]
        limit = kwargs["limit"]
        assert isinstance(offset, int)
        assert isinstance(limit, int)
        return self.operations[offset : offset + limit]

    async def count_confirmed_category_operations(self, **_kwargs: object) -> int:
        return len(self.operations)


class RuleSourceStub:
    def __init__(self, rules: list[TransactionRule]) -> None:
        self.rules = rules
        self.preview_limit: int | None = None

    async def list_category_preview(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
        limit: int,
    ) -> list[TransactionRule]:
        self.preview_limit = limit
        return self.rules[:limit]

    async def count_category_rules(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
    ) -> tuple[int, int]:
        return len(self.rules), sum(rule.is_active for rule in self.rules)


@pytest.mark.asyncio
async def test_detail_is_currency_safe_excludes_transfer_and_bounds_pages() -> None:
    workspace_id = uuid4()
    category = category_row(workspace_id)
    operations = [
        operation(workspace_id, OperationType.INCOME, "100.00", "10.00"),
        operation(workspace_id, OperationType.EXPENSE, "-35.00", "-5.00"),
        operation(
            workspace_id,
            OperationType.TRANSFER,
            "0.00",
            "999.00",
            affects_profit=False,
        ),
    ]
    rules = [transaction_rule(workspace_id, index) for index in range(7)]
    operation_source = OperationSourceStub(operations)
    rule_source = RuleSourceStub(rules)
    reader = CategoryDetailReader(
        categories=CategorySourceStub(category),
        currencies=CurrencySourceStub(),
        operations=operation_source,
        rules=rule_source,
    )

    detail = await reader.read(
        workspace_id=workspace_id,
        category_id=category.category.id,
        default_currency="RUB",
        can_write=True,
        currency="rub",
        search="market",
        operations_page=2,
        operations_page_size=2,
    )

    assert detail.summary.income == Decimal("100.00")
    assert detail.summary.expense == Decimal("35.00")
    assert detail.summary.profit == Decimal("65.00")
    assert detail.operations.page == 2
    assert detail.operations.total == 3
    assert detail.operations.total_pages == 2
    assert len(detail.operations.items) == 1
    assert detail.operations.items[0].signed_amount == Decimal("0.00")
    assert operation_source.page_calls[0]["offset"] == 2
    assert operation_source.page_calls[0]["limit"] == 2
    assert operation_source.page_calls[0]["search"] == "market"
    assert "search" not in operation_source.summary_calls[0]
    assert detail.rules.total == 7
    assert detail.rules.active_count == 4
    assert len(detail.rules.items) == CATEGORY_RULE_PREVIEW_LIMIT
    assert rule_source.preview_limit == CATEGORY_RULE_PREVIEW_LIMIT
    assert detail.kind_change_impact.operation_count == 3
    assert detail.kind_change_impact.rule_count == 7
    assert detail.kind_change_impact.requires_confirmation
    assert detail.kind_change_impact.existing_operations_unchanged
    assert [option.value for option in detail.kind_options] == list(CategoryKind)


@pytest.mark.asyncio
async def test_detail_defaults_currency_and_keeps_archived_category_readable() -> None:
    workspace_id = uuid4()
    row = category_row(workspace_id, is_active=False)
    reader = CategoryDetailReader(
        categories=CategorySourceStub(row),
        currencies=CurrencySourceStub(),
        operations=OperationSourceStub([]),
        rules=RuleSourceStub([]),
    )

    detail = await reader.read(
        workspace_id=workspace_id,
        category_id=row.category.id,
        default_currency="rub",
        can_write=False,
    )

    assert detail.applied_filters.currency == "RUB"
    assert detail.available_currencies == ["RUB", "USD"]
    assert not detail.category.is_active
    assert not detail.category.capabilities.can_update
    assert detail.operations.total_pages == 1


@pytest.mark.asyncio
async def test_detail_rejects_invalid_filters_and_hides_cross_workspace_ids() -> None:
    workspace_id = uuid4()
    missing_reader = CategoryDetailReader(
        categories=CategorySourceStub(None),
        currencies=CurrencySourceStub(),
        operations=OperationSourceStub([]),
        rules=RuleSourceStub([]),
    )
    with pytest.raises(CategoryDetailNotFoundError):
        await missing_reader.read(
            workspace_id=workspace_id,
            category_id=uuid4(),
            default_currency="RUB",
            can_write=True,
        )

    row = category_row(workspace_id)
    reader = CategoryDetailReader(
        categories=CategorySourceStub(row),
        currencies=CurrencySourceStub(),
        operations=OperationSourceStub([]),
        rules=RuleSourceStub([]),
    )
    with pytest.raises(CategoryDetailFilterError, match="Начало периода"):
        await reader.read(
            workspace_id=workspace_id,
            category_id=row.category.id,
            default_currency="RUB",
            can_write=True,
            date_from=date(2026, 8, 2),
            date_to=date(2026, 8, 1),
        )
    with pytest.raises(CategoryDetailFilterError, match="валюта"):
        await reader.read(
            workspace_id=workspace_id,
            category_id=row.category.id,
            default_currency="RUB",
            can_write=True,
            currency="EUR",
        )


def category_row(workspace_id: UUID, *, is_active: bool = True) -> CategoryManagementRow:
    return CategoryManagementRow(
        category=Category(
            id=uuid4(),
            workspace_id=workspace_id,
            name="Продукты",
            kind=CategoryKind.EXPENSE,
            is_active=is_active,
            is_system=False,
            updated_at=datetime(2026, 8, 1, 8, 30, tzinfo=UTC),
        ),
        operation_count=3,
        rule_count=7,
        active_rule_count=4,
    )


def operation(
    workspace_id: UUID,
    operation_type: OperationType,
    rub_amount: str,
    usd_amount: str,
    *,
    affects_profit: bool = True,
) -> Operation:
    account = Account(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Основной счёт",
        currency="RUB",
    )
    item = Operation(
        id=uuid4(),
        workspace_id=workspace_id,
        type=operation_type,
        status=OperationStatus.CONFIRMED,
        affects_profit=affects_profit,
        description="Операция",
        operation_date=date(2026, 8, 1),
        created_at=datetime(2026, 8, 1, 8, 30, tzinfo=UTC),
    )
    item.money_entries = [
        MoneyEntry(
            workspace_id=workspace_id,
            account_id=account.id,
            account=account,
            amount=Decimal(rub_amount),
            currency="RUB",
            entry_order=1,
        ),
        MoneyEntry(
            workspace_id=workspace_id,
            account_id=account.id,
            account=account,
            amount=Decimal(usd_amount),
            currency="USD",
            entry_order=2,
        ),
    ]
    return item


def transaction_rule(workspace_id: UUID, index: int) -> TransactionRule:
    return TransactionRule(
        id=uuid4(),
        workspace_id=workspace_id,
        name=f"Правило {index}",
        is_active=index % 2 == 0,
        priority=index,
        pattern=f"pattern-{index}",
        match_type=TransactionRuleMatchType.CONTAINS,
        application_mode=TransactionRuleApplicationMode.SUGGEST,
    )
