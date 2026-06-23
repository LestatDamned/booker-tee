from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.features.categories.models import Category, CategoryKind
from app.features.ledger.models import MoneyEntry, Operation, OperationStatus, OperationType
from app.features.properties.models import Property
from app.features.reports.router import parse_optional_query_date, parse_optional_query_uuid
from app.features.reports.service import (
    list_uncategorized_operations,
    summarize_by_category,
    summarize_by_property,
    summarize_income_expense,
)


def test_income_expense_summary_excludes_non_profit_transfer_operations() -> None:
    operations = [
        operation_with_entry(OperationType.INCOME, Decimal("100.00")),
        operation_with_entry(OperationType.EXPENSE, Decimal("-40.00")),
        operation_with_entry(OperationType.TRANSFER, Decimal("999.00"), affects_profit=False),
    ]

    summary = summarize_income_expense(
        [operation for operation in operations if operation.affects_profit]
    )

    assert summary.income == Decimal("100.00")
    assert summary.expense == Decimal("40.00")
    assert summary.profit == Decimal("60.00")


def test_property_summary_uses_only_property_linked_profit_operations() -> None:
    property_ = Property(workspace_id=uuid4(), name="9 Maya 20")
    operations = [
        operation_with_entry(OperationType.INCOME, Decimal("100.00"), property_=property_),
        operation_with_entry(OperationType.EXPENSE, Decimal("-30.00"), property_=property_),
        operation_with_entry(OperationType.INCOME, Decimal("50.00")),
        operation_with_entry(
            OperationType.TRANSFER,
            Decimal("1000.00"),
            affects_profit=False,
            property_=property_,
        ),
    ]

    rows = summarize_by_property(
        [operation for operation in operations if operation.affects_profit]
    )

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


def test_report_query_parsers_treat_empty_filter_values_as_none() -> None:
    assert parse_optional_query_uuid("", field_name="category_id") is None
    assert parse_optional_query_uuid(None, field_name="property_id") is None
    assert parse_optional_query_date("", field_name="date_from") is None
    assert parse_optional_query_date(None, field_name="date_to") is None


def test_report_query_parsers_accept_valid_filter_values() -> None:
    raw_uuid = uuid4()

    assert parse_optional_query_uuid(str(raw_uuid), field_name="category_id") == raw_uuid
    assert parse_optional_query_date("2026-06-13", field_name="date_from") == date(2026, 6, 13)


def test_report_query_parsers_raise_clear_bad_request_for_invalid_values() -> None:
    with pytest.raises(HTTPException) as uuid_exc:
        parse_optional_query_uuid("not-a-uuid", field_name="category_id")
    with pytest.raises(HTTPException) as date_exc:
        parse_optional_query_date("13.06.2026", field_name="date_from")

    assert uuid_exc.value.status_code == 400
    assert date_exc.value.status_code == 400


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
