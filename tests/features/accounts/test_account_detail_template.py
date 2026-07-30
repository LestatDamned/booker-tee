from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.features.accounts.models import AccountType
from app.features.accounts.presentation.detail.models import (
    AccountDetailMetricVM,
    AccountDetailPageVM,
    AccountMovementActionVM,
    AccountMovementMetaVM,
    AccountMovementVM,
    OperationResultVM,
)
from app.features.ledger.application.account_ledger import AccountLedgerEntryView
from app.features.ledger.models import OperationSource, OperationStatus, OperationType
from app.features.ledger.schemas.listing import AccountEntryFilters, LedgerPage
from app.templating import create_templates


def test_account_ledger_entry_amount_direction_tracks_money_sign() -> None:
    income_expense_operation = cast(Any, SimpleNamespace(type=OperationType.EXPENSE))
    transfer_operation = cast(Any, SimpleNamespace(type=OperationType.TRANSFER))

    assert (
        AccountLedgerEntryView(
            operation=income_expense_operation,
            operation_id=uuid4(),
            amount=Decimal("-10.00"),
            currency="RUB",
        ).amount_direction
        == "expense"
    )
    assert (
        AccountLedgerEntryView(
            operation=income_expense_operation,
            operation_id=uuid4(),
            amount=Decimal("10.00"),
            currency="RUB",
        ).amount_direction
        == "income"
    )
    assert (
        AccountLedgerEntryView(
            operation=income_expense_operation,
            operation_id=uuid4(),
            amount=Decimal("0.00"),
            currency="RUB",
        ).amount_direction
        == "transfer"
    )
    assert (
        AccountLedgerEntryView(
            operation=transfer_operation,
            operation_id=uuid4(),
            amount=Decimal("2342.19"),
            currency="RUB",
        ).amount_direction
        == "transfer"
    )


def test_account_detail_template_uses_compact_entry_cards() -> None:
    account_id = uuid4()
    operation_id = uuid4()
    raw_transaction_id = uuid4()
    document_id = uuid4()
    category_id = uuid4()
    account = SimpleNamespace(
        id=account_id,
        name="Экспобанк карта",
        type=AccountType.CARD,
        currency="RUB",
        is_active=True,
        initial_balance=Decimal("0.00"),
    )
    operation = SimpleNamespace(
        id=operation_id,
        operation_date="2026-06-05",
        type=OperationType.EXPENSE,
        status=OperationStatus.CONFIRMED,
        source=OperationSource.BANK_PDF,
        category=SimpleNamespace(id=category_id, name="Продукты"),
        property=None,
        description='Списание средств по платежу СБП | ООО "ЛЕНТА"',
        money_entries=[],
        raw_transactions=[SimpleNamespace(id=raw_transaction_id, uploaded_document_id=document_id)],
    )
    entry = SimpleNamespace(
        operation=operation,
        operation_id=operation_id,
        amount=Decimal("-2438.87"),
        currency="RUB",
        account=account,
    )
    operation.money_entries = [entry]
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("accounts/detail.html").render(
        app_name="Booker Tee",
        account_page=AccountDetailPageVM(
            account=cast(Any, account),
            balance=Decimal("32080.66"),
            metrics=[
                AccountDetailMetricVM("баланс", "32080.66 RUB"),
                AccountDetailMetricVM("начальный", "0.00 RUB"),
                AccountDetailMetricVM("проводки", "1"),
            ],
            movements=[
                AccountMovementVM(
                    id=f"operation-{operation_id}",
                    operation_id=operation_id,
                    tone="expense",
                    amount=Decimal("-2438.87"),
                    amount_direction="expense",
                    currency="RUB",
                    date_label="05.06.2026",
                    badges=[],
                    description='Списание средств по платежу СБП | ООО "ЛЕНТА"',
                    meta=[
                        AccountMovementMetaVM("Продукты", "classification"),
                        AccountMovementMetaVM("Экспобанк карта"),
                        AccountMovementMetaVM("подтверждено"),
                    ],
                    result=OperationResultVM(
                        eyebrow="расход · подтверждено",
                        title="Продукты",
                        tone="expense",
                    ),
                    primary_action=None,
                    secondary_actions=[
                        AccountMovementActionVM(
                            id="source",
                            label="строка импорта",
                            icon="refresh",
                            placement="secondary",
                            action_type="link",
                            url=f"/app/imports/documents/{document_id}/review#raw-{raw_transaction_id}",
                        )
                    ],
                    technical_label=f"ID {operation_id} · из выписки",
                )
            ],
            filters_active=False,
            page=LedgerPage(page=1, per_page=50, total=1),
        ),
        detail=SimpleNamespace(
            account=account,
            balance=Decimal("32080.66"),
            entries=[entry],
            page=LedgerPage(page=1, per_page=50, total=1),
        ),
        account_types=list(AccountType),
        categories=[operation.category],
        filters=AccountEntryFilters(),
        operation_sources=list(OperationSource),
        operation_statuses=list(OperationStatus),
        operation_types=list(OperationType),
        page_urls={"previous": None, "next": None},
        properties=[],
    )

    assert "account-movement-list" in html
    assert "financial-row account-movement account-movement--expense" in html
    assert f'hx-select="#operation-{operation_id}"' not in html
    assert f'hx-target="#operation-{operation_id}"' not in html
    assert "account-movement__topline" in html
    assert "financial-row__description account-movement__description" in html
    row_html = html[html.index("financial-row account-movement") :]
    assert row_html.index("05.06.2026") < row_html.index("-2438.87")
    assert row_html.index("-2438.87") < row_html.index("Списание средств по платежу")
    assert row_html.index("Списание средств по платежу") < row_html.index("Продукты")
    assert row_html.index("Продукты") < row_html.index("Экспобанк карта")
    assert row_html.index("Экспобанк карта") < row_html.index("подтверждено")
    assert "review-meta" not in html
    assert "operation-ref" not in html
    assert "account-detail-hero" in html
    assert "account-detail-hero__main" in html
    assert "account-detail-hero__context" in html
    assert "account-detail-hero__actions" in html
    assert "account-detail-metrics" in html
    assert "account-detail-metric" in html
    assert "карта" in html
    assert "RUB" in html
    assert "account-detail-tools" in html
    assert "account-detail-tool__summary" in html
    assert "account-detail-tool__toggle" in html
    assert "filter-form account-filter-form" in html
    assert "filter-details__state" in html
    assert "inline-hint inline-hint-info" in html
    assert "filter-form__group" in html
    assert "filter-form__fields" in html
    assert "filter-form__fields--primary" in html
    assert "filter-form__fields--classification" in html
    assert "filter-form__fields--display" in html
    assert "filter-form__fields--filters" not in html
    assert "filter-form__footer" in html
    assert "filter-form__field--search" in html
    assert "account-detail-title" in html
    assert "account-settings-form" not in html
    assert "фильтры проводок" in html
    assert "Основное" not in html
    assert "Быстрый фильтр" not in html
    assert "Уточнение" not in html
    assert "Показ" not in html
    assert "Открыть" in html
    assert "Закрыть" in html
    assert "financial-row__amount account-movement__amount money-value money-expense" in html
    assert (
        "financial-row__meta-item--classification account-movement__meta-item--classification"
        in html
    )
    assert "financial-row__meta-item--expense account-movement__meta-item--expense" not in html
    assert "financial-row__actions row-actions account-movement__actions" in html
    assert "action-button action-primary action-edit primary-action" not in html
    assert "action-button action-secondary action-source" in html
    assert "ui-action__button ui-action__button--secondary ui-action__button--source" in html
    assert "row-actions__technical account-movement__technical" in html
    assert "financial-row__drawer row-drawer account-movement__drawer" not in html
    assert (
        "row-drawer__form account-movement__drawer-form operation-form operation-form--drawer"
    ) not in html
    assert "operation-form__footer--actions" not in row_html
    assert "row-drawer__footer account-movement__drawer-submit" not in html
    assert "сохранить изменения" not in html
    assert "Действия с операцией" not in html
    assert "Исправить операцию" not in row_html
    assert "строка импорта" in html
    assert 'hx-boost="false"' in html
    assert "разметка" not in html
    assert "Продукты" in html
    assert "ID операции" in html
    assert f"ID {operation_id}" in html
    assert f"/app/imports/documents/{document_id}/review#raw-{raw_transaction_id}" in html
    assert "<th>операция</th>" not in html
    assert html.count('<span class="action-label ui-action__label">строка импорта</span>') == 1


def test_account_movement_transfer_uses_transfer_amount_tone() -> None:
    operation_id = uuid4()
    html = (
        create_templates()
        .env.get_template("accounts/detail/_movement.html")
        .render(
            movement=AccountMovementVM(
                id=f"operation-{operation_id}",
                operation_id=operation_id,
                tone="transfer",
                amount=Decimal("2342.19"),
                amount_direction="transfer",
                currency="RUB",
                date_label="30.06.2026",
                badges=[],
                description="Списание со вклада проценты",
                meta=[
                    AccountMovementMetaVM("ВТБ вклад -> Экспобанк карта", "classification"),
                    AccountMovementMetaVM("Экспобанк карта"),
                    AccountMovementMetaVM("не влияет на прибыль"),
                    AccountMovementMetaVM("подтверждено"),
                ],
                result=OperationResultVM(
                    eyebrow="перевод · подтверждено",
                    title="ВТБ вклад -> Экспобанк карта",
                    tone="transfer",
                    detail="не влияет на прибыль",
                ),
                primary_action=None,
                secondary_actions=[],
                technical_label=f"ID {operation_id}",
            )
        )
    )

    assert "account-movement--transfer" in html
    assert "money-value money-transfer" in html
    assert "money-income" not in html
    assert "account-movement__meta-item--classification" in html
    assert "account-movement__meta-item--transfer" not in html
