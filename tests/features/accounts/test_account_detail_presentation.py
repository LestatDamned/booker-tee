from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.features.accounts.models import AccountType
from app.features.accounts.presentation.detail.models import AccountDetailPresenterInput
from app.features.accounts.presentation.detail.presenter import AccountDetailPresenter
from app.features.categories.models import CategoryKind
from app.features.ledger.application.listing import LedgerPage
from app.features.ledger.mapping.dto import (
    AccountLedgerDetailView,
    AccountLedgerEntryView,
    AccountView,
    CategoryView,
    OperationRefMoneyEntryView,
    OperationRefView,
    RawTransactionLinkView,
)
from app.features.ledger.models import OperationSource, OperationStatus, OperationType


def test_presenter_builds_imported_expense_movement_with_drawer() -> None:
    account = account_view("Экспобанк карта")
    category = CategoryView(id=uuid4(), name="Продукты", kind=CategoryKind.EXPENSE)
    raw_link = RawTransactionLinkView(id=uuid4(), uploaded_document_id=uuid4())
    operation = operation_view(
        operation_type=OperationType.EXPENSE,
        source=OperationSource.BANK_PDF,
        category=category,
        raw_transactions=[raw_link],
    )
    entry = AccountLedgerEntryView(
        operation=operation,
        operation_id=operation.id,
        amount=Decimal("-744.94"),
        currency="RUB",
    )

    page = AccountDetailPresenter.build(
        detail_view(account=account, entries=[entry]),
        presenter_input(can_write=True),
    )

    movement = page.movements[0]

    assert movement.amount_direction == "expense"
    assert movement.date_label == "30.06.2026"
    assert movement.badges == []
    assert [item.label for item in movement.meta] == [
        "Продукты",
        "Экспобанк карта",
        "подтверждено",
    ]
    assert [item.tone for item in movement.meta] == ["classification", None, None]
    assert movement.result.eyebrow == "расход · подтверждено"
    assert movement.result.title == "Продукты"
    assert movement.primary_action is not None
    assert movement.primary_action.label == "исправить"
    assert movement.primary_action.action_type == "drawer_toggle"
    assert movement.primary_action.placement == "primary"
    assert movement.edit_panel_id == f"account-movement-edit-panel-{operation.id}"
    assert movement.edit_form_url == (
        f"/accounts/{account.id}/operations/{operation.id}/review-fields/edit"
    )
    edit_panel = AccountDetailPresenter.build_edit_panel(
        account_id=account.id,
        operation=operation,
    )
    assert edit_panel.drawer.category_id == category.id
    assert edit_panel.drawer.form_action == (
        f"/accounts/{account.id}/operations/{operation.id}/review-fields"
    )
    assert movement.secondary_actions[0].href == (
        f"/imports/documents/{raw_link.uploaded_document_id}/review#raw-{raw_link.id}"
    )
    assert movement.secondary_actions[0].action_type == "link"
    assert movement.secondary_actions[0].placement == "secondary"


def test_presenter_summarizes_transfer_route() -> None:
    source_account = account_view("ВТБ вклад")
    destination_account = account_view("Экспобанк карта")
    operation = operation_view(
        operation_type=OperationType.TRANSFER,
        source=OperationSource.BANK_PDF,
        money_entries=[
            OperationRefMoneyEntryView(
                account_id=source_account.id,
                account=source_account,
                amount=Decimal("-2342.19"),
            ),
            OperationRefMoneyEntryView(
                account_id=destination_account.id,
                account=destination_account,
                amount=Decimal("2342.19"),
            ),
        ],
    )
    entry = AccountLedgerEntryView(
        operation=operation,
        operation_id=operation.id,
        amount=Decimal("2342.19"),
        currency="RUB",
    )

    page = AccountDetailPresenter.build(
        detail_view(account=destination_account, entries=[entry]),
        presenter_input(can_write=True),
    )

    movement = page.movements[0]

    assert movement.result.title == "ВТБ вклад -> Экспобанк карта"
    assert movement.result.detail == "не влияет на прибыль"
    assert movement.meta[0].label == "ВТБ вклад -> Экспобанк карта"
    assert movement.meta[1].label == "Экспобанк карта"
    assert movement.meta[2].label == "не влияет на прибыль"
    assert movement.meta[3].label == "подтверждено"
    assert movement.amount_direction == "transfer"
    assert [item.tone for item in movement.meta] == ["classification", None, None, None]


def test_presenter_keeps_manual_operation_as_link_action_for_first_slice() -> None:
    account = account_view("Наличные")
    operation = operation_view(
        operation_type=OperationType.INCOME,
        source=OperationSource.MANUAL,
        description="Возврат долга",
    )
    entry = AccountLedgerEntryView(
        operation=operation,
        operation_id=operation.id,
        amount=Decimal("1000.00"),
        currency="RUB",
    )

    page = AccountDetailPresenter.build(
        detail_view(account=account, entries=[entry]),
        presenter_input(can_write=True),
    )

    movement = page.movements[0]

    assert movement.edit_panel_id is None
    assert movement.edit_form_url is None
    assert movement.primary_action is not None
    assert movement.primary_action.href == (
        f"/app/ledger/manual?operation_id={operation.id}#operation-{operation.id}"
    )
    assert movement.primary_action.action_type == "link"
    assert movement.primary_action.placement == "primary"
    assert movement.meta[-1].label == "подтверждено"


def test_presenter_promotes_review_status_to_badge() -> None:
    account = account_view("Экспобанк карта")
    operation = operation_view(
        operation_type=OperationType.EXPENSE,
        source=OperationSource.BANK_PDF,
        status=OperationStatus.NEEDS_REVIEW,
        category=None,
    )
    entry = AccountLedgerEntryView(
        operation=operation,
        operation_id=operation.id,
        amount=Decimal("-100.00"),
        currency="RUB",
    )

    page = AccountDetailPresenter.build(
        detail_view(account=account, entries=[entry]),
        presenter_input(can_write=True),
    )

    movement = page.movements[0]

    assert [badge.label for badge in movement.badges] == ["нужна проверка", "без категории"]
    assert [badge.tone for badge in movement.badges] == ["needs_review", "warning"]
    assert movement.meta[-1].label == "нужна проверка"


def test_presenter_detects_active_filters() -> None:
    page = AccountDetailPresenter.build(
        detail_view(account=account_view("Экспобанк карта"), entries=[]),
        presenter_input(
            can_write=False,
            filters_status=OperationStatus.IGNORED,
        ),
    )

    assert page.filters_active is True


def account_view(name: str) -> AccountView:
    return AccountView(
        id=uuid4(),
        name=name,
        type=AccountType.CARD,
        currency="RUB",
        is_active=True,
        initial_balance=Decimal("0.00"),
    )


def operation_view(
    *,
    operation_type: OperationType,
    source: OperationSource,
    status: OperationStatus = OperationStatus.CONFIRMED,
    description: str = "Операция",
    category: CategoryView | None = None,
    money_entries: list[OperationRefMoneyEntryView] | None = None,
    raw_transactions: list[RawTransactionLinkView] | None = None,
) -> OperationRefView:
    return OperationRefView(
        id=uuid4(),
        type=operation_type,
        status=status,
        source=source,
        operation_date=date(2026, 6, 30),
        description=description,
        category=category,
        property=None,
        money_entries=money_entries or [],
        raw_transactions=raw_transactions or [],
    )


def detail_view(
    *,
    account: AccountView,
    entries: list[AccountLedgerEntryView],
) -> AccountLedgerDetailView:
    return AccountLedgerDetailView(
        account=account,
        balance=Decimal("100.00"),
        entries=entries,
        page=LedgerPage(page=1, per_page=50, total=len(entries)),
    )


def presenter_input(
    *,
    can_write: bool,
    filters_status: OperationStatus | None = OperationStatus.CONFIRMED,
) -> AccountDetailPresenterInput:
    return AccountDetailPresenterInput(
        can_write=can_write,
        filters_date_from=None,
        filters_date_to=None,
        filters_source=None,
        filters_operation_type=None,
        filters_status=filters_status,
        filters_category_id=None,
        filters_property_id=None,
        filters_search=None,
    )
