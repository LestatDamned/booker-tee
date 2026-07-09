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

    html = templates.env.get_template("transaction_rules/index.html").render(
        app_name="Booker Tee",
        application_modes=list(TransactionRuleApplicationMode),
        categories=[SimpleNamespace(id=category_id, name="Продукты")],
        directions=list(MoneyDirection),
        match_types=list(TransactionRuleMatchType),
        operation_types=list(OperationType),
        page=TransactionRulesPagePresenter.build(cast(Any, [rule]), can_write=True),
        properties=[SimpleNamespace(id=property_id, name="Квартира")],
        workspace=SimpleNamespace(name="Personal"),
    )

    assert "form-panel" in html
    assert "Правила сильно ускоряют проверку выписок" in html
    assert "советуем загрузить базовые правила" in html
    assert "rule-advanced-details" in html
    assert "Условия применения" in html
    assert "/rules/seed-defaults" in html
    assert "seed-expobank" not in html
    assert "загрузить базовые правила" in html
    assert "новое правило" in html
    assert "entity-card-list" in html
    assert "entity-card" in html
    assert "rule-card__edit" in html
    assert "изменить правило" in html
    assert "row-actions" in html
    assert "badge badge-suggest" in html
    assert "badge badge-outflow" in html
    assert "badge badge-expense" in html
    assert "списание" in html
    assert "расход" in html
    assert f'id="rule-{rule_id}"' in html
    assert f'id="rule-form-{rule_id}"' in html
    assert 'type="hidden" name="name"' not in html
    assert "SAMOKAT -> Подписки и сервисы" not in html
    assert "SAMOKAT -&gt; Продукты" in html
    assert "Продукты" in html
    assert "SAMOKAT" in html
    assert "сохранить" in html
    assert "выключить" in html
    assert "danger-zone" in html
    assert "<summary>ID</summary>" in html
    assert f"ID {rule_id}" in html
    assert "<th>активно</th>" not in html


def test_transaction_rules_template_empty_state_points_to_rule_form() -> None:
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("transaction_rules/index.html").render(
        app_name="Booker Tee",
        application_modes=list(TransactionRuleApplicationMode),
        categories=[],
        directions=list(MoneyDirection),
        match_types=list(TransactionRuleMatchType),
        operation_types=list(OperationType),
        page=TransactionRulesPagePresenter.build([], can_write=True),
        properties=[],
        workspace=SimpleNamespace(name="Personal"),
    )

    assert 'id="new-rule"' in html
    assert "Правил транзакций пока нет" in html
    assert "минимальные подсказки для частых операций" in html
    assert 'href="#new-rule"' not in html


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

    page = TransactionRulesPagePresenter.build(cast(Any, [rule]), can_write=True)
    row = page.rules[0]

    assert page.total_rule_count == 1
    assert page.active_rule_count == 0
    assert page.inactive_rule_count == 1
    assert row.anchor_id == f"rule-{rule_id}"
    assert row.title == "YANDEX GO -> Такси"
    assert row.status_label == "выключено"
    assert row.status_tone == "muted"
    assert [item.label for item in row.meta] == [
        "содержит",
        "автоприменять",
        "списание",
        "расход",
        "до 1000.00",
    ]
    assert row.save_action.form_id == f"rule-form-{rule_id}"
    assert row.toggle_action.hidden_fields == {"is_active": "true"}
    assert row.delete_action.style == "danger"
