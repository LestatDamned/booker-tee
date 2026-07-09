from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.features.categories.models import CategoryKind
from app.features.ledger.application.listing import LedgerPage, ManualOperationFilters
from app.features.ledger.models import OperationStatus, OperationType
from app.features.ledger.presentation.manual_operations.presenter import ManualOperationsPresenter
from app.features.ledger.router import manual_operation_anchor_url, parse_manual_operation_date
from app.templating import create_templates


def test_manual_operations_template_renders_lifecycle_actions() -> None:
    account_id = uuid4()
    category_id = uuid4()
    property_id = uuid4()
    operation_id = uuid4()
    account = SimpleNamespace(
        id=account_id,
        name="Карта",
        currency="RUB",
        type=None,
        is_active=True,
        initial_balance=Decimal("0.00"),
    )
    primary_entry = SimpleNamespace(
        account_id=account_id,
        account=account,
        amount=Decimal("-350.00"),
    )
    operation = SimpleNamespace(
        id=operation_id,
        type=OperationType.EXPENSE,
        status=OperationStatus.CONFIRMED,
        operation_date=date(2026, 6, 15),
        description="Кофе",
        category_id=category_id,
        category=SimpleNamespace(id=category_id, name="Кафе", kind=CategoryKind.EXPENSE),
        property_id=property_id,
        property=SimpleNamespace(id=property_id, name="Дом"),
        primary_entry=primary_entry,
        source_entry=None,
        destination_entry=None,
        edit_amount=Decimal("350.00"),
    )
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("ledger/manual.html").render(
        app_name="Booker Tee",
        accounts=[account],
        categories=[operation.category],
        filters=ManualOperationFilters(),
        focused_operation_id=operation_id,
        manual_operations=[operation],
        manual_page=LedgerPage(page=1, per_page=50, total=1),
        manual_page_vm=ManualOperationsPresenter().build_page(
            operations=cast(Any, [operation]),
            page=LedgerPage(page=1, per_page=50, total=1),
            filters=ManualOperationFilters(),
            focused_operation_id=operation_id,
            can_write=True,
        ),
        operation_statuses=list(OperationStatus),
        operation_types=list(OperationType),
        page_urls={"previous": None, "next": None},
        properties=[operation.property],
        workspace=SimpleNamespace(name="Personal"),
    )

    assert "Ручные операции нужны" in html
    assert "перевод только перемещает деньги между счетами" in html
    assert 'id="new-manual-operation"' in html
    assert "manual-operation-hero" in html
    assert "manual-operation-hero__actions" in html
    assert "manual-create-form" in html
    assert (
        'id="new-manual-operation" class="manual-create-form operation-form operation-form--create"'
    ) in html
    assert "manual-create-form__fields--primary" in html
    assert "manual-create-form__fields--classification" in html
    assert "manual-create-form__bottom" in html
    assert "operation-form__fields--primary" in html
    assert "operation-form__fields--classification" in html
    assert "operation-form__footer" in html
    assert "segmented-control" in html
    assert 'name="operation_type" type="radio" value="income"' in html
    assert 'name="operation_type" type="radio" value="expense"' in html
    assert 'name="operation_type" type="radio" value="transfer"' in html
    assert "x-show=\"operationType === 'transfer'\"" in html
    assert "x-bind:disabled=\"operationType !== 'transfer'\"" in html
    assert f'id="operation-{operation_id}"' in html
    assert f'hx-select="#operation-{operation_id}"' in html
    assert f'hx-target="#operation-{operation_id}"' in html
    assert 'hx-swap="outerHTML show:none"' in html
    assert 'hx-push-url="false"' in html
    assert f'hx-get="/ledger/manual/{operation_id}/edit"' in html
    assert 'hx-select=".manual-operation-edit-panel-content"' in html
    assert f'id="manual-operation-edit-panel-{operation_id}"' in html
    assert f'id="manual-operation-form-{operation_id}"' not in html
    assert "financial-row-list" in html
    assert "manual-operation-row--current" in html
    assert 'name="date_from" type="date"' in html
    assert "фильтры операций" in html
    assert "фильтры списка" not in html
    assert "filter-form manual-filter-form" in html
    assert "filter-details__state" in html
    assert "применены" in html
    assert "filter-form__fields--primary" in html
    assert "filter-form__fields--classification" in html
    assert "filter-form__fields--display" in html
    assert "form-panel form-panel-embedded" not in html
    assert 'name="operation_id"' in html
    assert "financial-row manual-operation-row manual-operation-row--expense" in html
    assert "row-drawer manual-operation-row__drawer" in html
    assert "Загружаем форму..." in html
    assert "manual-operation-row__drawer-form operation-form operation-form--drawer" not in html
    assert "тип операции" in html
    assert "сохранить изменения" not in html
    assert "financial-row__meta-item financial-row__meta-item--expense" in html
    assert "подтверждено" in html
    assert "financial-row__amount manual-operation-row__amount money-value money-expense" in html
    assert "<small>RUB</small>" in html
    assert f'action="/ledger/manual/{operation_id}"' not in html
    assert f'action="/ledger/manual/{operation_id}/cancel"' in html
    assert "Кофе" in html
    assert "Кафе" in html
    assert "15.06.2026" in html
    assert "action-save" not in html
    assert "action-edit" in html
    assert "action-form action-form-secondary action-form-cancel" in html
    assert "ui-action__form ui-action__form--secondary ui-action__form--cancel" in html
    assert "action-button action-secondary action-cancel" in html
    assert "ui-action__button ui-action__button--secondary ui-action__button--cancel" in html
    assert "отменить" in html


def test_manual_operation_edit_panel_lazy_loads_form_options() -> None:
    account_id = uuid4()
    category_id = uuid4()
    property_id = uuid4()
    operation_id = uuid4()
    account = SimpleNamespace(
        id=account_id,
        name="Карта",
        currency="RUB",
        type=None,
        is_active=True,
        initial_balance=Decimal("0.00"),
    )
    operation = SimpleNamespace(
        id=operation_id,
        type=OperationType.EXPENSE,
        status=OperationStatus.CONFIRMED,
        operation_date=date(2026, 6, 15),
        description="Кофе",
        category_id=category_id,
        category=SimpleNamespace(id=category_id, name="Кафе", kind=CategoryKind.EXPENSE),
        property_id=property_id,
        property=SimpleNamespace(id=property_id, name="Дом"),
        primary_entry=SimpleNamespace(
            account_id=account_id,
            account=account,
            amount=Decimal("-350.00"),
        ),
        source_entry=None,
        destination_entry=None,
        edit_amount=Decimal("350.00"),
    )
    templates = create_templates()
    edit_panel = ManualOperationsPresenter().build_edit_panel(
        cast(Any, operation),
        can_write=True,
    )

    html = templates.env.get_template("ledger/manual/_edit_panel.html").render(
        accounts=[account],
        categories=[operation.category],
        edit_panel=edit_panel,
        properties=[operation.property],
    )

    assert "manual-operation-edit-panel-content" in html
    assert f'id="manual-operation-form-{operation_id}"' in html
    assert f'action="/ledger/manual/{operation_id}"' in html
    assert "Исправить операцию" in html
    assert "manual-operation-row__drawer-form operation-form operation-form--drawer" in html
    assert "тип операции" in html
    assert "дд.мм.гггг" in html
    assert "Карта · RUB" in html
    assert "Кафе" in html
    assert "Дом" in html
    assert "сохранить изменения" in html
    assert "action-save" in html


def test_manual_operations_template_guides_empty_states() -> None:
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html_without_accounts = templates.env.get_template("ledger/manual.html").render(
        app_name="Booker Tee",
        accounts=[],
        categories=[],
        filters=ManualOperationFilters(),
        manual_operations=[],
        manual_page=LedgerPage(page=1, per_page=50, total=0),
        manual_page_vm=ManualOperationsPresenter().build_page(
            operations=[],
            page=LedgerPage(page=1, per_page=50, total=0),
            filters=ManualOperationFilters(),
            focused_operation_id=None,
            can_write=True,
        ),
        operation_statuses=list(OperationStatus),
        operation_types=list(OperationType),
        page_urls={"previous": None, "next": None},
        properties=[],
        workspace=SimpleNamespace(name="Personal"),
    )

    assert "Сначала добавьте счет" in html_without_accounts
    assert "Ручная операция всегда двигает деньги" in html_without_accounts
    assert 'href="/accounts"' in html_without_accounts

    account = SimpleNamespace(
        id=uuid4(),
        name="Карта",
        currency="RUB",
        type=None,
        is_active=True,
        initial_balance=Decimal("0.00"),
    )
    html_with_account = templates.env.get_template("ledger/manual.html").render(
        app_name="Booker Tee",
        accounts=[account],
        categories=[],
        filters=ManualOperationFilters(),
        manual_operations=[],
        manual_page=LedgerPage(page=1, per_page=50, total=0),
        manual_page_vm=ManualOperationsPresenter().build_page(
            operations=[],
            page=LedgerPage(page=1, per_page=50, total=0),
            filters=ManualOperationFilters(),
            focused_operation_id=None,
            can_write=True,
        ),
        operation_statuses=list(OperationStatus),
        operation_types=list(OperationType),
        page_urls={"previous": None, "next": None},
        properties=[],
        workspace=SimpleNamespace(name="Personal"),
    )

    assert "Ручных операций пока нет" in html_with_account
    assert "наличных движений, корректировок" in html_with_account
    assert 'href="#new-manual-operation"' not in html_with_account


def test_manual_operations_template_allows_restore_and_delete_cancelled_operation() -> None:
    account_id = uuid4()
    operation_id = uuid4()
    account = SimpleNamespace(
        id=account_id,
        name="Карта",
        currency="RUB",
        type=None,
        is_active=True,
        initial_balance=Decimal("0.00"),
    )
    primary_entry = SimpleNamespace(
        account_id=account_id,
        account=account,
        amount=Decimal("100.00"),
    )
    operation = SimpleNamespace(
        id=operation_id,
        type=OperationType.INCOME,
        status=OperationStatus.IGNORED,
        operation_date=date(2026, 6, 15),
        description="Возврат",
        category_id=None,
        category=None,
        property_id=None,
        property=None,
        primary_entry=primary_entry,
        source_entry=None,
        destination_entry=None,
        edit_amount=Decimal("100.00"),
    )
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("ledger/manual.html").render(
        app_name="Booker Tee",
        accounts=[account],
        categories=[],
        filters=ManualOperationFilters(),
        manual_operations=[operation],
        manual_page=LedgerPage(page=1, per_page=50, total=1),
        manual_page_vm=ManualOperationsPresenter().build_page(
            operations=cast(Any, [operation]),
            page=LedgerPage(page=1, per_page=50, total=1),
            filters=ManualOperationFilters(),
            focused_operation_id=None,
            can_write=True,
        ),
        operation_statuses=list(OperationStatus),
        operation_types=list(OperationType),
        page_urls={"previous": None, "next": None},
        properties=[],
        workspace=SimpleNamespace(name="Personal"),
    )

    assert f'action="/ledger/manual/{operation_id}/restore"' in html
    assert f'action="/ledger/manual/{operation_id}/delete"' in html
    assert "восстановить" in html
    assert "удалить" in html
    assert "action-edit" not in html


def test_manual_operation_anchor_url_points_to_operation_card() -> None:
    operation_id = uuid4()

    assert (
        manual_operation_anchor_url(operation_id)
        == f"/ledger/manual?operation_id={operation_id}#operation-{operation_id}"
    )


def test_parse_manual_operation_date_accepts_russian_and_iso_formats() -> None:
    assert parse_manual_operation_date("15.06.2026") == date(2026, 6, 15)
    assert parse_manual_operation_date("2026-06-15") == date(2026, 6, 15)
