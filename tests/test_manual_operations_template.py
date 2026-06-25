from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.features.categories.models import CategoryKind
from app.features.ledger.models import OperationStatus, OperationType
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
        manual_operations=[operation],
        properties=[operation.property],
        workspace=SimpleNamespace(name="Personal"),
    )

    assert "Ручные операции нужны" in html
    assert "перевод только перемещает деньги между счетами" in html
    assert 'id="new-manual-operation"' in html
    assert "segmented-control" in html
    assert 'name="operation_type" type="radio" value="income"' in html
    assert 'name="operation_type" type="radio" value="expense"' in html
    assert 'name="operation_type" type="radio" value="transfer"' in html
    assert f'id="operation-{operation_id}"' in html
    assert f'class="detached-form" id="manual-operation-form-{operation_id}"' in html
    assert "entity-card-list" in html
    assert "entity-card manual-operation-card manual-operation-expense" in html
    assert "form-panel form-panel-embedded" in html
    assert "badge badge-expense" in html
    assert "badge badge-confirmed" in html
    assert "manual-operation-money money-value money-expense" in html
    assert "<small>RUB</small>" in html
    assert f'action="/ledger/manual/{operation_id}"' in html
    assert f'action="/ledger/manual/{operation_id}/cancel"' in html
    assert "Кофе" in html
    assert "Кафе" in html
    assert "15.06.2026" in html
    assert "дд.мм.гггг" in html
    assert "сохранить" in html
    assert "отменить" in html


def test_manual_operations_template_guides_empty_states() -> None:
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html_without_accounts = templates.env.get_template("ledger/manual.html").render(
        app_name="Booker Tee",
        accounts=[],
        categories=[],
        manual_operations=[],
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
        manual_operations=[],
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
        manual_operations=[operation],
        properties=[],
        workspace=SimpleNamespace(name="Personal"),
    )

    assert f'action="/ledger/manual/{operation_id}/restore"' in html
    assert f'action="/ledger/manual/{operation_id}/delete"' in html
    assert "восстановить" in html
    assert "удалить" in html


def test_manual_operation_anchor_url_points_to_operation_card() -> None:
    operation_id = uuid4()

    assert manual_operation_anchor_url(operation_id) == f"/ledger/manual#operation-{operation_id}"


def test_parse_manual_operation_date_accepts_russian_and_iso_formats() -> None:
    assert parse_manual_operation_date("15.06.2026") == date(2026, 6, 15)
    assert parse_manual_operation_date("2026-06-15") == date(2026, 6, 15)
