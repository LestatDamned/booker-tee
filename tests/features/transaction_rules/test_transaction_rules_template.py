from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.features.ledger.models import OperationType
from app.features.transaction_rules.domain.text import build_rule_name
from app.features.transaction_rules.models import (
    MoneyDirection,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)
from app.features.transaction_rules.presentation.presenter import TransactionRulesPagePresenter
from app.features.transaction_rules.router import rule_anchor_url
from app.templating import create_templates


def test_transaction_rules_template_uses_compact_rule_cards() -> None:
    category_id = uuid4()
    property_id = uuid4()
    rule_id = uuid4()
    rule = SimpleNamespace(
        id=rule_id,
        name="SAMOKAT -> Подписки и сервисы",
        is_active=True,
        pattern="SAMOKAT",
        match_type=TransactionRuleMatchType.CONTAINS,
        application_mode=TransactionRuleApplicationMode.SUGGEST,
        direction=MoneyDirection.OUTFLOW,
        target_operation_type=OperationType.EXPENSE,
        category_id=category_id,
        category=SimpleNamespace(name="Продукты"),
        property_id=property_id,
        property=SimpleNamespace(name="Квартира"),
        amount_min=Decimal("100.00"),
        amount_max=Decimal("5000.00"),
    )
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")
    categories = [SimpleNamespace(id=category_id, name="Продукты")]
    properties = [SimpleNamespace(id=property_id, name="Квартира")]

    html = templates.env.get_template("transaction_rules/index.html").render(
        app_name="Booker Tee",
        page=TransactionRulesPagePresenter.build(
            cast(Any, [rule]),
            categories=cast(Any, categories),
            properties=cast(Any, properties),
            can_write=True,
            recent_rule_id=rule_id,
        ),
        workspace=SimpleNamespace(name="Personal"),
    )

    assert "form-panel" in html
    assert "Правила помогают распознавать операции из выписок" in html
    assert "KRASNOE&amp;BELOE" in html
    assert "предложить категорию" in html
    assert "rule-advanced-details" in html
    assert "Если описание операции" in html
    assert "что искать в описании" in html
    assert "Тогда предложить" in html
    assert "Расширенные настройки" in html
    assert "Открыть" in html
    assert "Закрыть" in html
    assert "создадим автоматически" in html
    assert "/rules/seed-defaults" in html
    assert "seed-expobank" not in html
    assert "загрузить базовые правила" in html
    assert "rules-page-actions" in html
    assert "создать правило" in html
    assert 'id="rules-list-panel"' in html
    assert "rule-filter-form" in html
    assert 'name="q"' in html
    assert 'name="category_id"' in html
    assert 'name="status"' in html
    assert "магазин, правило, категория" in html
    assert "правило готово" in html
    assert "Показать в списке" in html
    assert f'href="#rule-{rule_id}"' in html
    assert "rule-card--recent" in html
    assert 'hx-target="#rules-list-panel"' in html
    assert 'hx-select="#rules-list-panel"' in html
    assert 'hx-on::after-request="if (event.detail.successful) this.reset()"' in html
    assert "entity-card-list" in html
    assert "entity-card" in html
    assert 'hx-boost="true"' in html
    assert 'hx-select="#rule-' in html
    assert 'hx-swap="outerHTML show:none settle:600ms"' in html
    assert 'hx-push-url="false"' in html
    assert "rule-card__edit" in html
    assert "изменить правило" in html
    assert f'hx-get="/rules/{rule_id}/edit"' in html
    assert 'hx-select=".rule-edit-panel-content"' in html
    assert f'id="rule-edit-panel-{rule_id}"' in html
    assert "Загружаем форму..." in html
    assert "Еще действия" in html
    assert "Показать ID" in html
    assert "row-actions" in html
    assert "review-actions__menu" in html
    assert "badge badge-active" in html
    assert "Если описание содержит “SAMOKAT”" in html
    assert "предлагать · списание · расход · Квартира · 100.00...5000.00" in html
    assert "списание" in html
    assert "расход" in html
    assert f'id="rule-{rule_id}"' in html
    assert f'id="rule-form-{rule_id}"' not in html
    assert 'type="hidden" name="name"' not in html
    assert "SAMOKAT -&gt; Продукты" in html
    assert "Продукты" in html
    assert "сохранить" not in html
    assert "выключить" in html
    assert "показано 1 из 1" in html
    assert "danger-zone review-actions__menu-section review-actions__danger-zone" in html
    assert "<summary>ID</summary>" not in html
    assert f"ID {rule_id}" in html
    assert "Оно больше не будет применяться к новым выпискам" in html
    assert "<th>активно</th>" not in html


def test_transaction_rule_edit_panel_lazy_loads_form_options() -> None:
    category_id = uuid4()
    property_id = uuid4()
    rule_id = uuid4()
    rule = SimpleNamespace(
        id=rule_id,
        name="SAMOKAT -> Подписки и сервисы",
        is_active=True,
        pattern="SAMOKAT",
        match_type=TransactionRuleMatchType.CONTAINS,
        application_mode=TransactionRuleApplicationMode.SUGGEST,
        direction=MoneyDirection.OUTFLOW,
        target_operation_type=OperationType.EXPENSE,
        category_id=category_id,
        category=SimpleNamespace(name="Продукты"),
        property_id=property_id,
        property=SimpleNamespace(name="Квартира"),
        amount_min=Decimal("100.00"),
        amount_max=Decimal("5000.00"),
    )
    templates = create_templates()
    form = TransactionRulesPagePresenter.build_edit_form(
        cast(Any, rule),
        categories=cast(Any, [SimpleNamespace(id=category_id, name="Продукты")]),
        properties=cast(Any, [SimpleNamespace(id=property_id, name="Квартира")]),
    )

    html = templates.env.get_template("transaction_rules/_rule_edit_panel.html").render(
        form=form,
    )

    assert "Изменить правило" in html
    assert "автоправило" in html
    assert f'id="rule-form-{rule_id}"' in html
    assert f'action="/rules/{rule_id}"' in html
    assert "SAMOKAT" in html
    assert "SAMOKAT -&gt; Подписки и сервисы" in html
    assert "Продукты" in html
    assert "Квартира" in html
    assert "сохранить" in html


def test_transaction_rules_template_empty_state_points_to_rule_form() -> None:
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("transaction_rules/index.html").render(
        app_name="Booker Tee",
        page=TransactionRulesPagePresenter.build(
            [],
            categories=[],
            properties=[],
            can_write=True,
        ),
        workspace=SimpleNamespace(name="Personal"),
    )

    assert 'id="new-rule"' in html
    assert 'id="rules-list-panel"' in html
    assert "Правил транзакций пока нет" in html
    assert "минимальные подсказки для частых операций" in html
    assert 'href="#new-rule"' not in html


def test_transaction_rules_template_filtered_empty_state_names_filters() -> None:
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("transaction_rules/index.html").render(
        app_name="Booker Tee",
        page=TransactionRulesPagePresenter.build(
            [],
            categories=[],
            properties=[],
            can_write=True,
            all_rule_count=10,
            filter_search="nope",
        ),
        workspace=SimpleNamespace(name="Personal"),
    )

    assert "Правила не найдены" in html
    assert "найдено 0 из 10" in html
    assert "сбросить" in html
    assert "Правил транзакций пока нет" not in html


def test_transaction_rules_template_read_only_keeps_rule_meaning_without_actions() -> None:
    category_id = uuid4()
    rule_id = uuid4()
    rule = SimpleNamespace(
        id=rule_id,
        name="OZON -> Продукты",
        is_active=True,
        pattern="OZON",
        match_type=TransactionRuleMatchType.CONTAINS,
        application_mode=TransactionRuleApplicationMode.SUGGEST,
        direction=MoneyDirection.OUTFLOW,
        target_operation_type=OperationType.EXPENSE,
        category_id=category_id,
        category=SimpleNamespace(name="Продукты"),
        property_id=None,
        property=None,
        amount_min=None,
        amount_max=None,
    )
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("transaction_rules/index.html").render(
        app_name="Booker Tee",
        page=TransactionRulesPagePresenter.build(
            cast(Any, [rule]),
            categories=cast(Any, [SimpleNamespace(id=category_id, name="Продукты")]),
            properties=[],
            can_write=False,
        ),
        workspace=SimpleNamespace(name="Personal"),
    )

    assert "OZON -&gt; Продукты" in html
    assert "Если описание содержит “OZON”" in html
    assert "предлагать · списание · расход" in html
    assert "badge badge-active" in html
    assert "изменить правило" not in html
    assert "выключить" not in html
    assert "Еще действия" not in html
    assert f'id="rule-form-{rule_id}"' not in html


def test_rule_anchor_url_points_to_rule_card() -> None:
    rule_id = uuid4()

    assert rule_anchor_url(rule_id) == f"/rules#rule-{rule_id}"


def test_generated_rule_name_uses_current_category() -> None:
    assert (
        build_rule_name(
            pattern='ООО "ВИСП"',
            match_type=TransactionRuleMatchType.CONTAINS,
            category_name="Подписки и сервисы",
            target_operation_type=OperationType.EXPENSE,
        )
        == 'ООО "ВИСП" -> Подписки и сервисы'
    )


def test_transaction_rules_presenter_prepares_display_state_and_actions() -> None:
    category_id = uuid4()
    rule_id = uuid4()
    rule = SimpleNamespace(
        id=rule_id,
        is_active=False,
        pattern="YANDEX GO",
        match_type=TransactionRuleMatchType.CONTAINS,
        application_mode=TransactionRuleApplicationMode.AUTO_APPLY,
        direction=MoneyDirection.OUTFLOW,
        target_operation_type=OperationType.EXPENSE,
        category_id=category_id,
        category=SimpleNamespace(name="Такси"),
        property_id=None,
        property=None,
        amount_min=None,
        amount_max=Decimal("1000.00"),
    )

    page = TransactionRulesPagePresenter.build(
        cast(Any, [rule]),
        categories=cast(Any, [SimpleNamespace(id=category_id, name="Такси")]),
        properties=[],
        can_write=True,
    )
    row = page.rules[0]

    assert page.total_rule_count == 1
    assert page.active_rule_count == 0
    assert page.inactive_rule_count == 1
    assert page.rule_count_label == "1 правил · 0 активных · 1 выключенных"
    assert page.recent_rule is None
    assert page.filters.is_active is False
    assert page.filters.result_label is None
    assert page.seed_defaults_action.url == "/rules/seed-defaults"
    assert page.seed_defaults_action.confirm_message is not None
    assert "Ваши правила не будут изменены" in page.seed_defaults_action.confirm_message
    assert page.create_rule_label == "создать правило"
    assert page.create_form.layout == "create"
    assert selected_values(page.create_form.match_type_options) == ["contains"]
    assert selected_values(page.create_form.application_mode_options) == ["suggest"]
    assert selected_values(page.create_form.direction_options) == ["any"]
    assert selected_values(page.create_form.operation_type_options) == ["expense"]
    assert page.create_form.advanced_label == "Расширенные настройки"
    assert row.anchor_id == f"rule-{rule_id}"
    assert row.is_recent is False
    assert row.title == "YANDEX GO -> Такси"
    assert row.condition_label == "Если описание содержит “YANDEX GO”"
    assert row.secondary_label == "автоприменение · списание · расход · до 1000.00"
    assert row.status_label == "выключено"
    assert row.status_tone == "muted"
    assert row.edit_form_url == f"/rules/{rule_id}/edit"
    assert row.edit_panel_id == f"rule-edit-panel-{rule_id}"
    assert row.edit_toggle_action.action_type == "panel_toggle"
    assert row.edit_toggle_action.panel_id == row.edit_summary_id
    assert row.edit_toggle_action.icon == "settings"
    assert row.toggle_action.icon == "check"
    assert row.toggle_action.hidden_fields == {"is_active": "true"}
    assert row.delete_action.style == "danger"
    assert row.delete_action.confirm_message is not None
    assert "YANDEX GO -> Такси" in row.delete_action.confirm_message

    form = TransactionRulesPagePresenter.build_edit_form(
        cast(Any, rule),
        categories=cast(Any, [SimpleNamespace(id=category_id, name="Такси")]),
        properties=[],
    )

    assert form.submit_action.form_id == f"rule-form-{rule_id}"
    assert form.advanced_label == "Расширенные настройки"
    assert form.show_name is True
    assert form.name == "YANDEX GO -> Такси"
    assert selected_values(form.category_options) == [str(category_id)]
    assert selected_values(form.property_options) == [""]


def test_transaction_rules_presenter_prepares_filter_state() -> None:
    category_id = uuid4()
    page = TransactionRulesPagePresenter.build(
        [],
        categories=cast(Any, [SimpleNamespace(id=category_id, name="Такси")]),
        properties=[],
        can_write=True,
        all_rule_count=7,
        filter_search="alibi",
        filter_category_id=category_id,
        filter_status="inactive",
    )

    assert page.filters.is_active is True
    assert page.filters.search == "alibi"
    assert page.filters.result_label == "найдено 0 из 7"
    assert page.rule_count_label == "7 правил · 0 активных · 0 выключенных"
    assert selected_values(page.filters.category_options) == [str(category_id)]
    assert selected_values(page.filters.status_options) == ["inactive"]


def test_transaction_rules_presenter_marks_recent_rule() -> None:
    rule_id = uuid4()
    rule = SimpleNamespace(
        id=rule_id,
        is_active=True,
        pattern="ALIBI",
        match_type=TransactionRuleMatchType.CONTAINS,
        application_mode=TransactionRuleApplicationMode.SUGGEST,
        direction=MoneyDirection.OUTFLOW,
        target_operation_type=OperationType.EXPENSE,
        category_id=None,
        category=None,
        property_id=None,
        property=None,
        amount_min=None,
        amount_max=None,
    )

    page = TransactionRulesPagePresenter.build(
        cast(Any, [rule]),
        categories=[],
        properties=[],
        can_write=True,
        recent_rule_id=rule_id,
    )

    assert page.recent_rule is page.rules[0]
    assert page.recent_rule.is_recent is True
    assert page.recent_rule.anchor_id == f"rule-{rule_id}"


def test_transaction_rules_presenter_prepares_load_more_state() -> None:
    rules = [
        SimpleNamespace(
            id=uuid4(),
            is_active=True,
            pattern=f"RULE {index}",
            match_type=TransactionRuleMatchType.CONTAINS,
            application_mode=TransactionRuleApplicationMode.SUGGEST,
            direction=MoneyDirection.OUTFLOW,
            target_operation_type=OperationType.EXPENSE,
            category_id=None,
            category=None,
            property_id=None,
            property=None,
            amount_min=None,
            amount_max=None,
        )
        for index in range(50)
    ]

    page = TransactionRulesPagePresenter.build(
        cast(Any, rules),
        categories=[],
        properties=[],
        can_write=True,
        all_rule_count=69,
        filtered_rule_count=69,
        active_rule_count=69,
        inactive_rule_count=0,
        filter_search="ozon",
        filter_status="active",
        limit=50,
    )

    assert page.rule_count_label == "69 правил · 69 активных · 0 выключенных"
    assert page.filters.result_label == "найдено 69 из 69"
    assert page.pagination.label == "показано 50 из 69"
    assert page.pagination.has_more is True
    assert page.pagination.next_url == "/rules?q=ozon&status=active&limit=69"


def selected_values(options: list[Any]) -> list[str]:
    return [option.value for option in options if option.selected]
