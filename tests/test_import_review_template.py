from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.features.categories.models import CategoryKind
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
    assert "review-money money-value" in html
    assert "KRASNOE&amp;BELOE" in html
    assert f'id="raw-{row_id}"' in html
    assert 'hx-boost="true"' in html
    assert f'hx-target="#raw-{row_id}"' in html
    assert 'hx-swap="outerHTML show:none"' in html
    assert 'hx-push-url="false"' in html
    assert "новая" in html
    assert "action-title-row" not in html
    assert f'action="/imports/documents/{document.id}/raw-transactions/{row_id}/categories"' in html
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


def test_review_action_response_sends_sibling_rows_oob() -> None:
    current_row = SimpleNamespace(
        id=uuid4(),
        row_index=1,
        status=RawTransactionStatus.NORMALIZED,
        operation_date="2026-05-29",
        operation_date_raw=None,
        amount=Decimal("-100.00"),
        amount_raw=None,
        currency="RUB",
        description_normalized="KRASNOE&BELOE",
        description_raw=None,
        normalization_error=None,
        suggested_by_rule_id=None,
        suggested_category_id=None,
        suggested_property_id=None,
        linked_operation_id=None,
        raw_payload={},
    )
    sibling_row = SimpleNamespace(
        id=uuid4(),
        row_index=2,
        status=RawTransactionStatus.SUGGESTED,
        operation_date="2026-05-30",
        operation_date_raw=None,
        amount=Decimal("-200.00"),
        amount_raw=None,
        currency="RUB",
        description_normalized="KRASNOE&BELOE",
        description_raw=None,
        normalization_error=None,
        suggested_by_rule_id=uuid4(),
        suggested_category_id=uuid4(),
        suggested_property_id=None,
        suggested_operation_type=OperationType.EXPENSE,
        linked_operation_id=None,
        raw_payload={
            "rule_suggestion": {
                "application_mode": "suggest",
                "pattern": "KRASNOE&BELOE",
            }
        },
    )
    document = SimpleNamespace(
        id=uuid4(),
        original_filename="statement.pdf",
        status="requires_review",
        parse_attempts=[],
        raw_transactions=[current_row, sibling_row],
    )
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("imports/_review_action_response.html").render(
        app_name="Booker Tee",
        document=document,
        current_row=current_row,
        categories=[SimpleNamespace(id=uuid4(), name="Без категории", system_key="uncategorized")],
        properties=[],
        accounts=[],
        balance_chain_problems={},
        transfer_suggestions={},
        oob_raw_transaction_ids=frozenset({sibling_row.id}),
    )

    assert f'id="raw-{current_row.id}"' in html
    assert f'id="raw-{sibling_row.id}"' in html
    assert html.count('hx-swap-oob="true"') == 2
    assert 'id="review-next-step" hx-swap-oob="true"' in html
    assert "Осталось обработать 2 из 2 строк." in html


def test_review_item_selects_newly_created_category() -> None:
    row_id = uuid4()
    created_category_id = uuid4()
    uncategorized_category_id = uuid4()
    row = SimpleNamespace(
        id=row_id,
        row_index=1,
        status=RawTransactionStatus.NORMALIZED,
        operation_date="2026-05-29",
        operation_date_raw=None,
        amount=Decimal("-100.00"),
        amount_raw=None,
        currency="RUB",
        description_normalized="Аптека",
        description_raw=None,
        normalization_error=None,
        suggested_by_rule_id=None,
        suggested_category_id=None,
        suggested_property_id=None,
        linked_operation_id=None,
        raw_payload={},
    )
    document = SimpleNamespace(id=uuid4(), raw_transactions=[row])
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("imports/_review_item.html").render(
        document=document,
        row=row,
        categories=[
            SimpleNamespace(
                id=uncategorized_category_id,
                name="Без категории",
                system_key="uncategorized",
            ),
            SimpleNamespace(id=created_category_id, name="Аптеки", system_key=None),
        ],
        category_kinds=list(CategoryKind),
        properties=[],
        accounts=[],
        balance_chain_problems={},
        open_category_editor_by_row={row_id: True},
        selected_category_id_by_row={row_id: created_category_id},
        transfer_suggestions={},
    )

    assert 'class="action-details action-accordion" open' in html
    assert f'<option value="{created_category_id}" selected>' in html
    assert f'<option value="{uncategorized_category_id}" selected>' not in html
    assert "Новая категория" in html
    assert "расход" in html
    assert "openCategoryDialog(event)" in html
    assert '@click.stop="openCategoryDialog($event)"' in html


def test_review_item_reopens_category_dialog_with_error() -> None:
    row_id = uuid4()
    row = SimpleNamespace(
        id=row_id,
        row_index=1,
        status=RawTransactionStatus.NORMALIZED,
        operation_date="2026-05-29",
        operation_date_raw=None,
        amount=Decimal("-100.00"),
        amount_raw=None,
        currency="RUB",
        description_normalized="Аптека",
        description_raw=None,
        normalization_error=None,
        suggested_by_rule_id=None,
        suggested_category_id=None,
        suggested_property_id=None,
        linked_operation_id=None,
        raw_payload={},
    )
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("imports/_review_item.html").render(
        document=SimpleNamespace(id=uuid4(), raw_transactions=[row]),
        row=row,
        categories=[SimpleNamespace(id=uuid4(), name="Без категории", system_key="uncategorized")],
        category_kinds=list(CategoryKind),
        properties=[],
        accounts=[],
        balance_chain_problems={},
        open_category_editor_by_row={row_id: True},
        category_dialog_error_by_row={row_id: "Категория с таким названием уже есть."},
        category_dialog_name_by_row={row_id: "Аптека"},
        transfer_suggestions={},
    )

    assert 'class="action-details action-accordion" open' in html
    assert 'role="alert"' in html
    assert "Категория с таким названием уже есть." in html
    assert 'value="Аптека"' in html
    assert "showModal()" in html


def test_review_template_shows_balance_chain_problem_on_row() -> None:
    row = SimpleNamespace(
        id=uuid4(),
        row_index=1,
        status=RawTransactionStatus.NORMALIZED,
        operation_date="2026-05-29",
        operation_date_raw=None,
        amount=Decimal("-30.00"),
        amount_raw=None,
        currency="RUB",
        description_normalized="Кафе",
        description_raw=None,
        normalization_error=None,
        suggested_by_rule_id=None,
        suggested_category_id=None,
        suggested_property_id=None,
        linked_operation_id=None,
        raw_payload={},
    )
    document = SimpleNamespace(
        id=uuid4(),
        original_filename="statement.pdf",
        status="requires_review",
        parse_attempts=[
            SimpleNamespace(
                validation_report_json={
                    "status": "mismatch",
                    "message": "Остатки после операций не совпадают с суммами строк.",
                    "extracted_count": 2,
                    "needs_review_count": 0,
                    "currency": "RUB",
                    "calculated_total_inflow": "100.00",
                    "calculated_total_outflow": "30.00",
                    "statement_total_inflow": None,
                    "statement_total_outflow": None,
                    "inflow_difference": None,
                    "outflow_difference": None,
                }
            )
        ],
        raw_transactions=[row],
    )
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("imports/review.html").render(
        app_name="Booker Tee",
        document=document,
        categories=[SimpleNamespace(id=uuid4(), name="Без категории", system_key="uncategorized")],
        properties=[],
        accounts=[],
        balance_chain_problems={1: ["остаток не сходится: ожидалось 1070.00, в строке 1060.00"]},
        transfer_suggestions={},
    )

    assert "Остатки после операций не совпадают с суммами строк." in html
    assert "суммы или остатки не сходятся с выпиской" in html
    assert "остаток не сходится: ожидалось 1070.00, в строке 1060.00" in html
