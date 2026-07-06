import re
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

from app.features.imports.models import RawTransactionStatus
from app.features.imports.presentation.review.models import ActionVM
from app.features.imports.presentation.review.page import build_review_page_context
from app.features.imports.routes.form_values import RawTransactionReviewFormParser
from app.features.imports.routes.review_responses import (
    ReviewActionResponseRequest,
    ReviewActionResponseState,
)
from app.features.ledger.models import OperationType
from app.templating import create_templates

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def render_review_page(
    *,
    document: object,
    categories: Sequence[object],
    properties: Sequence[object] | None = None,
    accounts: Sequence[object] | None = None,
    transfer_suggestions: Mapping[UUID, Sequence[object]] | None = None,
    existing_transfer_suggestions: Mapping[UUID, Sequence[object]] | None = None,
    selected_category_id_by_row: Mapping[UUID, UUID] | None = None,
    open_category_editor_by_row: Mapping[UUID, bool] | None = None,
    create_category_error_by_row: Mapping[UUID, str] | None = None,
    create_category_initial_name_by_row: Mapping[UUID, str] | None = None,
    extra_context: dict[str, object] | None = None,
) -> str:
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")
    page_context = build_review_page_context(
        document=document,
        accounts=accounts or [],
        categories=categories,
        properties=properties or [],
        transfer_suggestions=transfer_suggestions or {},
        existing_transfer_suggestions=existing_transfer_suggestions or {},
        selected_category_id_by_row=selected_category_id_by_row,
        open_category_editor_by_row=open_category_editor_by_row,
        create_category_error_by_row=create_category_error_by_row,
        create_category_initial_name_by_row=create_category_initial_name_by_row,
    )
    template_values = page_context.template_values(
        app_name="Booker Tee",
        workspace=SimpleNamespace(id=uuid4()),
    )
    if extra_context:
        template_values.update(extra_context)
    return templates.env.get_template("imports/review.html").render(**template_values)


def test_review_item_partial_keeps_review_item_vm_contract() -> None:
    source = (PROJECT_ROOT / "src/app/templates/imports/review/_item.html").read_text(
        encoding="utf-8"
    )

    assert re.search(r"\bitem\.row\b", source) is None
    assert "{% set row" not in source
    assert "document." not in source
    assert "use_review_item_vm" not in source


def render_action(action: ActionVM, *, csrf_token: str | None = "csrf-test-token") -> str:
    templates = create_templates()
    return templates.env.get_template("ui/_action.html").render(
        action=action,
        csrf_token=csrf_token,
    )


def render_action_set(item: object, *, csrf_token: str | None = "csrf-test-token") -> str:
    templates = create_templates()
    return templates.env.get_template("imports/review/_action_set.html").render(
        item=item,
        csrf_token=csrf_token,
    )


def test_action_partial_renders_post_action_with_csrf_hidden_fields_and_confirm() -> None:
    html = render_action(
        ActionVM(
            id="ignore",
            label="Игнорировать",
            icon="ignore",
            placement="danger",
            action_type="post",
            url="/imports/documents/document-id/raw-transactions/row-id/status",
            hidden_fields={"action": "ignore"},
            style="danger",
            confirm_message="Игнорировать эту строку импорта?",
        )
    )

    assert "<form" in html
    assert 'method="post"' in html
    assert 'action="/imports/documents/document-id/raw-transactions/row-id/status"' in html
    assert 'name="csrf_token" value="csrf-test-token"' in html
    assert 'name="action" value="ignore"' in html
    assert 'hx-confirm="Игнорировать эту строку импорта?"' in html
    assert "action-form-danger" in html
    assert "action-ignore" in html
    assert 'aria-label="Игнорировать"' in html
    assert '<span class="action-label">Игнорировать</span>' in html
    assert "button-danger" in html
    assert "Игнорировать" in html


def test_action_partial_renders_link_action_without_form_or_hidden_fields() -> None:
    html = render_action(
        ActionVM(
            id="open_operation",
            label="Открыть операцию",
            icon="file-text",
            placement="primary",
            action_type="link",
            url="/ledger/manual?operation_id=operation-id",
        )
    )

    assert "<a" in html
    assert "action-button" in html
    assert "action-primary" in html
    assert "action-open_operation" in html
    assert "primary-action" in html
    assert 'aria-label="Открыть операцию"' in html
    assert '<span class="action-label">Открыть операцию</span>' in html
    assert 'href="/ledger/manual?operation_id=operation-id"' in html
    assert "<form" not in html
    assert 'type="hidden"' not in html
    assert "Открыть операцию" in html


def test_action_partial_renders_panel_toggle_without_mutation_fields() -> None:
    html = render_action(
        ActionVM(
            id="category_panel",
            label="Разобрать",
            icon="settings",
            placement="primary",
            action_type="panel_toggle",
            panel_id="category-panel-row-id",
        )
    )

    assert "<button" in html
    assert 'type="button"' in html
    assert 'aria-controls="category-panel-row-id"' in html
    assert 'aria-label="Разобрать"' in html
    assert '<span class="action-label">Разобрать</span>' in html
    assert "document.getElementById('category-panel-row-id')" in html
    assert "?.click()" in html
    assert "<form" not in html
    assert 'type="hidden"' not in html
    assert "Разобрать" in html


def test_action_set_partial_renders_primary_secondary_menu_and_danger_slots() -> None:
    item = SimpleNamespace(
        primary_action=ActionVM(
            id="confirm",
            label="Подтвердить",
            icon="check",
            placement="primary",
            action_type="post",
            url="/status",
            hidden_fields={"action": "confirm"},
        ),
        visible_secondary_action=ActionVM(
            id="category_panel",
            label="Изменить",
            icon="settings",
            placement="secondary",
            action_type="panel_toggle",
            panel_id="category-panel",
        ),
        menu_actions=[
            ActionVM(
                id="transfer_panel",
                label="Сделать перевод",
                icon="refresh",
                placement="secondary",
                action_type="panel_toggle",
                panel_id="transfer-panel",
            )
        ],
        danger_actions=[
            ActionVM(
                id="ignore",
                label="Игнорировать",
                icon="ignore",
                placement="danger",
                action_type="post",
                url="/status",
                hidden_fields={"action": "ignore"},
                style="danger",
                confirm_message="Игнорировать эту строку импорта?",
            )
        ],
    )

    html = render_action_set(item)

    assert "review-actions__row" in html
    assert "primary-actions" in html
    assert "secondary-actions" in html
    assert "review-actions__menu" in html
    assert "review-actions__menu-section" in html
    assert "review-action-heading" not in html
    assert "Действие" not in html
    assert "Уточнить" not in html
    assert "Еще действия" in html
    assert "Открыть" in html
    assert "Закрыть" in html
    assert "danger-zone" in html
    assert "Опасная зона" in html
    assert "Подтвердить" in html
    assert "Изменить" in html
    assert "Сделать перевод" in html
    assert "Игнорировать" in html
    assert html.index("primary-actions") < html.index("secondary-actions")
    assert html.index("review-actions__menu-section") < html.index("danger-zone")


def test_action_set_partial_hides_single_danger_action_behind_correction_toggle() -> None:
    item = SimpleNamespace(
        primary_action=None,
        visible_secondary_action=None,
        menu_actions=[],
        danger_actions=[
            ActionVM(
                id="undo_posting",
                label="Отменить проведение",
                icon="rotate-ccw",
                placement="danger",
                action_type="post",
                url="/undo-posting",
                style="danger",
                confirm_message="Отменить связь строки с проведенной операцией?",
            )
        ],
    )

    html = render_action_set(item)

    assert "review-actions__correction" in html
    assert "Исправить" in html
    assert "Открыть" in html
    assert "Закрыть" in html
    assert "review-actions__danger-direct" in html
    assert "Отменить проведение" in html
    assert "Еще действия" not in html
    assert "Опасная зона" not in html
    assert "review-actions__menu" not in html


def test_review_page_context_uses_review_item_vm_by_default() -> None:
    account_id = uuid4()
    category_id = uuid4()
    row_id = uuid4()
    row = SimpleNamespace(
        id=row_id,
        row_index=1,
        status=RawTransactionStatus.NORMALIZED,
        account_id=account_id,
        operation_date="2026-05-29",
        operation_date_raw=None,
        amount=Decimal("-900.00"),
        amount_raw=None,
        currency="RUB",
        description_normalized="Veesp hosting",
        description_raw=None,
        normalization_error=None,
        suggested_by_rule_id=None,
        suggested_category_id=category_id,
        suggested_property_id=None,
        suggested_operation_type=None,
        linked_operation_id=None,
        linked_operation=None,
        raw_payload={},
    )
    document = SimpleNamespace(
        id=uuid4(),
        account_id=None,
        original_filename="statement.pdf",
        status="requires_review",
        parse_attempts=[],
        raw_transactions=[row],
    )
    categories = [SimpleNamespace(id=category_id, name="Хостинг", system_key=None)]
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    page_context = build_review_page_context(
        document=document,
        accounts=[SimpleNamespace(id=account_id, name="Карта")],
        categories=categories,
        properties=[],
        transfer_suggestions={},
        existing_transfer_suggestions={},
    )
    html = templates.env.get_template("imports/review.html").render(
        **page_context.template_values(
            app_name="Booker Tee",
            workspace=SimpleNamespace(id=uuid4()),
        ),
    )

    assert row_id in page_context.review_items_by_id
    assert page_context.review_item_for(row_id) is page_context.review_items_by_id[row_id]
    assert page_context.review_items_for_row_ids({row_id}) == page_context.review_items
    assert [item.id for item in page_context.review_items] == [row_id]
    assert page_context.review_page.header.status_label == "требует проверки"
    assert page_context.review_page.header.apply_rules_action.action_type == "post"
    assert (
        page_context.review_page.header.apply_rules_action.url
        == f"/imports/documents/{document.id}/apply-rules"
    )
    assert page_context.review_page.queue.title == "Продолжайте проверку"
    assert page_context.review_page.validation is None
    assert page_context.review_page.tools.workflow.steps[3].label == "Проверка"
    assert page_context.review_page.tools.workflow.steps[3].state == "current"
    assert page_context.review_page.has_review_items is True
    assert "review-item--vm" in html


def test_review_template_prefills_suggested_rule_category() -> None:
    account_id = uuid4()
    suggested_category_id = uuid4()
    uncategorized_category_id = uuid4()
    row_id = uuid4()
    row = SimpleNamespace(
        id=row_id,
        row_index=3,
        status=RawTransactionStatus.NEEDS_REVIEW,
        account_id=account_id,
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
        account_id=None,
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
    html = render_review_page(
        document=document,
        accounts=[SimpleNamespace(id=account_id, name="Экспобанк карта")],
        categories=categories,
    )

    assert "review-signal-proposal" in html
    assert "правило:" in html
    assert "KRASNOE" in html
    assert "BELOE" in html
    assert "категория: Продукты" in html
    assert "review-ledger-summary-suggested" in html
    assert "review-ledger-type tone-expense" in html
    assert "review-ledger-status" in html
    assert "review-ledger-title" in html
    assert "review-state-summary" not in html
    assert "Продукты" in html
    assert html.index("review-signal-proposal") < html.index("review-actions")
    assert html.index("review-ledger-summary-suggested") < html.index("Подтвердить предложение")
    assert "Подтвердить предложение" in html
    assert "review-queue-bar" in html
    assert "review-queue-status" in html
    assert "review-queue-actions" in html
    assert "review-page-tools" in html
    assert "review-rule-hint" in html
    assert "review-workflow-card" in html
    assert "import-hidden-technical-details" in html
    assert "Технические детали документа" not in html
    assert "review-item-next" in html
    assert "Продолжайте проверку" in html
    assert "к следующей" in html
    assert "review-money money-value" in html
    assert "KRASNOE&amp;BELOE" in html
    assert f'id="raw-{row_id}"' in html
    assert 'hx-boost="true"' in html
    assert f'hx-target="#raw-{row_id}"' in html
    assert 'hx-swap="outerHTML show:none"' in html
    assert 'hx-push-url="false"' in html
    assert 'aria-label="Новая категория"' in html
    assert "action-title-row" not in html
    assert f'action="/imports/documents/{document.id}/raw-transactions/{row_id}/status"' in html
    assert f'<option value="{suggested_category_id}" selected>' in html
    assert f'<option value="{uncategorized_category_id}" selected>' not in html
    assert "ID правила" not in html


def test_review_template_can_render_review_item_vm_slice() -> None:
    account_id = uuid4()
    category_id = uuid4()
    row = SimpleNamespace(
        id=uuid4(),
        row_index=7,
        status=RawTransactionStatus.NORMALIZED,
        account_id=account_id,
        operation_date="2026-05-29",
        operation_date_raw=None,
        amount=Decimal("-900.00"),
        amount_raw=None,
        currency="RUB",
        description_normalized="Veesp hosting",
        description_raw=None,
        normalization_error=None,
        suggested_by_rule_id=None,
        suggested_category_id=category_id,
        suggested_property_id=None,
        suggested_operation_type=None,
        linked_operation_id=None,
        linked_operation=None,
        raw_payload={},
    )
    document = SimpleNamespace(
        id=uuid4(),
        account_id=None,
        original_filename="statement.pdf",
        status="requires_review",
        parse_attempts=[],
        raw_transactions=[row],
    )
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")
    page_context = build_review_page_context(
        document=document,
        accounts=[SimpleNamespace(id=account_id, name="Карта")],
        categories=[SimpleNamespace(id=category_id, name="Хостинг", system_key=None)],
        properties=[],
        transfer_suggestions={},
        existing_transfer_suggestions={},
    )

    html = templates.env.get_template("imports/review.html").render(
        **page_context.template_values(
            app_name="Booker Tee",
            workspace=SimpleNamespace(id=uuid4()),
        ),
    )

    assert "review-item--vm" in html
    assert "review-status-ready_to_confirm" in html
    assert "готово" in html
    assert "Подтвердить" in html
    assert "Сохранить и подтвердить" in html
    assert "Игнорировать" in html
    assert "hx-confirm=" in html
    assert html.index("29.05.2026") < html.index("Veesp hosting")
    assert "review-topline" in html
    assert "review-date-chip" in html
    assert "review-state-summary" in html
    assert "review-state-primary" in html
    assert "review-state-secondary" in html
    assert "по сумме" in html
    assert "предложено операция связана" not in html
    assert "review-panels" in html
    assert "review-panel__tab--primary" in html
    assert "review-panel__tab--alternative" in html
    assert "основной разбор строки" in html
    assert "если это перемещение между счетами" in html
    assert "review-panel__tabs" in html
    assert "review-panel__drawers" in html
    assert "review-panel__tab" in html
    assert "togglePanel(" in html
    assert 'x-show="activePanel ===' in html
    assert "Открыть" in html
    assert "Закрыть" in html
    assert "review-panel-body" in html
    assert html.index("review-topline") < html.index("review-description")
    assert html.index("review-actions") < html.index("review-panels")


def test_review_item_vm_omits_empty_badge_flag_and_panel_regions() -> None:
    row_id = uuid4()
    item = SimpleNamespace(
        id=row_id,
        anchor_id=f"raw-{row_id}",
        row_index=1,
        visual_state="confirmed",
        is_next=False,
        date_label="2026-05-29",
        account_label="Карта",
        amount_label="100.00",
        currency="RUB",
        money_tone="money-income",
        description="Возврат",
        proposal_summary=None,
        operation_link=None,
        problems=[],
        primary_action=None,
        visible_secondary_action=None,
        menu_actions=[],
        danger_actions=[],
        panels=[],
        oob=False,
    )

    html = create_templates().env.get_template("imports/review/_item.html").render(item=item)

    assert "review-item--vm" in html
    assert "review-state-summary" not in html
    assert "review-flags" not in html
    assert "review-panels" not in html


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
    html = render_review_page(
        document=document,
        categories=[],
    )

    assert "перевод:" in html
    assert "review-signal-operation" not in html
    assert "review-action-status" in html
    assert "review-ledger-summary" in html
    assert "review-ledger-summary-confirmed" in html
    assert "review-ledger-title" in html
    assert f"ID {operation_id}" not in html
    assert "review-status-confirmed" in html
    assert "review-ledger-type tone-transfer" in html
    assert "Вклад ВТБ" in html
    assert "Карта Экспобанк" in html
    assert "из" in html
    assert "в" in html


def test_review_template_shows_expense_category_for_linked_operation() -> None:
    operation_id = uuid4()
    source_account = SimpleNamespace(name="Экспобанк карта")
    operation = SimpleNamespace(
        id=operation_id,
        operation_date="2026-06-30",
        type=OperationType.EXPENSE,
        category=SimpleNamespace(name="Продукты"),
        property=None,
        description="KRASNOE&BELOE",
        money_entries=[SimpleNamespace(amount=Decimal("-744.94"), account=source_account)],
    )
    row = SimpleNamespace(
        id=uuid4(),
        row_index=1,
        status=RawTransactionStatus.CONFIRMED,
        account_id=None,
        operation_date="2026-06-30",
        operation_date_raw=None,
        amount=Decimal("-744.94"),
        amount_raw=None,
        currency="RUB",
        description_normalized="Списание средств в KRASNOE&BELOE",
        description_raw=None,
        normalization_error=None,
        suggested_by_rule_id=uuid4(),
        suggested_category_id=None,
        suggested_property_id=None,
        suggested_operation_type=OperationType.EXPENSE,
        linked_operation_id=operation_id,
        linked_operation=operation,
        raw_payload={
            "rule_suggestion": {
                "application_mode": "auto_apply",
                "pattern": "KRASNOE&BELOE",
            },
        },
    )
    document = SimpleNamespace(
        id=uuid4(),
        account_id=None,
        original_filename="statement.pdf",
        status="requires_review",
        parse_attempts=[],
        raw_transactions=[row],
    )

    html = render_review_page(
        document=document,
        accounts=[source_account],
        categories=[],
    )

    assert "review-ledger-summary" in html
    assert "review-ledger-summary-confirmed" in html
    assert "review-ledger-type tone-expense" in html
    assert "review-ledger-status" in html
    assert "review-ledger-title" in html
    assert "review-action-status" in html
    assert "Продукты" in html
    assert "с Экспобанк карта" not in html
    assert "со счета: Экспобанк карта" not in html
    assert "автоприменено правило" not in html
    assert "автоправило: KRASNOE&amp;BELOE" not in html
    assert "строка уже в финальном состоянии" not in html
    assert "review-flags" not in html
    assert "review-actions__correction" in html
    assert "Исправить" in html
    assert "Отменить проведение" in html
    assert "Открыть операцию" not in html
    assert "Еще действия" not in html
    assert "review-panels" not in html
    assert "основной разбор строки" not in html
    assert "если это перемещение между счетами" not in html


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
    html = render_review_page(
        document=document,
        categories=[SimpleNamespace(id=uuid4(), name="Без категории", system_key="uncategorized")],
        accounts=[SimpleNamespace(id=account_id, name="Карта Экспобанк")],
        transfer_suggestions={row.id: [SimpleNamespace(raw_transaction=candidate, day_distance=0)]},
    )

    assert "Счет перевода" in html
    assert "Связать с" in html
    assert "создать новый перевод на выбранный счет" in html
    assert "review-transfer-panel-body" in html
    assert "review-transfer-grid" in html
    assert "review-panel-footer" in html
    assert "строка выписки" in html
    assert "29.05.2026" in html
    assert "Карта Экспобанк" in html
    assert "Зачисление средств по платежу" in html
    transfer_grid_index = html.index("review-transfer-grid")
    transfer_footer_index = html.index("review-panel-footer", transfer_grid_index)
    assert "transfer-help" not in html
    assert "transfer-empty-state" not in html
    assert transfer_grid_index < transfer_footer_index


def test_review_transfer_panel_does_not_offer_source_account_as_counterparty() -> None:
    source_account_id = uuid4()
    counterparty_account_id = uuid4()
    row = SimpleNamespace(
        id=uuid4(),
        row_index=1,
        status=RawTransactionStatus.NORMALIZED,
        account_id=source_account_id,
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
    document = SimpleNamespace(
        id=uuid4(),
        original_filename="statement.pdf",
        status="requires_review",
        parse_attempts=[],
        raw_transactions=[row],
    )
    html = render_review_page(
        document=document,
        categories=[SimpleNamespace(id=uuid4(), name="Без категории", system_key="uncategorized")],
        accounts=[
            SimpleNamespace(id=source_account_id, name="Основная карта"),
            SimpleNamespace(id=counterparty_account_id, name="Накопительный счет"),
        ],
    )

    assert f'<option value="{source_account_id}">Основная карта</option>' not in html
    assert f'<option value="{counterparty_account_id}">Накопительный счет</option>' in html
    assert "Подходящих строк выписки или ручных переводов не найдено." in html
    assert "Нет подходящих строк выписки или ручных переводов." in html
    assert "Ручной доход или расход сначала нужно исправить на перевод." in html


def test_review_transfer_panel_shows_candidate_with_document_account() -> None:
    expobank_account_id = uuid4()
    vtb_account_id = uuid4()
    row = SimpleNamespace(
        id=uuid4(),
        row_index=0,
        status=RawTransactionStatus.NORMALIZED,
        account_id=None,
        operation_date="2026-06-30",
        operation_date_raw=None,
        amount=Decimal("2342.19"),
        amount_raw=None,
        currency="RUB",
        description_normalized="Зачисление денежных средств на карту",
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
        row_index=4,
        account_id=None,
        account=None,
        uploaded_document=SimpleNamespace(
            account_id=vtb_account_id,
            account=SimpleNamespace(name="ВТБ вклад"),
        ),
        operation_date="2026-06-30",
        operation_date_raw=None,
        amount=Decimal("-2342.19"),
        currency="RUB",
        description_normalized="Перевод на карту",
        description_raw=None,
    )
    document = SimpleNamespace(
        id=uuid4(),
        account_id=expobank_account_id,
        original_filename="expobank.pdf",
        status="requires_review",
        parse_attempts=[],
        raw_transactions=[row],
    )

    html = render_review_page(
        document=document,
        categories=[SimpleNamespace(id=uuid4(), name="Без категории", system_key="uncategorized")],
        accounts=[
            SimpleNamespace(id=expobank_account_id, name="Экспобанк карта"),
            SimpleNamespace(id=vtb_account_id, name="ВТБ вклад"),
        ],
        transfer_suggestions={row.id: [SimpleNamespace(raw_transaction=candidate, day_distance=0)]},
    )

    assert f'<option value="{expobank_account_id}">Экспобанк карта</option>' not in html
    assert f'<option value="{vtb_account_id}">ВТБ вклад</option>' in html
    assert f'data-account-id="{vtb_account_id}"' in html
    assert "строка выписки" in html
    assert "ВТБ вклад" in html
    assert "Перевод на карту" in html


def test_review_template_shows_existing_manual_transfer_candidates() -> None:
    document_id = uuid4()
    vtb_account_id = uuid4()
    expobank_account_id = uuid4()
    operation_id = uuid4()
    row = SimpleNamespace(
        id=uuid4(),
        row_index=1,
        status=RawTransactionStatus.NORMALIZED,
        account_id=expobank_account_id,
        operation_date="2026-05-29",
        operation_date_raw=None,
        amount=Decimal("21000.00"),
        amount_raw=None,
        currency="RUB",
        description_normalized="Зачисление средств по платежу",
        description_raw=None,
        normalization_error=None,
        suggested_by_rule_id=None,
        suggested_category_id=None,
        suggested_property_id=None,
        linked_operation_id=None,
        raw_payload={},
    )
    counterparty_entry = SimpleNamespace(
        account_id=vtb_account_id,
        amount=Decimal("-21000.00"),
        currency="RUB",
        account=SimpleNamespace(name="ВТБ вклад"),
    )
    account_entry = SimpleNamespace(
        account_id=expobank_account_id,
        amount=Decimal("21000.00"),
        currency="RUB",
        account=SimpleNamespace(name="Экспобанк карта"),
    )
    operation = SimpleNamespace(
        id=operation_id,
        operation_date="2026-05-29",
        description="Со вклада снятие",
        money_entries=[counterparty_entry, account_entry],
    )
    document = SimpleNamespace(
        id=document_id,
        original_filename="statement.pdf",
        status="requires_review",
        parse_attempts=[],
        raw_transactions=[row],
    )
    html = render_review_page(
        document=document,
        categories=[SimpleNamespace(id=uuid4(), name="Без категории", system_key="uncategorized")],
        accounts=[
            SimpleNamespace(id=vtb_account_id, name="ВТБ вклад"),
            SimpleNamespace(id=expobank_account_id, name="Экспобанк карта"),
        ],
        existing_transfer_suggestions={
            row.id: [
                SimpleNamespace(
                    operation=operation,
                    account_entry=account_entry,
                    counterparty_entry=counterparty_entry,
                    day_distance=0,
                )
            ]
        },
    )

    assert "ручной перевод" in html
    assert "созданный перевод" not in html
    assert f'value="operation:{operation_id}"' in html
    assert 'name="matched_operation_id"' in html
    assert "29.05.2026" in html
    assert "ВТБ вклад" in html
    assert "Со вклада снятие" in html


def test_review_transfer_form_includes_csrf_token_from_context() -> None:
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
    document = SimpleNamespace(
        id=uuid4(),
        original_filename="statement.pdf",
        status="requires_review",
        parse_attempts=[],
        raw_transactions=[row],
    )
    html = render_review_page(
        document=document,
        categories=[SimpleNamespace(id=uuid4(), name="Без категории", system_key="uncategorized")],
        accounts=[SimpleNamespace(id=uuid4(), name="ВТБ вклад")],
        extra_context={"csrf_token": "csrf-test-token"},
    )

    assert 'name="csrf_token" value="csrf-test-token"' in html
    assert 'name="matched_raw_transaction_id"' in html
    assert 'name="matched_operation_id"' in html


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

    uncategorized_category_id = uuid4()
    vpn_category_id = uuid4()
    categories = [
        SimpleNamespace(
            id=uncategorized_category_id,
            name="Без категории",
            system_key="uncategorized",
        ),
        SimpleNamespace(id=vpn_category_id, name="VPN", system_key=None),
    ]
    page_context = build_review_page_context(
        document=document,
        accounts=[],
        categories=categories,
        properties=[],
        transfer_suggestions={},
        existing_transfer_suggestions={},
    )
    template_values = page_context.template_values(
        app_name="Booker Tee",
        workspace=SimpleNamespace(id=uuid4()),
    )
    template_values["current_item"] = page_context.review_items_by_id[current_row.id]
    template_values["oob_review_items"] = [page_context.review_items_by_id[sibling_row.id]]
    html = templates.env.get_template("imports/_review_action_response.html").render(
        **template_values,
    )

    assert f'id="raw-{current_row.id}"' in html
    assert f'id="raw-{sibling_row.id}"' in html
    assert html.count('hx-swap-oob="true"') == 2
    assert 'id="review-next-step" hx-swap-oob="true"' in html
    assert "Осталось обработать 2 из 2 строк." in html
    assert f'value="{vpn_category_id}"' in html
    assert "VPN" in html


def test_review_action_response_renders_prepared_review_item_vms() -> None:
    current_row = SimpleNamespace(
        id=uuid4(),
        row_index=1,
        status=RawTransactionStatus.NORMALIZED,
        account_id=None,
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
    sibling_row = SimpleNamespace(
        id=uuid4(),
        row_index=2,
        status=RawTransactionStatus.NORMALIZED,
        account_id=None,
        operation_date="2026-05-30",
        operation_date_raw=None,
        amount=Decimal("-200.00"),
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
        parse_attempts=[],
        raw_transactions=[current_row, sibling_row],
    )
    page_context = build_review_page_context(
        document=document,
        accounts=[],
        categories=[SimpleNamespace(id=uuid4(), name="Без категории", system_key="uncategorized")],
        properties=[],
        transfer_suggestions={},
        existing_transfer_suggestions={},
    )
    template_values = page_context.template_values(
        app_name="Booker Tee",
        workspace=SimpleNamespace(id=uuid4()),
    )
    template_values["current_item"] = page_context.review_items_by_id[current_row.id]
    template_values["oob_review_items"] = [page_context.review_items_by_id[sibling_row.id]]
    html = (
        create_templates()
        .env.get_template("imports/_review_action_response.html")
        .render(
            **template_values,
        )
    )

    assert "review-item--vm" in html
    assert f'id="raw-{current_row.id}"' in html
    assert f'id="raw-{sibling_row.id}"' in html
    assert html.count('hx-swap-oob="true"') == 2
    assert 'id="review-next-step" hx-swap-oob="true"' in html


def test_review_action_response_state_builds_transient_row_maps() -> None:
    row_id = uuid4()
    category_id = uuid4()
    state = ReviewActionResponseState(
        raw_transaction_id=row_id,
        oob_raw_transaction_ids=frozenset(),
        selected_category_id=category_id,
        open_category_editor=True,
        create_category_error="Категория с таким названием уже есть.",
        create_category_initial_name="Аптека",
    )

    assert state.selected_category_id_by_row() == {row_id: category_id}
    assert state.open_category_editor_by_row() == {row_id: True}
    assert state.create_category_error_by_row() == {row_id: "Категория с таким названием уже есть."}
    assert state.create_category_initial_name_by_row() == {row_id: "Аптека"}


def test_review_action_response_request_builds_presentation_state() -> None:
    document_id = uuid4()
    row_id = uuid4()
    category_id = uuid4()
    sibling_row_id = uuid4()
    response_request = ReviewActionResponseRequest(
        document_id=document_id,
        raw_transaction_id=row_id,
        oob_raw_transaction_ids=frozenset({sibling_row_id}),
        selected_category_id=category_id,
        open_category_editor=True,
        refresh_category_options=True,
    )

    state = response_request.response_state()

    assert response_request.redirect_url() == f"/imports/documents/{document_id}/review"
    assert state.raw_transaction_id == row_id
    assert state.oob_raw_transaction_ids == frozenset({sibling_row_id})
    assert state.selected_category_id == category_id
    assert state.open_category_editor is True
    assert state.refresh_category_options is True


def test_review_action_response_template_values_expose_only_review_item_vms() -> None:
    row_id = uuid4()
    sibling_row_id = uuid4()
    category_id = uuid4()
    document = SimpleNamespace(
        id=uuid4(),
        original_filename="statement.pdf",
        status="requires_review",
        parse_attempts=[],
        raw_transactions=[
            SimpleNamespace(
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
            ),
            SimpleNamespace(
                id=sibling_row_id,
                row_index=2,
                status=RawTransactionStatus.NORMALIZED,
                operation_date="2026-05-30",
                operation_date_raw=None,
                amount=Decimal("-200.00"),
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
            ),
        ],
    )
    page_context = build_review_page_context(
        document=document,
        accounts=[],
        categories=[SimpleNamespace(id=category_id, name="Аптеки", system_key=None)],
        properties=[],
        transfer_suggestions={},
        existing_transfer_suggestions={},
        selected_category_id_by_row={row_id: category_id},
        open_category_editor_by_row={row_id: True},
    )
    state = ReviewActionResponseState(
        raw_transaction_id=row_id,
        oob_raw_transaction_ids=frozenset({sibling_row_id}),
        selected_category_id=category_id,
        open_category_editor=True,
        create_category_error="",
        create_category_initial_name="",
    )

    values = state.template_values(
        page_context=page_context,
        document=document,
        app_name="Booker Tee",
        workspace=SimpleNamespace(id=uuid4()),
    )

    assert values["current_item"] is page_context.review_items_by_id[row_id]
    assert values["oob_review_items"] == [page_context.review_items_by_id[sibling_row_id]]
    assert "review_page" in values
    assert "document" not in values
    assert "review_queue" not in values
    assert "review_validation" not in values
    assert "current_row" not in values
    assert "oob_raw_transaction_ids" not in values
    assert "selected_category_id_by_row" not in values
    assert "open_category_editor_by_row" not in values
    assert "create_category_error_by_row" not in values
    assert "create_category_initial_name_by_row" not in values


def test_raw_transaction_review_form_parser_builds_application_command() -> None:
    document_id = uuid4()
    row_id = uuid4()
    category_id = uuid4()
    property_id = uuid4()
    counterparty_account_id = uuid4()
    matched_raw_transaction_id = uuid4()

    command = RawTransactionReviewFormParser().build_command(
        document_id=document_id,
        raw_transaction_id=row_id,
        action="transfer",
        category_id=str(category_id),
        property_id=str(property_id),
        counterparty_account_id=str(counterparty_account_id),
        matched_raw_transaction_id=str(matched_raw_transaction_id),
        matched_operation_id="",
        remember_rule="1",
        rule_pattern="KRASNOE&BELOE",
    )

    assert command.document_id == document_id
    assert command.raw_transaction_id == row_id
    assert command.action == "transfer"
    assert command.category_id == category_id
    assert command.property_id == property_id
    assert command.counterparty_account_id == counterparty_account_id
    assert command.matched_raw_transaction_id == matched_raw_transaction_id
    assert command.matched_operation_id is None
    assert command.remember_rule is True
    assert command.rule_pattern == "KRASNOE&BELOE"


def test_review_action_response_state_refreshes_only_non_final_sibling_rows() -> None:
    current_row_id = uuid4()
    refreshable_row_id = uuid4()
    confirmed_row_id = uuid4()
    ignored_row_id = uuid4()
    document = SimpleNamespace(
        raw_transactions=[
            SimpleNamespace(id=current_row_id, status=RawTransactionStatus.NORMALIZED),
            SimpleNamespace(id=refreshable_row_id, status=RawTransactionStatus.SUGGESTED),
            SimpleNamespace(id=confirmed_row_id, status=RawTransactionStatus.CONFIRMED),
            SimpleNamespace(id=ignored_row_id, status=RawTransactionStatus.IGNORED),
        ]
    )
    state = ReviewActionResponseState(
        raw_transaction_id=current_row_id,
        oob_raw_transaction_ids=frozenset(),
        refresh_category_options=True,
    )

    assert state.oob_row_ids(document) == frozenset({refreshable_row_id})


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
    document = SimpleNamespace(
        id=uuid4(),
        original_filename="statement.pdf",
        status="requires_review",
        parse_attempts=[],
        raw_transactions=[row],
    )
    html = render_review_page(
        document=document,
        categories=[
            SimpleNamespace(
                id=uncategorized_category_id,
                name="Без категории",
                system_key="uncategorized",
            ),
            SimpleNamespace(id=created_category_id, name="Аптеки", system_key=None),
        ],
        open_category_editor_by_row={row_id: True},
        selected_category_id_by_row={row_id: created_category_id},
    )

    assert "review-item--vm" in html
    assert "review-panel__tab--category" in html
    assert "review-category-panel-body" in html
    assert "review-category-grid" in html
    assert "review-category-primary" in html
    assert "review-rule-strip" in html
    assert "review-panel-footer" in html
    assert "Сохранить и подтвердить" in html
    assert 'aria-label="Новая категория"' in html
    assert f'action="/imports/documents/{document.id}/raw-transactions/{row_id}/categories"' in html
    assert "open" in html
    assert f'<option value="{created_category_id}" selected>' in html
    assert f'<option value="{uncategorized_category_id}" selected>' not in html
    assert "Новая категория" in html
    assert "review-dialog-header" in html
    assert "review-dialog-body" in html
    assert "review-dialog-footer" in html
    assert 'aria-label="Закрыть"' in html
    assert "расход" in html
    assert '<option value="expense" selected>расход</option>' in html
    assert "openCategoryDialog(event)" in html
    assert '@click.stop="openCategoryDialog($event)"' in html


def test_suggested_review_item_keeps_rule_proposal_when_new_category_is_selected() -> None:
    row_id = uuid4()
    account_id = uuid4()
    services_category_id = uuid4()
    created_category_id = uuid4()
    row = SimpleNamespace(
        id=row_id,
        row_index=10,
        status=RawTransactionStatus.SUGGESTED,
        account_id=account_id,
        operation_date="2026-05-25",
        operation_date_raw=None,
        amount=Decimal("-525.00"),
        amount_raw=None,
        currency="RUB",
        description_normalized="Списание средств в Veesp",
        description_raw=None,
        normalization_error=None,
        suggested_by_rule_id=uuid4(),
        suggested_category_id=services_category_id,
        suggested_property_id=None,
        suggested_operation_type=OperationType.EXPENSE,
        linked_operation_id=None,
        raw_payload={
            "rule_suggestion": {
                "application_mode": "auto_apply",
                "pattern": "Veesp",
            }
        },
    )
    document = SimpleNamespace(
        id=uuid4(),
        original_filename="statement.pdf",
        status="requires_review",
        parse_attempts=[],
        raw_transactions=[row],
    )
    html = render_review_page(
        document=document,
        categories=[
            SimpleNamespace(id=services_category_id, name="Сервисы", system_key=None),
            SimpleNamespace(id=created_category_id, name="TTTEST", system_key=None),
        ],
        accounts=[SimpleNamespace(id=account_id, name="Карта")],
        open_category_editor_by_row={row_id: True},
        selected_category_id_by_row={row_id: created_category_id},
    )

    assert "автоправило: Veesp" in html
    assert "review-signal-proposal" in html
    assert "review-signal-problem" not in html
    assert "категория: Сервисы" in html
    assert "категория: TTTEST" not in html
    assert "объект: без объекта" not in html
    assert "автоприменено правило" not in html
    assert f'<option value="{created_category_id}" selected>' in html
    assert f'<option value="{services_category_id}" selected>' not in html
    assert 'review-actions__secondary" open' not in html
    assert f'id="category-panel-{row_id}"' in html
    assert "review-panel__tab--category" in html
    assert "open" in html


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
    html = render_review_page(
        document=SimpleNamespace(
            id=uuid4(),
            original_filename="statement.pdf",
            status="requires_review",
            parse_attempts=[],
            raw_transactions=[row],
        ),
        categories=[SimpleNamespace(id=uuid4(), name="Без категории", system_key="uncategorized")],
        open_category_editor_by_row={row_id: True},
        create_category_error_by_row={row_id: "Категория с таким названием уже есть."},
        create_category_initial_name_by_row={row_id: "Аптека"},
    )

    assert "review-item--vm" in html
    assert "review-panel__tab--category" in html
    assert "open" in html
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
                    "balance_chain": {
                        "mismatches": [
                            {
                                "row_index": 1,
                                "expected_balance_after": "1070.00",
                                "actual_balance_after": "1060.00",
                            }
                        ]
                    },
                }
            )
        ],
        raw_transactions=[row],
    )
    html = render_review_page(
        document=document,
        categories=[SimpleNamespace(id=uuid4(), name="Без категории", system_key="uncategorized")],
    )

    assert "Остатки после операций не совпадают с суммами строк." in html
    assert "review-validation-panel" in html
    assert "review-validation-summary" in html
    assert "review-validation-message" in html
    assert "review-control-totals" in html
    assert "суммы или остатки не сходятся с выпиской" in html
    assert "review-signal-problem" in html
    assert "остаток не сходится: ожидалось 1070.00, в строке 1060.00" in html
