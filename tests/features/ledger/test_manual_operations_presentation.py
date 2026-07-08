from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.features.accounts.models import AccountType
from app.features.categories.models import CategoryKind
from app.features.ledger.application.listing import LedgerPage, ManualOperationFilters
from app.features.ledger.mapping.dto import (
    AccountView,
    CategoryView,
    ManualOperationView,
    OperationRefMoneyEntryView,
)
from app.features.ledger.models import OperationStatus, OperationType
from app.features.ledger.presentation.manual_operations.presenter import ManualOperationsPresenter


def test_manual_operations_presenter_builds_expense_row() -> None:
    account_id = uuid4()
    category_id = uuid4()
    operation_id = uuid4()
    account = AccountView(
        id=account_id,
        name="Карта",
        type=AccountType.CARD,
        currency="RUB",
        is_active=True,
        initial_balance=Decimal("0.00"),
    )
    category = CategoryView(id=category_id, name="Кафе", kind=CategoryKind.EXPENSE)
    operation = ManualOperationView(
        id=operation_id,
        type=OperationType.EXPENSE,
        status=OperationStatus.CONFIRMED,
        operation_date=date(2026, 6, 15),
        description="Кофе",
        category_id=category_id,
        property_id=None,
        category=category,
        property=None,
        primary_entry=OperationRefMoneyEntryView(
            account_id=account_id,
            account=account,
            amount=Decimal("-350.00"),
        ),
        source_entry=None,
        destination_entry=None,
        edit_amount=Decimal("350.00"),
    )

    page_vm = ManualOperationsPresenter().build_page(
        operations=[operation],
        page=LedgerPage(page=1, per_page=50, total=1),
        filters=ManualOperationFilters(),
        focused_operation_id=operation_id,
        can_write=True,
    )

    row = page_vm.rows[0]

    assert page_vm.total_label == "1 ручных операций"
    assert row.id == f"operation-{operation_id}"
    assert row.is_current is True
    assert row.amount_direction == "expense"
    assert row.currency == "RUB"
    assert row.drawer.account_id == account_id
    assert [item.label for item in row.meta] == [
        "Кафе",
        "Карта",
        "подтверждено",
    ]
    assert row.primary_action is not None
    assert row.primary_action.action_type == "drawer_toggle"
    assert row.save_action is not None
    assert row.save_action.action_type == "submit"
    assert row.save_action.form_id == f"manual-operation-form-{operation_id}"
    assert row.lifecycle_actions[0].form_action == f"/ledger/manual/{operation_id}/cancel"


def test_manual_operations_presenter_builds_transfer_row() -> None:
    source_account_id = uuid4()
    destination_account_id = uuid4()
    source_account = AccountView(
        id=source_account_id,
        name="Вклад",
        type=AccountType.DEPOSIT,
        currency="RUB",
        is_active=True,
        initial_balance=Decimal("0.00"),
    )
    destination_account = AccountView(
        id=destination_account_id,
        name="Карта",
        type=AccountType.CARD,
        currency="RUB",
        is_active=True,
        initial_balance=Decimal("0.00"),
    )
    operation = ManualOperationView(
        id=uuid4(),
        type=OperationType.TRANSFER,
        status=OperationStatus.CONFIRMED,
        operation_date=date(2026, 6, 16),
        description=None,
        category_id=None,
        property_id=None,
        category=None,
        property=None,
        primary_entry=None,
        source_entry=OperationRefMoneyEntryView(
            account_id=source_account_id,
            account=source_account,
            amount=Decimal("-1000.00"),
        ),
        destination_entry=OperationRefMoneyEntryView(
            account_id=destination_account_id,
            account=destination_account,
            amount=Decimal("1000.00"),
        ),
        edit_amount=Decimal("1000.00"),
    )

    page_vm = ManualOperationsPresenter().build_page(
        operations=[operation],
        page=LedgerPage(page=1, per_page=50, total=1),
        filters=ManualOperationFilters(search="перевод"),
        focused_operation_id=None,
        can_write=False,
    )

    row = page_vm.rows[0]

    assert page_vm.filters_active is True
    assert row.description == "Без описания"
    assert row.amount_direction == "transfer"
    assert row.drawer.account_id == source_account_id
    assert row.drawer.destination_account_id == destination_account_id
    assert [item.label for item in row.meta] == [
        "Вклад -> Карта",
        "не влияет на прибыль",
        "подтверждено",
    ]
    assert row.lifecycle_actions == []
    assert row.primary_action is None
    assert row.save_action is None


def test_manual_operations_presenter_builds_ignored_row_actions() -> None:
    operation_id = uuid4()
    operation = ManualOperationView(
        id=operation_id,
        type=OperationType.INCOME,
        status=OperationStatus.IGNORED,
        operation_date=date(2026, 6, 17),
        description="Возврат",
        category_id=None,
        property_id=None,
        category=None,
        property=None,
        primary_entry=None,
        source_entry=None,
        destination_entry=None,
        edit_amount=Decimal("100.00"),
    )

    page_vm = ManualOperationsPresenter().build_page(
        operations=[operation],
        page=LedgerPage(page=1, per_page=50, total=1),
        filters=ManualOperationFilters(),
        focused_operation_id=None,
        can_write=True,
    )

    row = page_vm.rows[0]

    assert row.is_inactive is True
    assert row.lifecycle_actions[0].form_action == f"/ledger/manual/{operation_id}/restore"
    assert row.danger_actions[0].form_action == f"/ledger/manual/{operation_id}/delete"
