from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.features.imports.models import RawTransactionStatus
from app.features.ledger.models import OperationType
from app.templating import create_templates


def test_review_template_prefills_suggested_rule_category() -> None:
    suggested_category_id = uuid4()
    uncategorized_category_id = uuid4()
    row_id = uuid4()
    row = SimpleNamespace(
        id=row_id,
        row_index=3,
        status=RawTransactionStatus.NEEDS_REVIEW,
        operation_date="2026-05-27",
        operation_date_raw=None,
        amount=Decimal("-1470.00"),
        amount_raw=None,
        currency="RUB",
        description_normalized="Списание в KRASNOE&BELOE по карте",
        description_raw=None,
        normalization_error=None,
        suggested_by_rule_id=uuid4(),
        suggested_category_id=suggested_category_id,
        suggested_property_id=None,
        linked_operation_id=None,
        raw_payload={
            "rule_suggestion": {
                "application_mode": "suggest",
                "pattern": "KRASNOE&BELOE",
            },
        },
    )
    document = SimpleNamespace(
        id=uuid4(),
        original_filename="statement.pdf",
        status="requires_review",
        parse_attempts=[],
        raw_transactions=[row],
    )
    categories = [
        SimpleNamespace(
            id=uncategorized_category_id, name="Без категории", system_key="uncategorized"
        ),
        SimpleNamespace(id=suggested_category_id, name="Продукты", system_key=None),
    ]
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("imports/review.html").render(
        app_name="Booker Tee",
        document=document,
        categories=categories,
        properties=[],
        accounts=[],
        transfer_suggestions={},
    )

    assert "совет правила" in html
    assert "Предложено" in html
    assert "Исправить" in html
    assert "Подтвердить" in html
    assert "KRASNOE&amp;BELOE" in html
    assert f'id="raw-{row_id}"' in html
    assert "review-status-needs_review" in html
    assert f'<input type="hidden" name="category_id" value="{suggested_category_id}">' in html
    assert f'<option value="{suggested_category_id}" selected>' in html
    assert f'<option value="{uncategorized_category_id}" selected>' not in html


def test_review_template_shows_transfer_route_for_linked_operation() -> None:
    operation_id = uuid4()
    source_account = SimpleNamespace(name="Вклад ВТБ")
    destination_account = SimpleNamespace(name="Карта Экспобанк")
    operation = SimpleNamespace(
        id=operation_id,
        operation_date="2026-05-29",
        type=OperationType.TRANSFER,
        category=SimpleNamespace(name="Перевод"),
        property=None,
        description="Перевод между своими счетами",
        money_entries=[
            SimpleNamespace(amount=Decimal("-21000.00"), account=source_account),
            SimpleNamespace(amount=Decimal("21000.00"), account=destination_account),
        ],
    )
    row = SimpleNamespace(
        id=uuid4(),
        row_index=1,
        status=RawTransactionStatus.CONFIRMED,
        operation_date="2026-05-29",
        operation_date_raw=None,
        amount=Decimal("-21000.00"),
        amount_raw=None,
        currency="RUB",
        description_normalized="Перевод через СБП",
        description_raw=None,
        normalization_error=None,
        suggested_by_rule_id=None,
        suggested_category_id=None,
        suggested_property_id=None,
        linked_operation_id=operation_id,
        linked_operation=operation,
        raw_payload={},
    )
    document = SimpleNamespace(
        id=uuid4(),
        original_filename="statement.pdf",
        status="requires_review",
        parse_attempts=[],
        raw_transactions=[row],
    )
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("imports/review.html").render(
        app_name="Booker Tee",
        document=document,
        categories=[],
        properties=[],
        accounts=[],
        transfer_suggestions={},
    )

    assert "перевод:" in html
    assert "review-status-confirmed" in html
    assert "badge-transfer" in html
    assert "Вклад ВТБ" in html
    assert "Карта Экспобанк" in html
    assert "из" in html
    assert "в" in html


def test_review_template_shows_readable_transfer_candidate_labels() -> None:
    document_id = uuid4()
    account_id = uuid4()
    row = SimpleNamespace(
        id=uuid4(),
        row_index=1,
        status=RawTransactionStatus.NORMALIZED,
        operation_date="2026-05-29",
        operation_date_raw=None,
        amount=Decimal("-21000.00"),
        amount_raw=None,
        currency="RUB",
        description_normalized="Перевод через СБП",
        description_raw=None,
        normalization_error=None,
        suggested_by_rule_id=None,
        suggested_category_id=None,
        suggested_property_id=None,
        linked_operation_id=None,
        raw_payload={},
    )
    candidate = SimpleNamespace(
        id=uuid4(),
        row_index=0,
        account_id=account_id,
        account=SimpleNamespace(name="Карта Экспобанк"),
        operation_date="2026-05-29",
        operation_date_raw=None,
        amount=Decimal("21000.00"),
        currency="RUB",
        description_normalized="Зачисление средств по платежу",
        description_raw=None,
    )
    document = SimpleNamespace(
        id=document_id,
        original_filename="statement.pdf",
        status="requires_review",
        parse_attempts=[],
        raw_transactions=[row],
    )
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("imports/review.html").render(
        app_name="Booker Tee",
        document=document,
        categories=[SimpleNamespace(id=uuid4(), name="Без категории", system_key="uncategorized")],
        properties=[],
        accounts=[SimpleNamespace(id=account_id, name="Карта Экспобанк")],
        transfer_suggestions={row.id: [SimpleNamespace(raw_transaction=candidate, day_distance=0)]},
    )

    assert "Счет перевода" in html
    assert "Парная строка" in html
    assert "без парной строки" in html
    assert "Карта Экспобанк" in html
    assert "Зачисление средств по платежу" in html
