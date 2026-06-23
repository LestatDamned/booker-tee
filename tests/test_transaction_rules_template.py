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
        properties=[SimpleNamespace(id=property_id, name="Квартира")],
        rules=[rule],
        workspace=SimpleNamespace(name="Personal"),
    )

    assert "form-panel" in html
    assert "/rules/seed-defaults" in html
    assert "seed-expobank" not in html
    assert "загрузить базовые правила" in html
    assert "entity-card-list" in html
    assert "entity-card" in html
    assert "badge badge-suggest" in html
    assert "badge badge-outflow" in html
    assert "badge badge-expense" in html
    assert f'id="rule-{rule_id}"' in html
    assert f'class="detached-form" id="rule-form-{rule_id}"' in html
    assert 'type="hidden" name="name"' not in html
    assert "SAMOKAT -> Подписки и сервисы" not in html
    assert "Продукты" in html
    assert "SAMOKAT" in html
    assert f"ID {str(rule_id)[:8]}" in html
    assert "<th>активно</th>" not in html


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
