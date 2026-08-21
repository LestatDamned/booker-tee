from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import create_autospec
from uuid import uuid4

from app.features.accounts.repository import AccountRepository
from app.features.categories.models import Category, CategoryKind
from app.features.ledger.models import MoneyEntry, Operation, OperationStatus, OperationType
from app.features.ledger.repository import LedgerRepository
from app.features.properties.models import Property
from app.features.reports.service import (
    ReportFilters,
    ReportsService,
    list_uncategorized_operations,
    summarize_by_category,
    summarize_by_property,
    summarize_income_expense,
)


def test_income_expense_summary_uses_signed_money_entries() -> None:
    operations = [
        operation_with_entry(OperationType.INCOME, Decimal("100.00")),
        operation_with_entry(OperationType.EXPENSE, Decimal("-40.00")),
    ]

    summary = summarize_income_expense(operations)

    assert summary.income == Decimal("100.00")
    assert summary.expense == Decimal("40.00")
    assert summary.profit == Decimal("60.00")


def test_property_summary_uses_only_property_linked_operations() -> None:
    property_ = Property(workspace_id=uuid4(), name="9 Maya 20")
    operations = [
        operation_with_entry(OperationType.INCOME, Decimal("100.00"), property_=property_),
        operation_with_entry(OperationType.EXPENSE, Decimal("-30.00"), property_=property_),
        operation_with_entry(OperationType.INCOME, Decimal("50.00")),
    ]

    rows = summarize_by_property(operations)

    assert len(rows) == 1
    assert rows[0].property_name == "9 Maya 20"
    assert rows[0].income == Decimal("100.00")
    assert rows[0].expense == Decimal("30.00")
    assert rows[0].profit == Decimal("70.00")


def test_category_summary_exposes_links_only_for_real_categories() -> None:
    category_id = uuid4()
    categorized = Category(
        id=category_id,
        workspace_id=uuid4(),
        name="Продукты",
        kind=CategoryKind.EXPENSE,
    )
    uncategorized = Category(
        id=uuid4(),
        workspace_id=uuid4(),
        name="Без категории",
        kind=CategoryKind.MIXED,
        is_system=True,
        system_key="uncategorized",
    )
    operations = [
        operation_with_entry(OperationType.EXPENSE, Decimal("-40.00"), category=categorized),
        operation_with_entry(OperationType.INCOME, Decimal("20.00"), category=uncategorized),
        operation_with_entry(OperationType.EXPENSE, Decimal("-10.00")),
    ]

    rows = summarize_by_category(operations)

    assert [(row.category_name, row.category_id) for row in rows] == [
        ("Без категории", None),
        ("Продукты", category_id),
    ]
    assert rows[0].income == Decimal("20.00")
    assert rows[0].expense == Decimal("10.00")
    assert rows[1].expense == Decimal("40.00")


def test_uncategorized_report_includes_missing_or_uncategorized_system_category() -> None:
    categorized = Category(
        workspace_id=uuid4(),
        name="Rent",
        kind=CategoryKind.INCOME,
        is_system=True,
        system_key="rent",
    )
    uncategorized = Category(
        workspace_id=uuid4(),
        name="Uncategorized",
        kind=CategoryKind.MIXED,
        is_system=True,
        system_key="uncategorized",
    )
    operations = [
        operation_with_entry(OperationType.INCOME, Decimal("100.00"), category=categorized),
        operation_with_entry(OperationType.INCOME, Decimal("20.00"), category=uncategorized),
        operation_with_entry(OperationType.EXPENSE, Decimal("-10.00")),
    ]

    rows = list_uncategorized_operations(operations)

    assert [row.total for row in rows] == [Decimal("20.00"), Decimal("-10.00")]


async def test_report_overview_applies_filters_and_excludes_transfers_from_profit() -> None:
    workspace_id = uuid4()
    selected_account_id = uuid4()
    other_account_id = uuid4()
    selected_account = SimpleNamespace(
        id=selected_account_id,
        initial_balance=Decimal("100.00"),
    )
    other_account = SimpleNamespace(
        id=other_account_id,
        initial_balance=Decimal("999.00"),
    )
    accounts = create_autospec(AccountRepository, instance=True)
    accounts.list_active_for_workspace.return_value = [selected_account, other_account]
    ledger = create_autospec(LedgerRepository, instance=True)
    ledger.get_confirmed_account_entries_total.return_value = Decimal("25.00")
    ledger.list_confirmed_operations.return_value = [
        operation_with_entry(OperationType.INCOME, Decimal("100.00")),
        operation_with_entry(OperationType.EXPENSE, Decimal("-40.00")),
        operation_with_entry(
            OperationType.TRANSFER,
            Decimal("999.00"),
            affects_profit=False,
        ),
    ]
    service = ReportsService(cast(Any, object()))
    service.accounts = accounts
    service.ledger = ledger

    overview = await service.build_overview(
        workspace_id=workspace_id,
        filters=ReportFilters(
            date_from=date(2026, 5, 1),
            date_to=date(2026, 5, 31),
            account_id=selected_account_id,
            currency="USD",
        ),
    )

    assert len(overview.account_balances) == 1
    assert overview.account_balances[0].account.id == selected_account_id
    assert overview.account_balances[0].balance == Decimal("125.00")
    assert overview.summary.income == Decimal("100.00")
    assert overview.summary.expense == Decimal("40.00")
    assert overview.summary.profit == Decimal("60.00")
    accounts.list_active_for_workspace.assert_awaited_once_with(workspace_id)
    ledger.get_confirmed_account_entries_total.assert_awaited_once_with(
        workspace_id=workspace_id,
        account_id=selected_account_id,
        date_to=date(2026, 5, 31),
    )
    ledger.list_confirmed_operations.assert_awaited_once_with(
        workspace_id=workspace_id,
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 31),
        account_id=selected_account_id,
        category_id=None,
        property_id=None,
        currency="USD",
    )


def operation_with_entry(
    operation_type: OperationType,
    amount: Decimal,
    *,
    affects_profit: bool = True,
    category: Category | None = None,
    property_: Property | None = None,
) -> Operation:
    workspace_id = uuid4()
    operation = Operation(
        workspace_id=workspace_id,
        type=operation_type,
        status=OperationStatus.CONFIRMED,
        affects_profit=affects_profit,
        category=category,
        property=property_,
        operation_date=date(2026, 6, 13),
    )
    operation.money_entries = [
        MoneyEntry(
            workspace_id=workspace_id,
            operation_id=uuid4(),
            account_id=uuid4(),
            amount=amount,
            currency="RUB",
            entry_order=1,
        )
    ]
    return operation
